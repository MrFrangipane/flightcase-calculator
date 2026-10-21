"""Main entry point for Flightcase Calculator application."""

import sys
from flightcase.ui import run_app


def main() -> int:
    """Launch the Flightcase Calculator PySide6 application."""
    return run_app()


if __name__ == "__main__":
    sys.exit(main())
