#!/usr/bin/env bash
# Creates .env from .env.example with random database and Redis passwords.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -e .env ]; then echo '.env already exists; not overwriting'; exit 1; fi
PG=$(openssl rand -hex 24)
RD=$(openssl rand -hex 24)
sed -e "s/__PG__/$PG/g" -e "s/__REDIS__/$RD/g" .env.example > .env
chmod 600 .env
echo '.env created (mode 600). Add your CoinGecko key and Telegram values.'
