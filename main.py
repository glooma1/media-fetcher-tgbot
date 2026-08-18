import asyncio
import logging

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    FSInputFile,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
    URLInputFile,
)

from modules.config import BOT_TOKEN, DOWNLOADS_DELAY, DOWNLOADS_RETRIES
from modules.downloaders import (
    clean_file,
    get_ig_post,
    get_short_video,
    get_x_post_content,
    get_ytmusic,
)
from modules.threads import get_threads_post
from modules.logging import setup_logging
from modules.speechtotext import speechtotext_router


logger = logging.getLogger(__name__)

dp = Dispatcher()
dp.include_router(speechtotext_router)

# ===========================================================================

CONTENT_PATTERNS = (
    ("tiktok.com", "short_video"),
    ("youtube.com/shorts/", "short_video"),
    ("instagram.com/reel/", "short_video"),
    ("instagram.com/p/", "instagram_post"),
    ("x.com/", "x_post"),
    ("twitter.com/", "x_post"),
    ("music.youtube.com/", "music"),
    ("threads.com/", "threads_post")
)

DOWNLOADERS = {
    "short_video": get_short_video,
    "instagram_post": get_ig_post,
    "music": get_ytmusic,
    "x_post": get_x_post_content,
    "threads_post": get_threads_post
}

def extract_content_info(message: Message):
    if not message.text:
        return None

    url = next((word for word in message.text.split() if "http" in word), None)
    if not url:
        return None

    for pattern, content_type in CONTENT_PATTERNS:
        if pattern in url:
            return {"url": url, "content_type": content_type}

    return None


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

# ===========================================================================

@dp.message(extract_content_info)
async def handle_download_request(message: Message, url: str, content_type: str):
    logger.info(f"Request @{message.from_user.username or message.from_user.id} -> {content_type}: {url}")
    processing_msg = await message.reply("⏳ Завантажую...")

    downloader = DOWNLOADERS.get(content_type)
    if downloader is None:
        await processing_msg.edit_text("❌ Невідомий тип контенту.")
        return

    result = await with_retries(processing_msg, downloader, url)
    if result.error:
        await processing_msg.edit_text(f"❌ Помилка під час завантаження: <blockquote expandable>{result.error}</blockquote>")
        return

    sender = message.from_user.username or message.from_user.full_name
    header = f"<b>@{html.quote(sender)}</b> -- <a href='{url}'>🔗</a>"
    author = html.quote(result.author)
    caption = html.quote(result.caption[:800])
    final_text = f"{header}\n🎬 <b>{author}</b>\n<blockquote expandable>📝 {caption}\n</blockquote>"

    def to_input(media_file):
        return URLInputFile(media_file.path) if media_file.is_remote else FSInputFile(media_file.path)

    try:
        if not result.files:
            await message.answer(final_text)

        elif len(result.files) == 1:
            media_file = result.files[0]
            media = to_input(media_file)

            if media_file.type in ("video", "gif"):
                await message.answer_video(video=media, caption=final_text)
            elif media_file.type in ("photo", "image"):
                await message.answer_photo(photo=media, caption=final_text)
            else:
                await message.answer_audio(audio=media, caption=header, title=caption, performer=author)

        else:
            media_group = [
                (InputMediaVideo if f.type in ("video", "gif") else InputMediaPhoto)(
                    media=to_input(f),
                    caption=final_text if i == 0 else None,
                )
                for i, f in enumerate(result.files)
            ]
            await message.answer_media_group(media=media_group)

        await processing_msg.delete()

    except Exception as e:
        logger.error(f"Sending error: {e}")
        await processing_msg.edit_text(f"❌ Сталася помилка: {e}")

    finally:
        for media_file in result.files:
            clean_file(media_file)

    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Unable to delete message: {e}")

# ===========================================================================

async def main():
    bot = Bot(token=BOT_TOKEN,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True))
    async with bot:
        await dp.start_polling(bot)


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())