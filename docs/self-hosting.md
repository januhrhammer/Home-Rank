# Self-hosting

Home-Rank runs on your own machine with Docker Compose, in three containers: the website, a
worker for background jobs, and PostgreSQL.

> Home-Rank is in early development. You can install it and log in, but there is nothing to do
> yet.

## Requirements

- [Docker Engine](https://docs.docker.com/engine/install/) with the Compose plugin:
  `docker compose version` must work.
- git, to download Home-Rank. There are no published images yet, so Compose builds one from the
  source code.
- About 2 GB of disk for the images, plus your data, and about 250 MB of memory. Engine analysis
  and reference databases will need more once they arrive.

Tested on x86-64 Linux.

## Installation

1. Download Home-Rank:

   ```sh
   git clone https://github.com/januhrhammer/Home-Rank.git
   cd Home-Rank
   ```

2. Create your settings file and open it in an editor:

   ```sh
   cp .env.example .env
   ```

   Fill in the four required values at the top:

   - `SECRET_KEY`: the output of `openssl rand -hex 32`.
   - `POSTGRES_PASSWORD`: the output of `openssl rand -hex 24`.
   - `ALLOWED_HOSTS`: the address you will type into the browser, without `http://` and port,
     e.g. `192.168.1.20` or `homeserver.local`.
   - `HTTPS`: `false` to reach Home-Rank over plain `http://` on your local network. HTTPS needs
     a reverse proxy in front of Home-Rank, see
     [HTTPS with a reverse proxy](#https-with-a-reverse-proxy).

3. Start Home-Rank:

   ```sh
   docker compose up -d
   ```

   The first start builds the image, which takes a few minutes. Afterwards `docker compose ps`
   shows all three containers as `healthy`.

4. Create your account:

   ```sh
   docker compose exec web python manage.py createsuperuser
   ```

   Passwords need at least 15 characters. There is no public sign-up: this first account is the
   administrator, who can add further users in the admin area at `/admin/`.

5. Open `http://<your ALLOWED_HOSTS value>:8000` and log in.

## Configuration

All settings live in `.env`, and `.env.example` explains each of them. After changing `.env`,
run `docker compose up -d` again: Compose recreates the containers whose settings changed.

The containers restart by themselves after a crash, and after a reboot if Docker starts at boot
(on most Linux systems: `sudo systemctl enable docker`).

To read the logs: `docker compose logs --follow web worker`. They are JSON by default, for log
collectors; set `LOG_FORMAT=console` in `.env` for lines that are easier to read.

Uploaded PGN files can be up to 200 MB, about 70,000 games with clock comments. Change the limit
with `IMPORT_MAX_MB` in `.env`; a reverse proxy in front of Home-Rank must allow uploads that
large too. Uploads wait in the Docker volume `home-rank_data` until the worker has imported them,
and are deleted afterwards.

### Changing the database password

PostgreSQL stores its password when it creates the database, on the very first start. Changing
`POSTGRES_PASSWORD` in `.env` alone therefore locks Home-Rank out of its database. Change it in
the database first:

```sh
docker compose exec db psql --username=homerank --command="ALTER USER homerank PASSWORD 'the-new-password'"
```

Then put the same password into `.env` and run `docker compose up -d`. If you changed `.env`
first and Home-Rank no longer starts, run the `psql` command above with the new password, then
`docker compose up -d` again.

## HTTPS with a reverse proxy

To reach Home-Rank over HTTPS, for example from the internet, put a reverse proxy in front of it.
The proxy holds the certificate and passes requests on to Home-Rank. Set these in `.env`, with
your own domain:

```sh
ALLOWED_HOSTS=chess.example.org
HTTPS=true
TRUST_PROXY_HEADERS=true
HOMERANK_PORT=127.0.0.1:8000
```

`TRUST_PROXY_HEADERS` lets Home-Rank believe what the proxy reports about each request: that it
came in over HTTPS, and from which address. `HOMERANK_PORT=127.0.0.1:8000` makes sure only the
proxy can report anything: Home-Rank is then reachable only from the machine itself, so nobody
can bypass the proxy and fake those reports. Don't rely on a firewall for this: Docker opens
published ports past firewalls such as ufw.

Any proxy works if it

- passes on the `Host` header the browser sent,
- sets `X-Forwarded-Proto` to `https`,
- adds the visitor's address to the end of `X-Forwarded-For`.

The examples below do all three; each was tested with a login through it.

Home-Rank expects exactly one proxy in front of it. If another one sits in front of yours, such as
Cloudflare, Home-Rank sees that one's address for every visitor, and its lockout after 10 failed
logins then blocks all visitors together.

### Caddy

Caddy gets a certificate from Let's Encrypt by itself. In its `Caddyfile`:

```caddy
chess.example.org {
	reverse_proxy 127.0.0.1:8000
}
```

### nginx

The certificate paths are where certbot puts them; change them for other certificates.

```nginx
server {
    listen 443 ssl;
    server_name chess.example.org;
    ssl_certificate     /etc/letsencrypt/live/chess.example.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/chess.example.org/privkey.pem;

    # nginx accepts uploads of 1 MB by default; allow PGN files up to IMPORT_MAX_MB.
    client_max_body_size 200m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Without the `Host` line, Home-Rank answers every request with "Bad Request (400)". Without
`X-Forwarded-Proto`, the browser reports too many redirects. Without `client_max_body_size`,
uploading a PGN file larger than 1 MB fails with "413 Request Entity Too Large". Caddy and Traefik
don't limit uploads by default.

### Traefik

When Traefik runs in Docker, it finds Home-Rank through labels. Create `compose.override.yaml`
next to `compose.yaml`; Compose merges it in by itself:

```yaml
services:
  web:
    ports: !reset []
    networks: [default, proxy]
    labels:
      traefik.enable: "true"
      traefik.docker.network: proxy
      traefik.http.routers.homerank.rule: Host(`chess.example.org`)
      traefik.http.routers.homerank.entrypoints: websecure
      traefik.http.routers.homerank.tls.certresolver: letsencrypt
      traefik.http.services.homerank.loadbalancer.server.port: "8000"

networks:
  proxy:
    external: true
```

`proxy` is the Docker network Traefik is in, and `websecure` and `letsencrypt` are the entry
point and certificate resolver from your Traefik configuration: use your names. `ports: !reset []`
removes Home-Rank's published port, so it is reachable only through Traefik and `HOMERANK_PORT`
doesn't matter.

## Backup and restore

All of Home-Rank's data lives in its database. (The `home-rank_data` volume only holds uploads
that haven't been imported yet.) To back it up into one file:

```sh
docker compose exec -T db pg_dump --username=homerank --format=custom homerank > home-rank-$(date +%F).dump
```

Keep the backup somewhere other than this machine, together with a copy of `.env`: without the
same `SECRET_KEY`, everyone has to log in again.

To restore a backup, stop Home-Rank, replace the database's contents, and start it again:

```sh
docker compose stop web worker
docker compose exec -T db pg_restore --username=homerank --dbname=homerank --clean --if-exists < home-rank-2026-10-22.dump
docker compose up -d
```

This replaces everything, including what was added after the backup. On a new machine, install
Home-Rank with the saved `.env`, start only the database with `docker compose up -d db`, then run
the last two commands. Restore with the same version of Home-Rank as the backup, or a newer one:
the website updates an older database when it starts.

## Updating

[Back up](#backup-and-restore) first, then:

```sh
git pull                      # the new version of Home-Rank
docker compose pull           # the newest PostgreSQL 18 release
docker compose build --pull   # rebuild Home-Rank, with updates to its base images
docker compose up -d          # restart what changed
```

When the website starts, it updates the database to the new version before it accepts requests,
and the worker waits until it has. Each update leaves the previous image behind;
`docker image prune` removes such leftovers.

## Uninstalling

`docker compose down` stops and removes the containers. Your data stays in the Docker volumes
`home-rank_db-data` and `home-rank_data` until you also remove them: `docker compose down
--volumes` deletes all of Home-Rank's data for good.
