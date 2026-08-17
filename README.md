<h1>Media-fetcher-tgbot</h1>

A Telegram bot for downloading media from popular platforms and transcribing voice messages.

<h2>Configuration</h2>

Create a <code>.env</code> file:

```env
BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key

DOWNLOADS_PATH=/dev/shm/
DOWNLOADS_RETRIES=3
DOWNLOADS_DELAY=2
```

<blockquote>
<strong>Note:</strong> <code>/dev/shm/</code> is recommended for <code>DOWNLOADS_PATH</code>
</blockquote>
