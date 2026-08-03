import logging

from aiogram import Bot, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import Message

from .database import Database

logger = logging.getLogger(__name__)
router = Router()


def is_private(message: Message) -> bool:
    return message.chat.type == ChatType.PRIVATE and message.from_user is not None


async def is_group_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except TelegramAPIError:
        logger.exception("Failed to check admin %s in chat %s", user_id, chat_id)
        return False
    return member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}


@router.message(Command("start"))
async def start(message: Message) -> None:
    if is_private(message):
        await message.bot.send_message(
            message.chat.id,
            "Панель управления ботом.\n\n"
            "Используйте /groups, чтобы выбрать группу, где вы являетесь администратором.\n\n"
            "Use /groups to select a group where you are an administrator.",
        )
    else:
        await message.delete()


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    if not is_private(message):
        await message.delete()
        return
    await message.bot.send_message(
        message.chat.id,
        "Команды управления ботом:\n\n"
        "/start — открыть панель управления\n"
        "/help — показать эту справку\n"
        "/groups — показать группы, где вы администратор\n"
        "/select НОМЕР — выбрать группу для управления\n"
        "/users — показать зарегистрированных пользователей выбранной группы\n"
        "/del НОМЕР — удалить пользователя из списка выбранной группы\n\n"
        "После удаления пользователь снова должен пройти проверку при следующем сообщении.\n\n"
        "Бот проверяет новых участников при первой попытке написать в группе. "
        "Администраторы и владелец группы не проверяются.\n\n"
        "Bot management commands:\n\n"
        "/start — open the control panel\n"
        "/help — show this help\n"
        "/groups — list groups where you are an administrator\n"
        "/select NUMBER — select a group\n"
        "/users — list registered users in the selected group\n"
        "/del NUMBER — remove a user from the selected group\n\n"
        "After removal, the user must pass the challenge again on the next message.\n\n"
        "The bot checks new users on their first attempt to write in a group. "
        "Administrators and the group owner are not checked.",
    )


@router.message(Command("groups"))
async def groups(message: Message, bot: Bot, db: Database) -> None:
    if not is_private(message):
        await message.delete()
        return
    available: list[dict[str, int | str]] = []
    for group in await db.list_known_groups():
        if await is_group_admin(bot, int(group["chat_id"]), message.from_user.id):  # type: ignore[union-attr]
            available.append(group)
    if not available:
        await bot.send_message(message.chat.id, "Доступных групп не найдено.\nNo available groups found.")
        return
    lines = ["Ваши группы / Your groups:"]
    for index, group in enumerate(available, 1):
        lines.append(f"{index}. {group['title']} ({group['chat_id']})")
    lines.append("\nВыберите группу / Select a group: /select NUMBER")
    # The temporary numbering is stored in the message text only; selection is
    # resolved against the currently available, freshly validated group list.
    await bot.send_message(message.chat.id, "\n".join(lines))


@router.message(Command("select"))
async def select_group(message: Message, bot: Bot, db: Database) -> None:
    if not is_private(message):
        await message.delete()
        return
    parts = (message.text or "").split()
    try:
        requested = int(parts[1])
    except (IndexError, ValueError):
        await bot.send_message(message.chat.id, "Использование / Usage: /select NUMBER")
        return
    available = [
        group for group in await db.list_known_groups()
        if await is_group_admin(bot, int(group["chat_id"]), message.from_user.id)  # type: ignore[union-attr]
    ]
    if requested < 1 or requested > len(available):
        await bot.send_message(message.chat.id, "Группа с таким номером не найдена.\nGroup number not found.")
        return
    group = available[requested - 1]
    await db.set_admin_context(message.from_user.id, int(group["chat_id"]))  # type: ignore[union-attr]
    await bot.send_message(message.chat.id, f"Выбрана группа / Selected group: {group['title']}\nТеперь используйте /users или /del NUMBER")


async def selected_group(message: Message, bot: Bot, db: Database) -> int | None:
    chat_id = await db.get_admin_context(message.from_user.id)  # type: ignore[union-attr]
    if chat_id is None or not await is_group_admin(bot, chat_id, message.from_user.id):  # type: ignore[union-attr]
        await bot.send_message(message.chat.id, "Сначала выберите доступную группу через /groups.\nSelect a group first using /groups.")
        return None
    return chat_id


@router.message(Command("users"))
async def users(message: Message, bot: Bot, db: Database) -> None:
    if not is_private(message):
        await message.delete()
        return
    chat_id = await selected_group(message, bot, db)
    if chat_id is None:
        return
    records = await db.list_verified_for_chat(chat_id)
    if not records:
        await bot.send_message(message.chat.id, "В выбранной группе зарегистрированных пользователей нет.\nNo registered users in the selected group.")
        return
    lines = [f"Зарегистрированные пользователи / Registered users (chat_id {chat_id}):"]
    for index, record in enumerate(records, 1):
        lines.append(f"{index}. {record['name'] or 'Без имени / No name'} — user_id {record['user_id']}")
    lines.append("\nДля удаления / To delete: /del NUMBER")
    await bot.send_message(message.chat.id, "\n".join(lines))


@router.message(Command("del"))
async def delete_user(message: Message, bot: Bot, db: Database) -> None:
    if not is_private(message):
        await message.delete()
        return
    chat_id = await selected_group(message, bot, db)
    if chat_id is None:
        return
    parts = (message.text or "").split()
    try:
        index = int(parts[1])
    except (IndexError, ValueError):
        await bot.send_message(message.chat.id, "Использование / Usage: /del NUMBER")
        return
    deleted = await db.delete_verified_by_index(chat_id, index)
    if deleted is None:
        await bot.send_message(message.chat.id, "Пользователь с таким номером не найден.\nUser number not found.")
    else:
        await bot.send_message(message.chat.id, f"Пользователь {deleted} удалён из списка выбранной группы.\nUser {deleted} was removed from the selected group.")
