import asyncio
import logging
import openai
import os
import json
import aiohttp

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

with open("librarian_settings.txt", "r") as file:
    librarian_settings = json.load(file)

data_store = {
    "users": {},
    "conversations": {}
}

class Librarian:
    def __init__(self):
        self.message_queue = asyncio.Queue()
        self.message_counter = 0
        self.messages_to_process = []
        self.messages_to_wait = 3  # Indicates number of messages to wait before processing

    async def monitor_messages(self, conversation_history):
        self.message_counter += 1
        # Ignore facts messages when processing conversation history
        usernames = [key for key in data_store["conversations"].keys()]
        self.messages_to_process = [msg for msg in conversation_history if not (msg["role"] == "assistant" and any(msg["content"].startswith(f"{username}:") for username in usernames))]
        if self.message_counter >= self.messages_to_wait:
            await self.process_messages()
            await asyncio.sleep(1)  # Add this line to allow for processing
            self.message_counter = 0  # Reset the message counter

    async def process_messages(self):
        system_message_content = (
            "You are an intelligent assistant specializing in extracting essential information from conversations. "
            "Analyze the given conversation and provide a summary of important facts about users\n\n"
            "When you identify characteristics about a given user, write them in this format:\n"
            "user:username_goes_here:fact\n\n"
            "Example:\n"
            "user:Zonaxx:Loves space travel\n\n"
        )
        input_text = "Extract facts from this conversation:\n\n" + "\n".join(msg["content"] for msg in self.messages_to_process)

        messages_to_send = [
            {"role": "system", "content": system_message_content},
            {"role": "user", "content": input_text},
        ]

        async def api_call():  # Define the api_call function inside process_messages
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=librarian_settings["client_timeout"])) as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={"model": librarian_settings["model"], 
                        "messages": messages_to_send,
                        "temperature": librarian_settings["temperature"],
                        "top_p": librarian_settings["top_p"],
                    },
                ) as response:
                    response_json = await response.json()
                    logger.debug(f"Librarian API response: {response_json}")
                    return response_json

        response_json = await api_call()

        if 'choices' in response_json:
            extracted_facts_text = response_json['choices'][0]['message']['content']

            extracted_facts_list = extracted_facts_text.strip().split("\n")

            for fact in extracted_facts_list:
                if fact.startswith("user:"):
                    fact_data = fact.split(":", 2)
                    if len(fact_data) == 3:
                        _, key, value = fact_data
                        key = key.strip()
                        value = value.strip()
                        if key not in data_store["conversations"]:
                            data_store["conversations"][key] = set()
                        data_store["conversations"][key].add(value)  # Store the facts in data_store

            self.messages_to_process = []
            self.message_counter = 0  # Reset the message counter
        else:
            logger.debug("Couldn't extract facts from the conversation due to an API error or empty response.")
            
    def get_facts(self):
        facts = ""
        for key, values in data_store["conversations"].items():
            facts += f"{key}:\n"
            facts += "\n".join(f"  - {fact}" for fact in values)
            facts += "\n\n"
            facts += "\n"
        return facts
    
    def get_facts_for_user(self, username):
        user_facts = data_store["conversations"].get(username, [])
        return "\n".join(sorted(user_facts))

async def librarian_main(client):
    logger.debug("Starting librarian process")
    librarian = Librarian()

    while True:
        conversation_history = await client.librarian_message_queue.get()
        
        # Add this line to ensure the conversation_history is passed to the monitor_messages function.
        await librarian.monitor_messages(conversation_history)
        await asyncio.sleep(1)