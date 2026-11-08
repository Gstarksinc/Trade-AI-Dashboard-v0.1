# Debian setup guide

Target: Debian 12 (bookworm) or 13 (trixie), Docker Compose. Hardware: 2 vCPU / 4 GB RAM / 40 GB SSD is enough for 5 coins; 8 vCPU / 32 GB / 500 GB NVMe suits 30-50 coins with frequent retraining. No GPU is needed.

Work as a normal sudo user (`signals`), not root. On a minimal install run `apt install sudo` as root first.

## 1. Base OS

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y curl git ca-certificates gnupg ufw fail2ban chrony unattended-upgrades htop ncdu jq make nano
sudo adduser signals && sudo usermod -aG sudo signals      # from root, once
```

Copy your SSH key (`ssh-copy-id signals@SERVER_IP`), then disable root and password login. Test a second session before closing the first.

```bash
sudo tee /etc/ssh/sshd_config.d/10-hardening.conf <<EOT
PermitRootLogin no
PasswordAuthentication no
EOT
sudo systemctl reload ssh
```

Firewall, time and kernel settings:

```bash
sudo ufw default deny incoming && sudo ufw default allow outgoing
sudo ufw allow 22/tcp && sudo ufw enable

sudo timedatectl set-timezone UTC
sudo systemctl enable --now chrony fail2ban

sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

sudo tee /etc/sysctl.d/99-signals.conf <<EOT
vm.swappiness=10
vm.overcommit_memory=1
EOT
sudo sysctl --system
sudo dpkg-reconfigure -plow unattended-upgrades
```

Docker publishes ports through its own iptables rules, which bypass ufw. That is why every published port in `docker-compose.yml` is bound to `127.0.0.1`. Never publish PostgreSQL or Redis on `0.0.0.0`.

## 2. Verify Binance access first

```bash
curl -s -o /dev/null -w '%{http_code}' https://fapi.binance.com/fapi/v1/ping; echo
curl -s -o /dev/null -w '%{http_code}' https://data.binance.vision/; echo
```

Expect `200`. `451` or `403` means the region or provider is blocked: choose another before continuing. No API key is needed for public data.

## 3. Install Docker Engine and Compose

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources <<EOT
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: $(. /etc/os-release && echo $VERSION_CODENAME)
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOT
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker signals
```

Log out and back in (group changes apply to new logins), then check `groups` shows `docker` and `docker run --rm hello-world` works. Never use `sudo docker compose`; it creates root-owned files and volumes.

## 4. Get the code and configure

```bash
sudo mkdir -p /opt/signals && sudo chown signals:signals /opt/signals
git clone https://github.com/Gstarksinc/Trade-AI-Dashboard-v0.1.git /opt/signals
cd /opt/signals
bash scripts/gen_env.sh
nano .env
```

Fill in `COINGECKO_API_KEY` (free Demo key, sent as the `x-cg-demo-api-key` header) and the Telegram values (below). Start small: `UNIVERSE_SIZE=5` to `30` and `SIM_MAX_LEVERAGE=3`.

## 5. Start and verify

```bash
docker compose build
docker compose up -d
docker compose ps
curl -s http://127.0.0.1:8000/health | jq .
docker compose exec db psql -U signals -d signals -c 'SELECT hypertable_name FROM timescaledb_information.hypertables;'
source .env && docker compose exec redis redis-cli -a $REDIS_PASSWORD ping
```

Expected: `ok` for api, db and redis; six hypertables (candles, funding_rates, open_interest, long_short_ratio, taker_volume, liquidations); `PONG` from Redis.

The scripts in `db/init/` run only when the database volume is empty (first start). To change the schema later, apply SQL manually with `psql` or write a migration.

Start the dashboard:

```bash
docker compose --profile full up -d --build dashboard
```

Do not run the whole `full` profile until the collector and notifier modules exist: they would restart in a loop with `No module named collector`.

## 6. Telegram bot

1. Open **@BotFather** in Telegram, send `/newbot`, copy the token into `TELEGRAM_BOT_TOKEN`.
2. Send any message to the new bot.
3. Read the chat ID: `curl -s 'https://api.telegram.org/botYOUR_TOKEN/getUpdates' | jq '.result[0].message.chat.id'` and put it in `TELEGRAM_CHAT_ID`.
4. Test: `curl -s 'https://api.telegram.org/botYOUR_TOKEN/sendMessage' -d chat_id=YOUR_CHAT_ID -d text=online`

## 7. Backups

```bash
chmod +x scripts/backup.sh
crontab -e     # add: 0 2 * * * /opt/signals/scripts/backup.sh >> /opt/signals/logs/backup.log 2>&1
```

Copy the dumps off the machine (rsync, rclone, object storage). To restore a TimescaleDB dump use Timescale's documented procedure (`timescaledb_pre_restore()` before `pg_restore`, `timescaledb_post_restore()` after) into a fresh database.

## 8. Remote access to the dashboard

The dashboard and API listen on `127.0.0.1` only. Use an SSH tunnel (`ssh -L 3000:127.0.0.1:3000 -L 8000:127.0.0.1:8000 signals@SERVER_IP`), a private VPN such as Tailscale or WireGuard, or a reverse proxy with HTTPS and authentication. Never expose the dashboard without authentication.

## 9. Operations

| Task | Command |
|---|---|
| Status | `docker compose ps` |
| Logs | `docker compose logs -f --tail=100 api` |
| Restart | `docker compose restart api` |
| Rebuild after a code change | `docker compose up -d --build api` |
| SQL shell | `docker compose exec db psql -U signals -d signals` |
| Stop (keeps data) | `docker compose down` |

`docker compose down -v` deletes the database and Redis volumes. Use `-v` only to wipe everything on purpose.

## 10. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `invalid option name` / `pipefail` when running a script | Windows line endings. Run `sed -i 's/\r$//' file`. |
| `permission denied ... docker.sock` | User not in the `docker` group or session not refreshed. `sudo usermod -aG docker signals`, log out and in. |
| `no configuration file provided: not found` | File name typo; it must be `docker-compose.yml`. `-f` goes before the subcommand: `docker compose -f file build`. |
| `unknown instruction` on Dockerfile line 1 | Prose pasted into the file. Delete the first line. |
| `npm ci` fails in the dashboard build | No `package-lock.json`. The dashboard Dockerfile uses `npm install` for this reason. |
| Containers restart in a loop under `--profile full` | Collector/notifier code not written yet. Start only `dashboard`. |
| HTTP 451/403 from Binance | Region or provider blocked. |
| HTTP 429/418 from Binance | Rate limit or IP ban. Back off, batch downloads, prefer websockets. |
| Error -1021 (timestamp) | Clock drift. Check `chronyc tracking`. |
| Schema missing after first start | Init scripts run on an empty volume only. Apply the SQL manually. |
| Files owned by root inside `/opt/signals` | `sudo chown -R signals:signals /opt/signals`. |
