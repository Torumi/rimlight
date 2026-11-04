"""GUI entry point (`rimlight`).

Phase 0: shows a placeholder window only. Qt is imported inside `main()` so that importing
this module never pulls PySide6 into core code paths.
"""

import sys


def main() -> int:
    from rimlight.logs import setup_logging
    from rimlight.ui.main_window import run

    setup_logging()
    return run(sys.argv)
