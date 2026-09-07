import logging

from aiogram import Bot, F, Router
from aiogram.types import Message
from openai import AsyncOpenAI

from modules.config import OPENAI_LLM_API, OPENAI_MODEL, LLM_MASTER_PROMPT

logger = logging.getLogger(__name__)

llm_router = Router()

client = AsyncOpenAI(api_key=OPENAI_LLM_API)


@llm_router.message(F.text)
async def handle_llm(message: Message, bot: Bot):
    me = await bot.get_me()
    mention = f"@{me.username}"

    if not message.text.lower().startswith(mention.lower()):
        return

    prompt = message.text[len(mention):].strip()

    if not prompt:
        return

    logger.info(f"LLM Request from @{message.from_user.username or message.from_user.id}")
    status_msg = await message.reply("💡Думаю...")

    try:
        replied = message.reply_to_message
        context = (
            f"Message user has replied to:\n{replied.text}\n\n"
            if replied and replied.text
            else ""
        )

        full_prompt = f"{context}User request:\n{prompt}"

        response = await client.responses.create(
            model=OPENAI_MODEL,
            instructions=LLM_MASTER_PROMPT,
            input=full_prompt,
        )

        await status_msg.edit_text(response.output_text)
        logger.info("LLM Request completed successfully")

    except Exception as e:
        logger.error(f"LLM Request error: {e}")
        await status_msg.edit_text(f"❌Сталася помилка: {e}")