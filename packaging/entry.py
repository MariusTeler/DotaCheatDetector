"""PyInstaller entry point (double-click -> local web UI; with arguments -> CLI)."""

import multiprocessing
import sys

from dotacheat.cli import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
