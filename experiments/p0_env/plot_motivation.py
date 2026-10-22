#!/usr/bin/env python3
"""P0 실측 결과로 README Motivation 그림을 만든다 (라이트·다크 두 벌, SVG).
값은 results/p0/ 아래 원시 결과에서 직접 읽는다. 색은 대상에 고정한다: 로컬=slot1, 원격=slot2, 재계산=slot3."""
import re, statistics as st
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
R, OUT = ROOT / "results/p0", ROOT / "docs/figures"
THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781", grid="#e1e0d9", axis="#c3c2b7",
                  s=["#2a78d6", "#eb6834", "#1baf7a"]),
    "dark":  dict(surface="#1a1a19", ink="#f0efec", ink2="#c3c2b7", muted="#898781", grid="#2c2c2a", axis="#383835",
                  s=["#3987e5", "#d95926", "#199e70"]),
}
plt.rcParams.update({"font.family": "Helvetica Neue", "font.size": 10, "svg.fonttype": "path"})

# ---------- 결과 파싱 ----------
def x1():
    rows = [re.search(r"^(local|remote)\s+ost=\d (write|read)\s+direct=(\d)\s+([\d.]+) MB/s.*cpu=\s*([\d.]+)%", l)
            for l in (R / "jetson1/x1_local_path.txt").read_text().splitlines()]
    d = {}
    for m in filter(None, rows):
        d.setdefault((m[1], m[2], m[3]), []).append((float(m[4]), float(m[5])))
    return {k: (st.mean(v[0] for v in vs), st.mean(v[1] for v in vs)) for k, vs in d.items()}
def c2():
    lines = (R / "jetson/c2_bandwidth.tsv").read_text().splitlines()[1:]
    d = {}
    for l in lines:
        f = l.split("\t")
        d.setdefault((f[0], f[2], f[3], f[4]), []).append((float(f[5]), float(f[8])))
    return d
def x2():
    out = []
    for l in (R / "jetson1/x2_prefill_vs_kv.txt").read_text().splitlines():
        f = l.split("\t")
        if len(f) == 9 and f[0].isdigit():
            out.append(tuple(map(float, f)))
    by = {}
    for n, rep, pre, sv, sz, loc, rem, ttft, pn in out:
        by.setdefault(int(n), []).append((pre, loc, rem, ttft))
    return {n: tuple(st.mean(v[i] for v in vs) / 1000 for i in range(4)) for n, vs in sorted(by.items())}
def x3():
    d, cur = {}, None
    for l in (R / "jetson1/x3_cache_gpu.txt").read_text().splitlines():
        if m := re.match(r"===== target (\d) GiB", l): tgt = int(m[1])
        if m := re.match(r"\[(A|B|C)\]", l): cur = m[1]
        if m := re.search(r"total (\d+) ms, worst chunk (\d+) ms", l): d[(tgt, cur)] = (int(m[1]), int(m[2]))
    return d
def c5():
    t = (R / "jetson/c5_memory.txt").read_text()
    out = {}
    for m in re.finditer(r"cap=(\d+)MiB \| before: MemFree:=(\d+)MiB.*?\| after: MemFree:=(\d+)MiB", t):
        out[int(m[1])] = int(m[2]) - int(m[3])
    return out
def iperf():
    d = {}
    for l in (R / "iperf3.txt").read_text().splitlines():
        m = re.match(r"(.+?) \| forward: ([\d.]+) Mbits/sec \| reverse: ([\d.]+)", l)
        if m: d[m[1].strip()] = (float(m[2]), float(m[3]))
    return d

# ---------- 공통 스타일 ----------
def frame(ax, t, horizontal=False):
    ax.set_facecolor(t["surface"])
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    for s in ("left", "bottom"): ax.spines[s].set_color(t["axis"]); ax.spines[s].set_linewidth(0.8)
    ax.tick_params(colors=t["muted"], labelcolor=t["ink2"], length=0)
    ax.grid(axis="x" if horizontal else "y", color=t["grid"], linewidth=0.8)
    ax.set_axisbelow(True)
def fig(t, w=6.4, h=3.2):
    f, ax = plt.subplots(figsize=(w, h), dpi=100)
    f.patch.set_facecolor(t["surface"]); frame(ax, t)
    return f, ax
def legend(ax, t, **kw):
    lg = ax.legend(frameon=False, labelcolor=t["ink2"], **kw)
    return lg
def title(ax, t, text):
    ax.set_title(text, loc="left", color=t["ink"], fontsize=11, fontweight="semibold", pad=10)
def save(f, name, mode):
    f.tight_layout(); f.savefig(OUT / f"{name}-{mode}.svg", facecolor=f.get_facecolor()); plt.close(f)
def hbars(t, name, mode, labels, vals, unit, ttl, xmax=None, fmt="{:,.0f}"):
    f, ax = fig(t, h=0.55 * len(labels) + 1.0); frame(ax, t, horizontal=True)
    y = range(len(labels))[::-1]
    ax.barh(list(y), vals, height=0.42, color=t["s"][0], edgecolor=t["surface"], linewidth=2)
    for yi, v in zip(y, vals):
        ax.text(v, yi, "  " + fmt.format(v) + unit, va="center", ha="left", color=t["ink"], fontsize=9.5)
    ax.set_yticks(list(y)); ax.set_yticklabels(labels)
    ax.set_xlim(0, (xmax or max(vals)) * 1.18)
    title(ax, t, ttl); save(f, name, mode)

# ---------- 그림 ----------
def plot_all(mode):
    t = THEMES[mode]
    # M1-a: 네트워크
    ip = iperf()
    nn = st.mean([ip["jetson0 -> jetson1 (eth)"][0], ip["jetson1 -> jetson2 (eth)"][0], ip["jetson0 -> jetson1 (eth)"][1], ip["jetson1 -> jetson2 (eth)"][1]])
    cl_rx = st.mean(v[1] for k, v in ip.items() if k.startswith("jetson -> ") and "eth" in k)
    cl_tx = st.mean(v[0] for k, v in ip.items() if k.startswith("jetson -> ") and "eth" in k)
    wifi = st.mean(ip["jetson -> jetson1 (wifi, ref)"])
    hbars(t, "m1a-network", mode, ["Server <-> server (1GbE)", "Server -> client (1GbE)", "Client -> server (1GbE)", "WiFi (reference)"],
          [nn, cl_rx, cl_tx, wifi], " Mb/s", "Node-to-node bandwidth (iperf3)")
    # M1-b: striping
    c = c2()
    cats = ["1 OST", "2 OSTs", "3 OSTs"]
    w = [st.mean(st.mean(x[0] for x in c[(f"ost{i}", "write", "4M", "1")]) for i in range(3)),
         st.mean(x[0] for x in c[("stripe2", "write", "4M", "1")]), st.mean(x[0] for x in c[("stripe3", "write", "4M", "1")])]
    r = [st.mean(st.mean(x[0] for x in c[(f"ost{i}", "read", "4M", "1")]) for i in range(3)),
         st.mean(x[0] for x in c[("stripe2", "read", "4M", "1")]), st.mean(x[0] for x in c[("stripe3", "read", "4M", "1")])]
    f, ax = fig(t); xs = range(3); bw = 0.14
    for i, (vals, lab, col) in enumerate([(w, "Write", t["s"][0]), (r, "Read", t["s"][1])]):
        pos = [x + (i - 0.5) * bw for x in xs]
        ax.bar(pos, vals, width=bw, color=col, edgecolor=t["surface"], linewidth=2, label=lab)
        for p, v in zip(pos, vals): ax.text(p, v + 2, f"{v:.0f}", ha="center", va="bottom", color=t["ink"], fontsize=9)
    ax.axhline(117, color=t["muted"], linewidth=1); ax.text(2.55, 120, "1GbE line rate", ha="right", va="bottom", color=t["ink2"], fontsize=8.5)
    ax.set_xticks(list(xs)); ax.set_xticklabels(cats); ax.set_ylim(0, 140); ax.set_xlim(-0.6, 2.6); ax.set_ylabel("MB/s", color=t["ink2"])
    legend(ax, t, loc="upper left", ncol=2); title(ax, t, "Client throughput vs. stripe count (remote OSTs)"); save(f, "m1b-striping", mode)
    # M2-a: 로컬 vs 원격
    d = x1()
    f, ax = fig(t); xs = range(2); bw = 0.11
    loc = [d[("local", "write", "1")][0], d[("local", "read", "1")][0]]
    rem = [d[("remote", "write", "1")][0], d[("remote", "read", "1")][0]]
    for i, (vals, lab, col) in enumerate([(loc, "Local OST (same node)", t["s"][0]), (rem, "Remote OST (1GbE)", t["s"][1])]):
        pos = [x + (i - 0.5) * bw for x in xs]
        ax.bar(pos, vals, width=bw, color=col, edgecolor=t["surface"], linewidth=2, label=lab)
        for p, v in zip(pos, vals): ax.text(p, v + 40, f"{v:,.0f}", ha="center", va="bottom", color=t["ink"], fontsize=9)
    for x, a, b in zip(xs, loc, rem):
        ax.text(x, max(a, b) + 330, f"{a / b:.0f}x faster", ha="center", color=t["ink"], fontsize=10, fontweight="semibold")
    ax.set_xticks(list(xs)); ax.set_xticklabels(["Write (direct)", "Read (direct)"]); ax.set_ylim(0, 3200); ax.set_xlim(-0.6, 1.6)
    ax.set_ylabel("MB/s", color=t["ink2"]); legend(ax, t, loc="upper left")
    title(ax, t, "Same-node vs. remote OST access (2 GiB, 4 MiB I/O)"); save(f, "m2a-local-remote", mode)
    # M2-b: I/O가 쓰는 CPU
    oss = st.mean([x[1] for k, v in c.items() if k[0] in ("ost0", "ost2") for x in v])
    hbars(t, "m2b-io-cpu", mode,
          ["Local OST read", "Local OST write", "Remote OST read (client side)", "Remote OST write (client side)", "OSS serving remote I/O (server side)"],
          [d[("local", "read", "1")][1], d[("local", "write", "1")][1], d[("remote", "read", "1")][1], d[("remote", "write", "1")][1], oss],
          "%", "CPU used while doing I/O (% of 6 cores)", fmt="{:.0f}")
    # M3: prefill vs KV 복원
    k = x2(); ns = list(k)
    f, ax = fig(t, h=3.4)
    series = [("Recompute (prefill)", 0, t["s"][2]), ("Restore KV from remote OST", 2, t["s"][1]), ("Restore KV from local OST", 1, t["s"][0])]
    for lab, idx, col in series:
        ys = [k[n][idx] for n in ns]
        ax.plot(ns, ys, color=col, linewidth=2, marker="o", markersize=6, markeredgecolor=t["surface"], markeredgewidth=2, label=lab, solid_capstyle="round")
        ax.text(ns[-1] * 1.06, ys[-1], f"{ys[-1]:.1f} s", va="center", color=t["ink"], fontsize=9)
    ax.set_xscale("log", base=2); ax.set_xticks(ns); ax.set_xticklabels([f"{n // 1024}k" for n in ns]); ax.set_xlim(ns[0] * 0.85, ns[-1] * 1.45)
    ax.set_xlabel("Context length (tokens)", color=t["ink2"]); ax.set_ylabel("Seconds", color=t["ink2"]); ax.set_ylim(0, 24)
    legend(ax, t, loc="upper left"); title(ax, t, "Recompute vs. restore stored KV (Qwen3-4B Q4, Orin Nano)"); save(f, "m3-prefill-vs-kv", mode)
    # M4-a: 캐시가 차지하는 메모리
    m = c5()
    hbars(t, "m4a-cache-memfree", mode, ["Default cache cap (3,810 MB)", "Cache cap 512 MB"], [m[3810], m[512]], " MiB",
          "Free memory lost after one 2 GiB buffered read")
    # M4-b: GPU 할당 시간
    g = x3()
    f, ax = fig(t); xs = range(2); bw = 0.1
    for i, (cond, lab, col) in enumerate([("A", "Cache empty", t["s"][0]), ("B", "Cache full (~3.9 GB)", t["s"][1]), ("C", "Cache capped 512 MB", t["s"][2])]):
        vals = [g[(4, cond)][0], g[(5, cond)][0]]
        pos = [x + (i - 1) * bw for x in xs]
        ax.bar(pos, vals, width=bw, color=col, edgecolor=t["surface"], linewidth=2, label=lab)
        for p, v in zip(pos, vals): ax.text(p, v + 30, f"{v:,}", ha="center", va="bottom", color=t["ink"], fontsize=8.5)
    ax.set_xticks(list(xs)); ax.set_xticklabels(["Allocate 4 GiB", "Allocate 5 GiB"]); ax.set_ylim(0, 2900); ax.set_xlim(-0.6, 1.6)
    ax.set_ylabel("Milliseconds", color=t["ink2"]); legend(ax, t, loc="upper left", ncol=3, fontsize=8.5)
    title(ax, t, "GPU memory allocation time vs. Lustre client cache"); save(f, "m4b-cache-gpu", mode)

for mode in ("light", "dark"):
    plot_all(mode)
print(sorted(p.name for p in OUT.glob("*.svg")))
