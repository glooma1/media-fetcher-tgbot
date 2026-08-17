import os
import logging
import yt_dlp
import uuid
import instaloader
import re
import requests

from urllib.parse import urlparse
from modules.config import DOWNLOADS_PATH, DOWNLOADS_RETRIES
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ==================================================================================
@dataclass
class Media:
    path: str
    type: str # "video" | "photo" | "audio" | "gif"
    is_remote: bool = False

@dataclass
class PulledData:
    files: list[Media] = field(default_factory=list)
    caption: str = ""
    author: str = ""
    error: str = None

def clean_file(media: Media):
    if not media.is_remote and media.path and os.path.exists(media.path):
        try:
            os.remove(media.path)
            logger.info(f"Clean-up --- {media.path} deleted")
        except Exception as e:
            logger.error(f"Unable to delete {media.path}: {e}")

# ==================================================================================

# Reels, Tiktok, Yt-shorts
def get_short_video(url: str):
    logger.info(f"Handling short video download: {url}")

    ydl_opts = {
            'format': 'best[ext=mp4][vcodec^=avc1]/best[ext=mp4]/best',
            'outtmpl': f'{DOWNLOADS_PATH}{uuid.uuid4()}.%(ext)s',
            'quiet': True,
            'noplaylist': True,
            'socket_timeout': 30,
            'retries': DOWNLOADS_RETRIES,
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

            if not os.path.exists(file_path):
                raise FileNotFoundError('File missing')

            caption = info.get('description') or info.get('title') or "Без опису"
            author = info.get('uploader') or info.get('uploader_id') or 'Unknown'

            logger.info(f"Download completed succesfully ({url})")

            return PulledData(
                files=[Media(path=file_path, type="video")],
                caption=caption,
                author=author
            )

    except Exception as e:
        logger.error(f"Downloading error {url}: {e}")
        return PulledData(error=str(e))

# Yt-music
def get_ytmusic(url: str):
    logger.info(f"Handling music download: {url}")

    ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{DOWNLOADS_PATH}{uuid.uuid4()}.%(ext)s',
            'quiet': True,
            'noplaylist': True,
            'socket_timeout': 30,
            'retries': DOWNLOADS_RETRIES,
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                },
                {
                    'key': 'FFmpegMetadata',
                },
            ],
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            original_file_path = ydl.prepare_filename(info)
            file_path = os.path.splitext(original_file_path)[0] + ".mp3"

            if not os.path.exists(file_path):
                raise FileNotFoundError('File missing')

            title = info.get('track') or info.get('title') or "Unknown track"
            artist = info.get('artist') or info.get('uploader') or info.get('uploader_id') or 'Unknown'

            logger.info(f"Download completed succesfully ({url})")

            return PulledData(
                files=[Media(path=file_path, type="audio")],
                caption=title,
                author=artist
            )

    except Exception as e:
        logger.error(f"Music downloading error {url}: {e}")
        return PulledData(error=str(e))

# Instagram posts
def get_ig_post(url: str):
    logger.info(f"Handling instagram post download: {url}")

    try:
        match = re.search(r"instagram\.com/p/([^/?]+)", url)
        if not match:
            return PulledData(error="Не вдалося розпізнати посилання на пост")
        shortcode = match.group(1)

        L = instaloader.Instaloader(quiet=True)
        post = instaloader.Post.from_shortcode(L.context, shortcode)

        media_files = []

        if post.typename == 'GraphSidecar':
            for node in post.get_sidecar_nodes():
                if node.is_video:
                    media_files.append({"url": node.video_url, "ext": "mp4", "type": "video"})
                else:
                    media_files.append({"url": node.display_url, "ext": "jpg", "type": "photo"})

        elif post.is_video:  
            media_files.append({"url": post.video_url, "ext": "mp4", "type": "video"})

        else:
            media_files.append({"url": post.url, "ext": "jpg", "type": "photo"})

        downloaded_media = []
        for item in media_files:
            file_path = f"{DOWNLOADS_PATH}{uuid.uuid4()}.{item['ext']}"
            
            response = requests.get(item["url"], timeout=15)
            if response.status_code == 200:
                with open(file_path, "wb") as f:
                    f.write(response.content)
                downloaded_media.append(Media(path=file_path, type=item["type"])) #({"path": file_path, "type": item["type"]})
            else:
                logger.warning(f"Instagram item pull error {url}")

        if not downloaded_media:
            return PulledData(error="Не вдалося завантажити файли.")

        logger.info(f"Download completed succesfully ({url})")
        return PulledData(
            files=downloaded_media,
            caption= post.caption or "Без опису",
            author= post.owner_username or "Unknown"
        )

    except Exception as e:
        logger.error(f"Instagram pull error {url}: {e}")
        return PulledData(error= str(e))

# Twitter/x posts
def get_x_post_content(url: str):
    logger.info(f"Handling x/twitter post download: {url}")

    try:
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split("/") if p]

        if len(path_parts) < 3 or "status" not in path_parts:
             return PulledData(error="Невірний формат посилання на пост")

        # user/status/123
        api_path = "/".join(path_parts[:3])
        api_url = f"https://api.vxtwitter.com/{api_path}"

        response = requests.get(api_url, timeout=10)

        if response.status_code != 200:
            logger.error(
                f"Failed to fetch data from vxtwitter API. "
                f"Status code: {response.status_code}, URL: {api_url}"
            )
            return PulledData(error=f"Не вдалося отримати дані. Код: {response.status_code}")

        data = response.json()

        caption = data.get("text", "")
        author = data.get("user_name", "Unknown")
        media_urls = []

        if "media_extended" in data:
            for item in data["media_extended"]:
                if item.get("type") in ("image", "video", "gif"):
                    media_urls.append(Media(path=item.get("url"), type=item.get("type"), is_remote=True))

        return PulledData(
            files= media_urls,
            caption= caption or "Без опису",
            author= author or "Unknown"
        )

    except Exception as e:
        logger.error(f"X/Twitter pull error {url}: {e}")
        return PulledData(error=str(e))
