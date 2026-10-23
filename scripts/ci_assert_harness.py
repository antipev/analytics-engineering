#!/usr/bin/env python3
"""TASK-09 checks 3, 5, 6, 7: run the real workflow step bodies with gcloud/curl/sleep stubbed.

Nothing here touches Google Cloud. The step text is read out of the workflow YAML,
so the assertions exercised are the ones that ship, not a paraphrase of them.

Usage: python scripts/ci_assert_harness.py   (exit 0 = every expected message was produced)

It runs top-to-bottom on import, so execute it — do not `import` it for reuse.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAGSTER = ROOT / ".github/workflows/deploy-dagster.yml"
PUBLISHER = ROOT / ".github/workflows/deploy-publisher.yml"

failures = []
checks = 0


def step_body(path: Path, name: str) -> str:
    """Return the dedented `run: |` body of the step called `name`.

    The body ends at the first non-blank line indented no deeper than `run: |` itself —
    the workflow's own comments sit at 6 spaces and would otherwise be swallowed and
    shift the dedent, silently corrupting embedded heredocs.
    """
    lines = path.read_text().split("\n")
    start = next(i for i, l in enumerate(lines) if l.strip() == f"- name: {name}")
    end = start + 1
    while end < len(lines) and not re.match(r"^      - name:", lines[end]):
        end += 1
    block = lines[start:end]
    run_at = next(i for i, l in enumerate(block) if l.strip() == "run: |")
    run_indent = len(block[run_at]) - len(block[run_at].lstrip())
    body = []
    for line in block[run_at + 1:]:
        if line.strip() and (len(line) - len(line.lstrip())) <= run_indent:
            break
        body.append(line)
    while body and not body[0].strip():
        body.pop(0)
    cut = min(len(l) - len(l.lstrip()) for l in body if l.strip())
    return "\n".join(l[cut:] if l.strip() else "" for l in body) + "\n"


GCLOUD_STUB = """#!/usr/bin/env python3
import json, os, re, sys
args = sys.argv[1:]
fixture = json.load(open(os.environ["GCLOUD_FIXTURE"]))
for a in args:
    if a.startswith("--format="):
        m = re.fullmatch(r"--format=(?:value\\()?(.*?)\\)?", a)
        print(fixture.get(m.group(1), ""))
        sys.exit(0)
print("")
"""

CURL_STUB = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
url = args[-1]
mode = json.load(open(os.environ["CURL_FIXTURE"]))
if "-w" in args:
    for suffix, code in mode.items():
        if url.endswith(suffix):
            print(code, end="")
            sys.exit(0)
    print("000", end="")
    sys.exit(0)
body = next((v for k, v in mode.items() if url.endswith(k)), None)
if body is None:
    sys.exit(22)
sys.stdout.write(body)
"""

SLEEP_STUB = "#!/bin/sh\nexit 0\n"


def run_step(body, env_extra, gcloud=None, curl=None, name="", timeout=None, stub_sleep=True):
    global checks
    checks += 1
    tmp = Path(tempfile.mkdtemp(prefix="t09-"))
    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    stubs = [("gcloud", gcloud), ("curl", curl), ("sleep", SLEEP_STUB if stub_sleep else None)]
    for exe, text in stubs:
        if text is None:
            continue
        p = bin_dir / exe
        p.write_text(text)
        p.chmod(0o755)
    script = tmp / "step.sh"
    script.write_text("set -euo pipefail\n" + body)
    env = dict(os.environ)
    env.update({"PATH": f"{bin_dir}:{env['PATH']}", **env_extra})
    rc = "timeout"
    out = ""
    try:
        proc = subprocess.run(["bash", str(script)], capture_output=True, text=True, env=env, timeout=timeout)
        rc = proc.returncode
        out = (proc.stdout + proc.stderr).strip()
    except subprocess.TimeoutExpired as exc:
        # A waiting step is expected to outlive the harness deadline; keep what it printed.
        for stream in (exc.stdout, exc.stderr):
            if stream:
                out += stream.decode() if isinstance(stream, bytes) else stream
        out = out.strip()
    print(f"\n{'=' * 70}\n{name}\n{'-' * 70}\nexit={rc}\n{out}")
    return rc, out


def expect(cond, label):
    if not cond:
        failures.append(label)
        print(f"  FAIL: {label}")
    else:
        print(f"  ok: {label}")


IMAGE = "gcr.io/my-1-st-project-training/analytics-dagster:sha-new111"
OLD = "gcr.io/my-1-st-project-training/analytics-dagster:sha-old000"
tmpdir = Path(tempfile.mkdtemp(prefix="t09-fix-"))


def fixture(name, data):
    p = tmpdir / name
    p.write_text(json.dumps(data))
    return str(p)


assert_body = step_body(DAGSTER, "Assert the live revision is the one we built")
base = {
    "spec.template.spec.containers[0].image": IMAGE,
    "status.latestCreatedRevisionName": "analytics-dagster-00099-aaa",
    "status.traffic[0].revisionName": "analytics-dagster-00099-aaa",
    "status.url": "https://example.test",
}
healthy_codes = {"/server_info": "200", "/dbt-docs/": "200", "/wake/status": "401"}
common = {"PROJECT_ID": "my-1-st-project-training", "SERVICE": "analytics-dagster", "REGION": "r", "TAG": "sha-new111"}

code, out = run_step(
    assert_body,
    {**common, "GCLOUD_FIXTURE": fixture("ok.json", base), "CURL_FIXTURE": fixture("okc.json", healthy_codes)},
    gcloud=GCLOUD_STUB, curl=CURL_STUB, name="check 5a: assert passes on a correct deploy")
expect(code == 0 and "[assert] image matches sha-new111" in out and "[assert] 100% of traffic on analytics-dagster-00099-aaa" in out,
       "exit 0 and both assert lines present")

code, out = run_step(
    assert_body,
    {**common, "GCLOUD_FIXTURE": fixture("old.json", {**base, "spec.template.spec.containers[0].image": OLD}),
     "CURL_FIXTURE": fixture("okc.json", healthy_codes)},
    gcloud=GCLOUD_STUB, curl=CURL_STUB, name="check 5b: image mismatch names live and expected")
expect(code == 1 and f"image mismatch: serving {OLD}, expected {IMAGE}" in out, "exit 1 with both images named")

code, out = run_step(
    assert_body,
    {**common, "GCLOUD_FIXTURE": fixture("stale.json", {**base, "status.traffic[0].revisionName": "analytics-dagster-00098-bbb"}),
     "CURL_FIXTURE": fixture("okc.json", healthy_codes)},
    gcloud=GCLOUD_STUB, curl=CURL_STUB, name="check 5c: a stale pin fails after the poll")
expect(code == 1 and "traffic did not move to analytics-dagster-00099-aaa" in out, "exit 1 naming the revision it waited for")

code, out = run_step(
    assert_body,
    {**common, "GCLOUD_FIXTURE": fixture("ok.json", base),
     "CURL_FIXTURE": fixture("wake.json", {**healthy_codes, "/wake/status": "200"})},
    gcloud=GCLOUD_STUB, curl=CURL_STUB, name="check 5d: wake route answering 200 is a failure")
expect(code == 1 and "wake API route missing or not enforcing" in out, "exit 1 naming the wake secret")

# -------------------------------------------------------------------- Guard (check 3)
# The guard reads the live-run table straight from the service, so the three branches
# are exercised with a stubbed /graphql body: a run inside the staleness window, a
# residue row only, and a body that is not GraphQL at all (proxy error, 5xx page).
guard_body = step_body(DAGSTER, "Guard — no live runs")
guard_env = {"PROJECT_ID": "my-1-st-project-training", "SERVICE": "analytics-dagster",
             "REGION": "r", "STALE_AFTER_SECONDS": "3600", "FORCE": "false"}
guard_gcloud = fixture("guard-gcloud.json", {"status.url": "https://dagster.test"})


def run_row(start_offset):
    return json.dumps({"data": {"runsOrError": {"__typename": "Runs", "count": 1, "results": [
        {"runId": "r-1", "jobName": "comics_ingestion_job", "status": "STARTED",
         "startTime": str(time.time() + start_offset)}]}}})


code, out = run_step(
    guard_body,
    {**guard_env, "GCLOUD_FIXTURE": guard_gcloud,
     "CURL_FIXTURE": fixture("guard-live.json", {"graphql": run_row(0)})},
    gcloud=GCLOUD_STUB, curl=CURL_STUB, name="check 3a: a run started seconds ago blocks the deploy",
    timeout=8, stub_sleep=False)
expect(out.startswith("1 live run(s); waiting 30 s (0 stale rows ignored)...") and "No live runs" not in out,
       "names the live-run count and waits instead of proceeding")

code, out = run_step(
    guard_body,
    {**guard_env, "GCLOUD_FIXTURE": guard_gcloud,
     "CURL_FIXTURE": fixture("guard-stale.json", {"graphql": run_row(-7200)})},
    gcloud=GCLOUD_STUB, curl=CURL_STUB, name="check 3b: a residue STARTED row two hours old does not block")
expect(code == 0 and "No live runs (1 stale STARTED rows ignored). Proceeding." in out,
       "exit 0 and says how many stale rows it ignored")

code, out = run_step(
    guard_body,
    {**guard_env, "GCLOUD_FIXTURE": guard_gcloud,
     "CURL_FIXTURE": fixture("guard-err.json", {"graphql": "<html>502 Bad Gateway</html>"})},
    gcloud=GCLOUD_STUB, curl=CURL_STUB, name="check 3c: a non-GraphQL body refuses the deploy")
expect(code == 1 and "Dagster did not answer the guard query; refusing to deploy." in out,
       "exit 1 and says it refuses rather than deploys blind")

# --------------------------------------------------------------- Publisher smoke
smoke_body = step_body(PUBLISHER, "Smoke-test the deployed service")
pub_fixture = {"status.url": "https://pub.test"}

broken = json.dumps({
    "operationalState": "serving",
    "environments": [{"packages": [{"name": "comics"}, {"name": "thelook_ecommerce"}]}],
    "loadErrors": [{"package": "jaffle_shop", "message": "Can't rename '_key_cafe_customers'"}],
})
healthy = json.dumps({
    "operationalState": "serving",
    "environments": [{"packages": [{"name": "comics"}, {"name": "jaffle_shop"}, {"name": "thelook_ecommerce"}]}],
    "loadErrors": [],
})

code, out = run_step(
    smoke_body,
    {"PROJECT_ID": "my-1-st-project-training", "SERVICE": "malloy-publisher-mcp", "REGION": "r",
     "GCLOUD_FIXTURE": fixture("pub.json", pub_fixture),
     "CURL_FIXTURE": fixture("broken.json", {"api/v0/status": broken})},
    gcloud=GCLOUD_STUB, curl=CURL_STUB, name="check 6a: a package that only appears in loadErrors fails")
expect(code == 1 and "missing=['jaffle_shop'] loadErrors=['jaffle_shop']" in out,
       "exit 1 with missing= and loadErrors= naming jaffle_shop")

code, out = run_step(
    smoke_body,
    {"PROJECT_ID": "my-1-st-project-training", "SERVICE": "malloy-publisher-mcp", "REGION": "r",
     "GCLOUD_FIXTURE": fixture("pub.json", pub_fixture),
     "CURL_FIXTURE": fixture("healthy.json", {"api/v0/status": healthy})},
    gcloud=GCLOUD_STUB, curl=CURL_STUB, name="check 6b: a healthy body passes")
expect(code == 0 and "serving both semantic packages" in out, "exit 0 and the success line present")

# -------------------------------------------------------------- Publisher traffic
route_body = step_body(PUBLISHER, "Route 100% of traffic to the new revision")
code, out = run_step(
    route_body,
    {"PROJECT_ID": "my-1-st-project-training", "SERVICE": "malloy-publisher-mcp", "REGION": "r",
     "GCLOUD_FIXTURE": fixture("route.json", {
         "status.latestCreatedRevisionName": "malloy-publisher-mcp-00099-zzz",
         "status.traffic[0].revisionName": "malloy-publisher-mcp-00098-yyy",
     })},
    gcloud=GCLOUD_STUB, curl=CURL_STUB, name="check 7: a revision that never receives traffic fails")
expect(code == 1 and "Traffic did not move to malloy-publisher-mcp-00099-zzz." in out,
       "exit 1 naming the revision")

print("\n" + "-" * 70)
print(f"{checks} check(s), {len(failures)} failure(s)")
for f in failures:
    print(f"  - {f}")
sys.exit(1 if failures else 0)

