#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -eq 0 ]; then
    echo "Запускайте install.sh от обычного пользователя, sudo будет вызван автоматически."
    exit 1
fi

APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
APP_USER="$(id -un)"
SERVICE_NAME="antispam-telebot.service"
SERVICE_TMP="$(mktemp)"
trap 'rm -f "$SERVICE_TMP"' EXIT

echo "Создаю виртуальное окружение..."
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    echo "Создан $APP_DIR/.env — укажите в нём BOT_TOKEN."
fi
mkdir -p "$APP_DIR/data"

sed \
    -e "s|__APP_USER__|$APP_USER|g" \
    -e "s|__APP_DIR__|$APP_DIR|g" \
    "$APP_DIR/antispam-telebot.service.in" > "$SERVICE_TMP"

sudo install -m 0644 "$SERVICE_TMP" "/etc/systemd/system/$SERVICE_NAME"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
echo "Установка завершена. Запустите сервис после заполнения .env:"
echo "  sudo systemctl start $SERVICE_NAME"
