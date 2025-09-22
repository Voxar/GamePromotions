from typing import Optional, List, Dict, Any
import requests
from datetime import datetime
from models.game import Game

AVATAR_FREE="https://raw.githubusercontent.com/Voxar/GamePromotions/main/assets/avatars/free/1.png"
AVATAR_DISCOUNTED="https://raw.githubusercontent.com/Voxar/GamePromotions/main/assets/avatars/discounted/1.png"

class DiscordWebhookError(Exception):
    pass

def create_embed(game: Game) -> Dict[str, Any]:
    """Create a Discord embed for a single game."""
    
    description = game.description
    if description == game.title:
        description = ""
    if len(description) > 200:
        description = description[:200] + '...'
    embed = {
        "title": game.title,
        "url": game.url,
        "description": description,
        "color": 0x57F287 if game.is_free else 0x5865F2, 
        "fields": [
            {"name": "Price", "value": f"{'**Free**' if game.is_free else game.price_with_currency}", "inline": True},
        ]
    }
    
    # Add discount percentage if available
    if hasattr(game, 'discount_percentage') and game.discount_percentage:
        embed["fields"].append({"name": "Discount", "value": f"{game.discount_percentage:.0f}% off", "inline": True})
        
    embed["fields"].append({"name": "Store", "value": game.store, "inline": True})
    
    # Add valid until if available
    if hasattr(game, 'valid_until') and game.valid_until:
        try:
            end_date = datetime.fromisoformat(game.valid_until.rstrip('Z'))
            embed["fields"].append({"name": "Offer ends", "value": f"<t:{int(end_date.timestamp())}:R>", "inline": True})
        except (ValueError, AttributeError):
            pass
    
    # Add image if available
    if hasattr(game, 'image_url') and game.image_url:
        embed["thumbnail"] = {"url": game.image_url}
    
    return embed

def send_to_discord_webhook(webhook_url: str, games: List[Game]) -> bool:
    """
    Send a list of games to a Discord webhook.
    
    Args:
        webhook_url: The Discord webhook URL
        games: A list of Game objects containing the games to send
        
    Returns:
        bool: True if the message was sent successfully, False otherwise
    """
    if not webhook_url:
        raise ValueError("Webhook URL is required")
    
    # Split games into free and discounted
    free_games = [game for game in games if game.is_free]
    discounted_games = [game for game in games if game.is_discounted]
            
    send(webhook_url, [create_embed(game) for game in discounted_games], "Discount Games")
    send(webhook_url, [create_embed(game) for game in free_games], "Free Games")
    return True
            
def send(webhook_url, embeds, username):
    # If no games, don't send anything
    if not embeds:
        return False
    
    # Split embeds into chunks of 10 (Discord's limit per message)
    for i in range(0, len(embeds), 10):
        chunk = embeds[i:i + 10]
        payload = {
            "username": username,
            "avatar_url": AVATAR_FREE if "Free" in username else AVATAR_DISCOUNTED,
            "embeds": chunk,
        }
        
        try:
            response = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise DiscordWebhookError(f"Failed to send Discord webhook: {e}")
    
    return True