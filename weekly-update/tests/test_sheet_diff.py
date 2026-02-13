# tests/test_sheet_diff.py
from sources.gdrive import _compute_sheet_diff


def test_changed_cell():
    """Should detect a cell value change in an existing row."""
    old_rows = [
        ["Task", "Status"],
        ["Build API", "In Progress"],
    ]
    new_rows = [
        ["Task", "Status"],
        ["Build API", "Done"],
    ]

    diff = _compute_sheet_diff(old_rows, new_rows)

    assert 'Row 2 (Build API): "Status" changed from "In Progress" to "Done"' in diff


def test_added_row():
    """Should detect a newly added row."""
    old_rows = [
        ["Task", "Status"],
        ["Build API", "Done"],
    ]
    new_rows = [
        ["Task", "Status"],
        ["Build API", "Done"],
        ["Write docs", "In Progress"],
    ]

    diff = _compute_sheet_diff(old_rows, new_rows)

    assert "added" in diff.lower()
    assert "Write docs" in diff


def test_removed_row():
    """Should detect a removed row."""
    old_rows = [
        ["Task", "Status"],
        ["Build API", "Done"],
        ["Old task", "Cancelled"],
    ]
    new_rows = [
        ["Task", "Status"],
        ["Build API", "Done"],
    ]

    diff = _compute_sheet_diff(old_rows, new_rows)

    assert "removed" in diff.lower()
    assert "Old task" in diff


def test_no_changes():
    """Should return empty string when nothing changed."""
    rows = [
        ["Task", "Status"],
        ["Build API", "Done"],
    ]

    diff = _compute_sheet_diff(rows, rows)

    assert diff == ""


def test_multiple_changes():
    """Should report multiple changes."""
    old_rows = [
        ["Task", "Owner", "Status"],
        ["Build API", "Alice", "In Progress"],
        ["Write docs", "Bob", "Not Started"],
    ]
    new_rows = [
        ["Task", "Owner", "Status"],
        ["Build API", "Alice", "Done"],
        ["Write docs", "Carol", "In Progress"],
        ["Deploy", "Dave", "Not Started"],
    ]

    diff = _compute_sheet_diff(old_rows, new_rows)

    assert "Build API" in diff
    assert '"Status" changed from "In Progress" to "Done"' in diff
    assert "Write docs" in diff
    assert "Deploy" in diff


def test_matched_by_first_column():
    """Rows should be matched by first column, not position."""
    old_rows = [
        ["Task", "Status"],
        ["Build API", "Done"],
        ["Write docs", "In Progress"],
    ]
    new_rows = [
        ["Task", "Status"],
        ["Write docs", "Done"],
        ["Build API", "Done"],
    ]

    diff = _compute_sheet_diff(old_rows, new_rows)

    # Build API didn't change, just moved. Write docs changed status.
    assert "Write docs" in diff
    assert '"Status" changed from "In Progress" to "Done"' in diff
    # Build API should NOT appear as changed (only reordered)
    assert "Build API" not in diff or "changed" not in diff.split("Build API")[1].split("\n")[0]


def test_duplicate_first_column_falls_back_to_positional():
    """Duplicate keys in first column should fall back to positional matching."""
    old_rows = [
        ["Task", "Status"],
        ["Bug fix", "Done"],
        ["Bug fix", "In Progress"],
    ]
    new_rows = [
        ["Task", "Status"],
        ["Bug fix", "Done"],
        ["Bug fix", "Done"],
    ]

    diff = _compute_sheet_diff(old_rows, new_rows)

    assert '"Status" changed from "In Progress" to "Done"' in diff


def test_empty_old_rows():
    """If old snapshot was empty, all current rows are new."""
    old_rows = []
    new_rows = [
        ["Task", "Status"],
        ["Build API", "Done"],
    ]

    diff = _compute_sheet_diff(old_rows, new_rows)

    assert "added" in diff.lower()
