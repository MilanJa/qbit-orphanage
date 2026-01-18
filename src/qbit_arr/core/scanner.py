"""Core scanner service that orchestrates all data collection."""

from pathlib import Path
from typing import Dict, List, Set
from datetime import datetime
import time
import logging
from collections import defaultdict

from qbit_arr.config import Config
from qbit_arr.api.qbit_client import QBittorrentClient
from qbit_arr.api.radarr_client import RadarrClient
from qbit_arr.api.sonarr_client import SonarrClient
from qbit_arr.core.hardlink import HardlinkDetector
from qbit_arr.core.models import (
    ScanResults,
    ScanStatistics,
    FileRelationship,
    OrphanedFile,
    CrossSeedGroup,
    TorrentInfo
)

logger = logging.getLogger(__name__)


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
            torrent_files = []
            for path in [self.config.paths.torrent_movies, self.config.paths.torrent_tv]:
                if path.exists():
                    files = self.hardlink_detector.scan_directory(path)
                    torrent_files.extend(files)
            results.statistics.torrent_files = len(torrent_files)
            
            logger.info("Scanning library directories...")
            library_files = []
            for path in [self.config.paths.library_movies, self.config.paths.library_tv]:
                if path.exists():
                    files = self.hardlink_detector.scan_directory(path)
                    library_files.extend(files)
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
                torrent_files + library_files
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
                results.sonarr_media
            )
            results.statistics.orphaned_files = len(results.orphaned_files)
            results.statistics.orphaned_size = sum(f.size for f in results.orphaned_files)
            
            # 7. Calculate statistics
            all_files = torrent_files + library_files
            results.statistics.total_files = len(all_files)
            results.statistics.total_size = sum(f.size for f in all_files)
            
            # 8. Find cross-seed groups
            results.statistics.cross_seeded_groups = len(self._find_cross_seed_groups(results.torrents))
            
            # 9. Record scan duration
            results.statistics.scan_duration = time.time() - start_time
            
            logger.info(f"Scan completed in {results.statistics.scan_duration:.2f}s")
            logger.info(f"Found {results.statistics.total_files} files, "
                       f"{results.statistics.orphaned_files} orphaned")
            
            return results
            
        except Exception as e:
            logger.error(f"Error during scan: {e}", exc_info=True)
            raise
    
    def _build_file_relationships(
        self,
        torrents: List[TorrentInfo],
        radarr_media: List,
        sonarr_media: List,
        all_files: List
    ) -> List[FileRelationship]:
        """Build relationships between files, torrents, and arr services."""
        relationships: Dict[Path, FileRelationship] = {}
        
        # Map files by inode for hardlink lookups
        inode_map = {f.inode: f for f in all_files}
        
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
                            hardlinked_files=self.hardlink_detector.get_hardlinks_for_file(tfile.path)
                        )
                
                if tfile.path in relationships:
                    relationships[tfile.path].torrents.append(torrent.hash)
        
        # Process Radarr files
        for media in radarr_media:
            if media.file_path and media.file_path in relationships:
                relationships[media.file_path].arr_services.append('radarr')
            elif media.file_path:
                file_info = next((f for f in all_files if f.path == media.file_path), None)
                if file_info:
                    relationships[media.file_path] = FileRelationship(
                        file_path=media.file_path,
                        size=file_info.size,
                        inode=file_info.inode,
                        hardlink_count=file_info.hardlink_count,
                        hardlinked_files=self.hardlink_detector.get_hardlinks_for_file(media.file_path),
                        arr_services=['radarr']
                    )
        
        # Process Sonarr files
        try:
            sonarr_files = self.sonarr_client.get_episode_files()
            for file_path in sonarr_files:
                if file_path in relationships:
                    relationships[file_path].arr_services.append('sonarr')
                else:
                    file_info = next((f for f in all_files if f.path == file_path), None)
                    if file_info:
                        relationships[file_path] = FileRelationship(
                            file_path=file_path,
                            size=file_info.size,
                            inode=file_info.inode,
                            hardlink_count=file_info.hardlink_count,
                            hardlinked_files=self.hardlink_detector.get_hardlinks_for_file(file_path),
                            arr_services=['sonarr']
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
        sonarr_media: List
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
                orphaned.append(OrphanedFile(
                    path=file.path,
                    size=file.size,
                    location='torrent',
                    reason='Not tracked by any torrent',
                    modified=file.modified
                ))
        
        # Check library directory files
        for file in library_files:
            if file.path not in radarr_tracked_paths and file.path not in sonarr_tracked_paths:
                # Skip common non-media files that are often added manually
                ignored_extensions = {'.srt', '.nfo', '.png', '.jpg', '.txt', '.srr'}
                if file.path.suffix.lower() in ignored_extensions:
                    continue
                
                # Skip files with "sample" in the name
                if 'sample' in file.path.name.lower():
                    continue
                
                # Skip files smaller than 1 MB
                if file.size < 1_000_000:
                    continue
                
                orphaned.append(OrphanedFile(
                    path=file.path,
                    size=file.size,
                    location='library',
                    reason='Not tracked by Radarr or Sonarr',
                    modified=file.modified
                ))
        
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
                    total_size=total_size
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
