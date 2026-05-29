from typing import Callable, List, Optional
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import re

from models.game import Game
import requests
import sentry_sdk
import logging

logger = logging.getLogger(__name__)

icon = "https://www.gog.com/favicon.ico"
store = "GOG"

DEFAULT_URL = (
    "https://catalog.gog.com/v1/catalog"
    "?limit=48&order=desc:discount&discounted=eq:true"
    "&productType=in:game,pack&page=1"
)

_PROMO_END_RE = re.compile(
    r"cardProductPromoEndDate\s*=\s*(\{[^}]+\})"
)
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)


def _fetch_promo_end(store_link: str) -> str:
    """Fetch a GOG product page and extract the discount expiry as ISO8601.

    GOG's catalog API doesn't expose discount expiration; the storefront only
    embeds it inside `window.productcardData.cardProductPromoEndDate` on the
    product HTML page. Returns "" on any failure.
    """
    if not store_link:
        return ""
    try:
        resp = requests.get(store_link, headers={"User-Agent": _BROWSER_UA}, timeout=15)
        resp.raise_for_status()
        match = _PROMO_END_RE.search(resp.text)
        if not match:
            return ""
        payload = json.loads(match.group(1))
        date_str = payload.get("date", "")
        tz = payload.get("timezone", "")
        if not date_str:
            return ""
        # date_str like "2026-06-02 09:59:59.000000", tz like "+03:00"
        dt = datetime.strptime(date_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
        iso = dt.strftime("%Y-%m-%dT%H:%M:%S")
        return f"{iso}{tz}" if tz else iso
    except Exception as e:
        logger.error(f"Could not fetch GOG promo end for {store_link}: {e}")
        return ""


def get_gog_promotions(
    catalog_url: str = DEFAULT_URL,
    filter_unposted: Optional[Callable[[List[str]], List[str]]] = None,
) -> List[Game]:
    """
    Fetches discounted games from the GOG catalog API, then enriches each
    with its promotion end date by scraping the product page.

    Args:
        catalog_url: URL to the GOG catalog endpoint (filtered to discounted products)
        filter_unposted: Optional callback `(game_urls) -> urls_to_enrich`. Given the
            full list of catalog URLs, returns the subset that still needs processing
            (i.e. has no current active posting). Games not returned by the callback
            are dropped from the result entirely, avoiding their product-page scrape.

    Returns:
        List[Game]: A list of Game objects representing the discounted games
    """
    try:
        response = requests.get(catalog_url, headers={"Accept": "application/json"}, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.error(f"Error fetching GOG promotions: {e}")
        sentry_sdk.capture_exception(e)
        return []

    games: List[Game] = []
    for product in data.get("products", []):
        price = product.get("price") or {}
        base_money = price.get("baseMoney") or {}
        final_money = price.get("finalMoney") or {}

        game = Game()
        game.store = store
        game.source_icon = icon
        game.source = "gog"
        game.store_game_id = str(product.get("id", ""))
        game.title = product.get("title", "") or ""
        game.description = ""
        game.url = product.get("storeLink") or (
            f"https://www.gog.com/en/game/{product.get('slug', '')}" if product.get("slug") else ""
        )
        game.image_url = product.get("coverHorizontal") or product.get("coverVertical") or ""
        game._original_price = str(base_money.get("amount", "") or "")
        game._discount_price = str(final_money.get("amount", "") or "")
        game.currency = final_money.get("currency") or base_money.get("currency") or ""

        raw_discount = price.get("discount") or ""
        game._discount_percentage = "".join(c for c in raw_discount if c.isdigit())
        game.valid_until = ""

        if not game.title or not game.url:
            continue

        games.append(game)

    # Drop games that already have an active posting; scrape expiry only for survivors.
    if filter_unposted and games:
        keep = set(filter_unposted([g.url for g in games]))
        games = [g for g in games if g.url in keep]

    if games:
        with ThreadPoolExecutor(max_workers=8) as pool:
            expiries = list(pool.map(_fetch_promo_end, [g.url for g in games]))
        for game, expiry in zip(games, expiries):
            game.valid_until = expiry
        # Drop games whose expiry couldn't be determined — without it we can't dedup,
        # which would cause re-posts on every run.
        games = [g for g in games if g.valid_until]

    return games


if __name__ == "__main__":
    for game in get_gog_promotions():
        print(game)
