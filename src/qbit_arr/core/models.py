"""Data models for qbit-arr."""

from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime
from pydantic import BaseModel, Field


class MediaFile(BaseModel):
    """Represents a media file on the filesystem."""
    
    path: Path
    size: int
    inode: int
    hardlink_count: int
    modified: datetime
    is_orphaned: bool = False
    
    class Config:
        arbitrary_types_allowed = True


class HardlinkGroup(BaseModel):
    """Group of files that are hardlinked together."""
    
    inode: int
    files: List[Path] = Field(default_factory=list)
    total_size: int
    hardlink_count: int
    
    class Config:
        arbitrary_types_allowed = True


class TorrentFile(BaseModel):
    """File within a torrent."""
    
    path: Path
    size: int
    
    class Config:
        arbitrary_types_allowed = True


class TorrentInfo(BaseModel):
    """Information about a torrent from qBittorrent."""
    
    hash: str
    name: str
    category: str
    save_path: Path
    state: str
    added_on: datetime
    tracker: Optional[str] = None
    files: List[TorrentFile] = Field(default_factory=list)
    
    class Config:
        arbitrary_types_allowed = True


class ArrMedia(BaseModel):
    """Media item from Radarr or Sonarr."""
    
    id: int
    title: str
    service: str  # 'radarr' or 'sonarr'
    file_path: Optional[Path] = None
    folder_path: Path
    monitored: bool
    has_file: bool
    
    class Config:
        arbitrary_types_allowed = True


class FileRelationship(BaseModel):
    """Represents relationships between a file and torrents/services."""
    
    file_path: Path
    size: int
    inode: int
    hardlink_count: int
    hardlinked_files: List[Path] = Field(default_factory=list)
    torrents: List[str] = Field(default_factory=list)  # Torrent hashes
    arr_services: List[str] = Field(default_factory=list)  # Service names
    is_orphaned: bool = False
    orphan_reason: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


class OrphanedFile(BaseModel):
    """File that exists but is not tracked by any service."""
    
    path: Path
    size: int
    location: str  # 'torrent' or 'library'
    reason: str
    modified: datetime
    
    class Config:
        arbitrary_types_allowed = True


class ScanStatistics(BaseModel):
    """Statistics from a scan operation."""
    
    total_files: int = 0
    total_size: int = 0
    torrent_files: int = 0
    library_files: int = 0
    hardlink_groups: int = 0
    orphaned_files: int = 0
    orphaned_size: int = 0
    cross_seeded_groups: int = 0
    torrents_count: int = 0
    radarr_items: int = 0
    sonarr_items: int = 0
    scan_duration: float = 0.0


class ScanResults(BaseModel):
    """Complete results from scanning all services and filesystems."""
    
    timestamp: datetime = Field(default_factory=datetime.now)
    statistics: ScanStatistics = Field(default_factory=ScanStatistics)
    torrents: List[TorrentInfo] = Field(default_factory=list)
    radarr_media: List[ArrMedia] = Field(default_factory=list)
    sonarr_media: List[ArrMedia] = Field(default_factory=list)
    hardlink_groups: List[HardlinkGroup] = Field(default_factory=list)
    file_relationships: List[FileRelationship] = Field(default_factory=list)
    orphaned_files: List[OrphanedFile] = Field(default_factory=list)
    
    # Mapping helpers for quick lookups
    inode_to_files: Dict[int, List[Path]] = Field(default_factory=dict)
    file_to_torrents: Dict[Path, List[str]] = Field(default_factory=dict)
    torrent_hash_map: Dict[str, TorrentInfo] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True


class CrossSeedGroup(BaseModel):
    """Group of torrents seeding the same files."""
    
    files: List[Path] = Field(default_factory=list)
    torrents: List[TorrentInfo] = Field(default_factory=list)
    trackers: Set[str] = Field(default_factory=set)
    total_size: int = 0
    
    class Config:
        arbitrary_types_allowed = True
