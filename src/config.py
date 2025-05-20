import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file. Please set it.")

# src/config.py
# ... (your GEMINI_API_KEY loading) ...

MAX_CONTEXT_ENTRIES_FOR_LLM = 5 # Or your preferred number for fallback