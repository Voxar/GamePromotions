import os
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.crons import monitor
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import logging
from jinja2 import Environment, FileSystemLoader, select_autoescape
import json

load_dotenv()

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    send_default_pii=True,
    enable_logs=True,
    enable_tracing=True,
    traces_sample_rate=1.0,
    profile_session_sample_rate=1.0,
    profile_lifecycle="trace",
)

logger = logging.getLogger(__name__)


def get_mongodb_connection():
    """Get MongoDB connection using existing pattern."""
    from databases.mongodb import MongoDB
    try:
        db = MongoDB()
        logger.info("Successfully connected to MongoDB")
        return db
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        sentry_sdk.capture_exception(e)
        raise


def fetch_all_game_data(db) -> List[Dict]:
    """Fetch all game data from posted_games collection."""
    try:
        games = list(db.posted_games.find({}))
        logger.info(f"Fetched {len(games)} games from MongoDB")
        return games
    except Exception as e:
        logger.error(f"Error fetching game data: {e}")
        sentry_sdk.capture_exception(e)
        return []


def aggregate_free_games_by_date(games: List[Dict]) -> Dict[str, Dict[str, int]]:
    """
    Aggregate free games by date (daily, weekly, monthly).
    Returns: {"daily": {date: count}, "weekly": {...}, "monthly": {...}}
    """
    daily = defaultdict(int)
    weekly = defaultdict(int)
    monthly = defaultdict(int)

    skipped = 0
    for game in games:
        # Check if game is free
        discount_price = game.get('discount_price')
        original_price = game.get('original_price')

        # Free if discount_price is 0, None, or doesn't exist
        is_free = discount_price == 0 or discount_price is None or discount_price == 0.0

        if not is_free:
            continue

        posted_at = game.get('posted_at')
        if not posted_at:
            skipped += 1
            continue

        try:
            if isinstance(posted_at, str):
                date = datetime.fromisoformat(posted_at.replace('Z', '+00:00'))
            else:
                date = posted_at

            # Daily aggregation
            daily_key = date.strftime('%Y-%m-%d')
            daily[daily_key] += 1

            # Weekly aggregation (ISO week)
            weekly_key = date.strftime('%Y-W%V')
            weekly[weekly_key] += 1

            # Monthly aggregation
            monthly_key = date.strftime('%Y-%m')
            monthly[monthly_key] += 1

        except (ValueError, AttributeError) as e:
            logger.warning(f"Invalid date format for game: {e}")
            skipped += 1
            continue

    if skipped > 0:
        logger.warning(f"Skipped {skipped} games due to missing or invalid dates")

    return {
        "daily": dict(sorted(daily.items())),
        "weekly": dict(sorted(weekly.items())),
        "monthly": dict(sorted(monthly.items()))
    }


def aggregate_discount_distribution(games: List[Dict]) -> Dict[str, int]:
    """
    Calculate discount distribution in buckets.
    Returns: {"0-20": count, "20-50": count, ...}
    """
    distribution = {
        "0-20": 0,
        "20-50": 0,
        "50-75": 0,
        "75-99": 0,
        "100": 0  # Free games
    }

    skipped = 0
    for game in games:
        original_price = game.get('original_price')
        discount_price = game.get('discount_price')

        # Skip if missing price data
        if original_price is None or discount_price is None:
            skipped += 1
            continue

        try:
            original = float(original_price)
            discount = float(discount_price)

            # Handle free games
            if discount == 0:
                distribution["100"] += 1
                continue

            # Skip if no discount
            if original <= 0 or discount >= original:
                skipped += 1
                continue

            # Calculate discount percentage
            discount_pct = ((original - discount) / original) * 100

            # Categorize
            if discount_pct >= 100:
                distribution["100"] += 1
            elif discount_pct >= 75:
                distribution["75-99"] += 1
            elif discount_pct >= 50:
                distribution["50-75"] += 1
            elif discount_pct >= 20:
                distribution["20-50"] += 1
            else:
                distribution["0-20"] += 1

        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid price data for game: {e}")
            skipped += 1
            continue

    if skipped > 0:
        logger.warning(f"Skipped {skipped} games in discount distribution due to invalid price data")

    return distribution


def aggregate_average_discount_over_time(games: List[Dict]) -> Dict[str, Dict[str, float]]:
    """
    Calculate average discount percentage over time (daily).
    Returns: {date: {"avg_discount": float, "count": int}}
    """
    daily_discounts = defaultdict(list)

    skipped = 0
    for game in games:
        original_price = game.get('original_price')
        discount_price = game.get('discount_price')
        posted_at = game.get('posted_at')

        # Skip if missing data
        if not posted_at or original_price is None or discount_price is None:
            skipped += 1
            continue

        try:
            original = float(original_price)
            discount = float(discount_price)

            # Skip if no valid discount
            if original <= 0 or discount >= original:
                continue

            # Calculate discount percentage
            discount_pct = ((original - discount) / original) * 100

            # Parse date
            if isinstance(posted_at, str):
                date = datetime.fromisoformat(posted_at.replace('Z', '+00:00'))
            else:
                date = posted_at

            daily_key = date.strftime('%Y-%m-%d')
            daily_discounts[daily_key].append(discount_pct)

        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Error processing game for discount average: {e}")
            skipped += 1
            continue

    if skipped > 0:
        logger.warning(f"Skipped {skipped} games in average discount calculation")

    # Calculate averages
    result = {}
    for date, discounts in sorted(daily_discounts.items()):
        result[date] = {
            "avg_discount": sum(discounts) / len(discounts) if discounts else 0,
            "count": len(discounts)
        }

    return result


def aggregate_games_by_store(games: List[Dict]) -> Dict[str, int]:
    """
    Count games by store (extracted from game_id).
    Returns: {"steam": count, "epic": count, ...}
    """
    store_counts = defaultdict(int)

    for game in games:
        game_id = game.get('game_id', '')
        if '_' in game_id:
            store = game_id.split('_')[0]
            store_counts[store] += 1
        else:
            # Try to get store from title or other field
            title = game.get('title', '')
            if title:
                store_counts['unknown'] += 1

    return dict(store_counts)


def calculate_summary_stats(games: List[Dict]) -> Dict[str, Any]:
    """Calculate summary statistics."""
    total_games = len(games)

    free_games = 0
    discounted_games = 0
    discount_sum = 0
    discount_count = 0

    earliest_date = None
    latest_date = None

    for game in games:
        discount_price = game.get('discount_price')
        original_price = game.get('original_price')
        posted_at = game.get('posted_at')

        # Count free games
        if discount_price == 0 or discount_price is None or discount_price == 0.0:
            free_games += 1
        elif original_price and discount_price:
            try:
                original = float(original_price)
                discount = float(discount_price)
                if discount < original and original > 0:
                    discounted_games += 1
                    discount_pct = ((original - discount) / original) * 100
                    discount_sum += discount_pct
                    discount_count += 1
            except (ValueError, TypeError):
                pass

        # Track date range
        if posted_at:
            try:
                if isinstance(posted_at, str):
                    date = datetime.fromisoformat(posted_at.replace('Z', '+00:00'))
                else:
                    date = posted_at

                if earliest_date is None or date < earliest_date:
                    earliest_date = date
                if latest_date is None or date > latest_date:
                    latest_date = date
            except (ValueError, AttributeError):
                pass

    avg_discount = discount_sum / discount_count if discount_count > 0 else 0

    # Calculate days of data
    days_of_data = 0
    if earliest_date and latest_date:
        days_of_data = (latest_date - earliest_date).days + 1

    avg_games_per_day = total_games / days_of_data if days_of_data > 0 else 0

    return {
        "total_games": total_games,
        "free_games": free_games,
        "discounted_games": discounted_games,
        "avg_discount": round(avg_discount, 1),
        "earliest_date": earliest_date.strftime('%Y-%m-%d') if earliest_date else "N/A",
        "latest_date": latest_date.strftime('%Y-%m-%d') if latest_date else "N/A",
        "days_of_data": days_of_data,
        "avg_games_per_day": round(avg_games_per_day, 1)
    }


def prepare_chart_data(aggregated_data: Dict) -> Dict[str, Any]:
    """Transform aggregated data into Chart.js format."""
    return {
        "free_games_data": {
            "labels": list(aggregated_data['free_games_by_date']['daily'].keys()),
            "values": list(aggregated_data['free_games_by_date']['daily'].values())
        },
        "discount_dist_data": {
            "labels": list(aggregated_data['discount_distribution'].keys()),
            "values": list(aggregated_data['discount_distribution'].values())
        },
        "avg_discount_data": {
            "labels": list(aggregated_data['avg_discount_over_time'].keys()),
            "values": [v['avg_discount'] for v in aggregated_data['avg_discount_over_time'].values()],
            "counts": [v['count'] for v in aggregated_data['avg_discount_over_time'].values()]
        },
        "store_dist_data": {
            "labels": list(aggregated_data['games_by_store'].keys()),
            "values": list(aggregated_data['games_by_store'].values())
        }
    }


def generate_html(stats_data: Dict, template_path: str, output_path: str):
    """Generate HTML from template with stats data."""
    try:
        # Set up Jinja2 environment
        template_dir = os.path.dirname(template_path)
        template_name = os.path.basename(template_path)

        env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )

        # Load template
        template = env.get_template(template_name)

        # Render template
        html = template.render(**stats_data)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Write output
        with open(output_path, 'w') as f:
            f.write(html)

        logger.info(f"Successfully generated HTML at {output_path}")

    except Exception as e:
        logger.error(f"Error generating HTML: {e}")
        sentry_sdk.capture_exception(e)
        raise


@monitor(monitor_slug='gha-stats-generation')
def main():
    """Main entry point for statistics generation."""
    try:
        # Connect to MongoDB
        db = get_mongodb_connection()

        # Fetch all game data
        games = fetch_all_game_data(db)

        if not games:
            logger.warning("No games found in database")
            # Create empty state HTML
            stats_data = {
                "last_updated": datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
                "summary_stats": {
                    "total_games": 0,
                    "free_games": 0,
                    "discounted_games": 0,
                    "avg_discount": 0,
                    "earliest_date": "N/A",
                    "latest_date": "N/A",
                    "days_of_data": 0,
                    "avg_games_per_day": 0
                },
                "free_games_data": {"labels": [], "values": []},
                "discount_dist_data": {"labels": [], "values": []},
                "avg_discount_data": {"labels": [], "values": [], "counts": []},
                "store_dist_data": {"labels": [], "values": []},
                "has_data": False
            }
        else:
            # Aggregate data
            logger.info("Aggregating game data...")
            free_games_by_date = aggregate_free_games_by_date(games)
            discount_distribution = aggregate_discount_distribution(games)
            avg_discount_over_time = aggregate_average_discount_over_time(games)
            games_by_store = aggregate_games_by_store(games)
            summary_stats = calculate_summary_stats(games)

            # Prepare chart data
            aggregated = {
                'free_games_by_date': free_games_by_date,
                'discount_distribution': discount_distribution,
                'avg_discount_over_time': avg_discount_over_time,
                'games_by_store': games_by_store
            }
            chart_data = prepare_chart_data(aggregated)

            # Prepare template data
            stats_data = {
                "last_updated": datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
                "summary_stats": summary_stats,
                "has_data": True,
                **chart_data
            }

        # Generate HTML
        template_path = os.path.join(os.path.dirname(__file__), 'templates', 'dashboard.html')
        output_path = os.path.join(os.path.dirname(__file__), 'build', 'index.html')

        generate_html(stats_data, template_path, output_path)

        logger.info("Statistics generation completed successfully")
        print(f"Generated statistics page at {output_path}")
        print(f"Total games: {stats_data['summary_stats']['total_games']}")
        print(f"Free games: {stats_data['summary_stats']['free_games']}")
        print(f"Average discount: {stats_data['summary_stats']['avg_discount']}%")

    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        sentry_sdk.capture_exception(e)
        raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    main()
