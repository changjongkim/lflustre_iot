#!/usr/bin/env python3
"""P0 C8: 플래너 실행 가능성. 플래너 형식 입력에 대해 JSON schema 제약 출력, 속도, 결정 지연을 측정한다."""
import json, sys, time, urllib.request
PORT = int(sys.argv[1]); REPS = int(sys.argv[2]) if len(sys.argv) > 2 else 3
SCHEMA = {"type": "object", "required": ["actions", "rationale"], "properties": {
  "actions": {"type": "array", "maxItems": 5, "items": {"type": "object", "required": ["type"], "properties": {
    "type": {"enum": ["set_residency", "prefetch_context", "set_ingest_batch", "pause_ingest_prefill", "schedule_compaction",
                      "schedule_regeneration", "schedule_replication", "set_tbf", "set_cache_limit", "migrate", "repartition", "set_objective"]},
    "target": {"type": "string"}, "value": {"type": "string"}}}},
  "rationale": {"type": "string", "maxLength": 400}}}
state = {"event": {"type": "load_shift", "detail": "stage 2 node memory pressure rising, p99 stage time +31%"},
  "slo": {"ttft_p99_s": 2.0, "tpot_p99_ms": 200, "lag_max_min": 10},
  "nodes": {f"N{i}": {"kv_free_gb": round(0.2 + 0.3*i, 1), "psi_mem": [3.1, 18.4, 2.2, 4.0][i-1], "cpu": 0.5, "nic": 0.2 + 0.05*i} for i in range(1, 5)},
  "contexts": [{"id": f"S{i}", "tokens": 4000 + 300*i, "resident": ["N2", "N3"] if i % 2 else [], "unprefilled_records": i*3} for i in range(1, 9)],
  "osts": {f"OST{i}": {"load_mbps": 20*i, "used_pct": 30 + 5*i} for i in range(4)}}
rules = "\n".join(f"- R{i}: " + t for i, t in enumerate([
  "If any stage is not resident for a context, TTFT is set by that stage's KV read time.",
  "Remote OST reads are about 115 MB/s; local OST reads are about 2.4 GB/s.",
  "Local I/O at full speed uses about 45% of node CPU.",
  "Cap the Lustre client cache at 512 MB on serving nodes.",
  "Prefer deferring replication and regeneration I/O to low-load windows.",
  "Never schedule two burst I/O classes on the same OST at the same time."] * 6))
system = "You are the storage planner of an edge LLM cluster. Output only JSON that follows the schema."
user = f"Rules:\n{rules}\n\nCurrent state:\n{json.dumps(state, indent=1)}\n\nPolicy: Line 3 requests have priority until 09:00.\nPropose at most 5 actions."
body = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": 300, "temperature": 0.2, "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {"type": "json_schema", "json_schema": {"name": "plan", "schema": SCHEMA}}}
print("rep\tprompt_tokens\tprompt_ms\tprompt_tok_s\tgen_tokens\tgen_tok_s\twall_s\tvalid_json\tn_actions")
for rep in range(REPS):
    t0 = time.time()
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=600).read()); wall = time.time() - t0
    t = r.get("timings", {}); content = r["choices"][0]["message"]["content"]
    try: plan = json.loads(content); ok = True; na = len(plan["actions"])
    except Exception: ok = False; na = -1
    print(f"{rep}\t{t.get('prompt_n')}\t{t.get('prompt_ms',0):.0f}\t{t.get('prompt_per_second',0):.0f}\t{t.get('predicted_n')}\t{t.get('predicted_per_second',0):.1f}\t{wall:.1f}\t{ok}\t{na}", flush=True)
print("sample output:", content[:500])
