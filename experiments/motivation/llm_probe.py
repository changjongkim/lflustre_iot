#!/usr/bin/env python3
"""llama-server에 요청을 반복해 prefill 시간, decode 속도, 토큰 간격을 기록한다 (M8 간섭 측정).
사용: python3 llm_probe.py <port> <label> <n_req> [prompt_tokens] [gen_tokens]
요청마다 프롬프트 앞부분을 바꾸고 cache_prompt=false로 보내 매번 전체 prefill이 일어나게 한다.
출력(TSV): label, req, t_start, prompt_n, prefill_ms, prefill_tok_s, gen_n, decode_tok_s, gap_p50_ms, gap_p99_ms, gap_max_ms"""
import json, random, sys, time, urllib.request, zlib

PORT, LABEL, N_REQ = int(sys.argv[1]), sys.argv[2], int(sys.argv[3])
P_TOK = int(sys.argv[4]) if len(sys.argv) > 4 else 2048
G_TOK = int(sys.argv[5]) if len(sys.argv) > 5 else 128
BASE = f"http://127.0.0.1:{PORT}"

def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())

def records(seed, n_lines):
    random.seed(seed)
    return "".join(f"{random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d} P{random.randint(1,8)} "
                   f"vib={random.uniform(0,9):.2f} T={random.uniform(20,90):.1f} a={random.uniform(0,1):.3f}\n" for _ in range(n_lines))

def make_prompt(i):
    text = f"Request {LABEL}-{i}. Summarize anomalies in these IoT sensor records.\n" + records(zlib.crc32(f"{LABEL}-{i}".encode()), P_TOK // 8)
    toks = post("/tokenize", {"content": text})["tokens"][:P_TOK]
    return post("/detokenize", {"tokens": toks})["content"]

def pct(v, p):
    v = sorted(v); return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))] if v else 0

for i in range(N_REQ):
    prompt = make_prompt(i)
    body = {"prompt": prompt, "n_predict": G_TOK, "stream": True, "cache_prompt": False, "ignore_eos": True, "temperature": 0}
    req = urllib.request.Request(BASE + "/completion", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t_start, arrivals, timings = time.time(), [], None
    with urllib.request.urlopen(req, timeout=600) as r:
        for line in r:
            if not line.startswith(b"data: "): continue
            d = json.loads(line[6:])
            if d.get("content"): arrivals.append(time.perf_counter())
            if d.get("stop"): timings = d.get("timings", {})
    gaps = [(b - a) * 1e3 for a, b in zip(arrivals, arrivals[1:])]
    print(f"{LABEL}\t{i}\t{t_start:.1f}\t{timings['prompt_n']}\t{timings['prompt_ms']:.0f}\t{timings['prompt_per_second']:.1f}\t"
          f"{timings['predicted_n']}\t{timings['predicted_per_second']:.2f}\t{pct(gaps,50):.1f}\t{pct(gaps,99):.1f}\t{max(gaps or [0]):.1f}", flush=True)
