"""Native page queries use a unique order even when every score is tied."""
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from apps.api.services.leadgen import store
from apps.api.services.leadgen.db import LeadDB
from apps.api.services.leadgen.models import Lead
from apps.api.services.leadgen.orm_models import LeadRow


@pytest.mark.parametrize("backend", ["sqlite", "orm"])
def test_tied_pages_keep_unique_ids_in_explicit_id_order(tmp_path, monkeypatch, backend):
    statements = []
    engine = None
    if backend == "sqlite":
        source = LeadDB(str(tmp_path / "ties.db"))
        source.conn.set_trace_callback(statements.append)
    else:
        engine = create_engine(f"sqlite:///{tmp_path / 'ties-orm.db'}")
        LeadRow.__table__.create(engine)
        @event.listens_for(engine, "before_cursor_execute")
        def record_sql(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)
        monkeypatch.setattr(store, "SessionLocal", sessionmaker(bind=engine))
        source = store.PgLeadStore("tied-pages")
    try:
        ids = [source.upsert_lead(Lead(company=f"Tied {i}", score=0, workspace_id="tied-pages"))
               for i in range(501)]
        statements.clear()
        first, total = source.query_leads_page({}, page=1, page_size=500)
        second, second_total = source.query_leads_page({}, page=2, page_size=500)
        found = [row["id"] for row in first + second]
        assert total == second_total == len(ids)
        assert found == sorted(ids)
        assert len(set(found)) == len(ids)
        ordered = [s for s in statements if "ORDER BY" in s.upper()]
        assert len(ordered) == 2
        # SQLite alone often keeps incidental insertion order without the fix.
        # Check the actual executed order, which must also hold on PostgreSQL.
        assert all("score DESC," in s and ("l.id" in s.split("ORDER BY", 1)[1]
                   or "leads.id" in s.split("ORDER BY", 1)[1]) for s in ordered)
    finally:
        source.close()
        if engine is not None:
            engine.dispose()
