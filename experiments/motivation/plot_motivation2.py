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

if __name__ == "__main__":
    for mode in ("light", "dark"):
        plot_m9(mode); plot_m13(mode)
    print(sorted(p.name for p in (ROOT / "docs/figures").glob("m*.svg") if p.name[:3] in ("m9a", "m9b", "m13")))
