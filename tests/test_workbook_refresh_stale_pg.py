"""Stale scalar selection on real PostgreSQL under the production FORCE RLS role."""
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import event

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = [pytest.mark.postgres, pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")]
NOW = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)

@pytest.fixture(scope="module")
def app_session():
    from tests.pg_rls_support import rls_app_session
    factory, dispose = rls_app_session(TEST_DATABASE_URL)
    try:
        yield factory
    finally:
        dispose()


def test_postgres_stale_ids_preserve_ttl_legacy_keys_nulls_cutoff_and_scope(app_session, monkeypatch):
    from apps.api.core.tenancy import workspace_scope
    from apps.api.services.workbook import refresh
    from apps.api.services.workbook.models import Workbook, WorkbookRow, WorkbookEnrichment
    monkeypatch.setattr(refresh, "_now", lambda: NOW)
    ws = "stale_" + uuid4().hex
    with workspace_scope(ws), app_session() as db:
        workbook = Workbook(name="Owned PG stale fixture", workspace_id=ws)
        other = Workbook(name="Other workbook", workspace_id=ws)
        db.add_all([workbook, other])
        db.flush()
        wid, other_id = workbook.id, other.id
        rows = []
        for position in range(8):
            row = WorkbookRow(workbook_id=wid, workspace_id=ws, position=position,
                              data={"payload": "x" * 4096}, enrichments={})
            db.add(row)
            db.flush()
            rows.append(row)
        rows[0].lead_id = 700001
        rows[2].lead_id = 0
        ids = [row.id for row in rows]
        for index, row in enumerate(rows):
            if index == 3:  # own overlay absent, even though another workbook has it
                continue
            for column in ["summary", "pitch"]:
                age = 7 if index == 6 and column == "summary" else 30 if index == 6 else 31 if index == 7 else 8
                db.add(WorkbookEnrichment(workbook_id=wid, workspace_id=ws,
                    lead_id=row.lead_id or row.id, column_id=column, status="complete",
                    updated_at=NOW - timedelta(days=age), value="y" * 4096))
        db.add(WorkbookEnrichment(workbook_id=other_id, workspace_id=ws,
            lead_id=ids[3], column_id="summary", status="complete", updated_at=NOW))
        db.commit()
        db.query(WorkbookEnrichment).filter_by(workbook_id=wid, lead_id=ids[4], column_id="summary").update({"status": None})
        db.query(WorkbookEnrichment).filter_by(workbook_id=wid, lead_id=ids[5], column_id="summary").update({"updated_at": None})
        db.commit()
        result = refresh._stale_row_columns(db, wid, [
            {"id": "summary", "target_field": "overview"}, {"id": "pitch"},
        ], {"overview": 7, "pitch": 30})
        expected = {str(ids[i]): ["summary"] for i in [0, 1, 2, 4, 5]}
        expected[str(ids[3])] = ["summary", "pitch"]
        expected[str(ids[7])] = ["summary", "pitch"]
        assert result == expected
        assert str(ids[6]) not in result  # exact cutoff remains fresh
    # The same production query runs as a non-superuser under FORCE RLS.
    with workspace_scope("other_" + uuid4().hex), app_session() as db:
        assert refresh._stale_row_columns(db, wid, [{"id": "summary"}], {}) == {}


def test_postgres_fresh_selection_materializes_no_payload_models(app_session, monkeypatch):
    from apps.api.core.tenancy import workspace_scope
    from apps.api.services.workbook import refresh
    from apps.api.services.workbook.models import Workbook, WorkbookRow, WorkbookEnrichment
    monkeypatch.setattr(refresh, "_now", lambda: NOW)
    ws = "fresh_" + uuid4().hex
    with workspace_scope(ws), app_session() as db:
        workbook = Workbook(name="Owned PG fresh fixture", workspace_id=ws)
        db.add(workbook)
        db.flush()
        wid = workbook.id
        for position in range(64):
            row = WorkbookRow(workbook_id=wid, workspace_id=ws, position=position,
                data={"payload": "x" * 4096}, enrichments={})
            db.add(row)
            db.flush()
            db.add(WorkbookEnrichment(workbook_id=wid, workspace_id=ws,
                lead_id=row.id, column_id="summary", status="complete", updated_at=NOW,
                value="y" * 4096))
        db.commit()
    loaded = []
    def record(instance, context):
        loaded.append(type(instance).__name__)
    event.listen(WorkbookRow, "load", record)
    event.listen(WorkbookEnrichment, "load", record)
    try:
        with workspace_scope(ws), app_session() as db:
            assert refresh._stale_row_columns(db, wid, [{"id": "summary"}], {}) == {}
            assert loaded == []
    finally:
        event.remove(WorkbookRow, "load", record)
        event.remove(WorkbookEnrichment, "load", record)
