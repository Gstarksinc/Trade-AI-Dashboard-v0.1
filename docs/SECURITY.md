# Security Architecture & Risk Audit

> **Scope**: Crypto futures paper trading & research only. Strictly zero order execution capabilities and zero exchange private keys.

---

## 1. Network Exposure & Interface Binding Audit

| Service / Container | Container Port | Host Port Binding | Exposure Scope | Security Finding & Recommendation |
| :--- | :---: | :---: | :---: | :--- |
| **`dashboard`** | `3000` | `0.0.0.0:3000` | **Public / LAN** | ⚠️ **Finding**: Accessible from local network interfaces. Recommended to configure `DASHBOARD_BIND=127.0.0.1`. |
| **`api-gateway`** | `8000` | `0.0.0.0:8000` | **Public / LAN** | ⚠️ **Finding**: Accessible from local network interfaces. Recommended to configure `GATEWAY_BIND=127.0.0.1`. |
| **`grafana`** | `3000` | `0.0.0.0:3001` | **Public / LAN** | ⚠️ **Finding**: Accessible from local network interfaces. Protected by admin credentials; recommend `GRAFANA_BIND=127.0.0.1`. |
| **`market-collector`**| `8001` | `127.0.0.1:8001` | **Localhost Only** | Secure (isolated to loopback). |
| **`feature-service`** | `8002` | `127.0.0.1:8002` | **Localhost Only** | Secure (isolated to loopback). |
| **`model-service`** | `8003` | `127.0.0.1:8003` | **Localhost Only** | Secure (isolated to loopback). |
| **`training-service`**| `8004` | `127.0.0.1:8004` | **Localhost Only** | Secure (isolated to loopback). |
| **`risk-service`** | `8005` | `127.0.0.1:8005` | **Localhost Only** | Secure (isolated to loopback). |
| **`signal-service`** | `8006` | `127.0.0.1:8006` | **Localhost Only** | Secure (isolated to loopback). |
| **`paper-exec-service`**| `8007`| `127.0.0.1:8007` | **Localhost Only** | Secure (isolated to loopback). |
| **`notifier-service`**| `8009` | `127.0.0.1:8009` | **Localhost Only** | Secure (isolated to loopback). |
| **`db` (TimescaleDB)**| `5432` | `127.0.0.1:5432` | **Localhost Only** | Secure (isolated to loopback). |
| **`redis`** | `6379` | `127.0.0.1:6379` | **Localhost Only** | Secure (password protected + loopback). |
| **`prometheus`** | `9090` | `127.0.0.1:9090` | **Localhost Only** | Secure (isolated to loopback). |

### Security Finding Report:
In `docker-compose.yml`, `dashboard`, `api-gateway`, and `grafana` bind `0.0.0.0` to permit container-to-container and developer browser access. On untrusted local area networks (LANs), external devices can access the web dashboard or gateway REST API.
- **Proposed Remediation**: Introduce environment variables `GATEWAY_HOST=${GATEWAY_HOST:-127.0.0.1}` and `DASHBOARD_HOST=${DASHBOARD_HOST:-127.0.0.1}` in `docker-compose.yml` defaulting strictly to loopback `127.0.0.1`.

---

## 2. Secrets Management & Credentials

1. **Zero Hardcoded Secrets**: All passwords (`POSTGRES_PASSWORD`, `REDIS_PASSWORD`) are injected via `.env` file.
2. **Git Exclusion**: `.gitignore` strictly excludes `.env`, `backups/`, and credential artifacts.
3. **Internal Network Trust**: Services communicate over the default Docker bridge network (`signals_default`) using internal Docker DNS hostnames (`http://signal-service:8006`, `http://paper-exec-service:8007`).
4. **Redis Authentication**: Redis enforces authentication via `--requirepass ${REDIS_PASSWORD}` across all microservice stream connections.

---

## 3. Cryptographic Verification: Zero Private Keys & No Real Order Execution

To ensure complete adherence to the **Paper Trading Only** scope, automated CI audits enforce that no exchange API secret keys or real execution routes exist in the repository:

### Static Verification Script:
```powershell
# 1. Verify zero Binance API secret keys exist
$secrets = git grep -i "binance.*api.*secret\|api_secret\|secret_key\|private_key" -- ":(exclude)docs/*" ":(exclude).env.example"
if ($secrets) {
    Write-Error "SECURITY VIOLATION: Exchange secret keys detected!"
    exit 1
}

# 2. Verify zero real order execution endpoints exist
$exec = git grep -i "POST /fapi/v1/order\|create_order\|new_order" -- "services/*"
if ($exec) {
    Write-Error "SECURITY VIOLATION: Real order execution code detected!"
    exit 1
}

# 3. Verify Dashboard has zero direct exchange connections
$dash = git grep -i "binance.com" -- "dashboard/app/*"
if ($dash) {
    Write-Error "SECURITY VIOLATION: Dashboard connects directly to exchange!"
    exit 1
}
```

---

## 4. Input Sanitization & Threat Model

- **SQL Injection**: Prevented across all 9 microservices through SQLAlchemy parameterized queries and asyncpg bound parameters. Raw string formatting into SQL queries is prohibited.
- **Cross-Site Scripting (XSS)**: Next.js 14 React framework escapes all rendered string properties by default.
- **Cross-Site Request Forgery (CSRF)**: The gateway is strictly read-only for public clients; state mutations are triggered solely by internal Redis Streams.
- **Denial of Service (DoS)**:
  - Redis Stream consumers limit memory via `maxlen=10000` approximate trimming.
  - SSE price tick streaming is throttled to 1 tick/second per symbol.
  - Ingestion rate-limits are enforced by `RateLimitBudgeter` to prevent Binance IP bans.

