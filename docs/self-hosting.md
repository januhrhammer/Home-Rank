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
     a reverse proxy in front of Home-Rank.

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

## Updating

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

`docker compose down` stops and removes the containers. Your data stays in the Docker volume
`home-rank_db-data` until you also remove it: `docker compose down --volumes` deletes all of
Home-Rank's data for good.
