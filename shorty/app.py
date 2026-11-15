"""Flask application: HTTP API for creating short links."""

import os
from datetime import datetime, timezone

from flask import Flask, current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException

from shorty.codes import (
    AliasTakenError,
    CodeGenerationError,
    InvalidAliasError,
    ShortCodeService,
)
from shorty.config import DatabaseConfig
from shorty.db import connect, migrate
from shorty.repository import Link, LinkRepository
from shorty.validation import ValidationError, parse_expires_at, validate_destination_url


def error_response(status: int, code: str, message: str):
    return jsonify({"error": {"code": code, "message": message}}), status


def get_repo() -> LinkRepository:
    if "repo" not in g:
        g.conn = connect(current_app.config["DATABASE"])
        g.repo = LinkRepository(g.conn)
    return g.repo


def short_url_for(code: str) -> str:
    base = current_app.config["BASE_URL"] or request.host_url
    return base.rstrip("/") + "/" + code


def link_to_json(link: Link) -> dict:
    def iso(dt: datetime | None):
        return None if dt is None else dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "short_code": link.short_code,
        "short_url": short_url_for(link.short_code),
        "url": link.target_url,
        "created_at": iso(link.created_at),
        "expires_at": iso(link.expires_at),
    }


def create_app(database: DatabaseConfig | None = None, base_url: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config["DATABASE"] = database or DatabaseConfig.from_env()
    app.config["BASE_URL"] = base_url if base_url is not None else os.environ.get("SHORTY_BASE_URL")

    conn = connect(app.config["DATABASE"])
    try:
        migrate(conn)
    finally:
        conn.close()

    @app.teardown_appcontext
    def close_connection(exc):
        conn = g.pop("conn", None)
        if conn is not None:
            conn.close()

    @app.errorhandler(HTTPException)
    def http_error(exc: HTTPException):
        code = (exc.name or "error").lower().replace(" ", "_")
        return error_response(exc.code or 500, code, exc.description or exc.name)

    @app.post("/api/links")
    def create_link():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return error_response(400, "invalid_json", "request body must be a JSON object")
        try:
            url = validate_destination_url(body.get("url"))
            expires_at = parse_expires_at(body.get("expires_at"))
            alias = body.get("alias")
            if alias is not None and not isinstance(alias, str):
                raise InvalidAliasError("alias must be a string")
            link = ShortCodeService(get_repo()).shorten(url, alias=alias, expires_at=expires_at)
        except ValidationError as exc:
            return error_response(400, exc.code, exc.message)
        except InvalidAliasError as exc:
            return error_response(400, "invalid_alias", str(exc))
        except AliasTakenError as exc:
            return error_response(409, "alias_taken", str(exc))
        except CodeGenerationError:
            return error_response(503, "code_generation_failed", "could not allocate a short code, try again")
        return jsonify({"data": link_to_json(link)}), 201

    return app
