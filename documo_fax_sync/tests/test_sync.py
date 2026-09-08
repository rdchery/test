import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from state import ProcessedFaxState
from sync import build_filename, sync_once


def test_build_filename_sanitizes_fields():
    fax = {"id": "abc123", "from": "+1 (555) 010-0000", "receivedAt": "2026-09-03T10:00:00Z"}
    name = build_filename(fax)
    assert name.endswith("_abc123.pdf")
    assert " " not in name and "(" not in name


def test_sync_once_downloads_saves_marks_read_and_skips_processed(tmp_path):
    client = MagicMock()
    client.list_inbound_faxes.return_value = {
        "faxes": [
            {"id": "1", "from": "5551234567", "receivedAt": "2026-09-03T10:00:00Z"},
            {"id": "2", "from": "5557654321", "receivedAt": "2026-09-03T10:05:00Z"},
        ]
    }
    client.download_fax.return_value = b"%PDF-1.4 fake"

    writer = MagicMock()
    writer.write.side_effect = lambda name, content: tmp_path / name

    state = ProcessedFaxState(tmp_path / "processed.json")
    state.mark_processed("2")  # already handled in a prior run

    sync_once(client, writer, state)

    client.download_fax.assert_called_once_with("1")
    writer.write.assert_called_once()
    client.mark_fax_read.assert_called_once_with("1")
    assert state.is_processed("1")


def test_sync_once_dry_run_touches_nothing(tmp_path):
    client = MagicMock()
    client.list_inbound_faxes.return_value = {
        "faxes": [{"id": "1", "from": "5551234567", "receivedAt": "2026-09-03T10:00:00Z"}]
    }

    writer = MagicMock()
    state = ProcessedFaxState(tmp_path / "processed.json")

    sync_once(client, writer, state, dry_run=True)

    client.download_fax.assert_not_called()
    writer.write.assert_not_called()
    client.mark_fax_read.assert_not_called()
    assert not state.is_processed("1")


def test_sync_once_mark_as_read_false_still_saves_but_skips_marking(tmp_path):
    client = MagicMock()
    client.list_inbound_faxes.return_value = {
        "faxes": [{"id": "1", "from": "5551234567", "receivedAt": "2026-09-03T10:00:00Z"}]
    }
    client.download_fax.return_value = b"%PDF-1.4 fake"

    writer = MagicMock()
    writer.write.side_effect = lambda name, content: tmp_path / name

    state = ProcessedFaxState(tmp_path / "processed.json")

    sync_once(client, writer, state, mark_as_read=False)

    writer.write.assert_called_once()
    client.mark_fax_read.assert_not_called()
    assert state.is_processed("1")


def test_sync_once_continues_after_a_failed_fax(tmp_path):
    client = MagicMock()
    client.list_inbound_faxes.return_value = {
        "faxes": [
            {"id": "1", "from": "5551234567", "receivedAt": "2026-09-03T10:00:00Z"},
            {"id": "2", "from": "5557654321", "receivedAt": "2026-09-03T10:05:00Z"},
        ]
    }
    client.download_fax.side_effect = [RuntimeError("boom"), b"%PDF-1.4 fake"]

    writer = MagicMock()
    writer.write.side_effect = lambda name, content: tmp_path / name

    state = ProcessedFaxState(tmp_path / "processed.json")

    sync_once(client, writer, state)

    assert not state.is_processed("1")
    assert state.is_processed("2")
