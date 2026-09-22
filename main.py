"""Run the Fantrax console app."""

from pathlib import Path
import sys

if __name__ == "__main__":
    print(f"Starting FanTraxWinner: {Path(__file__).resolve()}", flush=True)
    print(f"Python: {sys.executable}", flush=True)
    print("Loading application modules...", flush=True)

from app import FantraxApp
import requests


def main() -> None:
    """Start the existing reporting workflow."""
    app = FantraxApp()
    app.run()


if __name__ == "__main__":
    try:
        main()
        print("FanTraxWinner finished.", flush=True)
    except (ValueError, requests.RequestException) as exc:
        raise SystemExit(str(exc)) from None
