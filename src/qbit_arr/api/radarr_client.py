"""Radarr API client wrapper."""

from pathlib import Path
from typing import List, Optional
import logging

from pyarr import RadarrAPI
from pyarr.exceptions import PyarrConnectionError

from qbit_arr.core.models import ArrMedia
from qbit_arr.config import RadarrConfig, PathsConfig

logger = logging.getLogger(__name__)


class RadarrClient:
    """Client for interacting with Radarr API."""

    def __init__(self, config: RadarrConfig, path_config: Optional[PathsConfig] = None):
        """Initialize Radarr client."""
        self.config = config
        self.path_config = path_config
        self._client: RadarrAPI = None

    def connect(self) -> None:
        """Establish connection to Radarr."""
        try:
            self._client = RadarrAPI(host_url=self.config.url, api_key=self.config.api_key)
            # Test connection
            self._client.get_system_status()
            logger.info(f"Connected to Radarr at {self.config.url}")
        except PyarrConnectionError as e:
            logger.error(f"Failed to connect to Radarr: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Radarr: {e}")
            raise

    def get_movies(self) -> List[ArrMedia]:
        """Get all movies from Radarr."""
        if not self._client:
            self.connect()

        try:
            movies = self._client.get_movie()
            media_list = []

            for movie in movies:
                file_path = None
                if movie.get("hasFile") and movie.get("movieFile"):
                    file_path = Path(movie["movieFile"]["path"])
                    if self.path_config:
                        file_path = self.path_config.remap_path(file_path)

                folder_path = Path(movie["path"])
                if self.path_config:
                    folder_path = self.path_config.remap_path(folder_path)

                media = ArrMedia(
                    id=movie["id"],
                    title=movie["title"],
                    service="radarr",
                    file_path=file_path,
                    folder_path=folder_path,
                    monitored=movie.get("monitored", False),
                    has_file=movie.get("hasFile", False),
                )
                media_list.append(media)

            logger.info(f"Retrieved {len(media_list)} movies from Radarr")
            return media_list

        except Exception as e:
            logger.error(f"Failed to get movies from Radarr: {e}")
            raise

    def get_movie_files(self) -> List[Path]:
        """Get all movie file paths from Radarr."""
        movies = self.get_movies()
        return [m.file_path for m in movies if m.file_path]
