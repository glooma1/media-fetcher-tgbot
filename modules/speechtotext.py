import logging
import os
import uuid

from openai import AsyncOpenAI
from aiogram import Router, F
from aiogram.types import Message
from modules.config import DOWNLOADS_PATH, OPENAI_API_KEY
from modules.downloaders import clean_file

logger = logging.getLogger(__name__)

client = AsyncOpenAI(
    api_key=OPENAI_API_KEY
)

speechtotext_router = Router(name="speechtotext")

async def _get_voice_transcription(filepath:str):
    try:
        with open(filepath, "rb") as audio:
            transcription = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio,
                language="uk"
            )
        return transcription.text
    
    except Exception as e:
        logger.error(f"Whisper API error: {e}")
        raise


@speechtotext_router.message(F.voice)
async def handle_voice_message(message: Message):
    processing_msg = await message.reply("🎧 Слухаю...")
    file_path = f"{DOWNLOADS_PATH}{uuid.uuid4()}.ogg"

    try:
        file_info = await message.bot.get_file(message.voice.file_id)
        await message.bot.download_file(file_info.file_path, destination=file_path)

        transcription = await _get_voice_transcription(file_path)

        if not transcription:
            await processing_msg.edit_text("❌ Не вдалося розчути чи розпізнати текст.")
            return

        await processing_msg.edit_text(f"🗣 {transcription}")

    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        await processing_msg.edit_text(f"❌ Сталася помилка при обробці аудіо {e}")

    finally:
        clean_file(file_path)

