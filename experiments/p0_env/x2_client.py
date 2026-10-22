#!/usr/bin/env python3
"""go/no-go ②: prefill 시간 vs 저장된 KV를 로컬·원격 OST에서 복원하는 시간 (llama-server slot save/restore).
사용: python3 x2_client.py <port> <slot_dir> <reps>
slot_dir의 default layout은 로컬 OST로 미리 설정해 둔다. 원격 조건은 lfs migrate로 파일을 원격 OST로 옮겨 만든다."""
import json, os, random, subprocess, sys, time, urllib.request

PORT, SLOT_DIR, REPS = int(sys.argv[1]), sys.argv[2], int(sys.argv[3])
LOCAL_OST, REMOTE_OST = os.environ.get("LOCAL_OST", "0"), os.environ.get("REMOTE_OST", "1")
SUDO_PW = os.environ.get("SUDO_PW", "")
BASE = f"http://127.0.0.1:{PORT}"

def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())

def drop_caches():
    subprocess.run(["sudo", "-S", "-p", "", "sh", "-c", "sync; echo 3 > /proc/sys/vm/drop_caches"], input=SUDO_PW + "\n", text=True, check=True)

def make_prompt(n_tokens):
    random.seed(n_tokens)
    head = "You are an assistant that analyzes industrial IoT sensor and log records.\nRecords:\n"
    lines, text = [], head
    while True:
        t = f"{random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d} P{random.randint(1,8)} vib={random.uniform(0,9):.2f} T={random.uniform(20,90):.1f} a={random.uniform(0,1):.3f}\n"
        lines.append(t)
        if len(lines) % 50 == 0:
            text = head + "".join(lines)
            if len(post("/tokenize", {"content": text})["tokens"]) >= n_tokens:
                break
    toks = post("/tokenize", {"content": text})["tokens"][:n_tokens]
    return post("/detokenize", {"tokens": toks})["content"]

print("n_tokens\trep\tprefill_ms\tsave_ms\tkv_file_MiB\trestore_local_ms\trestore_remote_ms\tttft_after_restore_ms\tprompt_n_after_restore")
for n in [1024, 2048, 4096, 8192]:
    prompt = make_prompt(n)
    for rep in range(REPS):
        fn = f"kv_{n}_{rep}.bin"; path = os.path.join(SLOT_DIR, fn)
        post("/slots/0?action=erase", {})
        r = post("/completion", {"prompt": prompt, "n_predict": 1, "cache_prompt": True, "id_slot": 0})
        prefill_ms = r["timings"]["prompt_ms"]
        s = post("/slots/0?action=save", {"filename": fn})
        size_mib = os.path.getsize(path) / 2**20
        # 로컬 OST에서 복원
        post("/slots/0?action=erase", {}); drop_caches()
        rl = post("/slots/0?action=restore", {"filename": fn})
        # 복원 후 같은 프롬프트로 첫 토큰 시간 (꼬리만 계산되는지 확인)
        r2 = post("/completion", {"prompt": prompt, "n_predict": 1, "cache_prompt": True, "id_slot": 0})
        # 원격 OST로 옮긴 뒤 복원
        subprocess.run(["lfs", "migrate", "-c", "1", "-i", REMOTE_OST, path], check=True)
        post("/slots/0?action=erase", {}); drop_caches()
        rr = post("/slots/0?action=restore", {"filename": fn})
        print(f"{n}\t{rep}\t{prefill_ms:.0f}\t{s['timings']['save_ms']:.0f}\t{size_mib:.0f}\t"
              f"{rl['timings']['restore_ms']:.0f}\t{rr['timings']['restore_ms']:.0f}\t"
              f"{r2['timings']['prompt_ms']:.0f}\t{r2['timings']['prompt_n']}", flush=True)
        os.remove(path)
