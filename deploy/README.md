# Деплой VPN-бота на VPS (Docker + Caddy)

Проверено для Ubuntu 22.04 / 24.04. Бот работает в Docker, Caddy ставится нативно
на хост и даёт авто-HTTPS (Let's Encrypt).

## Что нужно заранее
- VPS с Ubuntu (>= 1 vCPU / 1 GB RAM достаточно для MVP).
- Домен бота, например `bot.example.com`, с **A-записью на IP VPS** (до запуска Caddy).
- Доступ к панели Remnawave по публичному HTTPS (бот к ней подключается извне).

## 1. Docker
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# перелогиниться, чтобы права docker применились
```

## 2. Caddy (официальный репозиторий)
```bash
sudo apt-get update -y
sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update -y
sudo apt-get install -y caddy
```

## 3. Код
```bash
sudo mkdir -p /opt/vpn-bot && sudo chown $USER /opt/vpn-bot
git clone https://github.com/bi333on/vpn-bot.git /opt/vpn-bot
cd /opt/vpn-bot
```

## 4. Конфигурация (.env)
```bash
cp .env.example .env
nano .env
```
Обязательно заполнить:
```ini
BOT_TOKEN=123456:ABC...          # токен из @BotFather
ADMIN_IDS=123456789              # ваш Telegram ID

DATABASE_URL=sqlite+aiosqlite:///data/bot.db   # путь внутри контейнера (volume ./data)

POLLING_MODE=false
WEBHOOK_HOST=https://bot.example.com
WEBHOOK_PATH=/telegram
WEBHOOK_SECRET_TOKEN=случайная-длинная-строка  # секрет для вебхука Telegram

REMNAWAVE_API_URL=https://panel.example.com
REMNAWAVE_USERNAME=admin
REMNAWAVE_PASSWORD=пароль
REMNAWAVE_SUB_URL=https://panel.example.com
REMNAWAVE_INBOUND_TAG=          # тег reality-inbound (опционально)

# Платежи (по необходимости)
YOOKASSA_ENABLED=true
YOOKASSA_SHOP_ID=...
YOOKASSA_SECRET_KEY=...
```

## 5. Caddyfile
Добавьте в конец `/etc/caddy/Caddyfile`:
```caddyfile
bot.example.com {
    reverse_proxy localhost:8000
}
```
```bash
sudo caddy fmt --overwrite /etc/caddy/Caddyfile
sudo systemctl reload caddy
```
> Caddy сам получит сертификат. Порт 8000 не публикуем наружу — docker-compose
> мапит его только на `127.0.0.1`, наружу бот виден только через Caddy.

## 6. Запуск
```bash
cd /opt/vpn-bot
docker compose up -d --build
docker compose logs -f   # посмотреть логи
```

## 7. Проверка
```bash
curl -s https://bot.example.com/health          # -> {"status":"ok"}
curl -sI https://bot.example.com/telegram        # -> 200 (если HEAD не проходит, GET)
```
После старта бот сам вызывает `set_webhook` на `https://bot.example.com/telegram`.

## Вебхуки платёжек (зарегистрировать в кабинетах провайдеров)
- ЮKassa: `https://bot.example.com/payments/yookassa`
- CryptoBot: `https://bot.example.com/payments/cryptobot`
- RollyPay: `https://bot.example.com/payments/rollypay`

## Обновление
```bash
cd /opt/vpn-bot
git pull
docker compose up -d --build
```

## Полезное
- Логи: `docker compose logs -f bot`
- Перезапуск: `docker compose restart`
- БД хранится в `./data/bot.db` на хосте (volume). Бэкап — просто копия этого файла.
- Фаервол: открыть только 22/80/443 (`sudo ufw allow 22,80,443/tcp`).

## Возможные проблемы
- **502 от Caddy**: проверьте, что бот слушает в контейнере (`docker compose logs`), а
  в Caddyfile `reverse_proxy localhost:8000` (не `127.0.0.1`).
- **Webhook не приходит**: проверьте `WEBHOOK_HOST` без слэша в конце и что домен
  резолвится на IP VPS; в логах ищите `set_webhook`.
- **Ошибка Remnawave**: сверьте поля API со Swagger панели (`{panel}/docs`) — см.
  `app/remnawave/client.py`.
