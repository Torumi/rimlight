"""GUI entry point (`rimlight`).

Phase 0: shows a placeholder window only. Qt is imported inside `main()` so that importing
this module never pulls PySide6 into core code paths.
"""

import sys


def main() -> int:
    from rimlight.ui.main_window import run

    return run(sys.argv)
