# Home-Rank

A self-hosted chess database and training app: your games, analysed overnight, turned into your
personal training plan.

Home-Rank stores your games, syncs them from Lichess and Chess.com, analyses them with Stockfish in
the background, and builds tactics puzzles and opening drills from your own mistakes. It can also
import large reference databases such as Lumbra's GigaBase for position search and an opening
explorer.

> **Status:** early development. You can install it and log in, but there is nothing to do yet.

## Quick start

With Docker and the Compose plugin installed:

```sh
git clone https://github.com/januhrhammer/Home-Rank.git
cd Home-Rank
cp .env.example .env   # then fill in the four required values at the top
docker compose up -d
docker compose exec web python manage.py createsuperuser
```

Then open port 8000 of that machine in your browser and log in.
[docs/self-hosting.md](docs/self-hosting.md) explains each step, configuration and updates.

## Development

See [docs/development.md](docs/development.md).

## Contributing

Contributions are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md). Please report security
problems privately, as described in [SECURITY.md](SECURITY.md).

## Licence

[AGPL-3.0-or-later](LICENSE). [ADR 0002](docs/adr/0002-license.md) explains why.
