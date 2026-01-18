"""Sonarr API client wrapper."""

from pathlib import Path
from typing import List, Optional
import logging

from pyarr import SonarrAPI
from pyarr.exceptions import PyarrConnectionError

from qbit_arr.core.models import ArrMedia
from qbit_arr.config import SonarrConfig, PathsConfig

logger = logging.getLogger(__name__)


class SonarrClient:
    """Client for interacting with Sonarr API."""
    
    def __init__(self, config: SonarrConfig, path_config: Optional[PathsConfig] = None):
        """Initialize Sonarr client."""
        self.config = config
        self.path_config = path_config
        self._client: SonarrAPI = None
    
    def connect(self) -> None:
        """Establish connection to Sonarr."""
        try:
            self._client = SonarrAPI(
                host_url=self.config.url,
                api_key=self.config.api_key
            )
            # Test connection
            self._client.get_system_status()
            logger.info(f"Connected to Sonarr at {self.config.url}")
        except PyarrConnectionError as e:
            logger.error(f"Failed to connect to Sonarr: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Sonarr: {e}")
            raise
    
    def get_series(self) -> List[ArrMedia]:
        """Get all series from Sonarr."""
        if not self._client:
            self.connect()
        
        try:
            series_list = self._client.get_series()
            media_list = []
            
            for series in series_list:
                # For TV shows, we need to get episode files
                # This is a simplified version - in reality you'd get all episode files
                folder_path = Path(series['path'])
                if self.path_config:
                    folder_path = self.path_config.remap_path(folder_path)
                
                media = ArrMedia(
                    id=series['id'],
                    title=series['title'],
                    service='sonarr',
                    file_path=None,  # TV shows have multiple files
                    folder_path=folder_path,
                    monitored=series.get('monitored', False),
                    has_file=series.get('statistics', {}).get('episodeFileCount', 0) > 0
                )
                media_list.append(media)
            
            logger.info(f"Retrieved {len(media_list)} series from Sonarr")
            return media_list
            
        except Exception as e:
            logger.error(f"Failed to get series from Sonarr: {e}")
            raise
    
    def get_episode_files(self) -> List[Path]:
        """Get all episode file paths from Sonarr."""
        if not self._client:
            self.connect()
        
        try:
            # Get all series first
            series_list = self._client.get_series()
            file_paths = []
            
            # For each series, get its episode files
            for series in series_list:
                if series.get('statistics', {}).get('episodeFileCount', 0) > 0:
                    try:
                        # Get episode files for this series using get_episode_file with series=True
                        episode_files = self._client.get_episode_file(series['id'], series=True)
                        
                        # Handle both list and dict responses
                        if not isinstance(episode_files, list):
                            episode_files = [episode_files] if episode_files else []
                        
                        for episode_file in episode_files:
                            if isinstance(episode_file, dict) and episode_file.get('path'):
                                path = Path(episode_file['path'])
                                if self.path_config:
                                    path = self.path_config.remap_path(path)
                                if path not in file_paths:  # Avoid duplicates
                                    file_paths.append(path)
                    except Exception as e:
                        logger.warning(f"Could not get episode files for series {series.get('title')}: {e}")
                        continue
            
            logger.info(f"Retrieved {len(file_paths)} episode files from Sonarr")
            return file_paths
        except Exception as e:
            logger.error(f"Failed to get episode files from Sonarr: {e}")
            raise
