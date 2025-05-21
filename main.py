import requests
import os
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv
from models.games import Games
from databases.mongodb import MongoDB

def main():
    load_dotenv()
    discord_webhooks = (os.getenv("DISCORD_WEBHOOK_URL") or "").split(";")
    epic_games_url = os.getenv("EPIC_GAMES_PROMOTIONS")

    db = MongoDB() if os.getenv("MONGODB_URI") else None
    
    games = Games()

    if epic_games_url:
        from sources.epic_games import get_epic_games_promotions
        games.add(get_epic_games_promotions(epic_games_url))

    # Add more sources here
    
    if games:
        # Print to console
        
        print("Discounted")
        for game in games.discounted:
            print(game)

        print("Free")
        for game in games.free:
            print(game)
        
        # Send to Discord
        if discord_webhooks and len(discord_webhooks) > 0:
            games_to_send = games.free + games.discounted
            if db:
                games_to_send = [game for game in games_to_send if not db.is_game_posted(game.id, 'discord')]
                for game in games_to_send:
                    db.mark_game_as_posted(game.id, game.title, "discord")
            from destinations.discord import send_to_discord_webhook
            for webhook in discord_webhooks:
                send_to_discord_webhook(webhook, games_to_send)

        # Add more destinations here
    else:
        print("No games found")

if __name__ == "__main__":
    main()
