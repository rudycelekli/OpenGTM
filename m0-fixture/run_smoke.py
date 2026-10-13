"""Native short correctness runner. Requires migrated ephemeral PostgreSQL."""
import asyncio
import json
import os
import sys
import time
import uuid
import hashlib
from pathlib import Path
from validator import validate

async def main():
    if os.environ.get("OPENGTM_M0_FIXTURE") != "owned-ephemeral-v1": raise RuntimeError("fixture flag absent")
    if os.environ.get("PROVENANCE_TRACKING_ENABLED") != "true": raise RuntimeError("native provenance required")
    from apps.api.database import SessionLocal
    from apps.api.models import Job
    from apps.api.core.tenancy import workspace_scope
    from apps.api.services.queue_service import QueueService
    from apps.api.services.job_registry import register_job_handlers
    from apps.api.services.workbook.models import Workbook, WorkbookRow, WorkbookEnrichment
    from apps.api.services.workbook.spend_models import WorkbookSpendAttempt
    q = QueueService()  # current environment/default worker configuration
    register_job_handlers(q)
    ids = []
    binding = json.loads(Path("/source/m0-source-binding.json").read_text())
    if binding["head"] != "9188fc4d040c186f3495902fe77e0d041deba3bd": raise RuntimeError("source head mismatch")
    def verify_binding():
        for base,key in ((Path("/source"),"source_hashes"),(Path("/fixture"),"fixture_hashes")):
            for name,digest in binding[key].items():
                if hashlib.sha256((base/name).read_bytes()).hexdigest()!=digest: raise RuntimeError("artifact hash mismatch")
    verify_binding()
    started = time.monotonic()
    # No create/drop/delete operations: caller provisions an ephemeral migrated DB.
    for tenant in ("m0-alpha", "m0-beta"):
        wid = "m0-" + uuid.uuid4().hex
        with workspace_scope(tenant), SessionLocal() as db:
            db.add(Workbook(id=wid, workspace_id=tenant, name="M0 synthetic smoke", columns_config=[
                {"id": "description", "name": "Description", "type": "enrichment", "target_field": "description", "provider": "website_scraper"}]))
            db.flush()
            row = WorkbookRow(workbook_id=wid, workspace_id=tenant, position=1,
                              data={"company": "success"}, enrichments={})
            db.add(row); db.commit(); db.refresh(row)
            job = q.add_job(db, "run_workbook", {"workspace_id": tenant, "workbook_id": wid,
              "column_ids": ["description"], "row_ids": [row.id], "retry_passes": 0,
              "provider_timeout": 2, "force": True})
            ids.append((tenant, wid, row.id, job.id))
    await q.start_worker()
    try:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            with SessionLocal() as db:
                states = [db.get(Job, job).status for _, _, _, job in ids]
            if all(s == "completed" for s in states): break
            if any(s in {"failed", "cancelled"} for s in states): raise RuntimeError("native worker terminal failure " + str(states))
            await asyncio.sleep(.1)
        else: raise RuntimeError("native worker smoke timed out")
    finally: await q.stop_worker()
    records = []
    for tenant, wid, rid, jid in ids:
        with workspace_scope(tenant), SessionLocal() as db:
            job = db.get(Job, jid)
            cell = db.query(WorkbookEnrichment).filter_by(workbook_id=wid, lead_id=rid, column_id="description").one()
            attempts = db.query(WorkbookSpendAttempt).filter_by(workspace_id=tenant, workbook_id=wid, run_id=f"job:{jid}").all()
            records.append({"workspace": tenant, "job_workspace": job.workspace_id, "workbook": wid,
              "row": rid, "job": jid, "column": "description", "job_status": job.status,
              "execution_result": {k: ((job.payload or {}).get("execution_result") or {}).get(k) for k in ("completed", "errors", "total", "rows", "stopped")}, "outcome": "success" if cell.status == "complete" and cell.value == "M0 synthetic result" else "unknown",
              "status": cell.status, "value": cell.value, "provider": cell.provider,
              "provenance": (cell.cell_metadata or {}).get("provenance"),
              "attempts": [{k: getattr(a, k) for k in ("attempt_key", "status", "settled_microusd", "workspace_id", "workbook_id", "run_id", "row_identity", "column_id", "provider", "result")} for a in attempts]})
    receipt = {"provenance": "simulated-provider-native-worker", "external_spend_microusd": 0,
      "duration_seconds": time.monotonic() - started, "records": records,
      "source_binding": binding,
      "worker_config": {"concurrency": q.concurrency, "max_active_per_workspace": q.max_active_per_workspace, "shutdown_grace": q.shutdown_grace,
                        "provider_executors": [(a.get("result") or {}).get("result", {}).get("fixture_executor") for row in records for a in row["attempts"]]},
      "baseline_completed": False, "validation_failures": []}
    verify_binding()
    receipt["validation_failures"] = validate(receipt)
    Path(sys.argv[1]).write_text(json.dumps(receipt, indent=2))
    if receipt["validation_failures"]: raise RuntimeError(str(receipt["validation_failures"]))

if __name__ == "__main__": asyncio.run(main())
