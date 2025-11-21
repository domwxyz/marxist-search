"""
Marxist Search CLI - General purpose command-line interface.

Commands:
- archive: Archive articles from RSS feeds
- index: Build txtai vector index from archived articles
- search: Search the indexed articles (TODO)
- stats: Display database and index statistics
"""

# Load environment variables before any other imports
# This ensures production paths are available to config modules
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists (for production paths)
env_path = Path(__file__).parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

# Standard library imports
import asyncio
import sys
import logging

# Third-party imports
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import print as rprint

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.search_config import DATABASE_PATH, RSS_FEEDS_CONFIG, INDEX_PATH, TERMS_CONFIG, LOG_LEVEL
from src.ingestion.archiving_service import run_archiving, ArchivingService, run_update as run_archiving_update
from src.ingestion.database import init_database

console = Console()

# Configure logging
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@click.group()
def cli():
    """Marxist Search CLI - Manage archiving, indexing, and search."""
    pass


# ============================================================================
# Archive Commands
# ============================================================================

@cli.group()
def archive():
    """Archive articles from RSS feeds."""
    pass


@archive.command(name='run')
@click.option('--feed-url', '-f', help='Specific feed URL to archive (optional)')
@click.option('--db-path', '-d', default=DATABASE_PATH, help='Database path')
@click.option('--config', '-c', default=RSS_FEEDS_CONFIG, help='RSS feeds config path')
def archive_run(feed_url, db_path, config):
    """
    Archive articles from RSS feeds.

    If --feed-url is provided, only that feed will be processed.
    Otherwise, all configured feeds will be processed.
    """
    console.print("\n[bold cyan]Marxist Search - Archiving Service[/bold cyan]\n")

    # Initialize database
    console.print("[yellow]Initializing database...[/yellow]")
    init_database(db_path)
    console.print("[green]✓[/green] Database initialized\n")

    # Run archiving
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        if feed_url:
            task = progress.add_task(f"Archiving feed: {feed_url}", total=None)
        else:
            task = progress.add_task("Archiving all feeds...", total=None)

        # Run async archiving
        stats = asyncio.run(run_archiving(db_path, config, feed_url, TERMS_CONFIG))

        progress.remove_task(task)

    # Display results
    console.print("\n[bold green]Archiving Complete![/bold green]\n")

    if 'error' in stats:
        console.print(f"[red]Error: {stats['error']}[/red]")
        return

    # Create results table
    if feed_url:
        # Single feed results
        table = Table(title="Archiving Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Feed", stats.get('feed', 'Unknown'))
        table.add_row("Entries Fetched", str(stats.get('entries', 0)))
        table.add_row("Articles Extracted", str(stats.get('extracted', 0)))
        table.add_row("Articles Saved", str(stats.get('saved', 0)))
        table.add_row("Duplicates", str(stats.get('duplicates', 0)))
        table.add_row("Duration", f"{stats.get('duration_seconds', 0):.2f}s")

        console.print(table)
    else:
        # All feeds results
        table = Table(title="Overall Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Feeds Processed", str(stats.get('feeds_processed', 0)))
        table.add_row("Feeds Failed", str(stats.get('feeds_failed', 0)))
        table.add_row("Total Entries", str(stats.get('total_entries', 0)))
        table.add_row("Articles Extracted", str(stats.get('articles_extracted', 0)))
        table.add_row("Articles Saved", str(stats.get('articles_saved', 0)))
        table.add_row("Duplicates", str(stats.get('duplicates', 0)))
        table.add_row("Duration", f"{stats.get('duration_seconds', 0):.2f}s")

        console.print(table)

        # Feed-specific details
        if stats.get('feed_details'):
            console.print("\n[bold]Feed Details:[/bold]\n")

            details_table = Table()
            details_table.add_column("Feed", style="cyan")
            details_table.add_column("Entries", justify="right")
            details_table.add_column("Extracted", justify="right")
            details_table.add_column("Saved", justify="right", style="green")
            details_table.add_column("Duplicates", justify="right", style="yellow")

            for feed_name, details in stats['feed_details'].items():
                details_table.add_row(
                    feed_name,
                    str(details['entries']),
                    str(details['extracted']),
                    str(details['saved']),
                    str(details['duplicates'])
                )

            console.print(details_table)

    console.print()


@archive.command(name='list')
@click.option('--config', '-c', default=RSS_FEEDS_CONFIG, help='RSS feeds config path')
def archive_list(config):
    """List all configured RSS feeds."""
    console.print("\n[bold cyan]Configured RSS Feeds[/bold cyan]\n")

    try:
        from src.ingestion.rss_fetcher import load_feed_configs

        feeds = load_feed_configs(config)

        if not feeds:
            console.print("[yellow]No feeds configured[/yellow]\n")
            return

        table = Table()
        table.add_column("Name", style="cyan")
        table.add_column("URL", style="blue")
        table.add_column("Pagination", style="green")
        table.add_column("Organization", style="yellow")

        for url, feed_config in feeds.items():
            table.add_row(
                feed_config.get('name', 'Unknown'),
                url,
                feed_config.get('pagination_type', 'standard'),
                feed_config.get('organization', 'N/A')
            )

        console.print(table)
        console.print(f"\n[green]Total feeds: {len(feeds)}[/green]\n")

    except Exception as e:
        console.print(f"[red]Error loading feeds: {e}[/red]\n")


@archive.command(name='update')
@click.option('--db-path', '-d', default=DATABASE_PATH, help='Database path')
@click.option('--config', '-c', default=RSS_FEEDS_CONFIG, help='RSS feeds config path')
@click.option('--duplicates', default=5, type=int, help='Stop after N consecutive duplicates')
def archive_update(db_path, config, duplicates):
    """
    Incremental update: fetch only new articles from RSS feeds.

    This is much faster than 'archive run' because it stops fetching
    from each feed after finding N consecutive articles that already
    exist in the database (default: 5).

    Use this for regular updates (e.g., every 30 minutes via systemd/cron).
    """
    console.print("\n[bold cyan]Marxist Search - Incremental Update[/bold cyan]\n")

    # Initialize database
    console.print("[yellow]Initializing database...[/yellow]")
    init_database(db_path)
    console.print("[green]✓[/green] Database initialized\n")

    # Run incremental update
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Checking feeds for new articles...", total=None)

        # Run async update
        stats = asyncio.run(run_archiving_update(db_path, config, duplicates, TERMS_CONFIG))

        progress.remove_task(task)

    # Display results
    console.print("\n[bold green]Incremental Update Complete![/bold green]\n")

    if 'error' in stats:
        console.print(f"[red]Error: {stats['error']}[/red]")
        return

    # Create results table
    table = Table(title="Update Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Feeds Processed", str(stats.get('feeds_processed', 0)))
    table.add_row("Feeds Failed", str(stats.get('feeds_failed', 0)))
    table.add_row("New Entries Found", str(stats.get('total_entries', 0)))
    table.add_row("Articles Extracted", str(stats.get('articles_extracted', 0)))
    table.add_row("Articles Saved", str(stats.get('articles_saved', 0)))
    table.add_row("Duplicates", str(stats.get('duplicates', 0)))
    table.add_row("Duration", f"{stats.get('duration_seconds', 0):.2f}s")

    console.print(table)

    # Feed-specific details
    if stats.get('feed_details'):
        console.print("\n[bold]Feed Details:[/bold]\n")

        details_table = Table()
        details_table.add_column("Feed", style="cyan")
        details_table.add_column("New Entries", justify="right")
        details_table.add_column("Extracted", justify="right")
        details_table.add_column("Saved", justify="right", style="green")
        details_table.add_column("Duplicates", justify="right", style="yellow")

        for feed_name, details in stats['feed_details'].items():
            details_table.add_row(
                feed_name,
                str(details['entries']),
                str(details['extracted']),
                str(details['saved']),
                str(details['duplicates'])
            )

        console.print(details_table)

    console.print()


# ============================================================================
# Index Commands
# ============================================================================

@cli.group()
def index():
    """Build and manage the txtai vector index."""
    pass


@index.command(name='build')
@click.option('--db-path', '-d', default=DATABASE_PATH, help='Database path')
@click.option('--index-path', '-i', default=INDEX_PATH, help='Index path')
@click.option('--force', '-f', is_flag=True, help='Force rebuild of existing index')
def index_build(db_path, index_path, force):
    """
    Build txtai vector index from archived articles.

    This will:
    1. Load articles from the database
    2. Chunk long articles (>3500 words)
    3. Generate embeddings using bge-small-en-v1.5
    4. Build and save the txtai index
    """
    from src.indexing.indexing_service import build_index

    console.print("\n[bold cyan]Marxist Search - Index Building[/bold cyan]\n")

    try:
        stats = build_index(db_path, index_path, force=force)

        console.print("\n[bold green]Index Building Complete![/bold green]\n")

        # Display results
        table = Table(title="Index Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Articles Processed", str(stats.get('articles_processed', 0)))
        table.add_row("Articles Chunked", str(stats.get('articles_chunked', 0)))
        table.add_row("Total Chunks Created", str(stats.get('chunks_created', 0)))
        table.add_row("Total Indexed Items", str(stats.get('total_indexed', 0)))
        table.add_row("Duration", f"{stats.get('duration_seconds', 0):.2f}s")

        console.print(table)
        console.print()

    except Exception as e:
        console.print(f"\n[red]Error building index: {e}[/red]\n")
        if LOG_LEVEL == "DEBUG":
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)


@index.command(name='update')
@click.option('--db-path', '-d', default=DATABASE_PATH, help='Database path')
@click.option('--index-path', '-i', default=INDEX_PATH, help='Index path')
def index_update(db_path, index_path):
    """
    Incrementally update txtai index with new articles.

    This will:
    1. Load only unindexed articles (indexed=0) from database
    2. Chunk long articles if needed
    3. Add new documents to existing index (no rebuild)
    4. Mark articles as indexed

    Much faster than full rebuild for regular updates.
    Use this after 'archive update' to make new articles searchable.
    """
    from src.indexing.indexing_service import update_index

    console.print("\n[bold cyan]Marxist Search - Index Update[/bold cyan]\n")

    try:
        # Run incremental index update
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Updating index with new articles...", total=None)

            stats = update_index(db_path, index_path)

            progress.remove_task(task)

        console.print("\n[bold green]Index Update Complete![/bold green]\n")

        # Check for errors
        if 'error' in stats:
            console.print(f"[yellow]{stats['error']}[/yellow]")
            console.print()
            return

        # Display results
        table = Table(title="Update Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Articles Processed", str(stats.get('articles_processed', 0)))
        table.add_row("Articles Chunked", str(stats.get('articles_chunked', 0)))
        table.add_row("Total Chunks Created", str(stats.get('chunks_created', 0)))
        table.add_row("Total Indexed Items", str(stats.get('total_indexed', 0)))
        table.add_row("Duration", f"{stats.get('duration_seconds', 0):.2f}s")

        console.print(table)
        console.print()

    except Exception as e:
        console.print(f"\n[red]Error updating index: {e}[/red]\n")
        if LOG_LEVEL == "DEBUG":
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)


@index.command(name='info')
@click.option('--index-path', '-i', default=INDEX_PATH, help='Index path')
def index_info(index_path):
    """Display information about the txtai index."""
    from src.indexing.txtai_manager import TxtaiManager

    console.print("\n[bold cyan]Index Information[/bold cyan]\n")

    try:
        manager = TxtaiManager(index_path)

        if not manager.index_exists():
            console.print("[yellow]No index found. Run 'index build' first.[/yellow]\n")
            return

        info = manager.get_index_info()

        table = Table(title="txtai Index Info")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Index Path", str(info.get('path', 'N/A')))
        table.add_row("Status", info.get('status', 'Unknown'))
        table.add_row("Total Documents", str(info.get('count', 0)))

        console.print(table)
        console.print()

    except Exception as e:
        console.print(f"[red]Error loading index info: {e}[/red]\n")


# ============================================================================
# Search Commands
# ============================================================================

@cli.command()
@click.argument('query')
@click.option('--source', '-s', help='Filter by article source')
@click.option('--author', '-a', help='Filter by article author')
@click.option('--date-range', '-d', help='Date range: past_week, past_month, past_3months, past_year, 2020s, 2010s, 2000s, 1990s')
@click.option('--start-date', help='Custom start date (YYYY-MM-DD)')
@click.option('--end-date', help='Custom end date (YYYY-MM-DD)')
@click.option('--limit', '-l', default=10, type=int, help='Maximum results to return')
@click.option('--db-path', default=DATABASE_PATH, help='Database path')
@click.option('--index-path', default=INDEX_PATH, help='Index path')
def search(query, source, author, date_range, start_date, end_date, limit, db_path, index_path):
    """
    Search the indexed articles.

    Example usage:
        marxist_cli search "climate change"
        marxist_cli search "revolution" --source "In Defence of Marxism"
        marxist_cli search "capitalism" --date-range past_year --limit 20
        marxist_cli search "imperialism" --author "Alan Woods"
    """
    from src.search.search_engine import SearchEngine

    console.print(f"\n[bold cyan]Searching for:[/bold cyan] '{query}'\n")

    try:
        # Initialize search engine
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Loading search index...", total=None)

            engine = SearchEngine(index_path=index_path, db_path=db_path)
            engine.load_index()

            progress.remove_task(task)

        # Build filters
        filters = {}
        if source:
            filters['source'] = source
        if author:
            filters['author'] = author
        if date_range:
            filters['date_range'] = date_range
        if start_date:
            filters['start_date'] = start_date
        if end_date:
            filters['end_date'] = end_date

        # Display active filters
        if filters:
            console.print("[bold]Active filters:[/bold]")
            for key, value in filters.items():
                console.print(f"  • {key}: {value}")
            console.print()

        # Execute search
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Searching...", total=None)

            results = engine.search(query=query, filters=filters, limit=limit)

            progress.remove_task(task)

        # Display results
        console.print(f"[bold green]Found {results['total']} articles[/bold green] (showing {len(results['results'])})\n")
        console.print(f"Query time: {results['query_time_ms']}ms\n")

        if not results['results']:
            console.print("[yellow]No results found. Try adjusting your query or filters.[/yellow]\n")
            return

        # Results table
        for i, result in enumerate(results['results'], 1):
            console.print(f"[bold cyan]{i}. {result['title']}[/bold cyan]")
            console.print(f"   [dim]{result['source']} • {result['author']} • {result['published_date']}[/dim]")
            console.print(f"   [green]Score: {result['score']:.4f}[/green]", end="")

            if result.get('matched_sections', 1) > 1:
                console.print(f" [yellow]({result['matched_sections']} sections matched)[/yellow]", end="")

            if result.get('recency_boost'):
                console.print(f" [blue]+{result['recency_boost']:.2f} recency boost[/blue]", end="")

            console.print()

            # Excerpt
            excerpt = result['excerpt']
            if len(excerpt) > 150:
                excerpt = excerpt[:150] + "..."
            console.print(f"   {excerpt}")

            # URL
            console.print(f"   [link={result['url']}]{result['url']}[/link]")
            console.print()

        # Pagination info
        if results['total'] > limit:
            console.print(f"[dim]Showing results 1-{len(results['results'])} of {results['total']} total[/dim]")
            console.print(f"[dim]Use --limit to see more results[/dim]\n")

        # Cleanup
        engine.close()

    except FileNotFoundError:
        console.print("[red]Index not found. Run 'index build' first.[/red]\n")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Search error: {e}[/red]\n")
        if LOG_LEVEL == "DEBUG":
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)


# ============================================================================
# Database Commands
# ============================================================================

@cli.command()
@click.option('--db-path', '-d', default=DATABASE_PATH, help='Database path')
def init_db(db_path):
    """Initialize the database schema."""
    console.print("\n[bold cyan]Initializing Database[/bold cyan]\n")

    try:
        db = init_database(db_path)
        console.print(f"[green]✓[/green] Database initialized at: {db_path}")
        console.print("[green]✓[/green] Schema created successfully\n")
    except Exception as e:
        console.print(f"[red]Error initializing database: {e}[/red]\n")
        sys.exit(1)


@cli.command()
@click.option('--db-path', '-d', default=DATABASE_PATH, help='Database path')
@click.option('--config', '-c', default=RSS_FEEDS_CONFIG, help='RSS feeds config path')
@click.option('--index-path', '-i', default=INDEX_PATH, help='Index path')
def stats(db_path, config, index_path):
    """Display comprehensive statistics."""
    console.print("\n[bold cyan]Marxist Search Statistics[/bold cyan]\n")

    # Archive stats
    service = ArchivingService(db_path, config, terms_config_path=TERMS_CONFIG)

    try:
        statistics = service.get_statistics()

        # Overall stats
        table = Table(title="Archive Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Articles", str(statistics['total_articles']))
        table.add_row("Configured Feeds", str(statistics['feeds_configured']))

        console.print(table)

        # Recent articles
        if statistics['recent_articles']:
            console.print("\n[bold]Recent Articles:[/bold]\n")

            recent_table = Table()
            recent_table.add_column("Title", style="cyan", max_width=50)
            recent_table.add_column("Source", style="yellow")
            recent_table.add_column("Author", style="green")
            recent_table.add_column("Date", style="blue")

            for article in statistics['recent_articles']:
                recent_table.add_row(
                    article['title'][:47] + "..." if len(article['title']) > 50 else article['title'],
                    article['source'],
                    article['author'] or "Unknown",
                    article['published_date']
                )

            console.print(recent_table)

    finally:
        service.close()

    # Index stats
    try:
        from src.indexing.txtai_manager import TxtaiManager

        manager = TxtaiManager(index_path)

        if manager.index_exists():
            console.print("\n")
            info = manager.get_index_info()

            index_table = Table(title="Index Statistics")
            index_table.add_column("Metric", style="cyan")
            index_table.add_column("Value", style="green")

            index_table.add_row("Index Status", info.get('status', 'Unknown'))
            index_table.add_row("Indexed Documents", str(info.get('count', 0)))

            console.print(index_table)
        else:
            console.print("\n[yellow]No index built yet. Run 'index build' to create one.[/yellow]")

    except Exception as e:
        console.print(f"\n[yellow]Could not load index stats: {e}[/yellow]")

    console.print()


if __name__ == '__main__':
    cli()
