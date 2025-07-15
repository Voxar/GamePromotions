import os
from dotenv import load_dotenv
from models.games import Games


def main():
    load_dotenv()
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
        from sources.epic_games import get_epic_games_promotions
        games.add(get_epic_games_promotions(epic_games_url))

    if steam_games_url:
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
                games_to_send = [game for game in games_to_send if not db.is_game_posted(getattr(game, 'id', game.title), getattr(game, 'valid_until', ''), 'discord')]
                for game in games_to_send:
                    db.mark_game_as_posted(
                        getattr(game, 'id', game.title),
                        game.title,
                        getattr(game, 'valid_until', ''),
                        "discord",
                        getattr(game, 'original_price', None),
                        getattr(game, 'price', None)
                    )
            from destinations.discord import send_to_discord_webhook
            for webhook in discord_webhooks:
                send_to_discord_webhook(webhook, games_to_send)

        # Add more destinations here
    else:
        print("No games found")

if __name__ == "__main__":
    main()
