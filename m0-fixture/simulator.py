"""Deterministic fixture operations; never makes a provider request."""
import os
import time
import multiprocessing

def provider_job(provider_name, lead_dict):
    if os.environ.get("OPENGTM_M0_FIXTURE") != "owned-ephemeral-v1":
        raise RuntimeError("fixture operation unavailable outside benchmark")
    if provider_name != "hunter_io":
        raise RuntimeError("non-fixture provider denied")
    scenario = lead_dict.get("company", "success")
    if scenario == "slow": time.sleep(0.1)
    if scenario == "timeout": time.sleep(30)
    if scenario == "crash": os._exit(71)
    success = scenario not in {"no-match", "rate-limit", "malformed"}
    return {"provider": provider_name, "success": success,
            "fields": {"email": "m0@fixture.example"} if success else {},
            "confidence": 1.0, "error": "fixture:" + scenario if not success else "",
            "billing_evidence": {"charged_microusd": 0, "reference": "SIMULATED-M0-NO-VENDOR-CHARGE", "fixture_executor": {"start_method": multiprocessing.get_start_method(), "provider_workers": int(os.environ.get("WORKBOOK_PROVIDER_WORKERS", "8")), "pid": os.getpid()}},
            "license": "unknown"}
