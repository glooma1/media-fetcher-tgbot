import asyncio
import logging
import sys
import configparser

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, FSInputFile, InputMediaPhoto, InputMediaVideo, URLInputFile

from modules.downloaders import download_short_video, download_ig_post, download_ytmusic, get_x_post_content, clean_file

logger = logging.getLogger(__name__)

config = configparser.ConfigParser()
config.read("config.ini", encoding="utf-8")
TOKEN = config["Telegram"]["TOKEN"]

dp = Dispatcher()

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
    "short_video": download_short_video,
    "instagram_post": download_ig_post,
    "music": download_ytmusic,
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


@dp.message(extract_content_info)
async def handle_download_request(message: Message, url: str, content_type: str):
    processing_msg = await message.reply("⏳ Обробляю посилання...")

    downloader = DOWNLOADERS.get(content_type)

    if downloader is None:
        await processing_msg.edit_text("❌ Невідомий тип контенту.")
        return

    # --- ЗАВАНТАЖЕННЯ ---
    result = await asyncio.to_thread(downloader, url)

    # --- ПЕРЕВІРКА РЕЗУЛЬТАТІВ ---
    if result.get("error"):
        await processing_msg.edit_text(f"❌ Помилка: {result['error']}")
        return

    files = result.get("files", [])
    # if not files:
    #     await processing_msg.edit_text("❌ Помилка: Файли не знайдено.")
    #     return

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

            if file_info["type"] in ("video" or "gif"):
                await message.answer_video(video=media, caption=final_text, parse_mode=ParseMode.HTML)

            elif file_info["type"] == ("photo" or "image"):
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
                media = FSInputFile(file_info["path"])
                media_caption = final_text if index == 0 else None

                if file_info["type"] == "video":
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
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    log_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)

    logging.basicConfig(level=logging.INFO, handlers=[console_handler])
    asyncio.run(main())