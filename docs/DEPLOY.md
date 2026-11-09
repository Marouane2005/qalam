# Deploying Qalam

This guide covers a first-time host setup, the GitHub Actions deploy workflow,
backups, and running behind a platform HTTPS proxy.

## Secrets for GitHub Actions

Configure these repository secrets before using `.github/workflows/deploy.yml`:

| Secret | Purpose |
| --- | --- |
| `DEPLOY_HOST` | SSH hostname or IP of the VM |
| `DEPLOY_USER` | SSH user |
| `DEPLOY_SSH_KEY` | Private key for that user |
| `DEPLOY_KNOWN_HOSTS` | Output of `ssh-keyscan` for the host |
| `DEPLOY_PATH` | Absolute path to the git checkout on the VM |

The workflow deploys on `workflow_dispatch` (input: `ref`) and on `v*` tags.
It waits for CI (`api`, `web`, `docker`) to succeed on the target SHA, then
SSHs in, checks out that SHA, runs `docker compose up -d --build`, polls
`http://127.0.0.1/health`, and rolls back to the previously deployed SHA on
failure. The current SHA is stored in `$DEPLOY_PATH/.deploy/current_sha`.

## First-time VM setup

1. Install Docker Engine and the Compose plugin.
2. Clone the repository to the path you will store in `DEPLOY_PATH`:

   ```sh
   git clone https://github.com/Marouane2005/qalam.git /opt/qalam
   cd /opt/qalam
   ```

3. Copy the env file and set strong values:

   ```sh
   cp .env.example .env
   ```

   Set at least:

   - `POSTGRES_PASSWORD` — long random string
   - `QALAM_BOOTSTRAP_API_KEY` — long random string (this is the admin API key)
   - `QALAM_CORS_ORIGINS` — the public origin browsers will use
   - `QALAM_SITE_ADDRESS` — see below
   - `ACME_EMAIL` — only needed when Caddy terminates TLS itself

4. Point a DNS name at the VM’s public IP with **no CDN / proxy** in front when
   Caddy should obtain certificates itself (for example a DuckDNS A record
   straight to the VM). Open ports **80** and **443** to the world in that case.

5. Start the stack:

   ```sh
   docker compose up -d --build
   ```

6. Confirm health:

   ```sh
   curl -fsS http://127.0.0.1/health
   ```

### Low-memory VMs (2 GB RAM or less)

Prefer the built-in hash embedder and a single worker process:

```env
QALAM_EMBEDDING_BACKEND=hash
```

And in `docker-compose.yml` (or an override), set the worker command concurrency
to `1`:

```yaml
command: ["celery", "-A", "qalam.worker:celery_app", "worker", "--loglevel=INFO", "--concurrency=1"]
```

## Behind a platform HTTPS proxy

Some hosts terminate TLS for you and forward plain HTTP to one published
container port. In that case Caddy should **not** request certificates.

1. Set `QALAM_SITE_ADDRESS=:80` so Caddy listens for plain HTTP on port 80
   (this is already the default in `.env.example` and compose).
2. Publish **only** Caddy’s HTTP port through the platform (container port 80).
   Compose also maps 443 for direct-TLS setups; that mapping can stay unused
   when the platform terminates HTTPS for you.
3. Set `QALAM_CORS_ORIGINS` to the platform’s public HTTPS URL, for example
   `https://my-app.example-host.com`.
4. Keep provider keys and `QALAM_BOOTSTRAP_API_KEY` in `.env` on the VM; do not
   commit them.

The bundled `deploy/Caddyfile` already supports this: when
`QALAM_SITE_ADDRESS` is `:80`, Caddy serves HTTP without ACME. `/health` and
`/v1/*` still proxy to the API.

## Cron: backups and DNS IP refresh

Install the backup script on a daily schedule (adjust the project path):

```cron
15 3 * * * cd /opt/qalam && /opt/qalam/scripts/backup.sh >> /var/log/qalam-backup.log 2>&1
```

Backups land in `/var/backups/qalam/<stamp>/` (`qalam.dump` + `uploads.tar.gz`)
and are pruned after 14 days. Restore with:

```sh
/opt/qalam/scripts/restore.sh /var/backups/qalam/<stamp>
```

If you use a dynamic DNS provider, refresh the A record every five minutes,
for example:

```cron
*/5 * * * * curl -fsS "https://www.duckdns.org/update?domains=<YOUR_SUBDOMAIN>&token=<DUCKDNS_TOKEN>&ip=" >/dev/null
```

Replace the placeholders; never commit the token.

## Manual deploy

```sh
cd /opt/qalam
git fetch --tags origin
git checkout --detach <sha>
docker compose up -d --build
curl -fsS http://127.0.0.1/health
```
