#!/usr/bin/env python3
"""추가 Motivation 실측(results/motivation)으로 README 그림을 만든다. 스타일은 p0_env/plot_motivation.py와 같다."""
import csv, statistics as st, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "p0_env"))
from plot_motivation import THEMES, fig, frame, legend, title, save, plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "results/motivation"

def rows(path):
    return list(csv.DictReader(open(path), delimiter="\t"))
def pct(v, p):
    v = sorted(v); return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))]

# ---------- 결과 파싱 ----------
def m9():
    d = {}
    for r in rows(R / "m9/m9_act.tsv"):
        d.setdefault((r["label"].rsplit("_", 1)[0], r["mode"], int(r["bytes"])), []).append(float(r["ms"]))
    return d

def m13():
    """M13. 첫 반복의 per_record stripe 1 측정은 OST0000이 내려간 동안 실행되어 제외한다."""
    d = {}
    for i, r in enumerate(rows(R / "m13/m13.tsv")):
        if i == 0 and r["case"] == "per_record": continue
        d.setdefault((r["case"], int(r["stripe"])), []).append(r)
    return {k: {"ops_s": st.mean(float(x["ops_s"]) for x in v), "MB_s": st.mean(float(x["MB_s"]) for x in v),
                "rpcs_per_op": sum(int(x["mdc_rpcs"]) for x in v) / sum(int(x["n_ops"]) for x in v)} for k, v in d.items()}

def m7():
    d = {}
    for r in rows(R / "m7/m7.tsv"):
        d.setdefault((r["label"].rsplit("_", 1)[0], r["rw"]), {}).setdefault(r["label"], []).append(float(r["MB_s"]))
    # 조건별: 반복마다 흐름 합계와 최소 흐름
    return {k: (st.mean(sum(v) for v in reps.values()), min(min(v) for v in reps.values()), st.mean(st.mean(v) for v in reps.values()))
            for k, reps in d.items()}

def m1112():
    d = {}
    for r in rows(R / "m11_m12/m11_m12.tsv"):
        if not r["op"]: continue   # "<node> ready" 줄
        d.setdefault((r["mode"], r["case"], r["op"].split("_ost")[0]), []).append((int(r["k"]), float(r["ms"])))
    return d

def hbars_note(t, name, mode, labels, vals, notes, ttl, xlabel, xmax):
    f, ax = fig(t, h=0.55 * len(labels) + 1.2); frame(ax, t, horizontal=True)
    y = list(range(len(labels)))[::-1]
    ax.barh(y, vals, height=0.42, color=t["s"][0], edgecolor=t["surface"], linewidth=2)
    for yi, v, n in zip(y, vals, notes):
        ax.text(v, yi, "  " + n, va="center", ha="left", color=t["ink"], fontsize=9.5)
    ax.set_yticks(y); ax.set_yticklabels(labels); ax.set_xlim(0, xmax)
    ax.set_xlabel(xlabel, color=t["ink2"]); title(ax, t, ttl); save(f, name, mode)

# ---------- 그림 ----------
def plot_m9(mode):
    t = THEMES[mode]; d = m9()
    conds = [("idle", "No storage traffic"), ("rx", "Storage writes into receiving stage"),
             ("tx", "Storage reads from sending stage"), ("both", "Both")]
    big = [st.median(d[(c, "burst", 8192 * 5120)]) for c, _ in conds]
    hbars_note(t, "m9a-activation-handoff", mode, [l for _, l in conds], big,
               [f"{v:,.0f} ms" + ("" if i == 0 else f"  ({v / big[0]:.1f}x)") for i, v in enumerate(big)],
               "Prefill activation handoff, 8k tokens (40 MiB)", "Milliseconds (median)", max(big) * 1.35)
    hop = [st.median(d[(c, "ping", 5120)]) for c, _ in conds]
    p99 = [pct(d[(c, "ping", 5120)], 99) for c, _ in conds]
    hbars_note(t, "m9b-decode-hop", mode, [l for _, l in conds], hop,
               [f"{v:.1f} ms (p99 {q:.1f})" for v, q in zip(hop, p99)],
               "Per-token decode message round trip (5 KiB)", "Milliseconds (median)", max(hop) * 1.6)

def plot_m13(mode):
    t = THEMES[mode]; d = m13()
    keys = [(("per_record", 1), "One file per record, stripe 1"), (("per_record", 3), "One file per record, stripe 3"),
            (("pack", 1), "Append to one pack (fsync every 32)")]
    vals = [d[k]["ops_s"] for k, _ in keys]
    notes = [f"{d[k]['ops_s']:,.0f} rec/s, {d[k]['rpcs_per_op']:.2f} MDS RPC/rec" if k[0] != "pack" else
             f"{d[k]['ops_s']:,.0f} rec/s ({d[k]['ops_s'] / vals[0]:.0f}x), {d[k]['rpcs_per_op']:.4f} MDS RPC/rec" for k, _ in keys]
    hbars_note(t, "m13-ingest-pack", mode, [l for _, l in keys], vals, notes,
               "Ingesting 3,000 IoT records of 512 B (client jetson)", "Records per second", max(vals) * 2.5)

def plot_m7(mode):
    t = THEMES[mode]; d = m7()
    f, ax = fig(t); xs = range(2); bw = 0.12
    for i, (cond, lab, col) in enumerate([("same", "3 flows on one OSS", t["s"][1]), ("spread", "3 flows on separate OSSes", t["s"][0])]):
        vals = [d[(cond, rw)][0] for rw in ("read", "write")]
        pos = [x + (i - 0.5) * bw for x in xs]
        ax.bar(pos, vals, width=bw, color=col, edgecolor=t["surface"], linewidth=2, label=lab)
        for p_, v, rw in zip(pos, vals, ("read", "write")):
            ax.text(p_, v + 6, f"{v:.0f}", ha="center", va="bottom", color=t["ink"], fontsize=9)
    for x, rw in zip(xs, ("read", "write")):
        ax.text(x, max(d[("spread", rw)][0], d[("same", rw)][0]) + 34, f"{d[('spread', rw)][0] / d[('same', rw)][0]:.1f}x",
                ha="center", color=t["ink"], fontsize=10, fontweight="semibold")
    ax.set_xticks(list(xs)); ax.set_xticklabels(["Read (direct, 4 MiB)", "Write (direct, 4 MiB)"]); ax.set_xlim(-0.6, 1.6); ax.set_ylim(0, 380)
    ax.set_ylabel("Total MB/s of 3 clients", color=t["ink2"]); legend(ax, t, loc="upper right")
    title(ax, t, "Three clients sharing one OSS vs. separate OSSes"); save(f, "m7-oss-sharing", mode)

def plot_m12(mode):
    t = THEMES[mode]; d = m1112()
    ks = [1, 2, 3, 4, 5]
    rem = [v for _, v in sorted(d[("relocation", "remote", "restore")])]
    rec = [v for _, v in sorted(d[("relocation", "recompute", "prefill")])]
    rel = dict(sorted(d[("relocation", "relocate", "restore")])); mig = d[("relocation", "relocate", "migrate")][0][1]
    cum = lambda xs: [sum(xs[:i + 1]) / 1000 for i in range(len(xs))]
    rel_steps = [rel[1] + mig] + [rel[k] for k in ks[1:]]
    f, ax = fig(t, h=3.4)
    for lab, ys, col in [("Recompute every time (prefill)", cum(rec), t["s"][2]), ("Keep KV on remote OST", cum(rem), t["s"][1]),
                         ("Move KV to local OST after first use", cum(rel_steps), t["s"][0])]:
        ax.plot(ks, ys, color=col, linewidth=2, marker="o", markersize=6, markeredgecolor=t["surface"], markeredgewidth=2, label=lab)
        ax.text(5.15, ys[-1], f"{ys[-1]:.1f} s", va="center", color=t["ink"], fontsize=9)
    ax.set_xticks(ks); ax.set_xlim(0.8, 5.7); ax.set_ylim(0, 40)
    ax.set_xlabel("Number of uses of the same 4k-token KV (576 MiB)", color=t["ink2"]); ax.set_ylabel("Cumulative seconds", color=t["ink2"])
    legend(ax, t, loc="upper left"); title(ax, t, "Read-aware relocation of a remote KV (jetson1)"); save(f, "m12-relocation", mode)

def plot_m11(mode):
    t = THEMES[mode]; d = m1112()
    cases = [("none", "No checkpoint"), ("concurrent", "Checkpoint at full speed"), ("throttled", "Checkpoint limited to 100 MB/s"),
             ("deferred", "Checkpoint deferred to gaps")]
    med = [st.median(v for _, v in d[("ckpt", c, "restore")]) for c, _ in cases]
    ck = [d.get(("ckpt", c, "ckpt_MiB_per_s"), [(0, 0)])[0][1] for c, _ in cases]
    mx = [max(v for _, v in d[("ckpt", c, "restore")]) for c, _ in cases]
    notes = [f"{m:,.0f} ms (max {x:,.0f})" + (f", ckpt {c:,.0f} MiB/s" if c else "") for m, x, c in zip(med, mx, ck)]
    hbars_note(t, "m11-runtime-aware", mode, [l for _, l in cases], med, notes,
               "KV restore (576 MiB) next to checkpoint writes, same OST", "Milliseconds (median of 10)", max(med) * 2.3)

def plot_f7(mode):
    import datetime
    t = THEMES[mode]; r = rows(R / "watch/j1_watch_crash2.tsv")
    t0 = float(r[0]["t"]); sel = [x for x in r if float(x["t"]) - t0 > 13 * 60]
    xs = [(float(x["t"]) - t0) / 60 for x in sel]
    f, ax = fig(t, h=3.4)
    ax.plot(xs, [int(x["mem_avail_MiB"]) for x in sel], color=t["s"][0], linewidth=2, label="MemAvailable")
    ax.plot(xs, [int(x["swap_used_MiB"]) for x in sel], color=t["s"][1], linewidth=2, label="zram swap used")
    # 시점 번호 (README 3장 표와 같다). 배치 로그 시각 - 감시 시작 18:02:12
    for i, xm in enumerate([13.5, 16.75, 17.1, 17.7, 18.75, 19.85], 1):
        ax.axvline(xm, color=t["grid"], linewidth=1)
        ax.text(xm, 7050, str(i), ha="center", va="bottom", color=t["ink"], fontsize=9, fontweight="semibold")
    ax.set_xlim(xs[0], xs[-1] + 0.4); ax.set_ylim(0, 7600)
    ax.set_xlabel("Minutes since batch start (jetson1)", color=t["ink2"]); ax.set_ylabel("MiB", color=t["ink2"])
    legend(ax, t, loc="center", bbox_to_anchor=(0.42, 0.62)); title(ax, t, "Memory on jetson1 before the second hang (1 s samples)"); save(f, "m10-jetson1-hang", mode)

def plot_m6(mode):
    t = THEMES[mode]
    r = [l.split("\t") for l in (ROOT / "results/p0/jetson/c8_planner.txt").read_text().splitlines() if l[:1].isdigit() and "\t" in l]
    pre = [float(x[2]) / 1000 for x in r]; gen = [int(x[4]) / float(x[5]) for x in r]; wall = [float(x[6]) for x in r]
    labels = ["Decision 1 (new prompt)", "Decision 2 (prompt cached)", "Decision 3 (prompt cached)"]
    f, ax = fig(t, h=0.55 * 3 + 1.9); frame(ax, t, horizontal=True)
    y = [2, 1, 0]
    ax.barh(y, pre, height=0.42, color=t["s"][0], edgecolor=t["surface"], linewidth=2, label="Prefill (1,653-token prompt)")
    ax.barh(y, gen, left=pre, height=0.42, color=t["s"][2], edgecolor=t["surface"], linewidth=2, label="Generate JSON plan (~15 tok/s)")
    for yi, w in zip(y, wall):
        ax.text(w, yi, f"  {w:.1f} s total", va="center", color=t["ink"], fontsize=9.5)
    ax.set_yticks(y); ax.set_yticklabels(labels); ax.set_xlim(0, 30); ax.set_xlabel("Seconds", color=t["ink2"])
    legend(ax, t, loc="upper center", bbox_to_anchor=(0.45, -0.28), ncol=2, fontsize=8.5)
    title(ax, t, "LLM planner decision time (Qwen3-4B Q4, 4.1 GB resident)"); save(f, "m6-planner", mode)

def plot_m10b(mode):
    t = THEMES[mode]; d = R / "m10_run2"
    r = rows(d / "j1_samp_idle_1.tsv") + [x for x in rows(d / "j1_samp_direct_1.tsv")]
    r = sorted({x["t"]: x for x in r}.values(), key=lambda x: float(x["t"]))
    t0 = float(r[0]["t"]); r = [x for x in r if float(x["t"]) - t0 <= 100]; xs = [float(x["t"]) - t0 for x in r]
    f, ax = fig(t, h=3.2)
    ax.plot(xs, [int(x["mem_avail_MiB"]) for x in r], color=t["s"][0], linewidth=2, label="MemAvailable")
    ax.axhline(700, color=t["s"][1], linewidth=1.2, linestyle=(0, (4, 3)))
    ax.text(xs[-1], 760, "guard threshold 700 MiB", ha="right", va="bottom", color=t["ink2"], fontsize=8.5)
    for i, xm in enumerate([0, 62, 72, 76], 1):   # README 3장 표의 번호
        ax.axvline(xm, color=t["grid"], linewidth=1)
        ax.text(xm, 7250, str(i), ha="center", va="bottom", color=t["ink"], fontsize=9, fontweight="semibold")
    ax.set_xlim(-3, xs[-1] + 2); ax.set_ylim(0, 7800); legend(ax, t, loc="center left")
    ax.set_xlabel("Seconds", color=t["ink2"]); ax.set_ylabel("MiB", color=t["ink2"])
    title(ax, t, "jetson1 memory with the guard on (llama-server ctx 8192)"); save(f, "m10b-guard", mode)

def plot_m5(mode):
    t = THEMES[mode]; d = {}
    for cond in ("idle", "read", "write"):
        for f in sorted((R / "m5").glob(f"j3_samp_m5_{cond}_*.tsv")):
            r = rows(f)[5:55]
            d.setdefault(cond, []).append((st.mean(float(x["cpu_pct"]) for x in r), st.mean(float(x["softirq_pct"]) for x in r)))
    cpu = [st.mean(v[0] for v in d[c]) for c in ("idle", "read", "write")]
    sirq = [st.mean(v[1] for v in d[c]) for c in ("idle", "read", "write")]
    hbars_note(t, "m5-oss-cpu", mode, ["Idle", "Serving remote reads (114 MB/s)", "Serving remote writes (93 MB/s)"], cpu,
               [f"{c:.1f}% (softirq {q:.1f}%)" for c, q in zip(cpu, sirq)],
               "OSS node CPU while serving one remote client (jetson3)", "% of 6 cores", 30)

def llm_by_cond(path):
    d = {}
    for r in rows(path):
        d.setdefault(r["label"].rsplit("_", 1)[0], []).append(r)
    return {c: {"prefill": st.mean(float(x["prefill_tok_s"]) for x in v), "decode": st.mean(float(x["decode_tok_s"]) for x in v),
                "gap_p99": st.mean(float(x["gap_p99_ms"]) for x in v), "n": len(v)} for c, v in d.items()}

def plot_m8(mode):
    t = THEMES[mode]
    loc, rem = llm_by_cond(R / "m8_local_cr0/m8_llm.tsv"), llm_by_cond(R / "m8_remote_cr0/m8_llm.tsv")
    idle = loc["idle"]
    conds = [(rem, "rread", "Remote client reads this OST"), (rem, "rwrite", "Remote client writes this OST"),
             (loc, "lread", "Local direct read"), (loc, "lwrite", "Local direct write"),
             (loc, "lread_buf", "Local buffered read"), (loc, "lwrite_buf", "Local buffered write")]
    conds = [c for c in conds if c[1] in c[0]]
    f, ax = fig(t, h=0.62 * len(conds) + 1.4); frame(ax, t, horizontal=True)
    y = list(range(len(conds)))[::-1]; bh = 0.3
    for i, (key, lab, col) in enumerate([("prefill", "Prefill speed", t["s"][0]), ("decode", "Decode speed", t["s"][2])]):
        vals = [100 * src[c][key] / idle[key] for src, c, _ in conds]
        pos = [yy + (0.5 - i) * bh for yy in y]
        ax.barh(pos, vals, height=bh, color=col, edgecolor=t["surface"], linewidth=2, label=lab)
        for p_, v in zip(pos, vals):
            ax.text(v, p_, f" {v:.0f}%", va="center", color=t["ink"], fontsize=8.5)
    ax.axvline(100, color=t["muted"], linewidth=1)
    ax.set_yticks(y); ax.set_yticklabels([l for _, _, l in conds]); ax.set_xlim(0, 125)
    ax.set_xlabel("% of LLM speed with no storage I/O (jetson1, Qwen3-4B Q4, ctx 4096)", color=t["ink2"])
    legend(ax, t, loc="upper center", bbox_to_anchor=(0.45, -0.2), ncol=2, fontsize=8.5)
    title(ax, t, "LLM speed on an OSS node during storage I/O"); save(f, "m8-llm-under-io", mode)

def plot_m14(mode):
    t = THEMES[mode]; d = {}
    for r in rows(R / "m14_cr0/m14.tsv"):
        d.setdefault(r["policy"], []).append(float(r["ttft_ms"]) / 1000)
    f, ax = fig(t, h=3.4)
    for pol, lab, col in [("lustre_default", "Lustre default allocator", t["s"][1]), ("balanced", "Load-balanced across OSSes (ignores the using node)", t["s"][2]),
                          ("local", "OST of the node that uses the KV", t["s"][0])]:
        if pol not in d: continue
        v = sorted(d[pol]); ys = [(i + 1) / len(v) for i in range(len(v))]
        ax.step(v, ys, where="post", color=col, linewidth=2, label=lab)
    ax.set_xscale("log"); ax.set_ylim(0, 1.02); ax.set_xlabel("Time to first token, seconds (log)", color=t["ink2"]); ax.set_ylabel("Fraction of requests", color=t["ink2"])
    ticks = [0.5, 1, 2, 5, 10, 20, 40]; ax.set_xticks(ticks); ax.set_xticklabels([f"{x:g}" for x in ticks]); ax.minorticks_off(); ax.set_xlim(0.5, 50)
    legend(ax, t, loc="upper left", bbox_to_anchor=(0.2, 0.98), fontsize=8.5)
    title(ax, t, "TTFT by KV placement policy (3 stage nodes, 12 stream contexts)"); save(f, "m14-ttft-cdf", mode)

def plot_m10c(mode):
    t = THEMES[mode]; d = R / "m10_cr0"; llm = llm_by_cond(d / "m10_llm.tsv")
    conds = [("direct", "Direct read (no page cache)"), ("buf_cap512", "Buffered read, cache cap 512 MB"), ("buf_default", "Buffered read, default cap 3,810 MB")]
    vals, notes = [], []
    for c, _ in conds:
        reps = [rows(f) for f in sorted(d.glob(f"j1_samp_{c}_*.tsv"))]
        scans = st.mean(sum(int(x["scan_direct"]) for x in r) for r in reps)
        kswapd = st.mean(sum(int(x["scan_kswapd"]) for x in r) for r in reps)
        vals.append(scans / 1000)
        notes.append(f"{scans / 1000:,.0f}k / {kswapd / 1000:,.0f}k, decode {100 * llm[c]['decode'] / llm['idle']['decode'] - 100:+.1f}%")
    hbars_note(t, "m10c-reclaim", mode, [l for _, l in conds], vals, notes,
               "Page reclaim during same-node Lustre reads (jetson1)", "Direct-reclaim scans per 85 s (thousands; label direct / kswapd)", max(vals) * 2.4)

if __name__ == "__main__":
    import os
    for mode in ("light", "dark"):
        if (R / "m8_remote_cr0/m8_llm.tsv").exists() and (R / "m8_local_cr0/m8_llm.tsv").exists(): plot_m8(mode)
        if (R / "m14_cr0/m14.tsv").exists(): plot_m14(mode)
        plot_m9(mode); plot_m13(mode); plot_m7(mode); plot_m11(mode); plot_m12(mode); plot_f7(mode); plot_m6(mode); plot_m10b(mode); plot_m5(mode); plot_m10c(mode)
    print(sorted(p.name for p in (ROOT / "docs/figures").glob("m*.svg") if p.name[:3] in ("m5-", "m6-", "m7-", "m9a", "m9b", "m10", "m11", "m12", "m13")))
