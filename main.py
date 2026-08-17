import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, FSInputFile, InputMediaPhoto, InputMediaVideo, URLInputFile
from dotenv import load_dotenv

from modules.logging import setup_logging
from modules.downloaders import get_short_video, get_ig_post, get_ytmusic, get_x_post_content, clean_file
from modules.speechtotext import speechtotext_router

logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
retries = int(os.getenv("DOWNLOADS_RETRIES", 3))
delay = int(os.getenv("DOWNLOADS_DELAY", 2))

dp = Dispatcher()
dp.include_router(speechtotext_router)
# -----------------------------

CONTENT_PATTERNS = (
    ("tiktok.com", "short_video"),
    ("youtube.com/shorts/", "short_video"),
    ("instagram.com/reel/", "short_video"),
    ("instagram.com/p/", "instagram_post"),
    ("x.com/", "x_post"),
    ("twitter.com/", "x_post"),
    ("music.youtube.com/", "music"),
)

DOWNLOADERS = {
    "short_video": get_short_video,
    "instagram_post": get_ig_post,
    "music": get_ytmusic,
    "x_post": get_x_post_content,
}


def extract_content_info(message: Message):
    if not message.text:
        return False

    url = next((word for word in message.text.split() if "http" in word), None)
    if not url:
        return False

    for pattern, content_type in CONTENT_PATTERNS:
        if pattern in url:
            return {"url": url, "content_type": content_type}

    return False

async def with_retries(processing_msg: Message, get_function, url: str):
    result = None
    for attempt in range(1, retries + 1):
        if attempt > 1:
            try:
                await processing_msg.edit_text(f"⏳ Спроба {attempt}/{retries}...")
            except Exception as e:
                logger.error(f"Unable to edit message: {e}")

        result = await asyncio.to_thread(get_function, url)

        if not result.get("error"):
            return result

        logger.warning(f"Attempt {attempt}/{retries} unsuccessful ({url}): {result['error']}")

        if attempt < retries:
            await asyncio.sleep(delay + 1)

    return result


@dp.message(extract_content_info)
async def handle_download_request(message: Message, url: str, content_type: str):

    logger.info(f"@{message.from_user.username or message.from_user.id} -> {content_type}: {url}")
    processing_msg = await message.reply("⏳ Обробляю посилання...")

    downloader = DOWNLOADERS.get(content_type)

    if downloader is None:
        await processing_msg.edit_text("❌ Невідомий тип контенту.")
        return

    # --- ЗАВАНТАЖЕННЯ ---
    result = await with_retries(processing_msg, downloader, url)

    # --- ПЕРЕВІРКА РЕЗУЛЬТАТІВ ---
    if result.get("error"):
        await processing_msg.edit_text(f"❌ Помилка: <blockquote expandable>{result['error']}</blockquote>")
        return

    files = result.get("files", [])

    # --- ФОРМУВАННЯ ТЕКСТУ ---
    sender = html.quote(message.from_user.username or message.from_user.full_name)
    author = html.quote(result.get("author", "Unknown"))
    caption = html.quote(result.get("caption", "Без опису"))[:800]

    final_text = (
        f"<b>@{sender}</b> -- <a href='{url}'>🔗</a>\n"
        f"🎬 <b>{author}</b>\n"
        f"<blockquote expandable>📝 {caption}\n</blockquote>"
    )

    # --- ВІДПРАВКА ---
    try:
        if not files:
            await message.answer(text=final_text, parse_mode=ParseMode.HTML)
            await processing_msg.delete()
            return

        if len(files) == 1:
            file_info = files[0]
            file_path = file_info["path"]

            if file_path.startswith(("http://", "https://")):
                media = URLInputFile(file_path)
            else:
                media = FSInputFile(file_info["path"])

            if file_info["type"] in ("video", "gif"):
                await message.answer_video(video=media, caption=final_text, parse_mode=ParseMode.HTML)

            elif file_info["type"] in ("photo", "image"):
                await message.answer_photo(photo=media, caption=final_text, parse_mode=ParseMode.HTML)

            else:
                await message.answer_audio(
                    audio=media,
                    caption=f"<b>@{sender}</b> -- <a href='{url}'>🔗</a>",
                    parse_mode=ParseMode.HTML,
                    title=caption,
                    performer=author
                )
        else:
            media_group = []
            for index, file_info in enumerate(files):
                file_path = file_info["path"]

                if file_path.startswith(("http://", "https://")):
                    media = file_path
                else:
                    media = FSInputFile(file_path)

                media_caption = final_text if index == 0 else None

                if file_info["type"] in ("video", "gif"):
                    media_group.append(InputMediaVideo(media=media, caption=media_caption, parse_mode=ParseMode.HTML))
                else:
                    media_group.append(InputMediaPhoto(media=media, caption=media_caption, parse_mode=ParseMode.HTML))

            await message.answer_media_group(media=media_group)

        await processing_msg.delete()

    except Exception as e:
        logger.error(f"Sending error: {e}")
        await processing_msg.edit_text(f"❌ Сталася помилка при надсиланні: {e}")

    finally:
        for file_info in files:
            clean_file(file_info["path"])

    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Unable to delete message: {e}")

# -----------------------------

async def main():
    bot = Bot(token=TOKEN,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True))
    await dp.start_polling(bot)

if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())