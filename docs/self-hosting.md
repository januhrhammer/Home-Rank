# Self-hosting

Home-Rank runs on your own machine with Docker Compose, in three containers: the website, a
worker for background jobs, and PostgreSQL.

## Requirements

- [Docker Engine](https://docs.docker.com/engine/install/) with the Compose plugin:
  `docker compose version` must work.
- About 2 GB of disk for the images, plus your data, and about 250 MB of memory, plus about
  300 MB while a game is analysed ([Engine analysis](#engine-analysis)), and about 55 MB per
  website worker once someone plays against Maia ([Bots](#bots)). Reference databases need
  more: about 1 GB per million games ([Reference databases](#reference-databases)). The image
  includes Stockfish, the chess engine, with its source code (it is GPL-licensed), and Maia, the
  model behind the human-like bot (AGPL); `/usr/share/doc/stockfish` and `/usr/share/doc/maia`
  in the image say where they come from.

Tested on x86-64 Linux.

## Installation

1. Make a folder for Home-Rank and download its two files from the latest release:

   ```sh
   mkdir home-rank && cd home-rank
   curl -fLO https://github.com/januhrhammer/Home-Rank/releases/latest/download/compose.yaml
   curl -fL -o .env.example https://github.com/januhrhammer/Home-Rank/releases/latest/download/env.example
   ```

   `compose.yaml` describes the three containers and names the version of Home-Rank to run;
   `.env.example` lists the settings.

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

   The first start downloads the images, about 1 GB. Afterwards `docker compose ps` shows all
   three containers as `healthy`.

4. Create your account:

   ```sh
   docker compose exec web python manage.py createsuperuser
   ```

   Passwords need at least 15 characters. There is no public sign-up: this first account is the
   administrator, who can add further users in the admin area at `/admin/`.

5. Open `http://<your ALLOWED_HOSTS value>:8000` and log in.

6. Under **Settings**, enter the names you play under, one per line: your name as tournament
   PGN files spell it ("Carlsen, Magnus") and your usernames on Lichess or Chess.com. Home-Rank
   uses them to find your side in each game, and so whether you won. Changing them later
   updates all your games in the background.

### On Proxmox VE

On a [Proxmox VE](https://www.proxmox.com/en/products/proxmox-virtual-environment/overview)
host, one command does steps 1 to 3 in a new container. Run it as root in the host's shell:

```sh
bash -c "$(curl -fsSL https://raw.githubusercontent.com/januhrhammer/Home-Rank/main/docker/proxmox-lxc.sh)"
```

It asks for the container's ID, host name, cores, memory, disk, storage and network (Enter
keeps the default), then creates an unprivileged Debian 13 container with Docker, puts
Home-Rank in `/opt/home-rank` with random passwords, `ALLOWED_HOSTS` set to the container's
address and `HTTPS=false`, and starts it. At the end it shows the address and how to create
your account (step 4). [The script](../docker/proxmox-lxc.sh) explains each step; read it
before running it.

A container rather than a virtual machine: Stockfish sees the host's CPU as it is and uses its
fastest instructions. In a virtual machine, set the CPU type to `host` for the same reason; the
default types hide them and Stockfish gets slower.

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

PGN files imported into a repertoire (an opening course, a Lichess study) can be up to 20 MB,
which is fixed. They are read while the upload's request waits: a heavily annotated 20 MB course
takes a few seconds on a desktop processor, and a few times that on a Raspberry Pi. A repertoire
holds at most 20,000 moves, and each user at most 50 repertoires.

Linked Lichess and Chess.com accounts are synced every 6 hours; change that with
`SYNC_INTERVAL_HOURS`, or set it to 0 to sync only when users press "Sync now". The server needs
to reach `lichess.org` and `api.chess.com` over HTTPS. Both sites like to know who is asking:
consider setting `SYNC_CONTACT` to your email address, so they can contact you rather than block
your server if something goes wrong. A first sync of a long Lichess history takes a while:
Lichess sends about 20 games a second.

### Engine analysis

The worker analyses games with Stockfish, which the image contains. Games users played are
analysed automatically soon after they arrive, a few at a time (users can turn this off in
their settings), and anyone can analyse a game from its page. Analysis takes CPU time: at the
default depth of 18, a game of 30 moves took 11 seconds on one core of a recent desktop PC;
expect several times that on a Raspberry Pi. These settings in `.env` tune it:

| Setting | Default | What it does |
|---|---|---|
| `ENGINE_THREADS` | 1 | CPU threads Stockfish uses per analysed game |
| `ENGINE_HASH_MB` | 64 | Memory for Stockfish's hash table per analysed game, in MB |
| `ANALYSIS_DEPTH` | 18 | How deep Stockfish searches each position. Each step deeper costs about half again as much time. Users can ask for up to 30 for a single game. |
| `ANALYSIS_CONCURRENCY` | 1 | How many games are analysed at the same time |
| `PUZZLE_DEPTH` | 20 | How deep Stockfish checks positions for puzzles |
| `ANALYSIS_HOURS` | (any time) | When automatic analyses may run, e.g. `23:00-07:00`; analyses users start run at once |
| `TIME_ZONE` | UTC | The server's time zone, for `ANALYSIS_HOURS`, e.g. `Europe/Berlin` |

Keep `ENGINE_THREADS` × `ANALYSIS_CONCURRENCY` below the number of CPU cores, so the website stays
responsive while games are analysed. On a 4-core Raspberry Pi, for example, `ENGINE_THREADS=2`
and `ANALYSIS_HOURS=00:00-07:00` analyse quickly at night and leave the days quiet. Memory:
Stockfish needs about 250 MB plus its hash table per game analysed at the same time (about
300 MB with the defaults), only while it analyses.

Someone who imports thousands of their games gets all of them analysed eventually, which can
take days on a small server; the website shows each game's analysis as soon as it is done.

Analysed games are then searched for puzzles: positions where one move clearly wins. Stockfish
compares the best two moves of each candidate at `PUZZLE_DEPTH` (default 20), which takes a few
seconds per game. The search runs in the same engine slots and hours as automatic analyses, so
the settings above apply to it as well.

### Bots

Users can play positions out against two bots. **Maia** plays the moves people of a chosen
rating play, from a model of about 20 MB; a move takes milliseconds. **Stockfish**, held back to
a chosen strength, is started for each of its moves, which takes about half a second. Both
answer in the website's own process, so neither needs the worker. Each website process loads
Maia the first time someone plays against it and keeps it: about 55 MB more memory per
process (`WEB_WORKERS`, 2 by default). There is nothing to set up.

To see that both bots work, e.g. after an update:

```sh
docker compose exec web python manage.py check_bots
```

It lets each bot answer 1. e4 and says how long it took.

### Live analysis

Live analysis on the board runs Stockfish in each user's own browser (ADR 0018), so it costs the
server nothing beyond sending its files once (about 1.2 MB). It uses several of the device's
cores, but browsers only allow that on secure pages: over HTTPS, or at `localhost`. Over plain
`http://` on your network it runs on one core, about four times slower, which still works. The
image holds the engine's licence (GPL) and where its source is, at `/engine/Copying.txt` and
`/engine/SOURCE.txt` on the website.

For the several cores, Home-Rank sends `Cross-Origin-Opener-Policy` and
`Cross-Origin-Embedder-Policy` headers. A reverse proxy must pass them on, as the examples below
do; one that adds headers of its own must not replace these.

### Reference databases

A reference database is a large collection of games that all users can browse, search by
position and compare with their own games in the opening explorer, for example
[Lumbra's GigaBase](https://lumbrasgigabase.com) (over 12 million over-the-board games) or a
month of the [Lichess database](https://database.lichess.org). Files of several GB aren't
uploaded through the website; put them into the import folder and import them from there:

1. Put the PGN files into `./import` next to `compose.yaml` (or the folder `HOMERANK_IMPORT_DIR`
   names in `.env`). `.pgn`, `.pgn.gz`, `.pgn.bz2`, `.pgn.zst` and `.7z` work; they are read as
   they are decompressed and never unpacked to disk.
2. Either in the admin (*Reference databases* → add one; saving it opens *Import files…*, which
   the database's page and the list also link to), which runs the import on the worker and
   keeps going when you close the browser, or in a shell, which shows an estimate first and runs
   it right there:

   ```sh
   docker compose exec worker python manage.py import_reference lumbra/otb.7z --name "Lumbra OTB"
   ```

   Several files can go into one database. An interrupted import resumes where it stopped when
   started again with the same files. Games already in the database are skipped.
3. Follow it in the admin under *Reference imports*, or in the shell's output.

How big and how long, measured with 1.5 million Lichess games (January 2015) on a 16-core PC:

| | 1.5 M Lichess games | Estimated for 12 M OTB games |
|---|---|---|
| Disk space (games, explorer, position index) | 1.6 GB | about 12 GB |
| Import with 15 processes | 6 minutes | about 50 minutes |
| Import with 3 processes on a 4-core mini PC (estimated) | about 30 minutes | about 4 hours |

The importer needs the space while it runs plus about as much again for a few minutes while it
builds the indexes. Positions are indexed for the first 30 half-moves of each game, which covers
the openings; a database created in the admin can index more or fewer (`--depth` in the shell),
and the space for the index grows with it. `REFERENCE_IMPORT_WORKERS` sets the number of
processes (default: all CPU cores but one). Deleting a database in the admin frees its space at
once.

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
that haven't been imported yet.) To back it up into one file, in Home-Rank's folder:

```sh
docker compose exec -T db pg_dump --username=homerank --format=custom homerank > home-rank-$(date +%F).dump
```

It takes seconds and needs no downtime. A thousand games take about 2.5 MB; a reference database
about 1 GB per million games. Keep the backup somewhere other than this machine, together with a
copy of `.env` and `compose.yaml`: without the same `SECRET_KEY`, everyone has to log in again.

### Backing up every night

With cron, e.g. at 3:00, keeping 30 days of backups in a `backups` folder (`crontab -e`, and the
path to Home-Rank's folder instead of `/srv/home-rank`; cron needs the `%` written as `\%`):

```sh
0 3 * * * cd /srv/home-rank && docker compose exec -T db pg_dump --username=homerank --format=custom homerank > backups/home-rank-$(date +\%F).dump && find backups -name "home-rank-*.dump" -mtime +30 -delete
```

### Restoring

Restoring replaces everything with the backup's contents, including what was added after it.
Stop Home-Rank, empty its database, restore the backup into it and start Home-Rank again:

```sh
docker compose stop web worker
docker compose exec -T db dropdb --username=homerank --force homerank
docker compose exec -T db createdb --username=homerank homerank
docker compose exec -T db pg_restore --username=homerank --dbname=homerank --exit-on-error < home-rank-2026-10-22.dump
docker compose up -d
```

Restore with the version of Home-Rank the backup was made with, or a newer one: the website
updates an older database when it starts. To go back to the version before an update, see
[Updating](#updating).

On a new machine, put the saved `.env` and `compose.yaml` in a folder, start only the database
with `docker compose up -d db`, and then run the commands above.

## Updating

[Back up](#backup-and-restore) first. Then, in Home-Rank's folder, download the `compose.yaml`
of the latest release, which names the new version, and start it:

```sh
curl -fLO https://github.com/januhrhammer/Home-Rank/releases/latest/download/compose.yaml
docker compose pull    # the new version, and the newest PostgreSQL 18 release
docker compose up -d   # restart what changed
```

If you installed Home-Rank with `git clone`, from before there were published images, run
`git pull` instead of the `curl` command; your data stays where it is.

Your `.env` stays as it is. The [release notes](https://github.com/januhrhammer/Home-Rank/releases)
list new settings; the release's `.env.example` explains them. The version to run is in the
`x-homerank-image` line of `compose.yaml`. To go back to an older one, put its version there and
[restore](#restoring) the backup made before the update: an older version can't read a database
that a newer one has updated.

When the website starts, it updates the database to the new version before it accepts requests,
and the worker waits until it has. Each update leaves the previous image behind;
`docker image prune` removes such leftovers.

### Running your own build

To run Home-Rank built from its source code instead, e.g. with your own changes, clone the
repository, put your `.env` there, and add the build file to every `docker compose` command:

```sh
git clone https://github.com/januhrhammer/Home-Rank.git
cd Home-Rank
docker compose --file compose.yaml --file docker/compose.build.yaml up -d
```

Every `up` rebuilds the image, which takes a few minutes the first time.

## Uninstalling

`docker compose down` stops and removes the containers. Your data stays in the Docker volumes
`home-rank_db-data` and `home-rank_data` until you also remove them: `docker compose down
--volumes` deletes all of Home-Rank's data for good.
