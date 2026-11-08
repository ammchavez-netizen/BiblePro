"""Entry point for PyInstaller builds (python -m digital_bible works too)."""
import sys

from digital_bible.app import main

if __name__ == "__main__":
    sys.exit(main())
