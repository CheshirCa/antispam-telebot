# Перенос и запуск без root

Текущая версия проекта указана в файле `VERSION`. Архивы релизов используют формат имени `antispam_telebot-vVERSION.tar.gz`.

Скопируйте каталог проекта в любое место, доступное обычному пользователю, например:

```bash
mkdir -p ~/antispam_telebot
# скопировать файлы проекта в ~/antispam_telebot
cd ~/antispam_telebot
chmod +x install.sh
./install.sh
```

Скрипт запускается не от root. Он создаёт `.venv`, устанавливает зависимости, создаёт `.env` и использует `sudo` только для установки systemd-службы.

После этого укажите токен:

```bash
nano .env
sudo systemctl start antispam-telebot.service
sudo systemctl status antispam-telebot.service
```

Процесс службы работает от пользователя, запустившего `install.sh`, а не от root. База создаётся в `data/antispam.sqlite3`. Для переноса вместе с данными копируйте каталог `data/` и `.env`.

Адрес и порт web-панели задаются параметрами `WEB_HOST` и `WEB_PORT` в `.env`.
