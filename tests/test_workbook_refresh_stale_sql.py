"""Real SQLite stale selection preserves cells without loading row payloads."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from apps.api.database import Base
from apps.api.services.workbook import refresh
from apps.api.services.workbook.models import Workbook, WorkbookRow, WorkbookEnrichment

NOW = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)

@pytest.fixture
def stale_db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(refresh, "_now", lambda: NOW)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.add(Workbook(id="stale-fixture", name="Owned stale fixture", workspace_id="fixture"))
        db.commit()
        yield db
    engine.dispose()


def add_row(db, row_id, *, lead_id=None):
    db.add(WorkbookRow(id=row_id, workbook_id="stale-fixture", workspace_id="fixture",
                       position=row_id, lead_id=lead_id,
                       data={"payload": "x" * 4096}, enrichments={}))


def add_cell(db, row_id, column, *, status="complete", age=0, workbook="stale-fixture"):
    db.add(WorkbookEnrichment(workbook_id=workbook, workspace_id="fixture",
                              lead_id=row_id, column_id=column, status=status,
                              updated_at=NOW - timedelta(days=age), value="y" * 4096))


def test_fresh_workbook_reads_no_row_or_overlay_payload_objects(stale_db):
    db = stale_db
    for row_id in range(1, 65):
        add_row(db, row_id)
        add_cell(db, row_id, "summary")
    db.commit()
    loaded = []
    def record(instance, context):
        loaded.append(type(instance).__name__)
    event.listen(WorkbookRow, "load", record)
    event.listen(WorkbookEnrichment, "load", record)
    try:
        assert refresh._stale_row_columns(db, "stale-fixture", [{"id": "summary"}], {}) == {}
        assert loaded == []
    finally:
        event.remove(WorkbookRow, "load", record)
        event.remove(WorkbookEnrichment, "load", record)


def test_stale_selection_uses_per_field_ttl_and_preserves_linked_execution_keys(stale_db):
    db = stale_db
    add_row(db, 1, lead_id=101)
    add_row(db, 2)
    add_row(db, 3, lead_id=0)
    for key in (101, 2, 3):
        add_cell(db, key, "summary", age=8)
        add_cell(db, key, "pitch", age=8)
    db.commit()
    result = refresh._stale_row_columns(db, "stale-fixture", [
        {"id": "summary", "target_field": "overview"}, {"id": "pitch"},
    ], {"overview": 7, "pitch": 30})
    assert result == {"1": ["summary"], "2": ["summary"], "3": ["summary"]}


def test_missing_failed_null_and_cutoff_cells_keep_their_exact_selection(stale_db):
    db = stale_db
    for row_id in range(1, 6):
        add_row(db, row_id)
    add_cell(db, 2, "summary", status="error")
    add_cell(db, 3, "summary", age=30)  # equality is fresh: the rule is strictly older
    add_cell(db, 4, "summary", age=31)
    add_cell(db, 5, "summary")
    db.commit()
    # Explicit native NULLs must match Python's status != complete / missing date.
    db.query(WorkbookEnrichment).filter(WorkbookEnrichment.lead_id == 5).update({"status": None})
    db.commit()
    assert refresh._stale_row_columns(db, "stale-fixture", [{"id": "summary"}], {}) == {
        "1": ["summary"], "2": ["summary"], "4": ["summary"], "5": ["summary"],
    }
    db.query(WorkbookEnrichment).filter(WorkbookEnrichment.lead_id == 3).update({"updated_at": None})
    db.commit()
    assert "3" in refresh._stale_row_columns(db, "stale-fixture", [{"id": "summary"}], {})


def test_empty_and_unrelated_overlay_columns_do_not_change_selection(stale_db):
    db = stale_db
    assert refresh._stale_row_columns(db, "stale-fixture", [{"id": "summary"}], {}) == {}
    add_row(db, 1)
    add_cell(db, 1, "unrequested", status="error")
    db.add(Workbook(id="other-workbook", name="Other", workspace_id="fixture"))
    add_cell(db, 1, "summary", workbook="other-workbook")
    db.commit()
    assert refresh._stale_row_columns(db, "stale-fixture", [{"id": "summary"}], {}) == {"1": ["summary"]}
    assert refresh._stale_row_columns(db, "stale-fixture", [], {}) == {}
