import hashlib
import json
from datetime import datetime
"""Fail-closed database observation validator; controls are not native results."""
def validate(receipt, *, require_baseline=False):
    failures = []
    if receipt.get("provenance") != "simulated-provider-native-worker": failures.append("provenance")
    if type(receipt.get("external_spend_microusd")) is not int or receipt.get("external_spend_microusd") != 0: failures.append("external-spend")
    binding = receipt.get("source_binding") or {}
    if binding.get("head") != "9188fc4d040c186f3495902fe77e0d041deba3bd" or binding.get("tree") != "f629a70255256e629a6e0737269413194dd62d7b" or not binding.get("source_hashes") or not {"run_smoke.py", "validator.py", "simulator.py", "sitecustomize.py"} <= set(binding.get("fixture_hashes", {})): failures.append("artifact-binding")
    records = receipt.get("records", [])
    if not records: failures.append("no-records")
    identities = set()
    accounting_keys = set()
    for row in records:
        key = (row.get("workspace"), row.get("workbook"), row.get("row"), row.get("column"))
        if key in identities: failures.append("duplicate-record")
        identities.add(key)
        if not all(key) or row.get("job_workspace") != key[0]: failures.append("tenant")
        native = row.get("execution_result") or {}
        if any(type(native.get(k)) is not int for k in ("completed", "errors", "total", "rows")) or type(native.get("stopped")) is not bool: failures.append("receipt-types")
        if row.get("job_status") != "completed" or native != {"completed": 1, "errors": 0, "total": 1, "rows": 1, "stopped": False}: failures.append("native-receipt")
        if row.get("outcome") != "success" or row.get("status") != "complete" or row.get("value") != "M0 synthetic result" or row.get("provider") != "website_scraper": failures.append("result")
        prov = row.get("provenance")
        if not isinstance(prov, dict) or set(prov) != {"source", "license", "confidence", "fetched_at"} or prov.get("source") != "website_scraper" or prov.get("license") != "scraped" or type(prov.get("confidence")) not in (float, int) or type(prov.get("confidence")) is bool or prov.get("confidence") != 1.0:
            failures.append("evidence")
        try:
            stamp = datetime.fromisoformat((prov or {}).get("fetched_at", ""))
            if stamp.tzinfo is None: failures.append("evidence")
        except (ValueError, TypeError, AttributeError): failures.append("evidence")
        attempts = row.get("attempts", [])
        if not attempts or any(a.get("status") != "settled" or type(a.get("settled_microusd")) is not int or a.get("settled_microusd") != 0 for a in attempts): failures.append("accounting")
        for a in attempts:
            expected = [key[0], key[1], f"job:{row.get('job')}", f"row:{key[2]}", key[3], "website_scraper"]
            linked = [a.get(k) for k in ("workspace_id", "workbook_id", "run_id", "row_identity", "column_id", "provider")]
            digest = hashlib.sha256(json.dumps(expected, separators=(",", ":")).encode()).hexdigest()
            if linked != expected or a.get("attempt_key") != digest: failures.append("attempt-link")
            unique = (key[0], a.get("attempt_key"))
            if unique in accounting_keys: failures.append("duplicate-accounting")
            accounting_keys.add(unique)
            envelope = a.get("result") or {}
            result = envelope.get("result") or {}
            if envelope.get("accounting_basis") != "confirmed_nonbillable" or result.get("provider") != "website_scraper" or result.get("success") is not True or result.get("fields") != {"description": "M0 synthetic result"} or type((result.get("billing_evidence") or {}).get("charged_microusd")) is not int or result.get("billing_evidence") != {"charged_microusd": 0, "reference": "SIMULATED-M0-NO-VENDOR-CHARGE"}: failures.append("accounting-evidence")
        keys = [a.get("attempt_key") for a in attempts]
        if not all(keys) or len(keys) != len(set(keys)): failures.append("duplicate-accounting")
    if require_baseline:
        if receipt.get("steady_seconds", 0) < 1800: failures.append("steady-duration")
        if not receipt.get("controlled_runner") or not receipt.get("overload_recovery"): failures.append("controlled-runner")
        if not receipt.get("metric_series"): failures.append("metrics")
    return sorted(set(failures))
