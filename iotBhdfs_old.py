#!/usr/bin/env python3
"""
iotBenchHDFS_v2.py — Python-based I/O benchmark targeting HDFS

Features:
- Lists datasets under a base directory and lets you choose by index.
- Spawns two processes to write TWO datasets concurrently to HDFS.
- Reports throughput PER DATASET (MiB/s), plus aggregate.
- Optional flags to override HDFS blocksize/replication for this run.
- Uses pyarrow.hdfs client (install with: pip install pyarrow)

Example:
  python iotBenchHDFS_v2.py \
      --base-dir /data/iot_datasets \
      --datasets 0 3 \
      --hdfs-host nn1 --hdfs-port 8020 --hdfs-base /bench \
      --buffer-size 4MiB \
      --blocksize 256MiB --replication 2

Notes:
- Datasets are subdirectories inside --base-dir.
- Each dataset's directory tree is uploaded to HDFS under:
    {hdfs-base}/{dataset_name}/<relative_path_of_file>
- Per-file throughput uses buffered streaming (no temp local copies).
"""

import argparse
import os
import sys
import time
import math
import re
import multiprocessing as mp
from typing import List, Tuple, Optional

try:
    import pyarrow as pa
except ImportError:
    print("ERROR: pyarrow is required. Install with: pip install pyarrow", file=sys.stderr)
    sys.exit(1)


def human_to_bytes(s: str) -> int:
    """
    Convert human size strings like '4MiB', '256MB', '1G', '512k' to bytes.
    Defaults to bytes if no unit is given.
    """
    if s is None:
        return None
    s = s.strip()
    m = re.match(r'^(\d+)([KMG]i?B?)?$', s, re.IGNORECASE)
    if not m:
        raise ValueError(f"Invalid size: {s}")
    value = int(m.group(1))
    unit = m.group(2)
    if not unit:
        return value
    unit = unit.upper()
    if unit in ("K", "KB"):
        return value * 1000
    if unit in ("KI", "KIB"):
        return value * 1024
    if unit in ("M", "MB"):
        return value * 1000**2
    if unit in ("MI", "MIB"):
        return value * 1024**2
    if unit in ("G", "GB"):
        return value * 1000**3
    if unit in ("GI", "GIB"):
        return value * 1024**3
    raise ValueError(f"Unknown unit: {unit}")


def list_datasets(base_dir: str) -> List[str]:
    entries = []
    for d in sorted(os.listdir(base_dir)):
        p = os.path.join(base_dir, d)
        if os.path.isdir(p):
            entries.append(d)
    return entries


def walk_files(root: str) -> List[str]:
    files = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            files.append(os.path.join(dirpath, fn))
    return files


def open_hdfs(host: str, port: int, user: Optional[str] = None, extra_conf=None):
    return pa.hdfs.connect(host=host, port=port, user=user, extra_conf=extra_conf or {})


def write_dataset_to_hdfs(dataset_name: str,
                          local_root: str,
                          hdfs_base: str,
                          host: str,
                          port: int,
                          buffer_size: int,
                          blocksize: Optional[int],
                          replication: Optional[int],
                          result_q: Queue,
                          user: Optional[str] = None):
    """
    Worker process: streams all files under local_root to HDFS under hdfs_base/dataset_name.
    Reports total bytes and duration back via result_q.
    """
    total_bytes = 0
    t0 = time.time()
    try:
        extra_conf = {}
        if blocksize is not None:
            extra_conf["dfs.blocksize"] = str(blocksize)
        if replication is not None:
            extra_conf["dfs.replication"] = str(replication)

        fs = open_hdfs(host, port, user=user, extra_conf=extra_conf)

        # Ensure dataset directory exists
        hdfs_dataset_dir = os.path.join(hdfs_base.rstrip("/"), dataset_name)
        try:
            fs.mkdir(hdfs_dataset_dir)
        except Exception:
            # ignore if exists
            pass

        local_files = walk_files(local_root)
        buf = bytearray(buffer_size)

        for lf in local_files:
            rel = os.path.relpath(lf, start=local_root)
            hdfs_path = os.path.join(hdfs_dataset_dir, rel).replace("\\", "/")
            # Ensure parent dirs
            parent = os.path.dirname(hdfs_path)
            try:
                fs.mkdir(parent)
            except Exception:
                pass

            # Stream copy
            with open(lf, "rb") as src, fs.open_output_stream(hdfs_path) as dst:
                while True:
                    n = src.readinto(buf)
                    if not n:
                        break
                    dst.write(memoryview(buf)[:n])
                    total_bytes += n

    except Exception as e:
        result_q.put(("error", dataset_name, str(e)))
        return
    finally:
        t1 = time.time()
        elapsed = max(t1 - t0, 1e-9)
        result_q.put(("ok", dataset_name, total_bytes, elapsed))


def main():
    ap = argparse.ArgumentParser(description="Two-dataset concurrent HDFS writer with per-dataset throughput reporting.")
    # ap.add_argument("--base-dir", required=True, help="Local base directory containing dataset subdirectories")
    ap.add_argument("--datasets", nargs=2, type=int, metavar=("IDX_A", "IDX_B"),
                    help="Two dataset indices to upload concurrently (from list under base-dir)")
    ap.add_argument("--hdfs-host", default="sdc3")
    ap.add_argument("--hdfs-port", type=int, default=8020)
    ap.add_argument("--hdfs-base", default="/bench", help="HDFS base directory where datasets will be written")
    ap.add_argument("--buffer-size", default="4MiB", help="Per-stream buffer size (e.g., 4MiB, 8MB)")
    ap.add_argument("--blocksize", default=None, help="Override HDFS block size for this run (e.g., 256MiB)")
    ap.add_argument("--replication", default=None, help="Override HDFS replication for this run (e.g., 2)")
    ap.add_argument("--user", default=None, help="HDFS user (defaults to current user)")
    args = ap.parse_args()

    base_dir = "/home/dcslab/iot/datasets/"

    # datasets = list_datasets(args.base_dir)
    datasets = list_datasets(base_dir)
    if not datasets:
        print(f"No dataset directories found under {base_dir}", file=sys.stderr)
        sys.exit(2)

    print("Datasets under base-dir:")
    for i, d in enumerate(datasets):
        print(f"  {i}: {d}")

    # If user didn't pass indices, default to 0 and 1 (hard-coded convenience)
    if not args.datasets:
        if len(datasets) < 2:
            print("Need at least two datasets. Specify with --datasets IDX_A IDX_B.", file=sys.stderr)
            sys.exit(3)
        sel = (0, 1)
        print("No --datasets provided; defaulting to indices:", sel)
    else:
        sel = tuple(args.datasets)

    try:
        dsA = datasets[sel[0]]
        dsB = datasets[sel[1]]
    except Exception:
        print(f"Invalid dataset indices: {sel}. Available indices: 0..{len(datasets)-1}", file=sys.stderr)
        sys.exit(4)

    localA = os.path.join(base_dir, dsA)
    localB = os.path.join(base_dir, dsB)

    buffer_bytes = human_to_bytes(args.buffer_size)
    block_bytes = human_to_bytes(args.blocksize) if args.blocksize else None
    repl = int(args.replication) if args.replication else None

    print("\n=== Run configuration ===")
    print(f"HDFS: hdfs://{args.hdfs_host}:{args.hdfs_port}{args.hdfs_base}")
    print(f"Datasets: A={dsA}  B={dsB}")
    print(f"Buffer size: {buffer_bytes} bytes")
    if block_bytes: print(f"Override blocksize: {block_bytes} bytes")
    if repl: print(f"Override replication: {repl}")
    print("=========================\n")

    # Spawn two processes
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    pA = Process(target=write_dataset_to_hdfs,
                 args=(dsA, localA, args.hdfs_base, args.hdfs_host, args.hdfs_port,
                       buffer_bytes, block_bytes, repl, q, args.user))
    pB = Process(target=write_dataset_to_hdfs,
                 args=(dsB, localB, args.hdfs_base, args.hdfs_host, args.hdfs_port,
                       buffer_bytes, block_bytes, repl, q, args.user))
    t0 = time.time()
    pA.start(); pB.start()

    # Collect two results
    results = {}
    for _ in range(2):
        msg = q.get()
        if not msg:
            continue
        if msg[0] == "error":
            _, ds, err = msg
            print(f"[{ds}] ERROR: {err}", file=sys.stderr)
            results[ds] = ("error", 0, 0.0)
        else:
            _, ds, bytes_written, elapsed = msg
            mib = bytes_written / (1024**2)
            thr = mib / elapsed
            print(f"[{ds}] bytes={bytes_written}  time={elapsed:.3f}s  throughput={thr:.2f} MiB/s")
            results[ds] = ("ok", bytes_written, elapsed)

    pA.join(); pB.join()
    t1 = time.time()
    total_bytes = sum(v[1] for k, v in results.items() if v[0] == "ok")
    total_time = t1 - t0
    total_thr = (total_bytes / (1024**2)) / total_time if total_time > 0 else 0.0
    print(f"\nAggregate: bytes={total_bytes}  walltime={total_time:.3f}s  throughput={total_thr:.2f} MiB/s")


if __name__ == "__main__":
    try:
        mp.set_start_method("spawn", force=True)
    except RuntimeError:
        pass
    main()
