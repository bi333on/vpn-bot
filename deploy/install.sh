#!/usr/bin/env bash
# Установка VPN-бота на Ubuntu 22.04/24.04 (Docker + Caddy).
#
# Одна команда (минимум — только бот; Remnawave настраивается в админке):
#   DOMAIN=bot.example.com \
#   BOT_TOKEN='...' ADMIN_IDS='...' \
#   DEPLOY=1 bash /tmp/vpn-install.sh
#
# Remnawave-параметры (URL/токен/нода) можно оставить пустыми — они задаются
# из админки бота (/admin -> 🔗 URL, 🔑 API, 🖧 Нода). Env-переменные ниже —
# необязательные фолбэки.
set -euo pipefail

DOMAIN="${DOMAIN:-}"
if [ -z "$DOMAIN" ]; then
  echo "Usage: DOMAIN=bot.example.com ./install.sh" >&2
  exit 1
fi

APP_DIR="/opt/vpn-bot"
ENV_FILE="$APP_DIR/.env"
# Для приватного репозитория можно указать SSH-ссылку:
#   REPO_URL=git@github.com:bi333on/vpn-bot.git
REPO_URL="${REPO_URL:-https://github.com/bi333on/vpn-bot.git}"

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
  git clone "$REPO_URL" "$APP_DIR"
else
  (cd "$APP_DIR" && git pull --ff-only) || true
fi

# --- .env: создать из шаблона, затем перезаписать значения из env ---
[ ! -f "$ENV_FILE" ] && cp "$APP_DIR/.env.example" "$ENV_FILE"

set_env() {
  local key="$1" value="$2"
  grep -v "^${key}=" "$ENV_FILE" > "$ENV_FILE.tmp" || true
  printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE.tmp"
  mv "$ENV_FILE.tmp" "$ENV_FILE"
}

echo "==> [4/6] .env"
set_env "WEBHOOK_HOST" "https://$DOMAIN"
set_env "WEBHOOK_PATH" "/telegram"
set_env "POLLING_MODE" "false"
set_env "DATABASE_URL" "sqlite+aiosqlite:///data/bot.db"

for var in \
  BOT_TOKEN ADMIN_IDS \
  REMNAWAVE_API_URL REMNAWAVE_API_TOKEN REMNAWAVE_NODE_UUID REMNAWAVE_NODE_FIELD \
  REMNAWAVE_SUB_URL REMNAWAVE_USERNAME REMNAWAVE_PASSWORD REMNAWAVE_INBOUND_TAG \
  YOOKASSA_SHOP_ID YOOKASSA_SECRET_KEY CRYPTOBOT_API_TOKEN ROLLYPAY_API_KEY; do
  val="${!var:-}"
  if [ -n "$val" ]; then
    set_env "$var" "$val"
  fi
done

# Секрет вебхука Telegram: генерируем, если не задан.
if [ -n "${WEBHOOK_SECRET_TOKEN:-}" ]; then
  set_env "WEBHOOK_SECRET_TOKEN" "$WEBHOOK_SECRET_TOKEN"
else
  set_env "WEBHOOK_SECRET_TOKEN" "$(openssl rand -hex 24)"
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

echo "==> [6/6] Запуск"
if [ "${DEPLOY:-0}" = "1" ]; then
  cd "$APP_DIR"
  (docker compose up -d --build) || sudo docker compose up -d --build
  echo ""
  echo "    Готово. Проверка: curl -s https://$DOMAIN/health   # {\"status\":\"ok\"}"
else
  echo "    DEPLOY не установлен. Запустите:"
  echo "      cd $APP_DIR && docker compose up -d --build"
fi
