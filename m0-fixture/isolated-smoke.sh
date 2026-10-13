#!/usr/bin/env bash
set -euo pipefail
# Run on a disposable hosted runner after root review; requires Docker + uv.
: "${M0_SOURCE_DIR:?exact frozen source checkout required}"
: "${M0_FIXTURE_DIR:?reviewed fixture directory required}"
: "${M0_OUTPUT_DIR:?receipt output required}"
test "$(git -C "$M0_SOURCE_DIR" rev-parse HEAD)" = 9188fc4d040c186f3495902fe77e0d041deba3bd
context=$(mktemp -d)
net="m0-owned-${GITHUB_RUN_ID:-$$}-${GITHUB_RUN_ATTEMPT:-1}"
pg="$net-postgres"
cleanup() { docker rm -f "$pg" >/dev/null 2>&1 || true; docker network rm "$net" >/dev/null 2>&1 || true; docker image rm "$net-image" >/dev/null 2>&1 || true; rm -rf "$context"; }
trap cleanup EXIT
mkdir -p "$context/source" "$context/fixture" "$M0_OUTPUT_DIR"
git -C "$M0_SOURCE_DIR" archive HEAD | tar -x -C "$context/source"
cp "$M0_FIXTURE_DIR"/*.py "$context/fixture/"
cp "$M0_FIXTURE_DIR/Dockerfile" "$context/Dockerfile"
cp "$(command -v uv)" "$context/uv"
python - "$M0_SOURCE_DIR" "$context" <<'BIND'
from pathlib import Path
import subprocess,json,hashlib,sys
source,context=map(Path,sys.argv[1:])
metadata={"head":subprocess.check_output(["git","-C",str(source),"rev-parse","HEAD"],text=True).strip(),"tree":subprocess.check_output(["git","-C",str(source),"rev-parse","HEAD^{tree}"],text=True).strip(),"source_hashes":{},"fixture_hashes":{}}
for f in (context/"source").rglob("*"):
    if f.is_file(): metadata["source_hashes"][str(f.relative_to(context/"source"))]=hashlib.sha256(f.read_bytes()).hexdigest()
for f in (context/"fixture").glob("*.py"):
    metadata["fixture_hashes"][f.name]=hashlib.sha256(f.read_bytes()).hexdigest()
(context/"source"/"m0-source-binding.json").write_text(json.dumps(metadata))
BIND
# Dependency downloads happen before isolated execution; no provider credentials supplied.
docker build -t "$net-image" "$context"
docker network create --internal "$net"
docker run -d --name "$pg" --network "$net" --network-alias postgres   -e POSTGRES_PASSWORD=m0_fixture_only -e POSTGRES_DB=m0_owned_smoke postgres:17
for i in $(seq 1 60); do docker exec "$pg" pg_isready -U postgres >/dev/null 2>&1 && break; sleep 1; done
docker exec "$pg" pg_isready -U postgres >/dev/null
envargs=(-e DATABASE_URL=postgresql+psycopg://postgres:m0_fixture_only@postgres:5432/m0_owned_smoke  -e OPENGTM_M0_FIXTURE=owned-ephemeral-v1 -e M0_INTERNAL_NETWORK_ATTESTATION=isolated-no-egress  -e PROVENANCE_TRACKING_ENABLED=true -e RUN_INLINE_WORKER=0)
docker run --rm --network "$net" "${envargs[@]}" "$net-image" alembic upgrade head
docker run --rm --network "$net" --cpus 2 --memory 2g "${envargs[@]}"  -v "$M0_OUTPUT_DIR:/receipts" "$net-image" python /fixture/run_smoke.py /receipts/native-smoke.json
docker image inspect "$net-image" --format '{{.Id}}' > "$M0_OUTPUT_DIR/image-id.txt"
docker network inspect "$net" > "$M0_OUTPUT_DIR/network.json"
# No 30-minute baseline or throughput claim. Ephemeral DB is destroyed by trap.
