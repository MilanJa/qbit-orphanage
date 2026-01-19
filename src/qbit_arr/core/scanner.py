"""Core scanner service that orchestrates all data collection."""

from pathlib import Path
from typing import Dict, List, Set
import time
import logging
import re
from collections import defaultdict

from qbit_arr.config import Config
from qbit_arr.api.qbit_client import QBittorrentClient
from qbit_arr.api.radarr_client import RadarrClient
from qbit_arr.api.sonarr_client import SonarrClient
from qbit_arr.core.hardlink import HardlinkDetector
from qbit_arr.core.models import (
    ScanResults,
    FileRelationship,
    OrphanedFile,
    CrossSeedGroup,
    TorrentInfo,
)

logger = logging.getLogger(__name__)

# Patterns for files to skip during scanning
SKIP_PATTERNS = [
    r"(?i)sample",  # Sample files
    r"(?i)\.nfo$",  # NFO metadata files
    r"(?i)\.txt$",  # Text files
    r"(?i)\.srt$",  # Subtitle files
    r"(?i)\.sub$",  # Subtitle files
    r"(?i)\.idx$",  # Subtitle index files
    r"(?i)\.jpg$",  # Image files
    r"(?i)\.jpeg$",  # Image files
    r"(?i)\.png$",  # Image files
    r"(?i)\.gif$",  # Image files
    r"(?i)\.bmp$",  # Image files
    r"(?i)[/\\]subs?[/\\]",  # Subtitle directories (Windows and Unix paths)
    r"(?i)[/\\]extras?[/\\]",  # Extras directories
    r"(?i)[/\\]featurettes?[/\\]",  # Featurette directories
    r"(?i)[/\\]behind[\s-]*the[\s-]*scenes?[/\\]",  # BTS directories
    r"(?i)[/\\]deleted[\s-]*scenes?[/\\]",  # Deleted scenes
    r"(?i)trailer",  # Trailer files
    r"(?i)\bproof\b",  # Proof files
    r"(?i)\.srr$",  # SRR files
]

# Minimum file size for valid media files (100MB)
MIN_MEDIA_SIZE = 100 * 1024 * 1024


def should_skip_file(file_path: Path) -> bool:
    """Check if a file should be skipped based on patterns."""
    file_path_str = str(file_path)
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, file_path_str):
            return True
    return False


def is_valid_media_file(file_path: Path, file_size: int) -> bool:
    """Check if a file is a valid media file for processing."""
    if should_skip_file(file_path):
        return False

    # Check if file size is above minimum threshold
    if file_size < MIN_MEDIA_SIZE:
        return False

    # Check if it's a video file
    video_extensions = {".mkv", ".mp4", ".avi", ".m2ts", ".ts", ".mov", ".wmv", ".flv", ".webm"}
    if file_path.suffix.lower() not in video_extensions:
        return False

    return True


def classify_files(files: List) -> Dict[str, List]:
    """Classify files into main content, samples, and extras."""
    result = {
        "main_files": [],
        "samples": [],
        "extras": [],
        "skipped": [],
    }

    for file in files:
        file_path_str = str(file.path)

        # Check if it's a sample file
        if re.search(r"(?i)sample", file_path_str):
            result["samples"].append(file)
        # Check if it should be skipped (subtitles, images, etc.)
        elif should_skip_file(file.path):
            result["skipped"].append(file)
        # Check if it's too small to be a main media file
        elif file.size < MIN_MEDIA_SIZE:
            result["extras"].append(file)
        else:
            result["main_files"].append(file)

    return result


class MediaScanner:
    """Main scanner service that coordinates all data collection and analysis."""

    def __init__(self, config: Config):
        """Initialize the media scanner."""
        self.config = config
        self.qbit_client = QBittorrentClient(config.qbittorrent, config.paths)
        self.radarr_client = RadarrClient(config.radarr, config.paths)
        self.sonarr_client = SonarrClient(config.sonarr, config.paths)
        self.hardlink_detector = HardlinkDetector()

    def scan_all(self) -> ScanResults:
        """
        Perform a complete scan of all services and filesystems.

        Returns:
            Complete scan results with all relationships and statistics
        """
        logger.info("Starting complete system scan")
        start_time = time.time()

        results = ScanResults()

        try:
            # 1. Collect data from all sources
            logger.info("Fetching data from qBittorrent...")
            results.torrents = self.qbit_client.get_torrents()
            results.statistics.torrents_count = len(results.torrents)

            logger.info("Fetching data from Radarr...")
            results.radarr_media = self.radarr_client.get_movies()
            results.statistics.radarr_items = len(results.radarr_media)

            logger.info("Fetching data from Sonarr...")
            results.sonarr_media = self.sonarr_client.get_series()
            results.statistics.sonarr_items = len(results.sonarr_media)

            # 2. Scan filesystems
            logger.info("Scanning torrent directories...")
            torrent_files_raw = []
            for path in [self.config.paths.torrent_movies, self.config.paths.torrent_tv]:
                if path.exists():
                    files = self.hardlink_detector.scan_directory(path)
                    torrent_files_raw.extend(files)

            # Classify torrent files
            torrent_classified = classify_files(torrent_files_raw)
            torrent_files = torrent_classified["main_files"]
            logger.info(
                f"Torrent files: {len(torrent_files)} main, "
                f"{len(torrent_classified['samples'])} samples, "
                f"{len(torrent_classified['extras'])} extras, "
                f"{len(torrent_classified['skipped'])} skipped"
            )
            results.statistics.torrent_files = len(torrent_files)

            logger.info("Scanning library directories...")
            library_files_raw = []
            for path in [self.config.paths.library_movies, self.config.paths.library_tv]:
                if path.exists():
                    files = self.hardlink_detector.scan_directory(path)
                    library_files_raw.extend(files)

            # Classify library files
            library_classified = classify_files(library_files_raw)
            library_files = library_classified["main_files"]
            logger.info(
                f"Library files: {len(library_files)} main, "
                f"{len(library_classified['samples'])} samples, "
                f"{len(library_classified['extras'])} extras, "
                f"{len(library_classified['skipped'])} skipped"
            )
            results.statistics.library_files = len(library_files)

            # 3. Detect hardlinks
            logger.info("Analyzing hardlinks...")
            results.hardlink_groups = self.hardlink_detector.get_hardlink_groups()
            results.statistics.hardlink_groups = len(results.hardlink_groups)

            # Build inode mapping for quick lookups
            for group in results.hardlink_groups:
                results.inode_to_files[group.inode] = group.files

            # 4. Build file relationships
            logger.info("Building file relationships...")
            results.file_relationships = self._build_file_relationships(
                results.torrents,
                results.radarr_media,
                results.sonarr_media,
                torrent_files + library_files,
            )

            # 5. Build torrent hash map for quick lookups
            results.torrent_hash_map = {t.hash: t for t in results.torrents}

            # 6. Detect orphaned files
            logger.info("Detecting orphaned files...")
            results.orphaned_files = self._find_orphaned_files(
                torrent_files,
                library_files,
                results.torrents,
                results.radarr_media,
                results.sonarr_media,
            )
            results.statistics.orphaned_files = len(results.orphaned_files)
            results.statistics.orphaned_size = sum(f.size for f in results.orphaned_files)

            # 7. Calculate statistics
            all_files = torrent_files + library_files
            results.statistics.total_files = len(all_files)
            results.statistics.total_size = sum(f.size for f in all_files)

            # 8. Find cross-seed groups
            results.statistics.cross_seeded_groups = len(
                self._find_cross_seed_groups(results.torrents)
            )

            # 9. Record scan duration
            results.statistics.scan_duration = time.time() - start_time

            logger.info(f"Scan completed in {results.statistics.scan_duration:.2f}s")
            logger.info(
                f"Found {results.statistics.total_files} files, "
                f"{results.statistics.orphaned_files} orphaned"
            )

            return results

        except Exception as e:
            logger.error(f"Error during scan: {e}", exc_info=True)
            raise

    def _build_file_relationships(
        self, torrents: List[TorrentInfo], radarr_media: List, sonarr_media: List, all_files: List
    ) -> List[FileRelationship]:
        """Build relationships between files, torrents, and arr services."""
        relationships: Dict[Path, FileRelationship] = {}

        # Process torrent files
        for torrent in torrents:
            for tfile in torrent.files:
                if tfile.path not in relationships:
                    file_info = next((f for f in all_files if f.path == tfile.path), None)
                    if file_info:
                        relationships[tfile.path] = FileRelationship(
                            file_path=tfile.path,
                            size=tfile.size,
                            inode=file_info.inode,
                            hardlink_count=file_info.hardlink_count,
                            hardlinked_files=self.hardlink_detector.get_hardlinks_for_file(
                                tfile.path
                            ),
                        )

                if tfile.path in relationships:
                    relationships[tfile.path].torrents.append(torrent.hash)

        # Process Radarr files
        for media in radarr_media:
            if media.file_path and media.file_path in relationships:
                relationships[media.file_path].arr_services.append("radarr")
            elif media.file_path:
                file_info = next((f for f in all_files if f.path == media.file_path), None)
                if file_info:
                    relationships[media.file_path] = FileRelationship(
                        file_path=media.file_path,
                        size=file_info.size,
                        inode=file_info.inode,
                        hardlink_count=file_info.hardlink_count,
                        hardlinked_files=self.hardlink_detector.get_hardlinks_for_file(
                            media.file_path
                        ),
                        arr_services=["radarr"],
                    )

        # Process Sonarr files
        try:
            sonarr_files = self.sonarr_client.get_episode_files()
            for file_path in sonarr_files:
                if file_path in relationships:
                    relationships[file_path].arr_services.append("sonarr")
                else:
                    file_info = next((f for f in all_files if f.path == file_path), None)
                    if file_info:
                        relationships[file_path] = FileRelationship(
                            file_path=file_path,
                            size=file_info.size,
                            inode=file_info.inode,
                            hardlink_count=file_info.hardlink_count,
                            hardlinked_files=self.hardlink_detector.get_hardlinks_for_file(
                                file_path
                            ),
                            arr_services=["sonarr"],
                        )
        except Exception as e:
            logger.warning(f"Could not get Sonarr episode files: {e}")

        return list(relationships.values())

    def _find_orphaned_files(
        self,
        torrent_files: List,
        library_files: List,
        torrents: List[TorrentInfo],
        radarr_media: List,
        sonarr_media: List,
    ) -> List[OrphanedFile]:
        """Find files that are not tracked by any service."""
        orphaned = []

        # Get all files tracked by torrents
        torrent_tracked_paths: Set[Path] = set()
        for torrent in torrents:
            for tfile in torrent.files:
                torrent_tracked_paths.add(tfile.path)

        # Get all files tracked by Radarr
        radarr_tracked_paths = {m.file_path for m in radarr_media if m.file_path}

        # Get all files tracked by Sonarr
        sonarr_tracked_paths = set()
        try:
            sonarr_tracked_paths = set(self.sonarr_client.get_episode_files())
        except Exception as e:
            logger.warning(f"Could not get Sonarr files for orphan detection: {e}")

        # Check torrent directory files
        for file in torrent_files:
            if file.path not in torrent_tracked_paths:
                orphaned.append(
                    OrphanedFile(
                        path=file.path,
                        size=file.size,
                        location="torrent",
                        reason="Not tracked by any torrent",
                        modified=file.modified,
                    )
                )

        # Check library directory files
        # Note: Files are already filtered by classify_files(), so we only have main media files here
        for file in library_files:
            if file.path not in radarr_tracked_paths and file.path not in sonarr_tracked_paths:
                orphaned.append(
                    OrphanedFile(
                        path=file.path,
                        size=file.size,
                        location="library",
                        reason="Not tracked by Radarr or Sonarr",
                        modified=file.modified,
                    )
                )

        return orphaned

    def _find_cross_seed_groups(self, torrents: List[TorrentInfo]) -> List[CrossSeedGroup]:
        """Find groups of torrents that share the same files (cross-seeding)."""
        # Group torrents by their file paths
        file_to_torrents: Dict[frozenset, List[TorrentInfo]] = defaultdict(list)

        for torrent in torrents:
            if torrent.files:
                file_paths = frozenset(f.path for f in torrent.files)
                file_to_torrents[file_paths].append(torrent)

        # Create cross-seed groups for torrents sharing files
        cross_seed_groups = []
        for file_paths, torrent_group in file_to_torrents.items():
            if len(torrent_group) > 1:
                # Multiple torrents point to same files = cross-seeding
                trackers = {t.tracker for t in torrent_group if t.tracker}
                total_size = sum(f.size for f in torrent_group[0].files)

                group = CrossSeedGroup(
                    files=list(file_paths),
                    torrents=torrent_group,
                    trackers=trackers,
                    total_size=total_size,
                )
                cross_seed_groups.append(group)

        return cross_seed_groups

    def get_orphans_only(self) -> List[OrphanedFile]:
        """Quick scan to get only orphaned files."""
        results = self.scan_all()
        return results.orphaned_files

    def get_hardlinks_only(self) -> List:
        """Quick scan to get only hardlink information."""
        results = self.scan_all()
        return results.hardlink_groups
