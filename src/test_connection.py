import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ServerError

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("MODEL_NAME", "gemini-3.8-flash")

if not api_key:
    raise ValueError("GEMINI_API_KEY not set in .env")

client = genai.Client(api_key=api_key)

# Helper function to send messages with built-in retry logic
def send_chat_message_with_retry(chat, message, max_retries=3):
    for attempt in range(max_retries):
        try:
            return chat.send_message(message)
        except ServerError as e:
            if e.code == 503:
                wait_time = 2 ** attempt  # 1s, 2s, 4s...
                print(f"[WARN] Google server busy (503). Retrying in {wait_time}s... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                raise e
    raise RuntimeError("API failed after maximum retries due to high server demand.")

# Initialize stateful chat with locked system instruction
chat = client.chats.create(
    model=model_name,
    config=types.GenerateContentConfig(
        system_instruction=(
            "You are the AI Procurement Assistant for a Ugandan SME shop. "
            "You support, never decide. You never approve orders or invent data. "
            "Always cite the CSV source for any number you state."
        ),
        temperature=0.1,
    )
)

# Execute request safely
response = send_chat_message_with_retry(
    chat, 
    "In one sentence, explain why digital inventory tracking beats an exercise book that could get water-damaged."
)

print("--- Model Response ---")
print(response.text)