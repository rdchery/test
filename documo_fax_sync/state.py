"""Tracks which fax IDs have already been copied to the share, so a
re-run (cron firing again, a crashed loop restarting) never writes the
same fax twice even if Documo still reports it as unread."""
import json
from pathlib import Path


class ProcessedFaxState:
    def __init__(self, path):
        self.path = Path(path)
        self._ids = set()
        if self.path.exists():
            self._ids = set(json.loads(self.path.read_text()))

    def is_processed(self, fax_id):
        return str(fax_id) in self._ids

    def mark_processed(self, fax_id):
        self._ids.add(str(fax_id))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(sorted(self._ids)))
