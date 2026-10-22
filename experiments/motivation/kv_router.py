#!/usr/bin/env python3
"""M14 프로토타입: KV 배치 정책별 TTFT (작은 end-to-end). client 노드 jetson에서 실행한다.
stage 노드 jetson1–3이 각자 llama-server를 띄우고 같은 Lustre 디렉터리를 --slot-save-path로 쓴다.
데이터 스트림 컨텍스트 12개(각 4k 토큰)는 담당 노드가 정해져 있다(c % 3). 요청이 오면 담당 노드가 KV slot 파일을 복원하고
질문 꼬리만 prefill해 첫 토큰을 낸다. 정책은 KV 파일을 어느 OST에 두느냐만 다르다.
  lustre_default : lfs migrate -c 1 (OST 지정 없음, Lustre 기본 할당기가 고름)
  balanced       : 지금까지 둔 KV 바이트가 가장 적은 OST (OSS 부하 기반, 소비 위치는 보지 않음. IFLustre식 분산)
  local          : 담당 노드의 OST (소비 노드 배치)
사용: python3 kv_router.py prep <slot_dir>
      python3 kv_router.py run <slot_dir> <policy> <duration_s> <rate_req_s> [seed]
출력(run, TSV): policy, i, ctx, node, ost, local, t_arrival, wait_ms, restore_ms, tail_prompt_n, tail_ms, ttft_ms"""
import json, os, queue, random, subprocess, sys, threading, time, urllib.request

NODES = {1: "192.168.0.51", 2: "192.168.0.52", 3: "192.168.0.53"}   # 노드 n의 로컬 OST index = n - 1
PORT, N_CTX, CTX_TOK = 8089, 12, 4096
home = lambda c: c % 3 + 1

def post(node, path, body, timeout=900):
    req = urllib.request.Request(f"http://{NODES[node]}:{PORT}{path}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def records(seed, n):
    random.seed(seed)
    return "".join(f"{random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d} line{seed % 4 + 1} "
                   f"vib={random.uniform(0,9):.2f} T={random.uniform(20,90):.1f} a={random.uniform(0,1):.3f}\n" for _ in range(n))

def ctx_prompt(c):
    text = f"Stream {c}: vibration and temperature records from production line {c % 4 + 1}.\n" + records(1000 + c, CTX_TOK // 6)
    toks = post(home(c), "/tokenize", {"content": text})["tokens"][:CTX_TOK]
    return post(home(c), "/detokenize", {"tokens": toks})["content"]

def ost_of(path):
    return int(subprocess.run(["lfs", "getstripe", "-i", path], capture_output=True, text=True).stdout.split()[0])

def prep(slot_dir):
    prompts = {}
    for c in range(N_CTX):
        n = home(c); p = ctx_prompt(c); prompts[c] = p
        post(n, "/slots/0?action=erase", {})
        r = post(n, "/completion", {"prompt": p, "n_predict": 1, "cache_prompt": True, "id_slot": 0})
        post(n, "/slots/0?action=save", {"filename": f"ctx{c}.bin"})
        print(f"prep ctx{c} node{n} prefill_ms={r['timings']['prompt_ms']:.0f} ost={ost_of(os.path.join(slot_dir, f'ctx{c}.bin'))}", file=sys.stderr, flush=True)
    json.dump(prompts, open(os.path.join(slot_dir, "prompts.json"), "w"))

def place(slot_dir, policy):
    load, where = {0: 0, 1: 0, 2: 0}, {}
    order = list(range(N_CTX))
    if policy == "balanced":   # 컨텍스트 번호 순서로 돌리면 담당 노드 배정(c % 3)과 우연히 같아진다. 고정 seed로 섞는다
        random.Random(11).shuffle(order)
    for c in order:
        f = os.path.join(slot_dir, f"ctx{c}.bin"); size = os.path.getsize(f)
        if policy == "lustre_default": cmd = ["lfs", "migrate", "-c", "1", f]
        elif policy == "balanced": cmd = ["lfs", "migrate", "-c", "1", "-i", str(min(load, key=load.get)), f]
        else: cmd = ["lfs", "migrate", "-c", "1", "-i", str(home(c) - 1), f]
        subprocess.run(cmd, check=True)
        where[c] = ost_of(f); load[where[c]] += size
    return where

def run(slot_dir, policy, duration, rate, seed):
    prompts = {int(k): v for k, v in json.load(open(os.path.join(slot_dir, "prompts.json"))).items()}
    t0 = time.perf_counter(); where = place(slot_dir, policy)
    print(f"{policy}: placement {where} ({time.perf_counter()-t0:.0f}s)", file=sys.stderr, flush=True)
    rng = random.Random(seed)
    zipf = [1 / (k + 1) for k in range(N_CTX)]; order = list(range(N_CTX)); rng.shuffle(order)
    qs = {n: queue.Queue() for n in NODES}; out_lock = threading.Lock(); results = []

    def worker(n):
        while True:
            item = qs[n].get()
            if item is None: return
            i, c, t_arr = item
            t_start = time.perf_counter()
            post(n, "/slots/0?action=erase", {})
            rr = post(n, "/slots/0?action=restore", {"filename": f"ctx{c}.bin"})
            q = f"\nQuestion {i}: which records in stream {c} look abnormal?"
            r = post(n, "/completion", {"prompt": prompts[c] + q, "n_predict": 1, "cache_prompt": True, "id_slot": 0})
            t_end = time.perf_counter()
            row = (policy, i, c, n, where[c], int(where[c] == n - 1), round(t_arr - t_begin, 2), round((t_start - t_arr) * 1e3),
                   round(rr["timings"]["restore_ms"]), r["timings"]["prompt_n"], round(r["timings"]["prompt_ms"]), round((t_end - t_arr) * 1e3))
            with out_lock:
                print("\t".join(map(str, row)), flush=True)

    t_begin = time.perf_counter(); i = 0
    ths = [threading.Thread(target=worker, args=(n,)) for n in NODES]
    for t in ths: t.start()
    while time.perf_counter() - t_begin < duration:
        time.sleep(rng.expovariate(rate))
        c = order[rng.choices(range(N_CTX), weights=zipf)[0]]
        qs[home(c)].put((i, c, time.perf_counter())); i += 1
    for n in NODES: qs[n].put(None)
    for t in ths: t.join()

if __name__ == "__main__":
    if sys.argv[1] == "prep":
        prep(sys.argv[2])
    else:
        run(sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5]), int(sys.argv[6]) if len(sys.argv) > 6 else 7)
