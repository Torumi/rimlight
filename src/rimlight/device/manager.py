"""Device lifecycle: open/reopen, hotplug, and recovery after resume.

Not implemented yet. Planned behavior (see CLAUDE.md): on resume or write error, close
the handle, wait for re-enumeration, reopen with backoff, re-send the init sequence from
docs/protocol.md. Runs off the UI thread.
"""
