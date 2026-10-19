# Browser demo page. Serves the static UI in static_demo/ and nothing else.

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

_STATIC = Path(__file__).resolve().parent / "static_demo"
_ASSETS = {"app.js": "text/javascript", "style.css": "text/css"}


@router.get("/demo", include_in_schema=False)
def demo_page():
    return FileResponse(_STATIC / "index.html")


@router.get("/demo/static/{name}", include_in_schema=False)
def demo_asset(name: str):
    media_type = _ASSETS.get(name)
    if media_type is None:
        raise HTTPException(status_code=404, detail="Not found.")
    return FileResponse(_STATIC / name, media_type=media_type)
