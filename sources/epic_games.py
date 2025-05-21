from typing import List, Dict, Any
import requests
import jmespath
from datetime import datetime
from models.game import Game

def get_epic_games_promotions(json_url: str) -> List[Game]:
    """
    Fetches and processes free games from the Epic Games Store API.
    
    Args:
        json_url: URL to the Epic Games promotions API endpoint
        
    Returns:
        List[Game]: A list of Game objects representing the free games
    """
    try:
        # Make the API request
        response = requests.get(
            json_url,
            params={'locale': 'en-US', 'country': 'US', 'allowCountries': 'US'}
        )
        response.raise_for_status()
        data = response.json()
        
        # Get all games
        all_games = jmespath.search('data.Catalog.searchStore.elements', data) or []
        
        games = []
        for game_data in all_games:
            # Check if the game has any promotions
            promotions = jmespath.search('promotions', game_data) or {}
            
            # Find the best discount (current or upcoming)
            current_offers = jmespath.search('promotionalOffers[].promotionalOffers[]', promotions) or []
            upcoming_offers = jmespath.search('upcomingPromotionalOffers[].promotionalOffers[]', promotions) or []
            all_offers = current_offers + upcoming_offers
            
            # Get the best discount (highest discount percentage)
            best_offer = max(
                all_offers,
                key=lambda x: float(jmespath.search('discountSetting.discountPercentage', x) or 0),
                default=None
            )
            # Extract game information using JMESPath
            title = (jmespath.search('title', game_data) or '').strip()
            description = (jmespath.search('description', game_data) or '').strip()
            
            # Skip mystery games or games with missing titles
            if not title or title.lower().startswith('mystery game'):
                continue
                
            # Get product URL - try to get from catalogNs.mappings first, then fall back to productSlug
            mappings = jmespath.search('catalogNs.mappings', game_data) or []
            page_slug = (mappings[0]['pageSlug'] if mappings and len(mappings) > 0 and 'pageSlug' in mappings[0] 
                        else jmespath.search('productSlug', game_data) or '')
            
            # Skip if we don't have a valid page slug
            if not page_slug or page_slug == '[]':
                continue
                
            url = f"https://www.epicgames.com/store/en-US/p/{page_slug}"
            
            # Get price information (use numeric values instead of formatted strings)
            price_data = jmespath.search('price.totalPrice', game_data) or {}
            original_price = str(price_data.get('originalPrice', 0) / 100)  # Convert cents to dollars
            discount_price = str(price_data.get('discountPrice', 0) / 100) if price_data.get('discountPrice') is not None else ''
            
            # Get image - prefer Thumbnail, fall back to other non-Vault images
            key_images = jmespath.search('keyImages', game_data) or []
            thumbnail_url = ''
            
            # First try to find a Thumbnail
            for img in key_images:
                if img.get('type') == 'Thumbnail' and 'vault' not in img.get('url', '').lower():
                    thumbnail_url = img.get('url', '')
                    break
            
            # If no Thumbnail found, try other non-Vault image types (in order of preference)
            if not thumbnail_url:
                preferred_types = ['OfferImageWide', 'OfferImageTall', 'DieselStoreFrontWide', 'DieselStoreFrontTall']
                for img_type in preferred_types:
                    for img in key_images:
                        if img.get('type') == img_type and 'vault' not in img.get('url', '').lower():
                            thumbnail_url = img.get('url', '')
                            break
                    if thumbnail_url:
                        break
                        
                # If still no image, try any non-Vault image
                if not thumbnail_url:
                    for img in key_images:
                        if 'vault' not in img.get('url', '').lower():
                            thumbnail_url = img.get('url', '')
                            break
            
            # Get categories
            categories = [cat.get('path', '') for cat in jmespath.search('categories', game_data) or []]
            
            # Create Game object with all fields
            game = Game()
            game.title = title
            game.description = description
            game.url = url
            game.image_url = thumbnail_url
            game.source = 'epic_games'
            game.categories = categories
            
            # Price information
            game._original_price = original_price
            game._discount_price = discount_price
            
            # Promotion information if available
            if best_offer:
                game._discount_percentage = str(jmespath.search('discountSetting.discountPercentage', best_offer) or '0')
                
                # Get promotion end date if available
                end_date = jmespath.search('endDate', best_offer)
                if end_date:
                    try:
                        # Convert to ISO format if it's not already
                        if 'T' in end_date:
                            game.valid_until = end_date
                        else:
                            # Handle different date formats if needed
                            dt = datetime.strptime(end_date, '%Y-%m-%d')
                            game.valid_until = dt.isoformat() + 'Z'
                    except (ValueError, TypeError):
                        game.valid_until = ''
            else:
                game._discount_percentage = '0'
                game.valid_until = ''
            
            games.append(game)
        
        return games
        
    except Exception as e:
        print(f"Error fetching Epic Games promotions: {e}")
        return []