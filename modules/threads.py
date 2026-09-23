# ================================================
# WAS WRITTEN ENTIRELY BY AI BECAUSE OF COMPLEXITY
# ================================================

import json
import logging
import re
import uuid

import requests
from playwright.sync_api import sync_playwright

from modules.config import DOWNLOADS_PATH
from modules.downloaders import Media, PulledData

logger = logging.getLogger(__name__)

THREAD_URL_PATTERN = re.compile(r"threads\.(?:net|com)/(?:@[^/]+/post|t)/([^/?#]+)")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def get_shortcode_from_url(url: str):
    match = THREAD_URL_PATTERN.search(url)
    if match:
        return match.group(1)  # те, що потрапило в дужки (...) регулярки
    return None


def find_all_values_by_key(data, key_name):
    results = []

    if isinstance(data, dict):
        for key, value in data.items():
            if key == key_name:
                results.append(value)
            else:
                results.extend(find_all_values_by_key(value, key_name))

    elif isinstance(data, list):
        for element in data:
            results.extend(find_all_values_by_key(element, key_name))

    return results


def find_dicts_with_code(data, code):
    results = []

    if isinstance(data, dict):
        if data.get("code") == code:
            results.append(data)
        for value in data.values():
            results.extend(find_dicts_with_code(value, code))

    elif isinstance(data, list):
        for element in data:
            results.extend(find_dicts_with_code(element, code))

    return results


def parse_post(raw_post: dict):
    media_list = []

    if raw_post.get("carousel_media"):
        items_to_check = raw_post["carousel_media"]
    else:
        items_to_check = [raw_post]

    for item in items_to_check:
        video_versions = item.get("video_versions")

        if video_versions:
            video_url = video_versions[0]["url"]
            media_list.append({"url": video_url, "type": "video"})
            continue

        image_data = item.get("image_versions2")
        if image_data and image_data.get("candidates"):
            photo_url = image_data["candidates"][0]["url"]
            media_list.append({"url": photo_url, "type": "photo"})

    if not media_list:
        nested_videos = find_all_values_by_key(raw_post, "video_versions")
        for vv in nested_videos:
            if vv:
                media_list.append({"url": vv[0]["url"], "type": "video"})
                break  # беремо перше знайдене відео, щоб не тягнути дублі/прев'ю

        if not media_list:
            nested_images = find_all_values_by_key(raw_post, "image_versions2")
            for img in nested_images:
                if img and img.get("candidates"):
                    media_list.append({"url": img["candidates"][0]["url"], "type": "photo"})
                    break

    caption_data = raw_post.get("caption")
    if caption_data and caption_data.get("text"):
        caption_text = caption_data["text"]
    else:
        caption_text = ""

    user_data = raw_post.get("user")
    if user_data and user_data.get("username"):
        username = user_data["username"]
    else:
        username = "Unknown"

    return {
        "code": raw_post.get("code"),
        "text": caption_text,
        "username": username,
        "media": media_list,
    }

def open_page_in_browser(url_to_open: str):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(user_agent=USER_AGENT)

            page.goto(url_to_open, wait_until="networkidle")

            page.wait_for_selector("[data-pressable-container=true]", timeout=15000)

            final_url = page.url
            html_content = page.content()
            return final_url, html_content
        finally:
            browser.close()


def extract_json_scripts_from_html(html: str):
    pattern = r'<script type="application/json"[^>]*data-sjs[^>]*>(.*?)</script>'
    return re.findall(pattern, html, re.DOTALL)


def find_post_in_html(html: str, shortcode: str):
    candidates = []

    for json_text in extract_json_scripts_from_html(html):
        if shortcode not in json_text:
            continue

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError:
            continue

        for raw_post in find_dicts_with_code(data, shortcode):
            candidates.append(parse_post(raw_post))

    if not candidates:
        return None

    # один і той самий пост може траплятись кілька разів - беремо найповніший
    return max(
        candidates,
        key=lambda p: (len(p["media"]), p["username"] != "Unknown", bool(p["text"])),
    )


def download_media_files(media_list: list) -> list:
    downloaded = []

    for media_item in media_list:
        try:
            response = requests.get(media_item["url"], timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"File download error: {e}")
            continue

        if media_item["type"] == "video":
            extension = "mp4"
        else:
            extension = "jpg"

        file_name = f"{uuid.uuid4()}.{extension}"
        file_path = f"{DOWNLOADS_PATH}{file_name}"

        with open(file_path, "wb") as f:
            f.write(response.content)

        downloaded.append(Media(path=file_path, type=media_item["type"]))

    return downloaded


def get_threads_post(url: str) -> PulledData:
    logger.info(f"Fetching Threads post: {url}")

    shortcode = get_shortcode_from_url(url)

    if shortcode:
        url_to_open = f"https://www.threads.com/t/{shortcode}"
    else:
        url_to_open = url

    try:
        final_url, html = open_page_in_browser(url_to_open)
    except Exception as e:
        logger.error(f"Unable to open {url}: {e}")
        return PulledData(error=f"Не вдалося завантажити сторінку: {e}")

    if not shortcode:
        shortcode = get_shortcode_from_url(final_url)
        if not shortcode:
            return PulledData(error="Не вдалося розпізнати посилання на пост")

    target_post = find_post_in_html(html, shortcode)

    if target_post is None:
        return PulledData(error="Не вдалося знайти саме цей пост на сторінці")

    downloaded_media = download_media_files(target_post["media"])

    if target_post["media"] and not downloaded_media:
        return PulledData(error="Не вдалося завантажити медіафайли")

    return PulledData(
        files=downloaded_media,
        caption=target_post["text"] or "Без опису",
        author=target_post["username"],
    )