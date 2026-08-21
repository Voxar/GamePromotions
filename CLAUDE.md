# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Game promotion tracker that fetches free and discounted games from multiple stores (Epic Games, Steam) and sends notifications to Discord. Supports MongoDB for tracking posted games to avoid duplicates. Includes Sentry monitoring for error tracking and cron monitoring.

## Development Commands

### Local Development
```bash
# Setup environment
python -m venv .venv
source .venv/bin/activate  # or `.venv/bin/activate` on Windows
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Discord webhook and MongoDB URI

# Run the script
python main.py
```

### Docker
```bash
# Build and run with Docker Compose
docker-compose up --build

# Build Docker image directly
docker build -t epic-free-games .

# Run container with environment variables
docker run --rm \
  -e DISCORD_WEBHOOK_URL=your_webhook_url \
  -e MONGODB_URI=your_mongodb_uri \
  -v $(pwd)/config.yml:/app/config.yml \
  epic-free-games
```

## Architecture

### Data Flow
1. **Sources** (`sources/`) fetch game promotions from store APIs
   - `epic_games.py`: Fetches from Epic Games Store API using JMESPath for JSON parsing
   - `steam.py`: Fetches from Steam featured categories API
   - Each source returns a list of `Game` objects

2. **Models** (`models/`) define data structures
   - `game.py`: Single game with pricing, discounts, validity period
   - `games.py`: Collection of games with filtering methods (free, discounted, etc.)

3. **Database** (`databases/`) handles persistence
   - `mongodb.py`: Tracks posted games by (game_id, valid_until, service) to prevent duplicate notifications
   - Stores price history and event sourcing for game changes

4. **Destinations** (`destinations/`) send notifications
   - `discord.py`: Formats games as Discord embeds and sends via webhooks
   - Splits free/discounted games into separate messages with custom avatars
   - Handles Discord's 10 embed per message limit

5. **Main** (`main.py`) orchestrates the flow:
   - Loads sources based on environment variables
   - Filters games (free + >50% discounted)
   - Checks database to avoid reposting
   - Sends to Discord webhooks
   - Updates database with posted games
   - Wrapped in Sentry cron monitor for reliability tracking

### Key Design Patterns
- **Modular sources**: Easy to add new game stores by implementing the source interface
- **Deduplication**: MongoDB tracks (game_id, valid_until, service) to avoid reposting same promotion
- **Multiple webhooks**: Semicolon-separated DISCORD_WEBHOOK_URL supports multiple Discord channels
- **Price parsing**: Game model handles various price formats and currency symbols
- **Timestamp handling**: Valid until dates stored as ISO8601 with timezone awareness

## Environment Variables

Required for operation:
- `DISCORD_WEBHOOK_URL`: Discord webhook(s) (semicolon-separated for multiple)
- `MONGODB_URI`: MongoDB connection string (optional, enables deduplication)
- `SENTRY_DSN`: Sentry DSN for error tracking and cron monitoring
- `EPIC_GAMES_PROMOTIONS`: Epic Games API URL (has default)
- `STEAM_PROMOTIONS`: Steam API URL (has default)

## Deployment

Runs on **raheth**, a shared server managed by Coolify (https://coolify.d.nevyn.dev), as a
resource under the `Voxar` project. Build pack: docker-compose.

The schedule lives **inside the container** — `crontab` is read by supercronic, started by
`docker-entrypoint.sh`. Nothing is installed on the host and no host cron is used. The container
is a long-running process (supercronic in the foreground), which is also what keeps Coolify's
health check happy.

- `crontab` — `0 */4 * * *`, six runs a day, UTC. Same cadence as the GHA schedule it replaced.
- `RUN_ON_START=true` — fires one run at boot instead of waiting for the next slot. Useful to
  verify a deploy; harmless because MongoDB dedupes.
- Secrets are set as environment variables on the Coolify app, not committed.
- supercronic is checksum-pinned in `deploy/supercronic.sha1` (amd64 + arm64).

Shared-box rules that constrain this deployment: memory is capped in docker-compose.yml, the
service must stay single-homed (no `networks:` block — a second network makes Traefik route to an
unreachable IP), and data must live in named volumes since Coolify re-clones the repo per deploy.

### GitHub Actions

`.github/workflows/run.yml` still exists but its `schedule:` trigger is **commented out** —
re-enabling it while the container runs would double-post. `workflow_dispatch` is kept as a
manual fallback and still needs the repo secrets.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

`tests/test_scheduling.py` covers the crontab and entrypoint (stubbing `python`/`supercronic`).
`tests/test_image.py` builds the real image and runs it — it auto-skips if docker is unavailable.

## Adding New Game Sources

To add a new source:
1. Create a new file in `sources/` (e.g., `sources/gog.py`)
2. Implement a function that returns `List[Game]`:
   ```python
   def get_gog_promotions(api_url: str) -> List[Game]:
       # Fetch API
       # Parse response
       # Create Game objects with required fields:
       #   - title, description, url, image_url
       #   - _original_price, _discount_price, _discount_percentage
       #   - valid_until (ISO8601), source, store
       return games
   ```
3. Import and call in `main.py`:
   ```python
   if gog_games_url:
       from sources.gog import get_gog_promotions
       games.add(get_gog_promotions(gog_games_url))
   ```

## Adding New Destinations

To add a new destination:
1. Create a new file in `destinations/` (e.g., `destinations/slack.py`)
2. Implement a send function:
   ```python
   def send_to_slack(webhook_url: str, games: List[Game]) -> bool:
       # Format games
       # Send to webhook
       return True
   ```
3. Call from `main.py` after Discord block

## Notes

- Sentry cron monitor slug is still `gha-gamepromotions` (see `main.py`) even though runs no
  longer come from GHA; renaming it creates a fresh monitor in Sentry and loses check-in history
- `config.yml` and `templates/` are not used by `main.py` (only `generate_stats.py`), so they are
  deliberately not copied into the image
- Game IDs are based on URL (see `game.py:id` property)
- Price values stored as strings and parsed on demand
- Discord embeds limited to 10 per message; code handles chunking automatically
