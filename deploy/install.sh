#!/usr/bin/env bash
# Установка VPN-бота на Ubuntu 22.04/24.04 (Docker + Caddy).
#
# Базовый запуск:
#   DOMAIN=bot.example.com ./deploy/install.sh
#
# Полностью одной командой (секреты через env, сразу запустить бота):
#   DOMAIN=bot.example.com \
#   BOT_TOKEN='...' ADMIN_IDS='...' \
#   REMNAWAVE_API_URL='https://...' REMNAWAVE_USERNAME='...' REMNAWAVE_PASSWORD='...' \
#   DEPLOY=1 ./deploy/install.sh
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
  sudo usermod -aG docker "$USER" || true
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
[ ! -f "$APP_DIR/.env" ] && cp "$APP_DIR/.env.example" "$APP_DIR/.env"

set_env() {
  local key="$1" value="$2"
  if grep -q "^${key}=" "$APP_DIR/.env"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$APP_DIR/.env"
  else
    echo "${key}=${value}" >> "$APP_DIR/.env"
  fi
}

set_env "WEBHOOK_HOST" "https://$DOMAIN"
set_env "WEBHOOK_PATH" "/telegram"
set_env "POLLING_MODE" "false"
set_env "DATABASE_URL" "sqlite+aiosqlite:///data/bot.db"

[ -n "${BOT_TOKEN:-}" ] && set_env "BOT_TOKEN" "$BOT_TOKEN"
[ -n "${ADMIN_IDS:-}" ] && set_env "ADMIN_IDS" "$ADMIN_IDS"
[ -n "${REMNAWAVE_API_URL:-}" ] && set_env "REMNAWAVE_API_URL" "$REMNAWAVE_API_URL"
[ -n "${REMNAWAVE_SUB_URL:-}" ] && set_env "REMNAWAVE_SUB_URL" "$REMNAWAVE_SUB_URL"
[ -n "${REMNAWAVE_USERNAME:-}" ] && set_env "REMNAWAVE_USERNAME" "$REMNAWAVE_USERNAME"
[ -n "${REMNAWAVE_PASSWORD:-}" ] && set_env "REMNAWAVE_PASSWORD" "$REMNAWAVE_PASSWORD"

set_env "WEBHOOK_SECRET_TOKEN" "${WEBHOOK_SECRET_TOKEN:-$(openssl rand -hex 24)}"

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

echo "==> [6/6] Запуск"
if [ "${DEPLOY:-0}" = "1" ]; then
  cd "$APP_DIR"
  (docker compose up -d --build) || sudo docker compose up -d --build
  echo ""
  echo "    Готово. Проверка: curl -s https://$DOMAIN/health   # {\"status\":\"ok\"}"
else
  echo "    Секреты не переданы или DEPLOY не установлен."
  echo "    Запустите: cd $APP_DIR && docker compose up -d --build"
fi
