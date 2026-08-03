import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import logging
import time

from aiogram import Bot, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError
from aiogram.types import ChatPermissions, Message

from .challenge import generate_challenge
from .database import ChallengeRecord, Database
from .words import is_correct_answer

logger = logging.getLogger(__name__)
router = Router()
user_locks: defaultdict[tuple[int, int], asyncio.Lock] = defaultdict(asyncio.Lock)


async def safe_delete(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id, message_id)
    except TelegramBadRequest as error:
        logger.debug("Message %s/%s was already unavailable: %s", chat_id, message_id, error)
    except TelegramAPIError:
        logger.exception("Telegram API error while deleting message %s/%s", chat_id, message_id)


async def delete_later(bot: Bot, chat_id: int, message_id: int, delay: int) -> None:
    await asyncio.sleep(delay)
    await safe_delete(bot, chat_id, message_id)


async def send_new_challenge(
    message: Message, bot: Bot, db: Database, user_id: int
) -> None:
    generated = generate_challenge()
    options = await db.get_bot_settings()
    timeout_minutes = int(options["challenge_timeout_minutes"])
    challenge_message = await bot.send_message(message.chat.id, generated.text(timeout_minutes))
    expires_at = time.time() + timeout_minutes * 60
    inserted = await db.add_challenge(
        message.chat.id, user_id, generated.answer, challenge_message.message_id, expires_at
    )
    if not inserted:
        await safe_delete(bot, message.chat.id, challenge_message.message_id)
        return
    logger.info("Challenge started: chat_id=%s user_id=%s", message.chat.id, user_id)


async def handle_answer(
    message: Message, bot: Bot, db: Database, record: ChallengeRecord
) -> None:
    chat_id = message.chat.id
    user_id = message.from_user.id  # type: ignore[union-attr]
    await safe_delete(bot, chat_id, message.message_id)
    await db.delete_challenge(chat_id, user_id)
    await safe_delete(bot, chat_id, record.challenge_message_id)

    if is_correct_answer(message.text or "", record.answer):
        await db.mark_verified(chat_id, user_id, message.from_user.full_name)  # type: ignore[union-attr]
        logger.info("Challenge passed: chat_id=%s user_id=%s", chat_id, user_id)
        options = await db.get_bot_settings()
        result = await bot.send_message(
            chat_id,
            "Проверка успешно пройдена. Добро пожаловать!\n\n"
            "Verification passed successfully. Welcome!",
        )
        asyncio.create_task(delete_later(bot, chat_id, result.message_id, int(options["success_delete_seconds"])))
        return

    logger.info("Wrong challenge answer: chat_id=%s user_id=%s", chat_id, user_id)
    options = await db.get_bot_settings()
    until_date = datetime.now(timezone.utc) + timedelta(hours=int(options["mute_hours"]))
    try:
        await bot.restrict_chat_member(
            chat_id,
            user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date,
        )
        logger.info("Muted user for 24 hours: chat_id=%s user_id=%s", chat_id, user_id)
    except TelegramAPIError:
        logger.exception("Telegram API error while muting chat_id=%s user_id=%s", chat_id, user_id)
    result = await bot.send_message(
        chat_id,
        "Проверка не пройдена.\n"
        f"Возможность отправки сообщений заблокирована на {options['mute_hours']} часа.\n\n"
        "Verification failed.\n"
        f"Messaging is blocked for {options['mute_hours']} hours."
    )
    asyncio.create_task(delete_later(bot, chat_id, result.message_id, int(options["failure_delete_seconds"])))


@router.message()
async def on_message(message: Message, bot: Bot, db: Database) -> None:
    if message.chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        return
    await db.remember_group(message.chat.id, message.chat.title or str(message.chat.id))
    # Joining/leaving service messages are not attempts to write. A challenge
    # starts only when the user sends an actual message in the group.
    # Messages authored by a channel (including linked-channel forwards) are
    # not regular users and must never receive a challenge.
    if (
        message.new_chat_members
        or message.left_chat_member
        or message.sender_chat is not None
        or message.is_automatic_forward
    ):
        return
    if message.from_user is None or message.from_user.is_bot:
        return

    try:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    except TelegramAPIError:
        logger.exception("Telegram API error while checking member status")
        return
    if member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}:
        return
    if await db.is_verified(message.chat.id, message.from_user.id):
        return

    key = (message.chat.id, message.from_user.id)
    async with user_locks[key]:
        record = await db.get_challenge(*key)
        if record is not None and record.expires_at > time.time():
            await handle_answer(message, bot, db, record)
            return
        if record is not None:
            await db.delete_challenge(*key)
            await safe_delete(bot, message.chat.id, record.challenge_message_id)
            logger.info("Challenge timed out: chat_id=%s user_id=%s", *key)

        await safe_delete(bot, message.chat.id, message.message_id)
        await send_new_challenge(message, bot, db, message.from_user.id)


async def cleanup_expired(bot: Bot, db: Database) -> None:
    for record in await db.expired_challenges(time.time()):
        await db.delete_challenge(record.chat_id, record.user_id)
        await safe_delete(bot, record.chat_id, record.challenge_message_id)
        logger.info("Challenge timed out: chat_id=%s user_id=%s", record.chat_id, record.user_id)


async def cleanup_loop(bot: Bot, db: Database) -> None:
    while True:
        await asyncio.sleep(20)
        try:
            await cleanup_expired(bot, db)
        except Exception:
            logger.exception("Error during expired challenge cleanup")
