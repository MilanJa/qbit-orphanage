"""Output formatters for CLI using Rich."""

from typing import List

from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

from qbit_arr.core.models import (
    ScanResults,
    OrphanedFile,
    HardlinkGroup,
    FileRelationship,
    ScanStatistics,
)

console = Console()


def format_size(size: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def print_statistics(stats: ScanStatistics) -> None:
    """Print scan statistics in a formatted panel."""
    table = Table(show_header=False, box=box.SIMPLE)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Files", str(stats.total_files))
    table.add_row("Total Size", format_size(stats.total_size))
    table.add_row("Torrent Files", str(stats.torrent_files))
    table.add_row("Library Files", str(stats.library_files))
    table.add_row("Hardlink Groups", str(stats.hardlink_groups))
    table.add_row("Orphaned Files", f"[red]{stats.orphaned_files}[/red]")
    table.add_row("Orphaned Size", f"[red]{format_size(stats.orphaned_size)}[/red]")
    table.add_row("Cross-Seeded Groups", str(stats.cross_seeded_groups))
    table.add_row("Torrents", str(stats.torrents_count))
    table.add_row("Radarr Items", str(stats.radarr_items))
    table.add_row("Sonarr Items", str(stats.sonarr_items))
    table.add_row("Scan Duration", f"{stats.scan_duration:.2f}s")

    console.print(Panel(table, title="[bold]Scan Statistics[/bold]", border_style="blue"))


def print_orphaned_files(orphans: List[OrphanedFile]) -> None:
    """Print orphaned files in a table."""
    if not orphans:
        console.print("[green]No orphaned files found![/green]")
        return

    table = Table(title=f"Orphaned Files ({len(orphans)})", box=box.ROUNDED)
    table.add_column("Location", style="cyan")
    table.add_column("Path", style="yellow")
    table.add_column("Size", style="green", justify="right")
    table.add_column("Reason", style="red")
    table.add_column("Modified", style="magenta")

    for orphan in orphans:
        table.add_row(
            orphan.location,
            str(orphan.path),
            format_size(orphan.size),
            orphan.reason,
            orphan.modified.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


def print_hardlink_groups(groups: List[HardlinkGroup]) -> None:
    """Print hardlink groups in a tree structure."""
    if not groups:
        console.print("[green]No hardlink groups found![/green]")
        return

    console.print(f"\n[bold]Hardlink Groups ({len(groups)})[/bold]\n")

    for i, group in enumerate(groups, 1):
        tree = Tree(
            f"[bold cyan]Group {i}[/bold cyan] "
            f"(inode: {group.inode}, {group.hardlink_count} files, {format_size(group.total_size)})"
        )

        for file_path in group.files:
            tree.add(f"[yellow]{file_path}[/yellow]")

        console.print(tree)
        console.print()


def print_file_relationships(relationships: List[FileRelationship], limit: int = 50) -> None:
    """Print file relationships in a table."""
    if not relationships:
        console.print("[yellow]No file relationships found![/yellow]")
        return

    table = Table(
        title=f"File Relationships (showing {min(limit, len(relationships))} of {len(relationships)})",
        box=box.ROUNDED,
    )
    table.add_column("File", style="yellow", overflow="fold")
    table.add_column("Size", style="green", justify="right")
    table.add_column("Hardlinks", style="cyan", justify="center")
    table.add_column("Torrents", style="blue", justify="center")
    table.add_column("Arr Services", style="magenta", justify="center")
    table.add_column("Orphaned", style="red", justify="center")

    for rel in relationships[:limit]:
        orphaned = "✓" if rel.is_orphaned else ""
        table.add_row(
            str(rel.file_path.name),
            format_size(rel.size),
            str(rel.hardlink_count),
            str(len(rel.torrents)),
            ", ".join(rel.arr_services) if rel.arr_services else "-",
            orphaned,
        )

    console.print(table)

    if len(relationships) > limit:
        console.print(f"\n[dim]... and {len(relationships) - limit} more files[/dim]")


def print_scan_results(results: ScanResults, detail_level: str = "summary") -> None:
    """
    Print complete scan results.

    Args:
        results: Scan results to print
        detail_level: 'summary', 'normal', or 'full'
    """
    console.print("\n")
    console.print(
        Panel.fit("[bold green]qbit-arr Media Scanner[/bold green]", border_style="green")
    )
    console.print()

    # Always show statistics
    print_statistics(results.statistics)
    console.print()

    if detail_level == "summary":
        return

    # Show orphaned files
    if results.orphaned_files:
        print_orphaned_files(results.orphaned_files)
        console.print()

    if detail_level == "normal":
        return

    # Full detail: show hardlinks and relationships
    if results.hardlink_groups:
        print_hardlink_groups(results.hardlink_groups[:10])  # Limit to first 10

    if results.file_relationships:
        console.print()
        print_file_relationships(results.file_relationships, limit=50)


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[bold yellow]Warning:[/bold yellow] {message}")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[bold green]✓[/bold green] {message}")


def create_progress() -> Progress:
    """Create a progress bar for long-running operations."""
    return Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    )
