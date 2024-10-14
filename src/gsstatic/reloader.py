from __future__ import annotations

from copy import deepcopy
import logging
import typing
from pathlib import Path
import time
from .static import Site
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class GSFileSystemEventHandler(FileSystemEventHandler):
    def __init__(self, site_options, site_class=Site, debounce=0.5):
        logger.info("Initializing GSFileSystemEventHandler")
        self.site_options = deepcopy(site_options) 
        logger.debug("Site options: %s", self.site_options)
        self.site_class = site_class
        self.site = self._rebuild_site_class()
        self.debounce = debounce
        self.last_event_timestamp = time.monotonic()

    
    def _rebuild_site_class(self):
        site = self.site_class(self.site_options)
        return site

    def on_any_event(self, event):
        now = time.monotonic()
        if (now - self.last_event_timestamp) < self.debounce:
            return
        event_type = event.event_type
        logger.debug('Event type: %s', event_type)
        src_path = Path(event.src_path)
        logger.debug('Source path: %s', src_path)

        if event_type in ("modified", "created") and src_path.is_file() and not src_path.resolve().is_relative_to(Path(self.site.output_dir).resolve()):

            if src_path.suffix == ".py":
                self.site = self._rebuild_site_class()
                logger.debug("Rebuilding static Site class")
            try:
                logger.debug("Rendering site")
                self.site.make()
            except Exception as e:
                logger.error("Error while rendering site %s", e)


def watch(site_options, site_class=Site, debounce=0.5):
    """Watch a directory for events.
    -   path should be the directory to watch
    -   handler should a function which takes an event_type and src_path
        and does something interesting. event_type will be one of 'created',
        'deleted', 'modified', or 'moved'. src_path will be the absolute
        path to the file that triggered the event.
    """
    path = Path.cwd()
    event_handler = GSFileSystemEventHandler(site_options, site_class, debounce=debounce)
    observer = Observer()
    observer.schedule(event_handler, path=path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


