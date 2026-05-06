#!/usr/bin/env python3
"""
iotBenchLustre_v1.py — Python-based I/O benchmark to Lustre (or any POSIX FS) with metadata & I/O latency metrics.

Differences from HDFS version:
- NO HDFS / PyArrow dependency.
- Writes to normal directories (e.g., Lustre mount) via standard open/write.
- For each dataset, creates a destination directory and (optionally) runs:
    lfs setstripe -c <stripe_count> [-S <stripe_size>] <dest_dir>

Usage examples:
  # Single dataset -> /mnt/lustre/botiot
  python iotBenchLustre_v1.py \
    --base-dir /data/iot_datasets \
    --datasets 0 \
    --dest-base /mnt/lustre \
    --buffer-size 1MiB \
    --stripe-count 4 --stripe-size 1M

  # Two datasets -> /mnt/lustre/botiot and /mnt/lustre/epicsound
  python iotBenchLustre_v1.py \
    --base-dir /data/iot_datasets \
    --datasets 0 1 \
    --dest-base /mnt/lustre \
    --buffer-size 1MiB \
    --stripe-count 4
"""

import argparse
import os
import sys
import time
import re
from typing import List, Optional, Tuple, Dict, Any
import multiprocessing as mp
import subprocess
import shutil

def human_to_bytes(s: Optional[str]) -> Optional[int]:
    if s is None:
        return None
    s = s.strip()
    m = re.match(r'^(\d+)([KMG]i?B?)?$', s, re.IGNORECASE)
    if not m:
        raise ValueError(f"Invalid size: {s}")
    value = int(m.group(1))
    unit = (m.group(2) or "").upper()
    if unit in ("",):
        return value
    if unit in ("K", "KB"):
        return value * 1000
    if unit in ("KI", "KIB"):
        return value * 1024
    if unit in ("M", "MB"):
        return value * (1000 ** 2)
    if unit in ("MI", "MIB"):
        return value * (1024 ** 2)
    if unit in ("G", "GB"):
        return value * (1000 ** 3)
    if unit in ("GI", "GIB"):
        return value * (1024 ** 3)
    raise ValueError(f"Unknown unit: {unit}")

def list_datasets(base_dir: str) -> List[str]:
    return sorted(
        [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
    )

def walk_files(root: str) -> List[str]:
    files = []
    for dp, _, fns in os.walk(root):
        for fn in fns:
            files.append(os.path.join(dp, fn))
    return files

def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    idx = max(0, min(len(v) - 1, int(round((p / 100.0) * (len(v) - 1)))))
    return v[idx]

def set_lustre_stripe(path: str, stripe_count: Optional[int], stripe_size: Optional[str]):
    """
    Run lfs setstripe on the given directory if stripe_count (and optional stripe_size) are provided.
    Assumes 'lfs' is in PATH.
    """
    if stripe_count is None and stripe_size is None:
        return

    if shutil.which("lfs") is None:
        print(f"[WARN] 'lfs' command not found in PATH; skipping stripe setup for {path}", file=sys.stderr)
        return

    cmd = ["lfs", "setstripe"]
    if stripe_count is not None:
        cmd += ["-c", str(stripe_count)]
    if stripe_size is not None:
        cmd += ["-S", stripe_size]
    cmd.append(path)

    try:
        subprocess.run(cmd, check=True)
        print(f"[INFO] Applied stripe on {path}: {' '.join(cmd)}")
    except subprocess.CalledProcessError as e:
        print(f"[WARN] Failed to set stripe on {path}: {e}", file=sys.stderr)

def write_dataset_to_dir(dataset_name: str,
                         local_root: str,
                         dest_root: str,
                         buffer_size: int,
                         q: "mp.Queue"):
    """
    Worker process:
    - Reads all files under local_root.
    - Writes them under dest_root, preserving relative paths.
    - Measures:
        * Metadata latencies (mkdirs, open, close)
        * I/O latencies (per write() call)

    Reports a metrics dict via the queue.
    """

    total_bytes = 0
    MAX_BYTES = 4 * 1024**3  # 4 GiB

    meta_lat: List[float] = []
    io_lat: List[float] = []
    meta_ops = 0
    io_ops = 0
    t_dataset_start = time.time()

    try:
        # Ensure top-level destination dir exists (count as metadata once)
        t0 = time.monotonic()
        os.makedirs(dest_root, exist_ok=True)
        meta_lat.append(time.monotonic() - t0)
        meta_ops += 1

        local_files = walk_files(local_root)
        buf = bytearray(buffer_size)

        for lf in local_files:
            if total_bytes >= MAX_BYTES:
                #print(f"[{dataset_name}] Reached 4 GiB limit, stopping further writes.")
                break

            rel = os.path.relpath(lf, start=local_root)
            dest_path = os.path.join(dest_root, rel)
            parent = os.path.dirname(dest_path)

            # mkdir -p parent (metadata)
            t0 = time.monotonic()
            os.makedirs(parent, exist_ok=True)
            meta_lat.append(time.monotonic() - t0)
            meta_ops += 1

            # open dest (metadata)
            t0 = time.monotonic()
            dst = open(dest_path, "wb")
            meta_lat.append(time.monotonic() - t0)
            meta_ops += 1

            # write loop (I/O)
            with open(lf, "rb") as src:
                while True:

                    n = src.readinto(buf)
                    if not n:
                        break

                    if total_bytes + n > MAX_BYTES:
                        n = MAX_BYTES - total_bytes
                        t1 = time.monotonic()
                        dst.write(memoryview(buf)[:n])
                        t2 = time.monotonic()
                        io_lat.append(t2 - t1)
                        io_ops += 1
                        total_bytes += n
                        break

                    t1 = time.monotonic()
                    dst.write(memoryview(buf)[:n])
                    t2 = time.monotonic()
                    io_lat.append(t2 - t1)
                    io_ops += 1
                    total_bytes += n

                    if total_bytes >= MAX_BYTES:
                        #print(f"[{dataset_name}] Reached 4 GiB limit during file write, stopping.")
                        break

            # close dest (metadata)
            t0 = time.monotonic()
            dst.close()
            meta_lat.append(time.monotonic() - t0)
            meta_ops += 1


    except Exception as e:
        elapsed = max(time.time() - t_dataset_start, 1e-9)
        q.put({
            "dataset": dataset_name,
            "status": "error",
            "error": str(e),
            "elapsed": elapsed,
        })
        return
    else:
        elapsed = max(time.time() - t_dataset_start, 1e-9)
        io_ops_sec = io_ops / elapsed if elapsed > 0 else 0.0
        meta_ops_sec = meta_ops / elapsed if elapsed > 0 else 0.0
        io_p95_ms = percentile(io_lat, 95) * 1000.0
        meta_p95_ms = percentile(meta_lat, 95) * 1000.0
        mib = total_bytes / (1024 ** 2)
        thr = mib / elapsed if elapsed > 0 else 0.0

        q.put({
            "dataset": dataset_name,
            "status": "ok",
            "bytes": total_bytes,
            "elapsed": elapsed,
            "throughput_mib_s": thr,
            "io_ops": io_ops,
            "io_ops_sec": io_ops_sec,
            "io_p95_ms": io_p95_ms,
            "meta_ops": meta_ops,
            "meta_ops_sec": meta_ops_sec,
            "meta_p95_ms": meta_p95_ms,
        })

def main():
    ap = argparse.ArgumentParser(description="Lustre (or POSIX FS) writer with per-dataset metadata & I/O latency metrics.")
    #ap.add_argument("--base-dir", required=True, help="Local base directory containing dataset subdirectories")
    ap.add_argument("--datasets", nargs="+", type=int, metavar=("IDX", "IDX"), help="One or two dataset indices (e.g., --datasets 0 or --datasets 0 1)")
    ap.add_argument("--dest-base", required=True, help="Destination base directory (e.g., Lustre mount like /mnt/lustre)")
    ap.add_argument("--buffer-size", default="1MiB", help="Per-stream buffer size (e.g., 1MiB, 4MB)")
    ap.add_argument("--stripe-count", type=int, default=None, help="Lustre stripe count for each dataset destination directory")
    ap.add_argument("--stripe-size", default=None, help="Lustre stripe size string (e.g., 1M, 4M). Optional.")
    args = ap.parse_args()

    base_dir = "/home/dcslab/iot/datasets/"

    datasets = list_datasets(base_dir)
    if not datasets:
        print(f"No dataset directories under {base_dir}", file=sys.stderr)
        sys.exit(2)

    print("Datasets:")
    for i, d in enumerate(datasets):
        print(f"  {i}: {d}")

    # determine which datasets to run
    if not args.datasets:
        sel_idx = [0] if len(datasets) == 1 else [0, 1]
        print("No --datasets provided; defaulting to:", sel_idx)
    else:
        if len(args.datasets) not in (1, 2):
            print("--datasets accepts 1 or 2 indices", file=sys.stderr)
            sys.exit(3)
        sel_idx = args.datasets

    try:
        selected = [datasets[i] for i in sel_idx]
    except Exception:
        print(
            f"Invalid indices {sel_idx}. Valid: 0..{len(datasets)-1}",
            file=sys.stderr,
        )
        sys.exit(4)

    buffer_bytes = human_to_bytes(args.buffer_size)

    # Prepare destination directories for each dataset (create + setstripe)
    dest_map: Dict[str, str] = {}
    for ds in selected:
        dest_root = os.path.join(args.dest_base, ds)
        os.makedirs(dest_root, exist_ok=True)
        # set stripe if requested
        set_lustre_stripe(dest_root, args.stripe_count, args.stripe_size)
        dest_map[ds] = dest_root

    print("\n=== Run configuration ===")
    print(f"Destination base: {args.dest_base}")
    print(f"Selected datasets: {selected}")
    for ds in selected:
        print(f"  {ds}: dest_dir={dest_map[ds]}")
    print(f"Buffer size: {buffer_bytes} bytes")
    if args.stripe_count is not None:
        print(f"Stripe count: {args.stripe_count}")
    if args.stripe_size is not None:
        print(f"Stripe size: {args.stripe_size}")
    print("=========================\n")

    ctx = mp.get_context("spawn")
    q: "mp.Queue" = ctx.Queue()

    procs = []
    t0 = time.time()
    for ds in selected:
        local_root = os.path.join(base_dir, ds)
        dest_root = dest_map[ds]
        p = ctx.Process(
            target=write_dataset_to_dir,
            args=(ds, local_root, dest_root, buffer_bytes, q),
        )
        p.start()
        procs.append(p)

    results = [q.get() for _ in range(len(procs))]
    for p in procs:
        p.join()

    total_bytes = 0
    for r in results:
        if r.get("status") != "ok":
            print(f"[{r.get('dataset')}] ERROR: {r.get('error')}")
            continue
        total_bytes += r["bytes"]
        print(
            f"[{r['dataset']}] bytes={r['bytes']}  time={r['elapsed']:.3f}s  "
            f"thr={r['throughput_mib_s']:.2f} MiB/s"
        )
        print(
            f"  I/O:   ops={r['io_ops']}  ops/s={r['io_ops_sec']:.1f}  "
            f"p95={r['io_p95_ms']:.2f} ms"
        )
        print(
            f"  Meta:  ops={r['meta_ops']}  ops/s={r['meta_ops_sec']:.1f}  "
            f"p95={r['meta_p95_ms']:.2f} ms"
        )

    wall = max(time.time() - t0, 1e-9)
    agg_thr = (total_bytes / (1024 ** 2)) / wall
    print(
        f"\nAggregate: bytes={total_bytes}  walltime={wall:.3f}s  "
        f"throughput={agg_thr:.2f} MiB/s"
    )

if __name__ == "__main__":
    try:
        mp.set_start_method("spawn", force=True)
    except RuntimeError:
        pass
    main()
