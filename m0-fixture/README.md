# Private M0 harness draft

Root review is required before executing `isolated-smoke.sh`. Source and SQL candidate refs are unchanged. `test_validator.py` has 19 local contract controls; these are synthetic evaluator tests, not a native completion proof.

The runnable draft uses an archived exact base checkout, frozen dependencies in an image, ephemeral internal Docker network/PostgreSQL, and a fixture-only Python bootstrap. Native QueueService and job subprocess remain unchanged. Provider operation and registry availability are replaced in memory only for this synthetic fixture process tree. The queue/result/accounting observer reads committed database state. No ambient credentials or .env are copied from the working directory. Python connection restriction is defense in depth; actual no-egress depends on Docker internal networking.

The smoke currently covers two tenant success records only. Its PostgreSQL owner role does not establish FORCE-RLS correctness; existing canonical PostgreSQL suite and future app-role fixture must remain separate gates. Full waterfall/failure/cancel/crash and overload/recovery scenario integration remain incomplete. A short success smoke cannot clear the M0 baseline requirement.

Controlled 30-minute baseline requires dedicated fixed hardware, PostgreSQL durability/role/config, fixed resource limits, time-series observers, all workload phases, replay/failure/tenant controls and reviewed thresholds. A hosted shared-runner smoke verifies correctness only. SQL publication remains HOLD until the owner's baseline ordering condition is fulfilled.

Local control command: `python -m pytest test_validator.py -q`.
Hosted reviewed command supplies M0_SOURCE_DIR (frozen base checkout), M0_FIXTURE_DIR (this reviewed packet), M0_OUTPUT_DIR (owned receipt directory) then runs `bash isolated-smoke.sh`. Workflow still requires exact fixture hashes and canonical source guards before dispatch.
