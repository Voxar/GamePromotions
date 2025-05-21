import requests
import os
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv
from models.games import Games

def main():
    load_dotenv()
    discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
    epic_games_url = os.getenv("EPIC_GAMES_PROMOTIONS")

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
        if discord_webhook:
            from destinations.discord import send_to_discord_webhook

            send_to_discord_webhook(discord_webhook, games)

        # Add more destinations here
    else:
        print("No games found")

    
    

if __name__ == "__main__":
    main()
