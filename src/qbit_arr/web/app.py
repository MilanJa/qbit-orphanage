"""FastAPI web application for qbit-arr."""

from pathlib import Path
from typing import Optional
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from qbit_arr.config import get_config, Config
from qbit_arr.core.scanner import MediaScanner
from qbit_arr.core.models import ScanResults, OrphanedFile, HardlinkGroup

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="qbit-arr",
    description="Media file relationship and orphan detection tool",
    version="0.1.0",
)

# Global config - will be set on startup
config: Optional[Config] = None


class ScanRequest(BaseModel):
    """Request model for triggering a scan."""

    config_path: Optional[str] = None


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")


manager = ConnectionManager()


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    global config
    config = get_config()
    logger.info("qbit-arr web server started")


@app.get("/")
async def root():
    """Serve the main dashboard page."""
    static_dir = Path(__file__).parent / "static"
    index_file = static_dir / "index.html"

    if index_file.exists():
        return FileResponse(index_file)

    # Return a simple HTML page if static files don't exist yet
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>qbit-arr Dashboard</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 1200px;
                margin: 50px auto;
                padding: 20px;
                background: #1e1e1e;
                color: #fff;
            }
            h1 { color: #4a9eff; }
            .status { 
                background: #2d2d2d; 
                padding: 20px; 
                border-radius: 8px; 
                margin: 20px 0;
            }
            button {
                background: #4a9eff;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
            }
            button:hover { background: #3a8eef; }
            .loading { color: #ffa500; }
            .error { color: #ff4444; }
            .success { color: #44ff44; }
        </style>
    </head>
    <body>
        <h1>🎬 qbit-arr Dashboard</h1>
        <div class="status">
            <h2>Status</h2>
            <p id="status">Ready. Click "Run Scan" to analyze your media files.</p>
            <button onclick="runScan()">Run Scan</button>
        </div>
        <div class="status">
            <h2>API Endpoints</h2>
            <ul>
                <li><a href="/api/scan" style="color: #4a9eff;">GET /api/scan</a> - Full scan</li>
                <li><a href="/api/orphans" style="color: #4a9eff;">GET /api/orphans</a> - Orphaned files only</li>
                <li><a href="/api/hardlinks" style="color: #4a9eff;">GET /api/hardlinks</a> - Hardlink groups</li>
                <li><a href="/docs" style="color: #4a9eff;">GET /docs</a> - API documentation</li>
            </ul>
        </div>
        
        <script>
            async function runScan() {
                const statusEl = document.getElementById('status');
                statusEl.innerHTML = '<span class="loading">⏳ Scanning... This may take a few minutes.</span>';
                
                try {
                    const response = await fetch('/api/scan');
                    const data = await response.json();
                    
                    statusEl.innerHTML = `
                        <span class="success">✅ Scan completed!</span><br><br>
                        <strong>Statistics:</strong><br>
                        Total Files: ${data.statistics.total_files}<br>
                        Orphaned Files: ${data.statistics.orphaned_files}<br>
                        Hardlink Groups: ${data.statistics.hardlink_groups}<br>
                        Torrents: ${data.statistics.torrents_count}<br>
                        Duration: ${data.statistics.scan_duration.toFixed(2)}s
                    `;
                } catch (error) {
                    statusEl.innerHTML = `<span class="error">❌ Error: ${error.message}</span>`;
                }
            }
        </script>
    </body>
    </html>
    """)


@app.get("/api/scan", response_model=ScanResults)
async def api_scan():
    """
    Perform a complete scan of all services and filesystems.

    Returns complete scan results including:
    - File relationships
    - Hardlink groups
    - Orphaned files
    - Statistics
    """
    try:
        scanner = MediaScanner(config)
        results = scanner.scan_all()

        # Broadcast scan completion to WebSocket clients
        await manager.broadcast(
            {"type": "scan_complete", "statistics": results.statistics.model_dump()}
        )

        return results

    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/orphans", response_model=list[OrphanedFile])
async def api_orphans():
    """
    Get orphaned files only.

    Returns a list of files that exist but are not tracked by any service.
    """
    try:
        scanner = MediaScanner(config)
        orphans = scanner.get_orphans_only()
        return orphans

    except Exception as e:
        logger.error(f"Orphan scan failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hardlinks", response_model=list[HardlinkGroup])
async def api_hardlinks():
    """
    Get hardlink groups only.

    Returns groups of files that are hardlinked together.
    """
    try:
        scanner = MediaScanner(config)
        groups = scanner.get_hardlinks_only()
        return groups

    except Exception as e:
        logger.error(f"Hardlink analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config")
async def api_config():
    """Get current configuration (sanitized)."""
    return {
        "qbittorrent": {"url": config.qbittorrent.url, "username": config.qbittorrent.username},
        "radarr": {"url": config.radarr.url, "configured": bool(config.radarr.api_key)},
        "sonarr": {"url": config.sonarr.url, "configured": bool(config.sonarr.api_key)},
        "paths": {
            "torrent_movies": str(config.paths.torrent_movies),
            "torrent_tv": str(config.paths.torrent_tv),
            "library_movies": str(config.paths.library_movies),
            "library_tv": str(config.paths.library_tv),
        },
    }


@app.delete("/api/file")
async def api_delete_file(file_path: str):
    """
    Delete a file from the filesystem.

    Args:
        file_path: Absolute path to the file to delete

    Returns:
        Success message
    """
    try:
        import os
        from pathlib import Path

        path = Path(file_path)

        # Security check - ensure file is within allowed directories
        allowed_dirs = [
            config.paths.torrent_movies,
            config.paths.torrent_tv,
            config.paths.library_movies,
            config.paths.library_tv,
        ]

        if not any(path.is_relative_to(allowed_dir) for allowed_dir in allowed_dirs):
            raise HTTPException(status_code=403, detail="File is not within allowed directories")

        if not path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        if not path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")

        # Delete the file
        os.remove(path)
        logger.info(f"Deleted file: {path}")

        return {"message": f"Successfully deleted {path.name}", "path": str(path)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete file {file_path}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.

    Clients can connect to receive live scan progress updates.
    """
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and receive any client messages
            data = await websocket.receive_text()
            # Echo back for now
            await websocket.send_json({"type": "pong", "message": data})

    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Mount static files if the directory exists
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Run the FastAPI server."""
    import uvicorn

    uvicorn.run("qbit_arr.web.app:app", host=host, port=port, reload=reload, log_level="info")
