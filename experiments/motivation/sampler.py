#!/usr/bin/env python3
"""노드 내부 샘플러 (F6 대응): SSH 조회 없이 노드 안에서 1초 간격으로 CPU, NIC, 메모리, 회수, GPU 부하를 기록한다.
사용: python3 sampler.py <out.tsv> <seconds> [iface]
SUDO_PW가 환경에 있으면 sudo tegrastats를 함께 띄워 EMC(메모리 컨트롤러) 사용률을 기록한다.
이 커널은 PSI(/proc/pressure)가 없으므로 메모리 압박은 /proc/vmstat의 회수 카운터로 본다."""
import os, re, subprocess, sys, threading, time

OUT, DUR = sys.argv[1], float(sys.argv[2])
IF = sys.argv[3] if len(sys.argv) > 3 else "enP8p1s0"
GPU_LOAD = "/sys/devices/platform/bus@0/17000000.gpu/load"   # 0–1000
VMSTAT_KEYS = ("pgscan_kswapd", "pgscan_direct", "pgsteal_kswapd", "pgsteal_direct", "pswpout", "pgmajfault")

emc = {"emc": "", "gr3d": "", "vdd_in": "", "tj": ""}

def tegra_reader(proc):
    for line in proc.stdout:
        for k, pat in (("emc", r"EMC_FREQ (\d+)%"), ("gr3d", r"GR3D_FREQ (\d+)%"), ("vdd_in", r"VDD_IN (\d+)mW"), ("tj", r"tj@([\d.]+)C")):
            m = re.search(pat, line)
            if m: emc[k] = m.group(1)

def cpu():
    v = list(map(int, open("/proc/stat").readline().split()[1:8]))
    return v   # user nice system idle iowait irq softirq

def net():
    for line in open("/proc/net/dev"):
        if line.strip().startswith(IF + ":"):
            f = line.split(":")[1].split(); return int(f[0]), int(f[8])
    return 0, 0

def meminfo():
    d = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":"); d[k] = int(v.split()[0]) // 1024
    return d

def vmstat():
    d = {}
    for line in open("/proc/vmstat"):
        k, v = line.split()
        if k in VMSTAT_KEYS: d[k] = int(v)
    return d

tegra = None
if os.environ.get("SUDO_PW"):
    tegra = subprocess.Popen(["sudo", "-S", "-p", "", "tegrastats", "--interval", "1000"], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    tegra.stdin.write(os.environ["SUDO_PW"] + "\n"); tegra.stdin.flush()
    threading.Thread(target=tegra_reader, args=(tegra,), daemon=True).start()

with open(OUT, "w") as f:
    f.write("t\tcpu_pct\tiowait_pct\tsoftirq_pct\trx_MBs\ttx_MBs\tmem_avail_MiB\tcached_MiB\tdirty_MiB\tswap_used_MiB\t"
            "scan_kswapd\tscan_direct\tswpout\tmajfault\tgpu_pct\temc_pct\tvdd_in_mW\ttj_C\n")
    c0, n0, v0, t0 = cpu(), net(), vmstat(), time.time()
    end = t0 + DUR
    while time.time() < end:
        time.sleep(1)
        c1, n1, v1, t1 = cpu(), net(), vmstat(), time.time()
        dc = [b - a for a, b in zip(c0, c1)]; tot = sum(dc) or 1; dt = t1 - t0
        m = meminfo()
        try: gpu = int(open(GPU_LOAD).read()) / 10
        except OSError: gpu = ""
        f.write(f"{t1:.1f}\t{100*(tot-dc[3]-dc[4])/tot:.1f}\t{100*dc[4]/tot:.1f}\t{100*dc[6]/tot:.1f}\t"
                f"{(n1[0]-n0[0])/dt/1e6:.1f}\t{(n1[1]-n0[1])/dt/1e6:.1f}\t{m['MemAvailable']}\t{m['Cached']}\t{m['Dirty']}\t"
                f"{m['SwapTotal']-m['SwapFree']}\t{v1['pgscan_kswapd']-v0['pgscan_kswapd']}\t{v1['pgscan_direct']-v0['pgscan_direct']}\t"
                f"{v1['pswpout']-v0['pswpout']}\t{v1['pgmajfault']-v0['pgmajfault']}\t{gpu}\t{emc['emc']}\t{emc['vdd_in']}\t{emc['tj']}\n")
        f.flush(); os.fsync(f.fileno())   # 노드가 멈춰도 직전 기록이 남도록 (F7)
        c0, n0, v0, t0 = c1, n1, v1, t1

if tegra:
    tegra.terminate()
