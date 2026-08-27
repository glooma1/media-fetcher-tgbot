import logging

from openai import AsyncOpenAI
from aiogram import Router, F, Bot
from aiogram.types import Message

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
        context = ""

        if message.reply_to_message:
            replied = message.reply_to_message

            if replied.text:
                context = (
                    "Message user has replied to:\n"
                    f"{replied.text}\n\n"
                )

        full_prompt = f"{context}User request:\n{prompt}"

        response = await client.responses.create(
            model=OPENAI_MODEL,
            instructions=LLM_MASTER_PROMPT,
            input=full_prompt,
        )

        await status_msg.edit_text(response.output_text)
        logger.info(f"LLM Request completed successfully")

    except Exception as e:
        logger.error(f"LLM Request error: {e}")
        await status_msg.edit_text(f"❌Сталася помилка: {e}")