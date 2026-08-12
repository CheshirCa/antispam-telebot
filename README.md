# Telegram Anti-Spam Bot / Telegram-бот против спама

**Version / Версия:** `0.1.3`

## Русский

### Возможности

- Проверяет нового пользователя при первой попытке написать сообщение в группе.
- Проверяет также сообщения, отправленные от имени группы, если Telegram передаёт реального отправителя.
- Администраторы и владелец группы не проверяются.
- Одноразовая проверка хранится отдельно для каждой группы.
- Задание содержит сложение, вычитание или умножение с результатом от 0 до 20.
- Ответ принимается словом на русском или английском языке; цифры не принимаются.
- При правильном ответе пользователь добавляется в `verified`.
- При неправильном ответе сообщение удаляется, а пользователь блокируется на настроенное время.
- Задания истекают через настроенное время.
- В группах с комментариями к постам вопрос отправляется ответом в ту же ветку комментариев.
- Web-панель доступна только владельцу сервера и позволяет менять настройки и удалять выбранных пользователей.
- Администраторы групп управляют пользователями через личный чат с ботом.

### Требования

- Linux с systemd (Debian/Ubuntu подходят).
- Python 3.12 или новее.
- Telegram-бот, созданный через `@BotFather`.
- Бот добавлен в группу администратором с правами удаления сообщений и ограничения пользователей.

### Установка без root

Проект должен находиться в каталоге обычного пользователя, например `~/antispam_telebot`. Не оставляйте его в `/root`, если бот будет работать не от root.

```bash
cd ~/antispam_telebot
chmod +x install.sh
./install.sh
cp .env.example .env       # install.sh делает это автоматически, если файла нет
nano .env
```

Укажите токен:

```env
BOT_TOKEN=123456:your-token
DATABASE_PATH=data/antispam.sqlite3
LOG_LEVEL=INFO
WEB_HOST=127.0.0.1
WEB_PORT=9992
```

`install.sh` запускается обычным пользователем. Он создаёт `.venv`, устанавливает зависимости и использует `sudo` только для установки systemd-службы.

Запуск и управление:

```bash
sudo systemctl start antispam-telebot.service
sudo systemctl status antispam-telebot.service
sudo journalctl -u antispam-telebot.service -f
sudo systemctl restart antispam-telebot.service
sudo systemctl stop antispam-telebot.service
```

Ручной запуск для проверки:

```bash
.venv/bin/python main.py
```

### Настройка Telegram

1. В `@BotFather` создайте бота и скопируйте токен в `.env`.
2. Добавьте бота администратором в каждую защищаемую группу.
3. Выдайте права на удаление сообщений и ограничение участников.
4. После первого обычного сообщения группы она появится в списке `/groups`.
5. Администратор должен открыть личный чат с ботом и выполнить `/start`.

В группе, связанной с каналом, пользователь должен писать комментарий непосредственно под постом. Бот отвечает на исходный комментарий в той же ветке, поэтому вопрос отображается в контексте этого поста.

### Команды администратора

Команды управления выполняются только в личном чате с ботом, поэтому списки пользователей не попадают в общую группу:

```text
/start       открыть панель управления
/help        показать справку
/groups      показать доступные группы
/select 1    выбрать группу номер 1
/users       показать зарегистрированных пользователей
/del 3       удалить пользователя номер 3
```

Перед каждой операцией бот заново проверяет, что администратор всё ещё имеет права в выбранной группе.

### Web-панель

Web-панель предназначена владельцу сервера. Её адрес и порт задаются через `WEB_HOST` и `WEB_PORT` в `.env`. Она позволяет:

- менять время проверки;
- менять длительность mute;
- менять время автоматического удаления уведомлений;
- просматривать пользователей с `chat_id`, `user_id` и именем;
- удалять выбранных пользователей из `verified`.

Не публикуйте порт панели во внешний интернет без аутентификации и firewall-ограничений.

### Перенос данных

Для переноса проекта скопируйте каталог вместе с `.env` и `data/antispam.sqlite3`. `.venv` переносить не требуется — запустите `install.sh` на новом сервере.

### Структура

```text
main.py                         запуск polling и web-панели
app/                            исходный код
requirements.txt                Python-зависимости
.env.example                    пример конфигурации
antispam-telebot.service.in     шаблон systemd-службы
install.sh                      установка от обычного пользователя
```

## English

### Features

- Checks a user on the first attempt to send a message in a group.
- Group administrators and the owner are ignored.
- Verification is stored independently for each group.
- Challenges use addition, subtraction, or multiplication with a result from 0 to 20.
- Answers must be written as Russian or English words; digits are rejected.
- A correct answer adds the user to `verified`.
- A wrong answer deletes the message and mutes the user for the configured period.
- Challenges expire after the configured timeout.
- In channel-linked discussion groups, challenges are sent as replies in the same comment thread.
- Messages sent on behalf of a group are checked when Telegram provides the actual sender.
- The private web panel manages settings and selected verified users.
- Group administrators manage users through the bot's private chat.

### Requirements

- Linux with systemd (Debian/Ubuntu are suitable).
- Python 3.12+.
- A Telegram bot created with `@BotFather`.
- The bot must be an administrator with message deletion and user restriction permissions.

### Non-root installation

Place the project in a normal user's directory, for example `~/antispam_telebot`. Do not keep it under `/root` when the service must run as a non-root user.

```bash
cd ~/antispam_telebot
chmod +x install.sh
./install.sh
nano .env
```

Set `BOT_TOKEN` in `.env`. The installer creates the virtual environment, installs dependencies, and uses `sudo` only to register the systemd service. The bot process itself runs as the installing user.

```bash
sudo systemctl start antispam-telebot.service
sudo systemctl status antispam-telebot.service
sudo journalctl -u antispam-telebot.service -f
sudo systemctl restart antispam-telebot.service
```

### Telegram setup

1. Create the bot with `@BotFather` and put the token in `.env`.
2. Add the bot as an administrator to every protected group.
3. Grant message deletion and member restriction permissions.
4. Send one normal message in a group so it becomes known to the bot.
5. Each administrator must open the bot privately and run `/start`.

### Private administrator commands

```text
/start       open the control panel
/help        show help
/groups      list available groups
/select 1    select group number 1
/users       list registered users
/del 3       remove user number 3
```

Commands are handled in private chat, and the bot re-checks administrator rights before every operation.

### Web panel and data

The owner-only web panel is configured with `WEB_HOST` and `WEB_PORT` in `.env`. Use a local address for access only from the server, or set the required LAN address when access from an internal network is needed. Restrict access with a firewall before exposing it beyond the server network. Keep `.env` and `data/antispam.sqlite3` when migrating data; recreate `.venv` with `install.sh`.
