import os
from dotenv import load_dotenv

load_dotenv()

DOWNLOADS_PATH = os.getenv("DOWNLOADS_PATH", "/dev/shm/")
BOT_TOKEN = os.getenv("BOT_TOKEN")
DOWNLOADS_RETRIES = int(os.getenv("DOWNLOADS_RETRIES", 3))
DOWNLOADS_DELAY = int(os.getenv("DOWNLOADS_DELAY", 3))
OPENAI_SPEECH_API_KEY = os.getenv("OPENAI_SPEECH_API_KEY")
OPENAI_SPEECH_MODEL = os.getenv("OPENAI_SPEECH_MODEL", "whisper-1")