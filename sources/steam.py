from typing import List
from datetime import datetime
from models.game import Game
from models.games import Games
import json
import requests


icon = "https://steamcommunity.com/favicon.ico"
store = "Steam"

def load_promoted_games(featured_url: str = "https://store.steampowered.com/api/featuredcategories") -> List[Game]:
    response = requests.get(featured_url)
    return parse_steam_promoted_games(response.text)

def parse_steam_promoted_games(data: str) -> List[Game]:
    """
    Fetches and processes promoted games from the Steam featured_url API.
    Args:
        featured_url: URL to the Steam featured_url endpoint
    Returns:
        List[Game]: A list of Game objects representing the promoted games
    """
    json_data = json.loads(data)
    
    games: List[Game] = []
    # The response is a dict with keys like '0', '1', ..., 'coming_soon', etc.
    for key, section in json_data.items():
        if not isinstance(section, dict) or 'items' not in section or key.isdigit():
            continue
        for item in section['items']:
            game = Game()
            game.store = store
            game.source_icon = icon
            game.title = item.get('name', '')
            game.description = item.get('body', '')
            game.url = "https://store.steampowered.com/app/" + str(item.get('id', ''))
            game.image_url = item.get('header_image', '')
            game.source = 'steam'
            # Price info
            if item.get('original_price') == None:
                game.free_to_play = True
            game._original_price = str(item.get('original_price', ''))
            game._discount_price = str(item.get('final_price', ''))
            game._discount_percentage = str(item.get('discount_percent', ''))
            game.currency = item.get('currency', '')
            # Valid until (if present as a timestamp)
            discount_exp = item.get('discount_expiration')
            if discount_exp:
                try:
                    from datetime import timezone
                    # Steam gives unix timestamp; convert to UTC-aware ISO8601
                    dt = datetime.fromtimestamp(int(discount_exp), tz=timezone.utc)
                    game.valid_until = dt.isoformat()  # e.g. '2025-05-25T17:00:00+00:00'
                except Exception:
                    game.valid_until = ''
            games.append(game)
    return games

if __name__ == "__main__":
    # read sample file
    data = open("samples/steam.json", "r").read()
    games = Games()
    
    games.add(load_promoted_games())
    for game in games.discounted:
        if game.discount_percentage > 50:
            print(game)