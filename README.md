# qbit-arr

> Media file relationship and orphan detection tool for qBittorrent, Radarr, and Sonarr

**qbit-arr** analyzes your media setup to show file relationships, hardlink status, and identify orphaned files across qBittorrent torrents, Radarr movies, and Sonarr TV shows.

## Features

- 🔍 **Complete System Scan** - Analyze all files across qBittorrent, Radarr, and Sonarr
- 🔗 **Hardlink Detection** - Find files hardlinked between torrent and library directories
- 🗑️ **Orphan Detection** - Identify files not tracked by any service
- 🌱 **Cross-Seed Analysis** - Detect torrents seeding the same files across multiple trackers
- 💻 **Dual Interface** - Both CLI and web dashboard
- 📊 **Rich Visualizations** - Tables, statistics, and relationship views

## Problem It Solves

When cross-seeding torrents across multiple trackers with hardlinked files:

- **Hard to track** which files belong to which torrents
- **Risk of orphaned files** when deleting media from one service but not others
- **No visibility** into hardlink relationships between torrent downloads and library files
- **Manual cleanup** is error-prone and time-consuming

**qbit-arr** gives you complete visibility and helps prevent orphaned files.

## Installation

### On Ubuntu Server

```bash
# Clone the repository
git clone https://github.com/yourusername/qbit-arr.git
cd qbit-arr

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install the package
pip install -e .
```

### Using Docker

```bash
docker build -t qbit-arr .
docker run -d \
  --name qbit-arr \
  -p 8000:8000 \
  -v /data/media:/data/media:ro \
  -v $(pwd)/config.yaml:/app/config.yaml \
  qbit-arr
```

## Configuration

### Option 1: YAML Configuration File

Copy the example configuration:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` with your settings:

```yaml
qbittorrent:
  host: localhost
  port: 8080
  username: admin
  password: your_password

radarr:
  host: localhost
  port: 7878
  api_key: your_radarr_api_key

sonarr:
  host: localhost
  port: 8989
  api_key: your_sonarr_api_key

paths:
  torrent_movies: /data/media/torrents/movies
  torrent_tv: /data/media/torrents/tv
  library_movies: /data/media/libraries/movies
  library_tv: /data/media/libraries/tv
```

### Option 2: Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```bash
QBIT_HOST=localhost
QBIT_PORT=8080
QBIT_USERNAME=admin
QBIT_PASSWORD=your_password

RADARR_HOST=localhost
RADARR_PORT=7878
RADARR_API_KEY=your_radarr_api_key

SONARR_HOST=localhost
SONARR_PORT=8989
SONARR_API_KEY=your_sonarr_api_key

PATH_TORRENT_MOVIES=/data/media/torrents/movies
PATH_TORRENT_TV=/data/media/torrents/tv
PATH_LIBRARY_MOVIES=/data/media/libraries/movies
PATH_LIBRARY_TV=/data/media/libraries/tv
```

## Usage

### CLI Interface

#### Run a complete scan

```bash
qbit-arr scan
```

Show detailed output:

```bash
qbit-arr scan --detail full
```

Export to JSON:

```bash
qbit-arr scan --json > scan-results.json
```

#### Find orphaned files only

```bash
qbit-arr orphans
```

#### Analyze hardlinks

```bash
qbit-arr hardlinks
```

#### View configuration

```bash
qbit-arr info
```

#### Use custom config file

```bash
qbit-arr --config /path/to/config.yaml scan
```

### Web Dashboard

Start the web server:

```bash
# Using Python
python -m uvicorn qbit_arr.web.app:app --host 0.0.0.0 --port 8000

# Or use the run_server function
python -c "from qbit_arr.web.app import run_server; run_server()"
```

Then open your browser to `http://localhost:8000`

The web dashboard provides:

- Real-time scan progress
- Interactive data tables
- Statistics cards
- Export to JSON
- REST API endpoints

### API Endpoints

- `GET /api/scan` - Perform complete scan
- `GET /api/orphans` - Get orphaned files only
- `GET /api/hardlinks` - Get hardlink groups
- `GET /api/config` - View current configuration (sanitized)
- `GET /docs` - Interactive API documentation
- `WS /ws` - WebSocket for real-time updates

## How It Works

1. **Connects to Services** - Queries qBittorrent, Radarr, and Sonarr APIs
2. **Scans Filesystems** - Recursively scans your torrent and library directories
3. **Detects Hardlinks** - Uses inode numbers to identify hardlinked files
4. **Builds Relationships** - Maps files to torrents and arr services
5. **Identifies Orphans** - Finds files not tracked by any service
6. **Analyzes Cross-Seeds** - Groups torrents sharing the same files

## Output Examples

### CLI Output

```
╭──────────────────────────────╮
│  qbit-arr Media Scanner      │
╰──────────────────────────────╯

╭─────── Scan Statistics ───────╮
│ Total Files        1,234      │
│ Total Size         2.5 TB     │
│ Orphaned Files     12         │
│ Hardlink Groups    156        │
│ Torrents           89         │
│ Cross-Seeded       23         │
╰───────────────────────────────╯
```

### Web Dashboard

The web interface shows:

- Statistics cards with key metrics
- Tabbed interface for different views
- Sortable tables with file details
- Color-coded badges for services
- Export functionality

## Use Cases

### 1. Safe Media Deletion

Before deleting media:

1. Run `qbit-arr scan` to see all relationships
2. Check which torrents use the files
3. Delete all related torrents from qBittorrent
4. Delete from Radarr/Sonarr (which removes library files)
5. Verify no orphans remain

### 2. Cross-Seed Management

View which torrents share files:

```bash
qbit-arr scan --detail full
```

Shows torrent groups seeding identical files across trackers.

### 3. Cleanup Orphaned Files

Find files not tracked anywhere:

```bash
qbit-arr orphans
```

Review and safely delete orphaned files.

### 4. Hardlink Analysis

Understand storage usage:

```bash
qbit-arr hardlinks
```

See which files are hardlinked between directories.

## Development

### Setup Development Environment

```bash
# Clone and install with dev dependencies
git clone https://github.com/yourusername/qbit-arr.git
cd qbit-arr
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest
```

### Code Formatting

```bash
black src/
ruff check src/
```

### Type Checking

```bash
mypy src/
```

## Project Structure

```
qbit-arr/
├── src/
│   └── qbit_arr/
│       ├── core/           # Business logic
│       │   ├── models.py   # Data models
│       │   ├── scanner.py  # Main scanner
│       │   └── hardlink.py # Hardlink detection
│       ├── api/            # API clients
│       │   ├── qbit_client.py
│       │   ├── radarr_client.py
│       │   └── sonarr_client.py
│       ├── cli/            # CLI interface
│       │   ├── commands.py
│       │   └── formatters.py
│       ├── web/            # Web interface
│       │   ├── app.py      # FastAPI app
│       │   └── static/     # Frontend
│       └── config.py       # Configuration
├── pyproject.toml
├── Dockerfile
└── README.md
```

## Requirements

- Python 3.9+
- qBittorrent with Web UI enabled
- Radarr API access
- Sonarr API access
- Linux filesystem (for inode-based hardlink detection)

## Troubleshooting

### Connection Errors

Ensure services are accessible:

```bash
# Test qBittorrent
curl http://localhost:8080

# Test Radarr
curl -H "X-Api-Key: YOUR_KEY" http://localhost:7878/api/v3/system/status

# Test Sonarr
curl -H "X-Api-Key: YOUR_KEY" http://localhost:8989/api/v3/system/status
```

### Permission Errors

Ensure read access to media directories:

```bash
ls -la /data/media/torrents/
ls -la /data/media/libraries/
```

### Slow Scans

For large libraries (1000+ files), scans may take several minutes. Consider:

- Running scans during off-peak hours
- Using the `--detail summary` option for faster results
- Checking network connectivity to services

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built with FastAPI, Click, Rich, and Pydantic
- Uses qbittorrent-api and pyarr for service integration

## Support

- Create an issue on GitHub
- Check the `/docs` API endpoint for API documentation
- Review logs for detailed error information
