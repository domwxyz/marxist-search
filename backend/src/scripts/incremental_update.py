#!/usr/bin/env python3
"""
Incremental update script for systemd timer / cron.

This script:
1. Fetches new articles from RSS feeds (stops after N consecutive duplicates)
2. Indexes new articles into txtai index
3. Logs results

Usage:
    python -m src.scripts.incremental_update

Environment:
    Can be run via systemd timer (every 30 minutes) or cron
"""

import asyncio
import sys
import logging
from pathlib import Path
from datetime import datetime, UTC

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.search_config import (
    DATABASE_PATH,
    RSS_FEEDS_CONFIG,
    INDEX_PATH,
    TERMS_CONFIG,
    LOG_LEVEL,
    CHUNKING_CONFIG
)
from src.ingestion.archiving_service import run_update as run_archiving_update
from src.ingestion.database import init_database
from src.indexing.indexing_service import update_index

# Configure logging
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/marxist-search/ingestion.log')
        if Path('/var/log/marxist-search').exists()
        else logging.StreamHandler(),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def _trigger_api_reload(api_url: str = "http://localhost:8000", timeout: int = 30) -> bool:
    """
    Trigger the API to reload its in-memory index.

    Args:
        api_url: Base URL of the API
        timeout: Request timeout in seconds

    Returns:
        True if reload was successful, False otherwise
    """
    try:
        import requests

        reload_url = f"{api_url}/api/v1/reload-index"
        logger.info(f"Sending reload request to {reload_url}...")

        response = requests.post(reload_url, timeout=timeout)

        if response.status_code == 200:
            data = response.json()
            logger.info(
                f"Reload successful: {data.get('old_count', 0)} -> {data.get('new_count', 0)} "
                f"documents ({data.get('documents_added', 0):+d} change)"
            )
            return True
        else:
            logger.warning(f"API returned status {response.status_code}: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        logger.warning(f"Could not connect to API at {api_url} (API may not be running)")
        return False
    except Exception as e:
        logger.warning(f"Error triggering API reload: {e}")
        return False


async def main():
    """
    Run incremental update: archive new articles and update index.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    start_time = datetime.now(UTC)
    logger.info("=" * 80)
    logger.info("Starting incremental update process")
    logger.info(f"Timestamp: {start_time.isoformat()}")
    logger.info("=" * 80)

    try:
        # Step 1: Initialize database
        logger.info("Initializing database...")
        init_database(DATABASE_PATH)
        logger.info("Database initialized")

        # Step 2: Fetch new articles from RSS feeds
        logger.info("\n--- STEP 1: Fetching new articles from RSS feeds ---")
        archive_stats = await run_archiving_update(
            db_path=DATABASE_PATH,
            rss_config_path=RSS_FEEDS_CONFIG,
            max_consecutive_duplicates=5,  # Stop after 5 consecutive duplicates
            terms_config_path=TERMS_CONFIG
        )

        logger.info("Archive update complete:")
        logger.info(f"  - Feeds processed: {archive_stats.get('feeds_processed', 0)}")
        logger.info(f"  - Feeds failed: {archive_stats.get('feeds_failed', 0)}")
        logger.info(f"  - New articles saved: {archive_stats.get('articles_saved', 0)}")
        logger.info(f"  - Duplicates found: {archive_stats.get('duplicates', 0)}")
        logger.info(f"  - Duration: {archive_stats.get('duration_seconds', 0):.2f}s")

        # Step 3: Update txtai index with new articles
        if archive_stats.get('articles_saved', 0) > 0:
            logger.info("\n--- STEP 2: Updating txtai index with new articles ---")
            index_stats = update_index(
                db_path=DATABASE_PATH,
                index_path=INDEX_PATH,
                chunk_threshold=CHUNKING_CONFIG['threshold_words'],
                chunk_size=CHUNKING_CONFIG['chunk_size_words'],
                overlap=CHUNKING_CONFIG['overlap_words']
            )

            if 'error' in index_stats:
                logger.error(f"Index update error: {index_stats['error']}")
            else:
                logger.info("Index update complete:")
                logger.info(f"  - Articles processed: {index_stats.get('articles_processed', 0)}")
                logger.info(f"  - Articles chunked: {index_stats.get('articles_chunked', 0)}")
                logger.info(f"  - Chunks created: {index_stats.get('chunks_created', 0)}")
                logger.info(f"  - Total indexed: {index_stats.get('total_indexed', 0)}")
                logger.info(f"  - Duration: {index_stats.get('duration_seconds', 0):.2f}s")

            # Step 4: Trigger index reload in the API
            logger.info("\n--- STEP 3: Reloading index in running API ---")
            reload_success = _trigger_api_reload()
            if reload_success:
                logger.info("API index reloaded successfully")
            else:
                logger.warning("Failed to reload API index (API may not be running)")
        else:
            logger.info("\n--- STEP 2: Skipped (no new articles to index) ---")

        # Calculate total duration
        end_time = datetime.now(UTC)
        total_duration = (end_time - start_time).total_seconds()

        logger.info("\n" + "=" * 80)
        logger.info("Incremental update completed successfully")
        logger.info(f"Total duration: {total_duration:.2f}s")
        logger.info(f"New articles added: {archive_stats.get('articles_saved', 0)}")
        logger.info("=" * 80)

        return 0

    except Exception as e:
        logger.error(f"Error during incremental update: {e}", exc_info=True)
        logger.error("=" * 80)
        logger.error("Incremental update FAILED")
        logger.error("=" * 80)
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
