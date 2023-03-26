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

# Set up logging so we can see debug messages
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables for our Discord token and OpenAI API key
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Set up intents for the Discord bot to read messages and message content
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

def count_tokens(text, model="gpt-3.5-turbo"):
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

# Load bot settings from bot_settings.txt
with open("bot_settings.txt", "r") as file:
    bot_settings = json.load(file)

class ChatBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conversation_history = deque()
        self.message_queue = asyncio.Queue()

    async def on_ready(self):
        logger.debug(f'{self.user} is connected to Discord!')
        self.loop.create_task(self.process_message_queue())

    async def on_message(self, message):
        if message.author == self.user or message.channel.name != 'placeholder-gpt':
            return

        await self.message_queue.put(message)

    async def process_message_queue(self):
        while True:
            message = await self.message_queue.get()
            await self.handle_message(message)
            await asyncio.sleep(1)  # Rate-limiting: wait for 1 second before processing the next message

    async def handle_message(self, message):
        username = message.author.display_name
        timestamp = message.created_at.isoformat()
        user_content = f"{username} ({timestamp}): {message.content}"
        logger.debug(f"Received message: {user_content}")

        self.conversation_history.append({"role": "user", "content": user_content})

        max_tokens = 2048

        token_count = sum(count_tokens(msg["content"]) for msg in self.conversation_history)
        while token_count > max_tokens:
            removed_message = self.conversation_history.popleft()
            token_count -= count_tokens(removed_message["content"])

        logger.debug(f"$$$$$ Current token count: {token_count}")

        system_message_content = bot_settings["system_message"]

        messages_to_send = [
            {"role": "system", "content": system_message_content},
            *self.conversation_history
        ]

        # Use bot_settings values in the API call
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=bot_settings["client_timeout"])) as session:
            for _ in range(3):  # Change 3 to the desired number of retries
                try:
                    logger.debug("Making assistant API call")
                    logger.debug(f"Sending these messages: {messages_to_send}")
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

            if 'choices' in assistant_response_json:
                assistant_response = assistant_response_json['choices'][0]['message']['content']

                index = assistant_response.find("):")
                if index != -1:
                    assistant_response = assistant_response[index + 2:]
                else:
                    assistant_response = assistant_response.lstrip()

                # Split assistant_response into multiple messages if it exceeds 2000 characters
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