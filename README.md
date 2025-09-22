# Epic Free Games Notifier

This script fetches the current free games from the Epic Games Store and can optionally send them to a Discord channel. It's designed to run in a Docker container for easy deployment.

## Prerequisites

- Docker and Docker Compose installed on your system
- A Discord webhook URL (optional, for notifications)

## Quick Start

1. Clone this repository
2. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
3. Edit the `.env` file and add your Discord webhook URL:
   ```
   DISCORD_WEBHOOK_URL=your_discord_webhook_url_here
   ```
   For multiple webhooks, separate them with semicolons (;)

## Running with Docker Compose (Recommended)

```bash
docker-compose up --build
```

## Running with Docker Directly

Build the image:
```bash
docker build -t epic-free-games .
```

Run the container:
```bash
docker run --rm \
  -e DISCORD_WEBHOOK_URL=your_webhook_url_here \
  -v $(pwd)/config.yml:/app/config.yml \
  epic-free-games
```

## Running Locally (Without Docker)

1. Install Python 3.8+ and optionally setup a venv
   ```bash
   asdf install
   python -m venv .venv
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the script:
   ```bash
   python main.py
   ```

## Configuration

You can customize the behavior using the following environment variables:

- `DISCORD_WEBHOOK_URL`: Your Discord webhook URL (semicolon-separated for multiple)
- `CONFIG_PATH`: Path to config file (default: `/app/config.yml` in container, `config.yml` locally)

## Creating a Discord Webhook

1. Open your Discord server settings
2. Go to "Integrations" > "Webhooks"
3. Click "New Webhook"
4. Configure the webhook (name, channel, etc.)
5. Copy the Webhook URL
6. Add it to your `.env` file

## Scheduling

To run this on a schedule, you can use:

1. **Docker with systemd/cron**: Create a systemd service or cron job that runs `docker-compose up`
2. **Kubernetes**: Create a CronJob resource
3. **Local cron**: Add a crontab entry to run the script or container

Example crontab entry to run daily at 10 AM:
```
0 10 * * * cd /path/to/epic-free-games && docker-compose up
```

## Building for Different Architectures

To build for ARM architectures (like Raspberry Pi), modify the Dockerfile:

```dockerfile
FROM --platform=linux/arm64 python:3.9-slim
```

Then build with:
```bash
docker buildx build --platform linux/arm64 -t epic-free-games:arm64 .
```
