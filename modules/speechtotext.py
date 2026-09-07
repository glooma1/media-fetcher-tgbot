import logging
import uuid

from aiogram import F, Router
from aiogram.types import Message
from openai import AsyncOpenAI

from modules.config import DOWNLOADS_PATH, OPENAI_SPEECH_API_KEY, OPENAI_SPEECH_MODEL
from modules.downloaders import Media, clean_file

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_SPEECH_API_KEY)

speechtotext_router = Router(name="speechtotext")


async def _get_voice_transcription(filepath: str) -> str:
    try:
        with open(filepath, "rb") as audio:
            transcription = await client.audio.transcriptions.create(
                model=OPENAI_SPEECH_MODEL,
                file=audio,
                language="uk",
            )
        return transcription.text

    except Exception as e:
        logger.error(f"Whisper API error: {e}")
        raise


@speechtotext_router.message(F.voice)
async def handle_voice_message(message: Message):
    logger.info(f"Transcribing voice message from @{message.from_user.username or message.from_user.id}")
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
        logger.info("Transcription completed successfully")

    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        await processing_msg.edit_text(f"❌ Сталася помилка при обробці аудіо {e}")

    finally:
        clean_file(Media(path=file_path, type="audio"))

