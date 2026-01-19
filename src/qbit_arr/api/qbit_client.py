"""qBittorrent API client wrapper."""

from pathlib import Path
from typing import List, Optional
from datetime import datetime
import logging
import re

from qbittorrentapi import Client as QBitClient
from qbittorrentapi.exceptions import APIConnectionError

from qbit_arr.core.models import TorrentInfo, TorrentFile
from qbit_arr.config import QBittorrentConfig, PathsConfig

logger = logging.getLogger(__name__)

# Minimum file size for valid media files (100MB)
MIN_MEDIA_SIZE = 100 * 1024 * 1024

# Patterns for files to skip during torrent file processing
SKIP_PATTERNS = [
    r"(?i)sample",
    r"(?i)\.nfo$",
    r"(?i)\.txt$",
    r"(?i)\.srt$",
    r"(?i)\.sub$",
    r"(?i)\.idx$",
    r"(?i)\.jpg$",
    r"(?i)\.jpeg$",
    r"(?i)\.png$",
    r"(?i)trailer",
    r"(?i)\bproof\b",
]


def should_skip_torrent_file(file_path: Path, file_size: int) -> bool:
    """Check if a torrent file should be skipped."""
    file_path_str = str(file_path)

    # Check against skip patterns
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, file_path_str):
            return True

    # Skip small files (likely not main media content)
    # But be more lenient than the filesystem scan (10MB vs 100MB)
    # to allow for legitimate small video files in torrents
    if file_size < 10 * 1024 * 1024:  # 10MB
        return True

    return False


class QBittorrentClient:
    """Client for interacting with qBittorrent API."""

    def __init__(self, config: QBittorrentConfig, path_config: Optional[PathsConfig] = None):
        """Initialize qBittorrent client."""
        self.config = config
        self.path_config = path_config
        self._client: Optional[QBitClient] = None

    def connect(self) -> None:
        """Establish connection to qBittorrent."""
        try:
            self._client = QBitClient(
                host=self.config.host,
                port=self.config.port,
                username=self.config.username,
                password=self.config.password,
            )
            self._client.auth_log_in()
            logger.info(f"Connected to qBittorrent at {self.config.url}")
        except APIConnectionError as e:
            logger.error(f"Failed to connect to qBittorrent: {e}")
            raise

    def disconnect(self) -> None:
        """Disconnect from qBittorrent."""
        if self._client:
            self._client.auth_log_out()
            logger.info("Disconnected from qBittorrent")

    def get_torrents(self) -> List[TorrentInfo]:
        """Get all torrents from qBittorrent."""
        if not self._client:
            self.connect()

        try:
            torrents = self._client.torrents_info()
            torrent_list = []

            for torrent in torrents:
                # Get files for this torrent
                files = self._client.torrents_files(torrent_hash=torrent.hash)

                torrent_files = []
                skipped_count = 0
                for file in files:
                    file_path = Path(torrent.save_path) / file.name

                    # Remap path if path_config is provided
                    if self.path_config:
                        file_path = self.path_config.remap_path(file_path)

                    # Skip sample files and other non-essential files
                    if should_skip_torrent_file(file_path, file.size):
                        skipped_count += 1
                        logger.debug(f"Skipping file: {file_path} (size: {file.size})")
                        continue

                    torrent_files.append(TorrentFile(path=file_path, size=file.size))

                if skipped_count > 0:
                    logger.debug(
                        f"Torrent '{torrent.name}': kept {len(torrent_files)} files, skipped {skipped_count} files"
                    )

                # Get tracker info
                trackers = self._client.torrents_trackers(torrent_hash=torrent.hash)
                tracker_url = None
                if trackers:
                    # Get first non-DHT tracker
                    for t in trackers:
                        if t.url and not t.url.startswith("**"):
                            tracker_url = t.url
                            break

                torrent_info = TorrentInfo(
                    hash=torrent.hash,
                    name=torrent.name,
                    category=torrent.category or "",
                    save_path=self.path_config.remap_path(Path(torrent.save_path))
                    if self.path_config
                    else Path(torrent.save_path),
                    state=torrent.state,
                    added_on=datetime.fromtimestamp(torrent.added_on),
                    tracker=tracker_url,
                    files=torrent_files,
                )
                torrent_list.append(torrent_info)

            logger.info(f"Retrieved {len(torrent_list)} torrents from qBittorrent")
            return torrent_list

        except Exception as e:
            logger.error(f"Failed to get torrents: {e}")
            raise

    def get_torrent_by_hash(self, hash: str) -> Optional[TorrentInfo]:
        """Get a specific torrent by hash."""
        if not self._client:
            self.connect()

        try:
            torrents = self.get_torrents()
            for torrent in torrents:
                if torrent.hash == hash:
                    return torrent
            return None
        except Exception as e:
            logger.error(f"Failed to get torrent {hash}: {e}")
            return None
