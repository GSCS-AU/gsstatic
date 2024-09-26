from __future__ import annotations

import logging
import typing
from pathlib import Path
import time

logger = logging.getLogger(__name__)


class Reloader:
    """
    Watches ``site.searchpath`` for changes and re-renders any changed
    Templates.

    :param site:
        A :class:`Site <Site>` object.

    """

    def __init__(self, site, delay=None) -> None:
        self.site = site
        self.delay = delay

    @property
    def searchpath(self) -> FilePath:
        return self.site.cwd

    def should_handle(self, event_type: str, filename: FilePath) -> bool:
        """Check if an event should be handled.

        An event should be handled if a file was created or modified, and
        still exists.

        :param event_type: a string, representing the type of event

        :param filename: the path to the file that triggered the event.
        """
        return event_type in ("modified", "created") and Path(filename).is_file() and not Path(filename).resolve().is_relative_to(Path(self.site.output_dir).resolve())

    def event_handler(self, event_type: str, src_path: FilePath) -> None:
        """Re-render templates if they are modified.

        :param event_type: a string, representing the type of event

        :param src_path: the absolute path to the file that triggered the event.
        """
        if not self.should_handle(event_type, src_path):
            return
        if self.site.delay:
            time.sleep(self.site.delay)
        filename = Path(src_path).relative_to(self.searchpath)
        logger.info("%s %s", event_type, filename)
        self.site.render_templates()

    def watch(self) -> None:
        """Watch and reload modified templates."""
        from staticjinja import _easywatch

        logger.info("Watching '%s' for changes...", self.searchpath)
        logger.info("Press Ctrl+C to stop.")
        _easywatch.watch(self.searchpath, self.event_handler)
