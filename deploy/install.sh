#!/usr/bin/env bash
# Установка VPN-бота на Ubuntu 22.04/24.04 (Docker + Caddy).
# Запуск: DOMAIN=bot.example.com ./deploy/install.sh
set -euo pipefail

DOMAIN="${DOMAIN:-}"
if [ -z "$DOMAIN" ]; then
  echo "Usage: DOMAIN=bot.example.com ./deploy/install.sh" >&2
  exit 1
fi

APP_DIR="/opt/vpn-bot"

echo "==> [1/6] Docker"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
else
  echo "    уже установлен"
fi

echo "==> [2/6] Caddy"
if ! command -v caddy >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
  sudo apt-get update -y
  sudo apt-get install -y caddy
else
  echo "    уже установлен"
fi

echo "==> [3/6] Код"
if [ ! -d "$APP_DIR" ]; then
  sudo mkdir -p "$APP_DIR"
  sudo chown "$USER" "$APP_DIR"
  git clone https://github.com/bi333on/vpn-bot.git "$APP_DIR"
fi

echo "==> [4/6] .env"
if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  echo "    создан $APP_DIR/.env — ЗАПОЛНИТЕ BOT_TOKEN, ADMIN_IDS, REMNAWAVE_*, WEBHOOK_HOST=https://$DOMAIN"
fi

echo "==> [5/6] Caddyfile"
CADDYFILE="/etc/caddy/Caddyfile"
if ! grep -q "$DOMAIN" "$CADDYFILE" 2>/dev/null; then
  {
    echo ""
    echo "$DOMAIN {"
    echo "    reverse_proxy localhost:8000"
    echo "}"
  } | sudo tee -a "$CADDYFILE" >/dev/null
  sudo caddy fmt --overwrite "$CADDYFILE"
  sudo systemctl reload caddy
  echo "    добавлен блок для $DOMAIN"
else
  echo "    блок для $DOMAIN уже есть"
fi

echo "==> [6/6] Готово"
echo "Теперь:"
echo "  1. nano $APP_DIR/.env   # заполнить токены/креды"
echo "  2. cd $APP_DIR && docker compose up -d --build"
echo "  3. curl -s https://$DOMAIN/health   # ожидаем {\"status\":\"ok\"}"
