#!/usr/bin/env bash
set -euo pipefail

# Jednorazowa instalacja video-analizier na VPS (Ubuntu/Debian).
#
# Użycie (wklej w terminal VPS-a):
#   curl -fsSL https://raw.githubusercontent.com/3Cement/video-analizier/claude/project-setup-review-ce6l8x/scripts/vps_setup.sh | bash
#
# Z domeną (automatyczny HTTPS; najpierw ustaw rekord DNS A -> IP VPS-a):
#   curl -fsSL https://raw.githubusercontent.com/3Cement/video-analizier/claude/project-setup-review-ce6l8x/scripts/vps_setup.sh | DOMAIN=app.twoja-domena.pl bash

REPO_URL="${REPO_URL:-https://github.com/3Cement/video-analizier.git}"
BRANCH="${BRANCH:-claude/project-setup-review-ce6l8x}"
APP_DIR="${APP_DIR:-$HOME/video-analizier}"

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  SUDO="sudo"
fi

echo "==> Sprawdzam narzędzia…"
if ! command -v git >/dev/null 2>&1; then
  echo "==> Instaluję git…"
  $SUDO apt-get update -y && $SUDO apt-get install -y git
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Instaluję Dockera…"
  curl -fsSL https://get.docker.com | $SUDO sh
fi

if ! $SUDO docker compose version >/dev/null 2>&1; then
  echo "BŁĄD: docker compose v2 niedostępny — zaktualizuj Dockera." >&2
  exit 1
fi

echo "==> Pobieram aplikację (branch: $BRANCH)…"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch origin "$BRANCH"
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
else
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> Utworzyłem .env z domyślnymi ustawieniami."
fi

echo "==> Buduję obrazy i startuję (pierwsze uruchomienie: kilka minut)…"
DOMAIN="${DOMAIN:-}" $SUDO docker compose -f docker-compose.prod.yml up -d --build

echo
echo "================================================================"
echo "  Gotowe!"
if [ -n "${DOMAIN:-}" ]; then
  echo "  UI:   https://$DOMAIN"
  echo "        (rekord DNS A musi wskazywać na IP tego serwera)"
else
  IP="$(curl -fsS --max-time 5 ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
  echo "  UI:   http://$IP"
fi
echo
echo "  Klucz LLM (lepsze podsumowania — opcjonalnie):"
echo "    nano $APP_DIR/.env          # ustaw OPENAI_API_KEY"
echo "    cd $APP_DIR && $SUDO docker compose -f docker-compose.prod.yml up -d"
echo
echo "  Logi:   cd $APP_DIR && $SUDO docker compose -f docker-compose.prod.yml logs -f"
echo "  Status: cd $APP_DIR && $SUDO docker compose -f docker-compose.prod.yml ps"
echo "================================================================"
