"""HTTP API for the shortener."""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from .store import AliasTaken, InvalidAlias, InvalidURL, Link, LinkStore


class ShortenRequest(BaseModel):
    url: str
    alias: str | None = None


class LinkResponse(BaseModel):
    code: str
    short_url: str
    url: str
    created_at: str
    clicks: int


def create_app(db_path: str | None = None, base_url: str | None = None) -> FastAPI:
    """Build the app. Arguments fall back to SHORTY_DB and SHORTY_BASE_URL."""
    store = LinkStore(db_path or os.environ.get("SHORTY_DB", "links.db"))
    public_base = base_url or os.environ.get("SHORTY_BASE_URL")

    app = FastAPI(title="shorty", description="A small URL shortener")

    def describe(link: Link, request: Request) -> LinkResponse:
        base = public_base or str(request.base_url)
        return LinkResponse(
            code=link.code,
            short_url=f"{base.rstrip('/')}/{link.code}",
            url=link.url,
            created_at=link.created_at,
            clicks=link.clicks,
        )

    @app.get("/", include_in_schema=False)
    def index() -> RedirectResponse:
        return RedirectResponse("/docs")

    @app.post("/api/links", status_code=201, response_model=LinkResponse)
    def shorten(body: ShortenRequest, request: Request) -> LinkResponse:
        try:
            link = store.create(body.url, body.alias)
        except (InvalidURL, InvalidAlias) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except AliasTaken as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        return describe(link, request)

    @app.get("/api/links/{code}", response_model=LinkResponse)
    def link_info(code: str, request: Request) -> LinkResponse:
        link = store.get(code)
        if link is None:
            raise HTTPException(status_code=404, detail="unknown code")
        return describe(link, request)

    @app.get("/{code}", include_in_schema=False)
    def follow(code: str) -> RedirectResponse:
        url = store.resolve(code)
        if url is None:
            raise HTTPException(status_code=404, detail="unknown code")
        return RedirectResponse(url, status_code=302)

    return app
