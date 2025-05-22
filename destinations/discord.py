from typing import Optional, List, Dict, Any
import requests
from datetime import datetime
from models.game import Game

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
            {"name": "Price", "value": f"{'**Free**' if game.is_free else game.price}", "inline": True}
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
    
    # Prepare embeds
    embeds = []
    
    # Add free games section if there are any
    if free_games:
        for game in free_games:
            embeds.append(create_embed(game))
    
    # Add discounted games section if there are any
    if discounted_games:
        for game in discounted_games:
            embeds.append(create_embed(game))
    
    # If no games, don't send anything
    if not embeds:
        return False
    
    # Split embeds into chunks of 10 (Discord's limit per message)
    for i in range(0, len(embeds), 10):
        chunk = embeds[i:i + 10]
        payload = {"embeds": chunk}
        
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