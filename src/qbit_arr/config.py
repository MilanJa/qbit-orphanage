"""Configuration management for qbit-arr."""

from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class QBittorrentConfig(BaseSettings):
    """qBittorrent connection settings."""
    
    host: str = Field(default="localhost", description="qBittorrent host")
    port: int = Field(default=8080, description="qBittorrent port")
    username: str = Field(default="admin", description="qBittorrent username")
    password: str = Field(default="", description="qBittorrent password")
    
    @property
    def url(self) -> str:
        """Get the full URL for qBittorrent."""
        return f"http://{self.host}:{self.port}"
    
    model_config = SettingsConfigDict(env_prefix="QBIT_")


class RadarrConfig(BaseSettings):
    """Radarr connection settings."""
    
    host: str = Field(default="localhost", description="Radarr host")
    port: int = Field(default=7878, description="Radarr port")
    api_key: str = Field(default="", description="Radarr API key")
    
    @property
    def url(self) -> str:
        """Get the full URL for Radarr."""
        return f"http://{self.host}:{self.port}"
    
    model_config = SettingsConfigDict(env_prefix="RADARR_")


class SonarrConfig(BaseSettings):
    """Sonarr connection settings."""
    
    host: str = Field(default="localhost", description="Sonarr host")
    port: int = Field(default=8989, description="Sonarr port")
    api_key: str = Field(default="", description="Sonarr API key")
    
    @property
    def url(self) -> str:
        """Get the full URL for Sonarr."""
        return f"http://{self.host}:{self.port}"
    
    model_config = SettingsConfigDict(env_prefix="SONARR_")


class PathsConfig(BaseSettings):
    """File system path settings."""
    
    torrent_movies: Path = Field(
        default=Path("/data/media/torrents/movies"),
        description="Path to torrent movies directory"
    )
    torrent_tv: Path = Field(
        default=Path("/data/media/torrents/tv"),
        description="Path to torrent TV shows directory"
    )
    library_movies: Path = Field(
        default=Path("/data/media/libraries/movies"),
        description="Path to movie library directory"
    )
    library_tv: Path = Field(
        default=Path("/data/media/libraries/tv"),
        description="Path to TV library directory"
    )
    
    # Path mapping for Docker containers
    # If qBittorrent/Radarr/Sonarr report paths differently than filesystem
    remote_path_base: str = Field(
        default="/media",
        description="Base path as reported by qBittorrent/Radarr/Sonarr"
    )
    local_path_base: str = Field(
        default="/data/media",
        description="Actual filesystem path where files are located"
    )
    
    def remap_path(self, remote_path: Path) -> Path:
        """
        Remap a path from qBittorrent/Radarr/Sonarr to actual filesystem path.
        
        Example: /media/torrents/movies/file.mkv -> /data/media/torrents/movies/file.mkv
        """
        path_str = str(remote_path)
        if path_str.startswith(self.remote_path_base):
            # Replace remote base with local base
            local_path = path_str.replace(self.remote_path_base, self.local_path_base, 1)
            return Path(local_path)
        return remote_path
    
    model_config = SettingsConfigDict(env_prefix="PATH_")


class WebConfig(BaseSettings):
    """Web server settings."""
    
    host: str = Field(default="0.0.0.0", description="Web server host")
    port: int = Field(default=8000, description="Web server port")
    reload: bool = Field(default=False, description="Enable auto-reload in development")
    
    model_config = SettingsConfigDict(env_prefix="WEB_")


class Config(BaseSettings):
    """Main configuration class."""
    
    qbittorrent: QBittorrentConfig = Field(default_factory=QBittorrentConfig)
    radarr: RadarrConfig = Field(default_factory=RadarrConfig)
    sonarr: SonarrConfig = Field(default_factory=SonarrConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False
    )
    
    @classmethod
    def load_from_yaml(cls, yaml_path: Path) -> "Config":
        """Load configuration from YAML file."""
        import yaml
        
        if not yaml_path.exists():
            return cls()
        
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        
        return cls(**data if data else {})
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """Load configuration from file or environment."""
        if config_path and config_path.exists():
            return cls.load_from_yaml(config_path)
        
        # Try default locations
        default_paths = [
            Path("config.yaml"),
            Path("config.yml"),
            Path.home() / ".qbit-arr" / "config.yaml",
            Path("/etc/qbit-arr/config.yaml"),
        ]
        
        for path in default_paths:
            if path.exists():
                return cls.load_from_yaml(path)
        
        # Fall back to environment variables
        return cls()


def get_config(config_path: Optional[Path] = None) -> Config:
    """Get the configuration instance."""
    return Config.load(config_path)
