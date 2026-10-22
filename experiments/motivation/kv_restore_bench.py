#!/usr/bin/env python3
"""M11·M12: stage 노드에서 KV slot 복원 시간을 정책별로 잰다. 노드의 llama-server(--slot-save-path=<slot_dir>)가 떠 있어야 한다.
  relocation : KV를 원격 OST에 둔 뒤 k번 재사용. 항상 원격 / 매번 재계산 / 첫 사용 후 lfs migrate로 로컬 이동 (M12, read-aware relocation)
  ckpt       : 주기적 KV 복원과 체크포인트 쓰기를 같은 로컬 OST에서. 없음 / 동시 / 속도 제한 / 복원 사이로 지연 (M11, runtime-aware)
사용: python3 kv_restore_bench.py relocation <port> <slot_dir> <local_ost> <remote_ost> [reuse=5] [tokens=4096]
      python3 kv_restore_bench.py ckpt <port> <slot_dir> <local_ost> [rounds=10] [tokens=4096]
SUDO_PW가 환경에 있으면 복원 전마다 page cache를 비운다.
출력(TSV): mode, case, k, op, ms"""
import json, os, random, subprocess, sys, time, urllib.request

MODE, PORT, SLOT = sys.argv[1], int(sys.argv[2]), sys.argv[3]
BASE = f"http://127.0.0.1:{PORT}"
SUDO_PW = os.environ.get("SUDO_PW", "")

def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(r.read())

def drop_caches():
    if SUDO_PW:
        subprocess.run(["sudo", "-S", "-p", "", "sh", "-c", "sync; echo 3 > /proc/sys/vm/drop_caches"], input=SUDO_PW + "\n", text=True, check=True)

def prompt(n_tok):
    random.seed(n_tok)
    text = "Stream 0 records:\n" + "".join(f"{random.randint(0,23):02d}:{random.randint(0,59):02d} vib={random.uniform(0,9):.2f} "
                                           f"T={random.uniform(20,90):.1f}\n" for _ in range(n_tok // 5))
    toks = post("/tokenize", {"content": text})["tokens"][:n_tok]
    return post("/detokenize", {"tokens": toks})["content"]

def prefill(p):
    post("/slots/0?action=erase", {})
    return post("/completion", {"prompt": p, "n_predict": 1, "cache_prompt": True, "id_slot": 0})["timings"]["prompt_ms"]

def restore(fn):
    post("/slots/0?action=erase", {}); drop_caches()
    return post("/slots/0?action=restore", {"filename": fn})["timings"]["restore_ms"]

def out(*a): print("\t".join(map(str, a)), flush=True)

def relocation(local_ost, remote_ost, reuse, n_tok):
    p = prompt(n_tok); fn = "m12.bin"; path = os.path.join(SLOT, fn)
    prefill(p); post("/slots/0?action=save", {"filename": fn})
    for case in ("remote", "recompute", "relocate"):
        subprocess.run(["lfs", "migrate", "-c", "1", "-i", str(remote_ost), path], check=True)
        for k in range(1, reuse + 1):
            if case == "recompute":
                out("relocation", case, k, "prefill", round(prefill(p)))
            else:
                out("relocation", case, k, f"restore_ost{subprocess.run(['lfs','getstripe','-i',path],capture_output=True,text=True).stdout.strip()}", round(restore(fn)))
                if case == "relocate" and k == 1:
                    t0 = time.perf_counter(); subprocess.run(["lfs", "migrate", "-c", "1", "-i", str(local_ost), path], check=True)
                    out("relocation", case, k, "migrate", round((time.perf_counter() - t0) * 1e3))
    os.remove(path)

def ckpt(local_ost, rounds, n_tok):
    p = prompt(n_tok); fn = "m11.bin"; path = os.path.join(SLOT, fn); ck = os.path.join(SLOT, "ckpt.bin")
    prefill(p); post("/slots/0?action=save", {"filename": fn})
    subprocess.run(["lfs", "migrate", "-c", "1", "-i", str(local_ost), path], check=True)
    subprocess.run(["lfs", "setstripe", "-c", "1", "-i", str(local_ost), ck], check=True)
    subprocess.run(["dd", "if=/dev/zero", f"of={ck}", "bs=4M", "count=256", "oflag=direct", "status=none"], check=True)  # 1GiB, 레이아웃 유지
    fio = ["fio", "--name=m11ck", f"--filename={ck}", "--rw=write", "--bs=4M", "--size=1G", "--direct=1", "--ioengine=libaio",
           "--iodepth=16", "--time_based", "--runtime=3600", "--output-format=json"]
    for case in ("none", "concurrent", "throttled", "deferred"):
        bg = None
        if case == "concurrent": bg = subprocess.Popen(fio, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        if case == "throttled": bg = subprocess.Popen(fio + ["--rate=100m"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        time.sleep(2); t_case = time.perf_counter(); written = 0
        for k in range(1, rounds + 1):
            out("ckpt", case, k, "restore", round(restore(fn)))
            if case == "deferred":   # 복원이 끝난 뒤 다음 복원 전까지 256MiB 쓰기
                t0 = time.perf_counter()
                subprocess.run(["dd", "if=/dev/zero", f"of={ck}", "bs=4M", "count=64", "oflag=direct", "conv=notrunc", "status=none"], check=True)
                written += 256; out("ckpt", case, k, "write_256MiB", round((time.perf_counter() - t0) * 1e3))
            time.sleep(3)
        if bg:
            bg.send_signal(2); s = bg.communicate()[0]
            j = json.loads(s[s.index("{"):])["jobs"][0]; written = j["write"]["io_bytes"] / 2**20
        out("ckpt", case, 0, "ckpt_MiB_per_s", round(written / (time.perf_counter() - t_case), 1))
    os.remove(path); os.remove(ck)

if MODE == "relocation":
    relocation(int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]) if len(sys.argv) > 6 else 5, int(sys.argv[7]) if len(sys.argv) > 7 else 4096)
else:
    ckpt(int(sys.argv[4]), int(sys.argv[5]) if len(sys.argv) > 5 else 10, int(sys.argv[6]) if len(sys.argv) > 6 else 4096)
