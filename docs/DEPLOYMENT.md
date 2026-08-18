# VPS deployment

The production stack is designed for the existing VPS at `69.62.77.202` and follows its `/opt/<service>` convention. It runs two containers:

- `app` — FastAPI, the compiled React application, SQLite, workbook ingestion, and exports
- `caddy` — the only publicly exposed service; terminates HTTPS and proxies to `app` over the private Compose network

The application container runs as an unprivileged user, has a read-only root filesystem, and uses one Uvicorn worker. One worker is intentional: SQLite and workbook refresh are safe for this deployment shape, while multiple web workers would duplicate startup/import work and introduce competing SQLite writers.

## Server readiness

Verified on 18 August 2026:

| Check | Result |
| --- | --- |
| Operating system | Ubuntu 24.04, x86_64 |
| Capacity | 8 CPUs, 31 GiB RAM, 332 GiB free disk |
| Container runtime | Docker 29.5.3, Compose 5.1.4 |
| Host security | Key-only SSH, UFW, fail2ban, unattended upgrades |
| Deployment user | `aswin`, passwordless sudo, member of the Docker group |
| Secret tooling | BWS CLI and `jq` installed; exactly one `Openrouter API Key` entry found |
| Port conflicts | Nothing currently listening on TCP 80 or 443 |
| Public web access | Not enabled yet: UFW does not allow 80/443 |

The server has ample capacity for this application. Before it is publicly reachable, point a DNS name to `69.62.77.202` and allow TCP ports 80 and 443 through UFW. UDP 443 is optional but enables HTTP/3. No existing service needs to be moved.

There is no swap configured, but the host had approximately 28 GiB available during inspection, so this is not a launch blocker. The host also has two long-running unnamed `sec-edgar-mcp` containers; they are unrelated to Synergy but should eventually be named or documented for operational clarity.

## Files and persistent state

The checkout lives at `/opt/synergy-poc`:

```text
/opt/synergy-poc/
├── .env.production       # mode 0600, generated on the VPS
├── input/
│   ├── learning.xlsx     # environment-specific, read-only in the container
│   └── headcount.xlsx    # environment-specific, read-only in the container
└── data/
    ├── learning_chat.db  # users, chats, imported analytics, and export metadata
    ├── exports/          # generated CSV/XLSX downloads
    └── backups/          # rolling local SQLite backups
```

The environment file, workbooks, database, exports, and backups are excluded from Git. Preserve `data/` across deployments. Replacing a workbook causes the application to refresh its analytics tables at startup while retaining users and chat history.

## One-time DNS and server setup

Create an `A` record for the chosen hostname pointing to `69.62.77.202`. If the DNS provider supports proxying, leave it DNS-only until Caddy has obtained the first certificate.

Open a second SSH session before changing firewall rules, keep the first session connected, and then run:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw status numbered
```

Prepare the checkout as the `aswin` user:

```bash
sudo install -d -o aswin -g aswin /opt/synergy-poc
git clone https://github.com/aswinkp/synergy-poc.git /opt/synergy-poc
cd /opt/synergy-poc
mkdir -p input data
sudo chown -R aswin:10001 data
sudo chmod -R u+rwX,g+rwX,o-rwx data
```

If `/opt/synergy-poc` already exists and is empty, clone with `git clone ... .` from inside it instead. If the repository is private, configure a read-only deploy key before cloning.

Copy the two environment-specific workbooks from the local machine:

```bash
scp Learning_Overall_Report_120820261822.xlsx aswin@69.62.77.202:/opt/synergy-poc/input/learning.xlsx
scp 'AsonHeadCount (3).xlsx' aswin@69.62.77.202:/opt/synergy-poc/input/headcount.xlsx
```

Generate the production environment on the VPS. This reads the OpenRouter key from BWS and generates a distinct authentication signing secret without printing either value:

```bash
cd /opt/synergy-poc
./deploy/configure-env.sh synergy.example.com
```

Replace `synergy.example.com` with the real hostname. The script deliberately refuses to overwrite an existing `.env.production` file.

## First deployment

Once DNS resolves to the VPS and the workbook files are present:

```bash
cd /opt/synergy-poc
./deploy/deploy.sh
```

The deployment script backs up an existing SQLite database, fast-forwards `main`, builds the image, starts the stack, waits for application health, and prints container state. A running app uses SQLite's online backup API inside the container; a stopped app uses the host's Python runtime. Caddy obtains and renews the TLS certificate automatically.

Create the first production user if the production database does not already contain one:

```bash
./deploy/provision-user.sh add \
  --email admin@chillsoft.io \
  --name "Chillsoft Admin"
```

The command prompts for the password, so it does not enter shell history. To move unassigned historical chats into this account on a migrated database, add `--claim-existing-chats` when creating the user.

Verify externally:

```bash
curl --fail --show-error https://synergy.example.com/healthz
```

Expected response:

```json
{"status":"ok"}
```

Then sign in through the browser, open an existing chat, ask a cross-workbook question, render a chart, and request one CSV or Excel export.

## Automated backups

Install the included daily systemd timer:

```bash
cd /opt/synergy-poc
sudo cp deploy/systemd/synergy-backup.service /etc/systemd/system/
sudo cp deploy/systemd/synergy-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now synergy-backup.timer
systemctl list-timers synergy-backup.timer
```

The timer uses SQLite's online backup API at 02:30 UTC daily and retains local backups for 14 days. Run one immediately with:

```bash
./deploy/backup.sh
```

Local backups protect against application mistakes, not total VPS loss. Add provider snapshots or copy `data/backups/` to encrypted off-server storage before treating the service as production-critical.

## Routine deployment and diagnostics

Deploy the latest `main`:

```bash
cd /opt/synergy-poc
./deploy/deploy.sh
```

Inspect status and recent logs:

```bash
docker compose --env-file .env.production -f compose.production.yml ps
docker compose --env-file .env.production -f compose.production.yml logs --tail 200 app caddy
```

Restart without rebuilding:

```bash
docker compose --env-file .env.production -f compose.production.yml restart app
```

To roll back code, check out a known-good commit in `/opt/synergy-poc`, set `APP_VERSION` to its short commit ID, and rebuild/start the stack:

```bash
git checkout <known-good-commit>
export APP_VERSION="$(git rev-parse --short HEAD)"
docker compose --env-file .env.production -f compose.production.yml build
docker compose --env-file .env.production -f compose.production.yml up -d
```

If the database must also be restored, stop the application first, copy the selected backup over `data/learning_chat.db`, preserve the `aswin:10001` ownership and group-write permissions, and start the stack again. Take a copy of the failed database before replacing it.

## Scaling boundary

This design is appropriate for one VPS and low-to-moderate concurrent internal usage. Do not increase the Uvicorn worker count or run multiple app replicas while SQLite is the system of record. Move application state to PostgreSQL and exports/workbooks to shared object storage before horizontal scaling.
