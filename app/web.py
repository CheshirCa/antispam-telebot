from html import escape
import logging

from aiohttp import web

from .config import Settings
from .database import Database

logger = logging.getLogger(__name__)


def _page(body: str, message: str = "", show_back_link: bool = False) -> str:
    notice = f'<div class="notice">{escape(message)}</div>' if message else ""
    back_link = '<p><a href="/">← Вернуться на главную</a></p>' if show_back_link else ""
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Anti-spam bot</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:1100px;margin:30px auto;padding:0 20px;background:#f5f6f8;color:#202124}}
section{{background:white;border:1px solid #ddd;border-radius:10px;padding:20px;margin:16px 0}}
h1{{margin-top:0}} table{{border-collapse:collapse;width:100%}} th,td{{padding:9px;border-bottom:1px solid #eee;text-align:left}}
input[type=number]{{width:100px;padding:6px}} button{{padding:8px 14px;cursor:pointer}} .danger{{background:#b42318;color:white;border:0;border-radius:5px}}
.notice{{background:#e8f5e9;border:1px solid #a5d6a7;padding:10px;margin:10px 0;border-radius:5px}}
.muted{{color:#666;font-size:.9em}} label{{display:block;margin:10px 0}}
</style></head><body><h1>Панель Anti-spam бота</h1>{notice}{body}{back_link}</body></html>"""


async def index(request: web.Request) -> web.Response:
    db: Database = request.app["db"]
    settings: Settings = request.app["settings"]
    users = await db.list_verified()
    values = await db.get_bot_settings()
    rows = "".join(
        f"<tr><td><input type='checkbox' name='users' value='{user['chat_id']}:{user['user_id']}'></td>"
        f"<td>{user['chat_id']}</td><td>{user['user_id']}</td><td>{escape(str(user['name']))}</td>"
        f"<td>{escape(str(user['verified_at']))}</td></tr>"
        for user in users
    ) or "<tr><td colspan='5' class='muted'>Проверенных пользователей нет</td></tr>"
    body = f"""
<section><h2>Настройки</h2>
<form method="post" action="/settings">
<label>Время проверки, минут: <input type="number" min="1" max="60" name="challenge_timeout_minutes" value="{escape(values['challenge_timeout_minutes'])}"></label>
<label>Mute, часов: <input type="number" min="1" max="168" name="mute_hours" value="{escape(values['mute_hours'])}"></label>
<label>Удаление сообщения об успехе, секунд: <input type="number" min="1" max="3600" name="success_delete_seconds" value="{escape(values['success_delete_seconds'])}"></label>
<label>Удаление сообщения об ошибке, секунд: <input type="number" min="1" max="3600" name="failure_delete_seconds" value="{escape(values['failure_delete_seconds'])}"></label>
<button type="submit">Сохранить настройки</button>
</form><p class="muted">Web: {escape(settings.web_host)}:{settings.web_port}; база: {escape(str(settings.database_path))}</p></section>
<section><h2>Проверенные пользователи ({len(users)})</h2>
<form method="post" action="/users/delete"><table><thead><tr><th></th><th>Chat ID</th><th>User ID</th><th>Имя</th><th>Проверен</th></tr></thead><tbody>{rows}</tbody></table>
<p><button class="danger" type="submit" onclick="return confirm('Удалить выбранных пользователей из verified?')">Удалить выбранных</button></p></form></section>
"""
    return web.Response(text=_page(body), content_type="text/html")


async def save_settings(request: web.Request) -> web.Response:
    db: Database = request.app["db"]
    data = await request.post()
    names = ("challenge_timeout_minutes", "mute_hours", "success_delete_seconds", "failure_delete_seconds")
    values: dict[str, str] = {}
    try:
        for name in names:
            value = int(data.get(name, ""))
            if value < 1:
                raise ValueError
            values[name] = str(value)
    except (TypeError, ValueError):
        return web.Response(text=_page("<p>Некорректное значение настройки.</p>"), content_type="text/html", status=400)
    await db.update_bot_settings(values)
    return web.Response(text=_page("<p>Настройки сохранены.</p>"), content_type="text/html")


async def delete_users(request: web.Request) -> web.Response:
    db: Database = request.app["db"]
    data = await request.post()
    selected: list[tuple[int, int]] = []
    for raw in data.getall("users", []):
        try:
            chat_id, user_id = (int(part) for part in raw.split(":", 1))
            selected.append((chat_id, user_id))
        except (TypeError, ValueError):
            logger.warning("Ignoring malformed user selection: %r", raw)
    deleted = await db.delete_verified(selected)
    return web.Response(text=_page(f"Удалено пользователей: {deleted}", show_back_link=True), content_type="text/html")


async def delete_users_page(request: web.Request) -> web.Response:
    raise web.HTTPFound("/")


def create_web_app(db: Database, settings: Settings) -> web.Application:
    app = web.Application()
    app["db"] = db
    app["settings"] = settings
    app.router.add_get("/", index)
    app.router.add_get("/users/delete", delete_users_page)
    app.router.add_post("/settings", save_settings)
    app.router.add_post("/users/delete", delete_users)
    return app
