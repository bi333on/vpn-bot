# VPN-бот (продажа vless+reality через Remnawave 2.7.x)

Telegram-бот на **Python + aiogram 3** для продажи VPN-подписок VLESS + Reality.
Общается с панелью Remnawave 2.7.x по REST API. Оплата: ЮKassa, CryptoBot (Crypto Pay),
RollyPay — за единым интерфейсом `PaymentProvider`.

## Возможности
- Тарифы с лимитом устройств (`hwidDeviceLimit`), покупка, продление.
- Промокоды (процент/фиксированная скидка), реферальная программа.
- Ручное пополнение баланса (админом), оплата с баланса (частично/полностью).
- Смена лимита устройств без продления (пересчёт в Remnawave).
- Настраиваемый trial (дни + трафик + лимит устройств).
- Выдача `vless://` конфига + QR-кода.
- Админ-панель: статистика, пользователи, тарифы, промокоды, пополнение, лимит устройств, рассылка.
- Планировщик: синхронизация трафика, автоотключение истёкших, уведомления (срок/трафик).

## Запуск (dev, polling)
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env   # заполнить BOT_TOKEN, REMNAWAVE_*, ADMIN_IDS
POLLING_MODE=true python -m app.main
```

## Запуск (webhook + Caddy, прод)
```bash
docker compose up -d --build
```
`.env`: `POLLING_MODE=false`, `WEBHOOK_HOST=https://bot.example.com`.
Caddyfile из `deploy/` → reverse_proxy на `localhost:8000`.

## Верификация Remnawave API
Точные имена полей (`shortUuid`/`uuid`, `accessToken`, `hwidDeviceLimit`,
`usedTrafficBytes`, структура `settings.realitySettings`) сверьте со Swagger панели
(`{panel}/docs`). Клиент — `app/remnawave/client.py`, сборка конфига —
`app/services/config_builder.py`.

## Тесты
```bash
pytest
```
