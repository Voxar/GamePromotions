import os
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.crons import monitor

load_dotenv()

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    # Add data like request headers and IP for users,
    # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
    send_default_pii=True,
    enable_logs=True,
    enable_tracing=True,
    enable_db_query_source=True,
    
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
    # To collect profiles for all profile sessions,
    # set `profile_session_sample_rate` to 1.0.
    profile_session_sample_rate=1.0,
    # Profiles will be automatically collected while
    # there is an active span.
    profile_lifecycle="trace",
)

from models.games import Games
import logging

@monitor(monitor_slug='gha-gamepromotions')
def main():
    discord_webhooks = [e for e in (os.getenv("DISCORD_WEBHOOK_URL") or "").split(";") if len(e) > 0]
    epic_games_url = os.getenv("EPIC_GAMES_PROMOTIONS")
    steam_games_url = os.getenv("STEAM_PROMOTIONS")

    db = None
    if os.getenv("MONGODB_URI"):
        print("Using MongoDB", os.getenv("MONGODB_URI"))
        from databases.mongodb import MongoDB
        db = MongoDB()
    
    games = Games()

    if epic_games_url:
        logging.info("Loading Epic Games promotions from %s", epic_games_url)
        from sources.epic_games import get_epic_games_promotions
        games.add(get_epic_games_promotions(epic_games_url))

    if steam_games_url:
        logging.info("Loading Steam promotions from %s", steam_games_url)
        from sources.steam import load_promoted_games
        games.add(load_promoted_games(steam_games_url))

    # Add more sources here
    
    if games:
        # Print to console
        if games.count == 0:
            print("No games found")
            return
        
        discounted = games.discounted_more_than(50)
        discounted.sort(key=lambda x: x.discount_percentage, reverse=True)
        print(len(discounted), "Discounted")
        for game in discounted:
            print(game)

        free = games.free
        print(len(free), "Free")
        for game in free:
            print(game)
        
        # Send to Discord
        if discord_webhooks and len(discord_webhooks) > 0:
            print("Sending to Discord", discord_webhooks)
            games_to_send = free + discounted
            
            if db: 
                filtered_games = []
                for game in games_to_send:
                    game_id = getattr(game, 'id', game.title)
                    valid_until = getattr(game, 'valid_until', '')
                    if not db.is_game_posted(game_id, valid_until, 'discord'):
                        filtered_games.append(game)
                games_to_send = filtered_games
            
            from destinations.discord import send_to_discord_webhook
            for webhook in discord_webhooks:
                send_to_discord_webhook(webhook, games_to_send)
                
            if db:
                for game in games_to_send:
                    db.mark_game_as_posted(
                        getattr(game, 'id', game.title),
                        game.title,
                        getattr(game, 'valid_until', ''),
                        "discord",
                        getattr(game, 'original_price', None),
                        getattr(game, 'price', None)
                    )

        # Add more destinations here
    else:
        print("No games found")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    main()
