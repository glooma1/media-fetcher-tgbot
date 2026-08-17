import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, FSInputFile, InputMediaPhoto, InputMediaVideo, URLInputFile

from modules.config import BOT_TOKEN, DOWNLOADS_RETRIES, DOWNLOADS_DELAY
from modules.logging import setup_logging
from modules.downloaders import get_short_video, get_ig_post, get_ytmusic, get_x_post_content, clean_file, PulledData
from modules.speechtotext import speechtotext_router


logger = logging.getLogger(__name__)

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
    for attempt in range(1, DOWNLOADS_RETRIES + 1):
        if attempt > 1:
            try:
                await processing_msg.edit_text(f"⏳ Спроба {attempt}/{DOWNLOADS_RETRIES}...")
            except Exception as e:
                logger.error(f"Unable to edit message: {e}")

        result = await asyncio.to_thread(get_function, url)

        if not result.error:
            return result

        logger.warning(f"Attempt {attempt}/{DOWNLOADS_RETRIES} unsuccessful ({url}): {result.error}")

        if attempt < DOWNLOADS_RETRIES:
            await asyncio.sleep(DOWNLOADS_DELAY + 1)

    return result


@dp.message(extract_content_info)
async def handle_download_request(message: Message, url: str, content_type: str):

    logger.info(f"@{message.from_user.username or message.from_user.id} -> {content_type}: {url}")
    processing_msg = await message.reply("⏳ Завантажую...")

    downloader = DOWNLOADERS.get(content_type)

    if downloader is None:
        await processing_msg.edit_text("❌ Невідомий тип контенту.")
        return

    # --- ЗАВАНТАЖЕННЯ ---
    result = await with_retries(processing_msg, downloader, url)

    # --- ПЕРЕВІРКА РЕЗУЛЬТАТІВ ---
    if result.error:
        await processing_msg.edit_text(f"❌ Помилка: <blockquote expandable>{result.error}</blockquote>")
        return

    # --- ФОРМУВАННЯ ТЕКСТУ ---
    sender = html.quote(message.from_user.username or message.from_user.full_name)
    author = html.quote(result.author)
    caption = html.quote(result.caption[:800])

    final_text = (
        f"<b>@{sender}</b> -- <a href='{url}'>🔗</a>\n"
        f"🎬 <b>{author}</b>\n"
        f"<blockquote expandable>📝 {caption}\n</blockquote>"
    )

    # --- ВІДПРАВКА ---
    try:
        if not result.files:
            await message.answer(text=final_text)
            await processing_msg.delete()
            return

        if len(result.files) == 1:
            media_file = result.files[0]
            
            media = URLInputFile(media_file.path) if media_file.is_remote else FSInputFile(media_file.path)

            if media_file.type in ("video", "gif"):
                await message.answer_video(video=media, caption=final_text)
            elif media_file.type in ("photo", "image"):
                await message.answer_photo(photo=media, caption=final_text)
            else:
                await message.answer_audio(
                    audio=media,
                    caption=f"<b>@{sender}</b> -- <a href='{url}'>🔗</a>",
                    title=caption,
                    performer=author
                )
        else:
            media_group = []
            for index, media_file in enumerate(result.files):
                media = URLInputFile(media_file.path) if media_file.is_remote else FSInputFile(media_file.path)
                
                media_caption = final_text if index == 0 else None

                if media_file.type in ("video", "gif"):
                    media_group.append(InputMediaVideo(media=media, caption=media_caption))
                else:
                    media_group.append(InputMediaPhoto(media=media, caption=media_caption))

            await message.answer_media_group(media=media_group)

        await processing_msg.delete()

    except Exception as e:
        logger.error(f"Sending error: {e}")
        await processing_msg.edit_text(f"❌ Сталася помилка під час надсилання: {e}")

    finally:
        for media_file in result.files:
            clean_file(media_file)

    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Unable to delete message: {e}")

# -----------------------------

async def main():
    bot = Bot(token=BOT_TOKEN,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True))
    await dp.start_polling(bot)

if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())