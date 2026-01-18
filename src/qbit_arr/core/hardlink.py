"""Hardlink detection and filesystem scanning utilities."""

import os
from pathlib import Path
from typing import Dict, List, Set, Tuple
from datetime import datetime
from collections import defaultdict
import logging

from qbit_arr.core.models import MediaFile, HardlinkGroup

logger = logging.getLogger(__name__)


class HardlinkDetector:
    """Detects and analyzes hardlinks in the filesystem."""
    
    def __init__(self):
        """Initialize hardlink detector."""
        self.inode_map: Dict[int, List[Path]] = defaultdict(list)
        self.file_cache: Dict[Path, MediaFile] = {}
    
    def scan_directory(self, directory: Path, recursive: bool = True) -> List[MediaFile]:
        """Scan a directory and collect file information."""
        if not directory.exists():
            logger.warning(f"Directory does not exist: {directory}")
            return []
        
        files: List[MediaFile] = []
        
        try:
            if recursive:
                pattern = "**/*"
            else:
                pattern = "*"
            
            for path in directory.glob(pattern):
                if path.is_file():
                    try:
                        media_file = self._get_file_info(path)
                        files.append(media_file)
                        
                        # Track inodes for hardlink detection
                        self.inode_map[media_file.inode].append(path)
                        self.file_cache[path] = media_file
                        
                    except (OSError, PermissionError) as e:
                        logger.warning(f"Cannot access file {path}: {e}")
            
            logger.info(f"Scanned {len(files)} files in {directory}")
            return files
            
        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}")
            return []
    
    def _get_file_info(self, path: Path) -> MediaFile:
        """Get detailed information about a file."""
        stat = path.stat()
        
        return MediaFile(
            path=path,
            size=stat.st_size,
            inode=stat.st_ino,
            hardlink_count=stat.st_nlink,
            modified=datetime.fromtimestamp(stat.st_mtime)
        )
    
    def get_hardlink_groups(self) -> List[HardlinkGroup]:
        """Get all hardlink groups (files sharing the same inode)."""
        groups = []
        
        for inode, paths in self.inode_map.items():
            if len(paths) > 1:
                # Multiple files point to the same inode = hardlinks
                first_file = self.file_cache.get(paths[0])
                if first_file:
                    group = HardlinkGroup(
                        inode=inode,
                        files=paths,
                        total_size=first_file.size,
                        hardlink_count=len(paths)
                    )
                    groups.append(group)
        
        logger.info(f"Found {len(groups)} hardlink groups")
        return groups
    
    def are_hardlinked(self, path1: Path, path2: Path) -> bool:
        """Check if two files are hardlinked."""
        try:
            stat1 = path1.stat()
            stat2 = path2.stat()
            
            # Same inode and same device = hardlinked
            return stat1.st_ino == stat2.st_ino and stat1.st_dev == stat2.st_dev
            
        except (OSError, FileNotFoundError):
            return False
    
    def get_hardlinks_for_file(self, file_path: Path) -> List[Path]:
        """Get all files hardlinked to the given file."""
        try:
            stat = file_path.stat()
            inode = stat.st_ino
            
            return self.inode_map.get(inode, [file_path])
            
        except (OSError, FileNotFoundError):
            return []
    
    def find_hardlinks_between_dirs(
        self,
        dir1: Path,
        dir2: Path
    ) -> Dict[Path, Path]:
        """Find hardlinks between two directories."""
        hardlinks = {}
        
        files1 = self.scan_directory(dir1)
        files2 = self.scan_directory(dir2)
        
        # Build inode map for dir1
        dir1_inodes = {f.inode: f.path for f in files1}
        
        # Check files in dir2 against dir1
        for file2 in files2:
            if file2.inode in dir1_inodes:
                hardlinks[file2.path] = dir1_inodes[file2.inode]
        
        logger.info(f"Found {len(hardlinks)} hardlinks between {dir1} and {dir2}")
        return hardlinks
    
    def clear_cache(self) -> None:
        """Clear internal caches."""
        self.inode_map.clear()
        self.file_cache.clear()


def scan_paths(paths: List[Path]) -> Tuple[List[MediaFile], List[HardlinkGroup]]:
    """
    Scan multiple paths and detect hardlinks.
    
    Args:
        paths: List of directory paths to scan
    
    Returns:
        Tuple of (all files, hardlink groups)
    """
    detector = HardlinkDetector()
    all_files = []
    
    for path in paths:
        if path.exists():
            files = detector.scan_directory(path)
            all_files.extend(files)
    
    hardlink_groups = detector.get_hardlink_groups()
    
    return all_files, hardlink_groups


def get_file_inode(path: Path) -> int:
    """Get the inode number for a file."""
    try:
        return path.stat().st_ino
    except (OSError, FileNotFoundError):
        return -1


def get_hardlink_count(path: Path) -> int:
    """Get the number of hardlinks for a file."""
    try:
        return path.stat().st_nlink
    except (OSError, FileNotFoundError):
        return 0
