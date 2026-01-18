"""CLI commands for qbit-arr."""

import sys
import logging
from pathlib import Path
from typing import Optional

import click

from qbit_arr.config import get_config
from qbit_arr.core.scanner import MediaScanner
from qbit_arr.cli.formatters import (
    print_scan_results,
    print_orphaned_files,
    print_hardlink_groups,
    print_error,
    print_success,
    create_progress,
    console
)


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.group()
@click.option(
    '--config',
    type=click.Path(exists=True, path_type=Path),
    help='Path to configuration file'
)
@click.pass_context
def cli(ctx: click.Context, config: Optional[Path]) -> None:
    """
    qbit-arr: Media file relationship and orphan detection tool.
    
    Analyzes your qBittorrent, Radarr, and Sonarr setup to show file
    relationships, hardlink status, and identify orphaned files.
    """
    ctx.ensure_object(dict)
    
    try:
        ctx.obj['config'] = get_config(config)
    except Exception as e:
        print_error(f"Failed to load configuration: {e}")
        sys.exit(1)


@cli.command()
@click.option(
    '--detail',
    type=click.Choice(['summary', 'normal', 'full']),
    default='normal',
    help='Level of detail in output'
)
@click.option(
    '--json',
    'output_json',
    is_flag=True,
    help='Output results as JSON'
)
@click.pass_context
def scan(ctx: click.Context, detail: str, output_json: bool) -> None:
    """
    Perform a complete scan of all services and filesystems.
    
    This will scan qBittorrent, Radarr, Sonarr, and your media directories
    to analyze file relationships, detect hardlinks, and identify orphaned files.
    """
    config = ctx.obj['config']
    
    with create_progress() as progress:
        task = progress.add_task("[cyan]Scanning media files...", total=None)
        
        try:
            scanner = MediaScanner(config)
            results = scanner.scan_all()
            progress.update(task, completed=True)
            
        except Exception as e:
            progress.stop()
            print_error(f"Scan failed: {e}")
            logger.exception("Scan failed")
            sys.exit(1)
    
    if output_json:
        import json
        console.print(json.dumps(results.model_dump(mode='json'), indent=2, default=str))
    else:
        print_scan_results(results, detail_level=detail)
    
    print_success("Scan completed successfully")


@cli.command()
@click.option(
    '--json',
    'output_json',
    is_flag=True,
    help='Output results as JSON'
)
@click.pass_context
def orphans(ctx: click.Context, output_json: bool) -> None:
    """
    Find and display orphaned files.
    
    Shows files that exist in your torrent or library directories but are
    not tracked by qBittorrent, Radarr, or Sonarr.
    """
    config = ctx.obj['config']
    
    with create_progress() as progress:
        task = progress.add_task("[cyan]Scanning for orphaned files...", total=None)
        
        try:
            scanner = MediaScanner(config)
            orphaned = scanner.get_orphans_only()
            progress.update(task, completed=True)
            
        except Exception as e:
            progress.stop()
            print_error(f"Orphan scan failed: {e}")
            logger.exception("Orphan scan failed")
            sys.exit(1)
    
    if output_json:
        import json
        console.print(json.dumps(
            [o.model_dump(mode='json') for o in orphaned],
            indent=2,
            default=str
        ))
    else:
        print_orphaned_files(orphaned)


@cli.command()
@click.option(
    '--json',
    'output_json',
    is_flag=True,
    help='Output results as JSON'
)
@click.pass_context
def hardlinks(ctx: click.Context, output_json: bool) -> None:
    """
    Analyze hardlinks between torrent and library directories.
    
    Shows groups of files that are hardlinked together, which is useful
    for understanding cross-seeding and space usage.
    """
    config = ctx.obj['config']
    
    with create_progress() as progress:
        task = progress.add_task("[cyan]Analyzing hardlinks...", total=None)
        
        try:
            scanner = MediaScanner(config)
            groups = scanner.get_hardlinks_only()
            progress.update(task, completed=True)
            
        except Exception as e:
            progress.stop()
            print_error(f"Hardlink analysis failed: {e}")
            logger.exception("Hardlink analysis failed")
            sys.exit(1)
    
    if output_json:
        import json
        console.print(json.dumps(
            [g.model_dump(mode='json') for g in groups],
            indent=2,
            default=str
        ))
    else:
        print_hardlink_groups(groups)


@cli.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """Display configuration information."""
    config = ctx.obj['config']
    
    from rich.table import Table
    from rich import box
    
    table = Table(title="Configuration", box=box.ROUNDED)
    table.add_column("Service", style="cyan")
    table.add_column("Setting", style="yellow")
    table.add_column("Value", style="green")
    
    # qBittorrent
    table.add_row("qBittorrent", "URL", config.qbittorrent.url)
    table.add_row("", "Username", config.qbittorrent.username)
    
    # Radarr
    table.add_row("Radarr", "URL", config.radarr.url)
    table.add_row("", "API Key", "***" if config.radarr.api_key else "[red]Not set[/red]")
    
    # Sonarr
    table.add_row("Sonarr", "URL", config.sonarr.url)
    table.add_row("", "API Key", "***" if config.sonarr.api_key else "[red]Not set[/red]")
    
    # Paths
    table.add_row("Paths", "Torrent Movies", str(config.paths.torrent_movies))
    table.add_row("", "Torrent TV", str(config.paths.torrent_tv))
    table.add_row("", "Library Movies", str(config.paths.library_movies))
    table.add_row("", "Library TV", str(config.paths.library_tv))
    
    console.print(table)


def main() -> None:
    """Main entry point for CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()
