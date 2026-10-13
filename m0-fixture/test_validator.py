import copy
from validator import validate

def fixture():
    import hashlib,json
    a = dict(workspace_id="tenant", workbook_id="wb", run_id="job:1", row_identity="row:1", column_id="description", provider="website_scraper", status="settled", settled_microusd=0)
    a["attempt_key"] = hashlib.sha256(json.dumps(["tenant", "wb", "job:1", "row:1", "description", "website_scraper"], separators=(",", ":")).encode()).hexdigest()
    a["result"] = {"accounting_basis": "confirmed_nonbillable", "result": {"provider": "website_scraper", "success": True, "fields": {"description": "M0 synthetic result"}, "billing_evidence": {"charged_microusd": 0, "reference": "SIMULATED-M0-NO-VENDOR-CHARGE"}}}
    return {"provenance": "simulated-provider-native-worker", "external_spend_microusd": 0,
      "source_binding": {"head": "9188fc4d040c186f3495902fe77e0d041deba3bd", "tree": "f629a70255256e629a6e0737269413194dd62d7b", "source_hashes": {"synthetic-control": "0"*64}, "fixture_hashes": {name: "0"*64 for name in ("run_smoke.py", "validator.py", "simulator.py", "sitecustomize.py")}}, "records": [{"workspace": "tenant", "job_workspace": "tenant", "workbook": "wb", "row": 1, "job": 1,
      "column": "description", "job_status": "completed", "execution_result": {"completed": 1, "errors": 0, "total": 1, "rows": 1, "stopped": False},
      "outcome": "success", "status": "complete", "value": "M0 synthetic result", "provider": "website_scraper",
      "provenance": {"source": "website_scraper", "license": "scraped", "confidence": 1.0, "fetched_at": "2026-10-13T12:00:00+00:00"}, "attempts": [a]}]}

def test_positive_contract_control(): assert validate(fixture()) == []
def test_queue_status_alone_rejected():
    r=fixture(); r["records"][0] = {"job_status": "completed"}
    assert {"native-receipt", "result", "accounting", "evidence", "tenant"} - {"result"} <= set(validate(r))
def test_missing_result_rejected():
    r=fixture(); r["records"][0]["value"] = None; assert "result" in validate(r)
def test_missing_evidence_rejected():
    r=fixture(); r["records"][0]["provenance"] = {}; assert "evidence" in validate(r)
def test_missing_accounting_rejected():
    r=fixture(); r["records"][0]["attempts"] = []; assert "accounting" in validate(r)
def test_duplicate_accounting_rejected():
    r=fixture(); r["records"][0]["attempts"] *= 2; assert "duplicate-accounting" in validate(r)
def test_cross_tenant_rejected():
    r=fixture(); r["records"][0]["job_workspace"] = "other"; assert "tenant" in validate(r)
def test_short_smoke_cannot_clear_baseline(): assert "steady-duration" in validate(fixture(), require_baseline=True)

def test_failed_native_receipt_rejected():
    r=fixture(); r["records"][0]["execution_result"]["errors"] = 1; assert "native-receipt" in validate(r)

def test_unknown_outcome_rejected():
    r=fixture(); r["records"][0]["outcome"]="unknown"; assert "result" in validate(r)
def test_missing_outcome_rejected():
    r=fixture(); del r["records"][0]["outcome"]; assert "result" in validate(r)
def test_truthy_forged_evidence_rejected():
    r=fixture(); r["records"][0]["provenance"]={"fake":True}; assert "evidence" in validate(r)
def test_bool_native_count_rejected():
    r=fixture(); r["records"][0]["execution_result"]["errors"]=False; assert "receipt-types" in validate(r)
def test_forged_attempt_link_rejected():
    r=fixture(); r["records"][0]["attempts"][0]["row_identity"]="row:999"; assert "attempt-link" in validate(r)
def test_forged_accounting_evidence_rejected():
    r=fixture(); r["records"][0]["attempts"][0]["result"]={}; assert "accounting-evidence" in validate(r)

def test_missing_artifact_binding_rejected():
    r=fixture(); del r["source_binding"]; assert "artifact-binding" in validate(r)

def test_boolean_accounting_amount_rejected():
    r=fixture(); r["records"][0]["attempts"][0]["result"]["result"]["billing_evidence"]["charged_microusd"]=False; assert "accounting-evidence" in validate(r)

def test_fabricated_long_baseline_rejected():
    r=fixture(); r.update(steady_seconds=1800, controlled_runner=True, overload_recovery=True, metric_series=[{}]); assert "baseline-not-implemented" in validate(r, require_baseline=True)
