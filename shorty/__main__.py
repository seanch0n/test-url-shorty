"""Run the shortener: python -m shorty"""

from __future__ import annotations

import argparse

import uvicorn

from .app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(prog="shorty", description="A small URL shortener")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", help="SQLite file (default: $SHORTY_DB or links.db)")
    parser.add_argument(
        "--base-url",
        help="public address used to build short links, e.g. https://sho.rt "
        "(default: $SHORTY_BASE_URL or the request's own address)",
    )
    args = parser.parse_args()
    uvicorn.run(create_app(args.db, args.base_url), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
