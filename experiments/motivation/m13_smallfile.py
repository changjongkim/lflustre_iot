#!/usr/bin/env python3
"""M13: IoT 레코드 수집 방식별 처리량과 MDS 요청 수 (client 노드 jetson에서 실행, 마운트 추가 없음).
  per_record : 레코드마다 파일 1개 (stripe count 1, 3)
  per_window : 256KiB 창 파일 200개 (원 IFLustre IoTJ의 소파일 크기, stripe count 1, 3)
  pack       : 하나의 pack 파일에 append, 32개마다 fsync (CoStripe pack 봉인 단위)
per_record와 per_window는 fsync하지 않는다. pack만 fsync하므로 비교는 pack에 불리한 쪽이다.
사용: python3 m13_smallfile.py <test_dir> [n_records] [record_bytes]
출력(TSV): case, stripe, n_ops, bytes, sec, ops_s, MB_s, mdc_rpcs, rpcs_per_op"""
import os, random, shutil, subprocess, sys, time

D = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
RB = int(sys.argv[3]) if len(sys.argv) > 3 else 512
WIN = 256 * 1024

def mdc_rpcs():
    out = subprocess.run(["lctl", "get_param", "-n", "mdc.*.stats"], capture_output=True, text=True).stdout
    return sum(int(l.split()[1]) for l in out.splitlines() if l.startswith("req_waittime"))

def record(i):
    random.seed(i)
    line = f"{i} P{random.randint(1,8)} vib={random.uniform(0,9):.3f} T={random.uniform(20,90):.2f} a={random.uniform(0,1):.4f} "
    return (line * (RB // len(line) + 1))[:RB - 1].encode() + b"\n"

RECS = [record(i) for i in range(N)]

def run(case, stripe, fn):
    d = os.path.join(D, f"{case}_c{stripe}")
    os.makedirs(d); subprocess.run(["lfs", "setstripe", "-c", str(stripe), d], check=True)
    r0, t0 = mdc_rpcs(), time.perf_counter()
    n_ops, nbytes = fn(d)
    dt, r1 = time.perf_counter() - t0, mdc_rpcs()
    print(f"{case}\t{stripe}\t{n_ops}\t{nbytes}\t{dt:.2f}\t{n_ops/dt:.0f}\t{nbytes/dt/1e6:.2f}\t{r1-r0}\t{(r1-r0)/n_ops:.2f}", flush=True)
    shutil.rmtree(d)

def per_record(d):
    for i, r in enumerate(RECS):
        with open(os.path.join(d, f"r{i:06d}"), "wb") as f: f.write(r)
    return N, N * RB

def per_window(d):
    n = 200
    blob = b"".join(RECS)[:WIN].ljust(WIN, b"0")
    for i in range(n):
        with open(os.path.join(d, f"w{i:05d}"), "wb") as f: f.write(blob)
    return n, n * WIN

def pack(d):
    with open(os.path.join(d, "pack0"), "ab") as f:
        for i, r in enumerate(RECS):
            f.write(r)
            if (i + 1) % 32 == 0: f.flush(); os.fsync(f.fileno())
        f.flush(); os.fsync(f.fileno())
    return N, N * RB

os.makedirs(D, exist_ok=True)
print("case\tstripe\tn_ops\tbytes\tsec\tops_s\tMB_s\tmdc_rpcs\trpcs_per_op")
for rep in range(2):
    for stripe in (1, 3):
        run("per_record", stripe, per_record)
        run("per_window", stripe, per_window)
    run("pack", 1, pack)
