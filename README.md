<h1>Media-fetcher-tgbot</h1>

A Telegram bot for downloading media from popular platforms (Tiktok, Reels, YtShorts/Music, X/Twiter, Threads) and transcribing voice messages.

<blockquote>
<strong>This bot is intended for personal use only, with a small number of active users.</strong>
</blockquote>

<h2>Configuration</h2>

Create a <code>.env</code> file:

```env
BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key

DOWNLOADS_PATH=/dev/shm/
DOWNLOADS_RETRIES=3
DOWNLOADS_DELAY=2