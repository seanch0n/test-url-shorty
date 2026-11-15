import argparse

from .server import make_server
from .store import LinkStore


def main() -> None:
    parser = argparse.ArgumentParser(prog="shortener", description="Run the URL shortener.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default="links.db", help="SQLite database file")
    parser.add_argument(
        "--base-url",
        help="public URL to build short links from (default: the request's Host header)",
    )
    args = parser.parse_args()

    store = LinkStore(args.db)
    server = make_server(store, args.host, args.port, args.base_url)
    print(f"Listening on http://{args.host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        store.close()


if __name__ == "__main__":
    main()
