# M0 completion harness: review proposal

Status: PREPARED CONTRACT; no native baseline executed, no product capacity claim.
Frozen production revision: 9188fc4d040c186f3495902fe77e0d041deba3bd.
SQL candidate dfc09d98586f4a4c75672d350e0b3404f0af54db remains separate and held.
Owner order: https://github.com/debpalash/OpenGTM/issues/33#issuecomment-6139656266
Primary specification: docs/plans/go-python-backend-rewrite.md, completion definition and performance evaluation section.

## Specification
A completed input record requires committed result, native cell provenance and linked persisted provider-result evidence, settled internal accounting, and durable fenced run receipt. Queue status alone does not count. Terminal no-match is a separate outcome. Count jobs, records and provider attempts separately. Simulated accounting is never a vendor charge or live-provider receipt.

## Pseudocode and architecture
Seed isolated PostgreSQL with synthetic tenants/workbooks/rows and deterministic scenarios. Submit real run_workbook jobs. Execute real QueueService claims, subprocess timeout/cancellation fencing, native workbook execution, provider process pool, reservation settlement, row persistence, traces and run receipts. Replace only provider operation with a picklable deterministic simulator. A benchmark-only child bootstrap is needed because native job subprocess and forkserver imports do not inherit parent registry changes. Root must review that boundary before implementation/dispatch. Do not change production provider registry, HTTP URL protections or production secrets.

All benchmark containers must use an isolated internal network with no external egress and no ambient provider credentials. Simulator fixtures include single success, waterfall fallback, no-match, slow, rate limit, timeout, malformed, cancellation and worker crash. Replay must preserve accounting uniqueness and tenant boundaries. Fixture costs are explicitly synthetic; actual external spend is zero.

## Evaluation contract
Observe native committed rows, WorkbookEnrichment provenance and WorkbookSpendAttempt with unique tenant/attempt keys, plus Job.payload.execution_result. Cross-check intended row/column/provider identity and observed terminal outcome. Do not accept caller-authored completion booleans as database evidence. Require exact artifact head/tree, observer query hash, fixture hash, complete worker config, database durability and hardware/resource limits in receipt. WORKER_CONCURRENCY defaults 1, workspace active cap defaults 2, provider workers default 8; record actual values rather than tune secretly.

Warm up, then at least 1800 seconds steady load, then overload and recovery. Try load points 100/300/1000 records/s as targets; record actual rate and unsustainable targets. Capture committed completion rate, end-to-end and queue p50/p95/p99, API latency, CPU/RSS, PostgreSQL connections/writes/lock waits, attempts/errors/429/timeouts, per-tenant fairness, backlog and cost/record. Boundedness and threshold decisions require observed series and explicit evaluator criteria, not invented performance thresholds. AI/browser profiles remain separate.

## Refinement and acceptance
First validate harness correctness with native short smoke and negative controls: queue-only manual status, missing trace/result/settlement, duplicate accounting, cross-tenant attribution, short steady duration and missing recovery must reject. Independent root review precedes controlled 30-minute baseline. Shared hosted CI may verify correctness but is explicitly insufficient alone for throughput evidence. No available locked local environment currently; local dependency gaps prevent native execution. A controlled isolated runner with fixed resources and PostgreSQL is required. Never label synthetic evaluation controls as a native baseline.

Native evidence source pointers: `apps/api/services/workbook/enrichment.py:_set_enrichment` persists provenance in cell_metadata; `leadgen/enrichment/licenses.py:provenance_for` defines source/license/confidence/fetched_at; `workbook/spend_service.py:settle` persists accounting_basis/result; `workbook/execution_identity.py:attempt_key` binds workspace/workbook/job/row/column/provider. Ordinary enrichment does not produce agent-column CellTrace.
