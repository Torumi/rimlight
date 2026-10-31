"""PySide6 user interface. The only package allowed to import Qt.

Submodules import PySide6 at module level; this package `__init__` does not, so that
`import rimlight.ui` stays cheap and headless-safe.
"""
