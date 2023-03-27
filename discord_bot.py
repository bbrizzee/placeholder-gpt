import os
import discord
import openai
import aiohttp
import asyncio
import logging
import json
from collections import deque
from datetime import datetime
import tiktoken
from librarian import Librarian, librarian_main

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

def count_tokens(text, model="gpt-3.5-turbo"):
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

with open("bot_settings.txt", "r") as file:
    bot_settings = json.load(file)

class ChatBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conversation_history = deque()
        self.message_queue = asyncio.Queue()
        self.librarian_message_queue = asyncio.Queue()  # Add this line

    async def on_ready(self):
        logger.debug(f'{self.user} is connected to Discord!')
        self.loop.create_task(self.process_message_queue())
        self.librarian = Librarian() 
        self.loop.create_task(librarian_main(self))  # Replace 'librarian_main' with 'self.librarian'

    async def on_message(self, message):
        if message.author == self.user:
            return

        logger.debug(f"New message: {message.content}")
        if message.channel.name != 'placeholder-gpt':
            return

        if message.content == "!facts":
            facts = self.librarian.get_facts()
            if facts:
                await message.channel.send(f"Facts:\n{facts}")
            else:
                await message.channel.send("No facts available.")
        else:
            # Add the user's message to the conversation_history first
            self.conversation_history.append({"role": "user", "content": f"{message.author.display_name} ({message.created_at.isoformat()}): {message.content}"})
            
            # Then, add the updated conversation_history to the librarian_message_queue
            await self.librarian_message_queue.put(self.conversation_history.copy())
            
            # Finally, add the message to the message_queue for the main bot
            await self.message_queue.put(message)


    async def process_message_queue(self):
        while True:
            message = await self.message_queue.get()
            if not message.author.bot:
                self.conversation_history.append({"role": "user", "content": f"{message.author.display_name} ({message.created_at.isoformat()}): {message.content}"})
                await self.handle_message(message)

    async def handle_message(self, message):
        logger.debug(f"Received message: {message.content}")

        max_tokens = bot_settings["max_tokens"]

        token_count = sum(count_tokens(msg["content"]) for msg in self.conversation_history)
        while token_count > max_tokens:
            removed_message = self.conversation_history.popleft()
            token_count -= count_tokens(removed_message["content"])

        logger.debug(f"$$$$$ Current token count: {token_count}")

        system_message_content = bot_settings["system_message"]

        # Get the sender's username from the most recent message
        sender_username = message.author.display_name

        # Retrieve relevant facts about the sender from the Librarian
        sender_facts = self.librarian.get_facts_for_user(sender_username)
        logger.debug(f"*****************User facts: {sender_facts}")

        # Check if the most recent assistant message is not already about the sender's facts
        if (
            sender_facts
            and not (
                self.conversation_history[-1]["role"] == "assistant"
                and self.conversation_history[-1]["content"].startswith(f"Facts about {sender_username}:")
            )
        ):
            self.conversation_history.append({"role": "assistant", "content": f"Facts about {sender_username}: {sender_facts}"})

        messages_to_send = [
            {"role": "system", "content": system_message_content},
            *self.conversation_history
        ]

        async def show_typing_indicator():
            async with message.channel.typing():
                await asyncio.sleep(2)

        async def api_call():
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=bot_settings["client_timeout"])) as session:
                for attempt in range(3):
                    logger.debug(f"API call attempt {attempt + 1}")
                    try:
                        logger.debug(f"[{datetime.utcnow().isoformat()}] Making assistant API call (attempt {attempt + 1})")
                        logger.debug(f"[{datetime.utcnow().isoformat()}] Sending these messages: {messages_to_send}")
                        async with session.post(
                            "https://api.openai.com/v1/chat/completions",
                            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                            json={"model": bot_settings["model"], 
                                  "messages": messages_to_send,
                                  "temperature": bot_settings["temperature"],
                                  "top_p": bot_settings["top_p"],
                                  "presence_penalty": bot_settings["presence_penalty"],
                                  "frequency_penalty": bot_settings["frequency_penalty"],
                            },
                        ) as response:
                            assistant_response_json = await response.json()
                            logger.debug(f"Assistant API response: {assistant_response_json}")
                    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                        logger.debug(f"Error: {type(e).__name__} occurred during API call. Retrying...")
                        await asyncio.sleep(7)
                    else:
                        if 'choices' in assistant_response_json:
                            break
                        else:
                            if 'error' in assistant_response_json and assistant_response_json['error'].get('type') == 'server_error':
                                pass
                            else:
                                logger.debug(f"Error: 'choices' not found in assistant_response_json. Retrying...\nFull response: {assistant_response_json}")
                            await asyncio.sleep(7)
                return assistant_response_json

        typing_task = asyncio.create_task(show_typing_indicator())
        assistant_response_json = await asyncio.gather(typing_task, api_call())
        assistant_response_json = assistant_response_json[1]  # Get the result of the api_call()

        if 'choices' in assistant_response_json:
            assistant_response = assistant_response_json['choices'][0]['message']['content']

            index = assistant_response.find("):")
            if index != -1:
                assistant_response = assistant_response[index + 2:]
            else:
                assistant_response = assistant_response.lstrip()

            response_chunks = [assistant_response[i:i + 2000] for i in range(0, len(assistant_response), 2000)]

            for response_chunk in response_chunks:
                await message.channel.send(response_chunk)
                logger.debug(f"Message posted in channel: {response_chunk}")

                assistant_timestamp = datetime.utcnow().isoformat()
                assistant_content = f"{self.user.display_name} ({assistant_timestamp}): {response_chunk}"
                self.conversation_history.append({"role": "assistant", "content": assistant_content})
        else:
            error_message = "I'm sorry, I'm experiencing some technical difficulties at the moment. Please try again later."
            await message.channel.send(error_message)
            logger.debug(f"Error message posted in channel: {error_message}")

client = ChatBot(intents=intents)
client.run(DISCORD_TOKEN)