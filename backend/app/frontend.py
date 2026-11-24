"""Serve the built React app from the same process as the API (one container, one origin)."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles

DEFAULT_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class ImmutableStaticFiles(StaticFiles):
    """Vite puts a content hash into every asset name, so a file under a name never changes."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def mount_frontend(app: FastAPI, static_dir: Path) -> None:
    """Real files are served as they are; any other path gets index.html for the router."""
    root = static_dir.resolve()
    if not (root / "index.html").is_file():
        return  # no build (local development runs the Vite dev server instead)
    if (root / "assets").is_dir():
        app.mount("/assets", ImmutableStaticFiles(directory=root / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        file = (root / path).resolve()
        if path and file.is_file() and file.is_relative_to(root):
            return FileResponse(file)
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})
