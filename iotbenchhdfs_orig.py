#!/usr/bin/env python3
"""
iotBenchHDFS_v2.py — Python-based I/O benchmark targeting HDFS (spawn-safe)

- Spawns TWO processes to write TWO datasets concurrently.
- Reports throughput PER DATASET + aggregate.
- Uses multiprocessing "spawn" start method to avoid fork() warning/deadlocks on Python 3.13.
- Uses pyarrow.hdfs (pip install pyarrow).

Usage example:
  python iotBenchHDFS_v2.py \
      --base-dir /data/iot_datasets \
      --datasets 0 3 \
      --hdfs-host nn1 --hdfs-port 8020 --hdfs-base /bench \
      --buffer-size 4MiB \
      --blocksize 256MiB --replication 2
"""

import argparse
import os
import sys
import time
import re
from typing import List, Optional
import multiprocessing as mp

try:
    from pyarrow import fs 
except ImportError:
    print("ERROR: pyarrow is required. Install with: pip install pyarrow", file=sys.stderr)
    sys.exit(1)

def human_to_bytes(s: str) -> int:
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
    if unit in ("K", "KB"):   return value * 1000
    if unit in ("KI", "KIB"): return value * 1024
    if unit in ("M", "MB"):   return value * 1000**2
    if unit in ("MI", "MIB"): return value * 1024**2
    if unit in ("G", "GB"):   return value * 1000**3
    if unit in ("GI", "GIB"): return value * 1024**3
    raise ValueError(f"Unknown unit: {unit}")

def list_datasets(base_dir: str) -> List[str]:
    return sorted([d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))])

def walk_files(root: str) -> list[str]:
    files = []
    for dp, _, fns in os.walk(root):
        for fn in fns:
            files.append(os.path.join(dp, fn))
    return files

def open_hdfs(host: str, port: int, user: Optional[str] = None, extra_conf=None):
    # return pa.hdfs.connect(host=host, port=port, user=user, extra_conf=extra_conf or {})
    return fs.HadoopFileSystem(host=host, port=port, user=user, extra_conf=extra_conf or {})

def write_dataset_to_hdfs(dataset_name: str,
                          local_root: str,
                          hdfs_base: str,
                          host: str,
                          port: int,
                          buffer_size: int,
                          blocksize: Optional[int],
                          replication: Optional[int],
                          q: "mp.Queue",
                          user: Optional[str] = None):
    total_bytes = 0
    MAX_BYTES = 4 * 1024**3  # 4 GiB
    t0 = time.time()
    try:
        extra_conf = {}
        if blocksize is not None:
            extra_conf["dfs.blocksize"] = str(blocksize)
        if replication is not None:
            extra_conf["dfs.replication"] = str(replication)

        fs = open_hdfs(host, port, user=user, extra_conf=extra_conf)
        hdfs_dataset_dir = os.path.join(hdfs_base.rstrip("/"), dataset_name)
        try:
            fs.mkdir(hdfs_dataset_dir)
        except Exception:
            pass

        local_files = walk_files(local_root)
        buf = bytearray(buffer_size)

        for lf in local_files:
            if total_bytes >= MAX_BYTES:
                # print(f"[{dataset_name}] Reached 4 GB limit, stopping writes.")
                break

            rel = os.path.relpath(lf, start=local_root)
            hdfs_path = os.path.join(hdfs_dataset_dir, rel).replace("\\", "/")
            parent = os.path.dirname(hdfs_path)
            try:
                fs.mkdir(parent)
            except Exception:
                pass

            with open(lf, "rb") as src, fs.open_output_stream(hdfs_path) as dst:
                while True:
                    n = src.readinto(buf)
                    if not n: break
                    if total_bytes + n > MAX_BYTES:
                        n = MAX_BYTES - total_bytes
                        dst.write(memoryview(buf)[:n])
                        total_bytes += n
                        break

                    dst.write(memoryview(buf)[:n])
                    total_bytes += n

                    if total_bytes >= MAX_BYTES:
                        break

    except Exception as e:
        q.put(("error", dataset_name, str(e)))
        return
    finally:
        elapsed = max(time.time() - t0, 1e-9)
        q.put(("ok", dataset_name, total_bytes, elapsed))

def main():
    ap = argparse.ArgumentParser(description="Two-dataset concurrent HDFS writer with per-dataset throughput.")
    #ap.add_argument("--base-dir", required=True, help="Local base directory containing dataset subdirectories")
    ap.add_argument("--datasets", nargs=2, type=int, metavar=("IDX_A", "IDX_B"),
                    help="Two dataset indices to upload concurrently (defaults to 0 and 1)")
    ap.add_argument("--hdfs-host", default="sdc3")
    ap.add_argument("--hdfs-port", type=int, default=8020)
    ap.add_argument("--hdfs-base", default="/bench", help="HDFS base directory where datasets will be written")
    ap.add_argument("--buffer-size", default="4MiB", help="Per-stream buffer size (e.g., 4MiB, 8MB)")
    ap.add_argument("--blocksize", default=None, help="Override HDFS block size for this run (e.g., 256MiB)")
    ap.add_argument("--replication", default=None, help="Override HDFS replication for this run (e.g., 2)")
    ap.add_argument("--user", default=None, help="HDFS user (defaults to current user)")
    args = ap.parse_args()

    base_dir = "/home/dcslab/iot/datasets/"

    datasets = list_datasets(base_dir)
    if len(datasets) < 2:
        print(f"Need at least two datasets under {base_dir}. Found: {len(datasets)}", file=sys.stderr)
        sys.exit(2)

    print("Datasets:")
    for i, d in enumerate(datasets):
        print(f"  {i}: {d}")

    if not args.datasets:
        sel = (0, 1)
        print("No --datasets provided; defaulting to indices:", sel)
    else:
        sel = (args.datasets[0], args.datasets[1])

    try:
        dsA = datasets[sel[0]]
        dsB = datasets[sel[1]]
    except Exception:
        print(f"Invalid dataset indices {sel}. Valid range: 0..{len(datasets)-1}", file=sys.stderr)
        sys.exit(3)

    localA = os.path.join(args.base-dir if hasattr(args, 'base-dir') else base_dir, dsA)
    localB = os.path.join(args.base-dir if hasattr(args, 'base-dir') else base_dir, dsB)

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

    ctx = mp.get_context("spawn")
    q = ctx.Queue()

    t0 = time.time()
    pA = ctx.Process(target=write_dataset_to_hdfs,
                     args=(dsA, localA, args.hdfs_base, args.hdfs_host, args.hdfs_port,
                           buffer_bytes, block_bytes, repl, q, args.user))
    pB = ctx.Process(target=write_dataset_to_hdfs,
                     args=(dsB, localB, args.hdfs_base, args.hdfs_host, args.hdfs_port,
                           buffer_bytes, block_bytes, repl, q, args.user))
    pA.start(); pB.start()

    results = {}
    for _ in range(2):
        msg = q.get()
        if not msg: continue
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
    total_bytes = sum(v[1] for v in results.values() if v[0] == "ok")
    total_time = max(t1 - t0, 1e-9)
    total_thr = (total_bytes / (1024**2)) / total_time
    print(f"\nAggregate: bytes={total_bytes}  walltime={total_time:.3f}s  throughput={total_thr:.2f} MiB/s")

if __name__ == "__main__":
    try:
        mp.set_start_method("spawn", force=True)
    except RuntimeError:
        pass
    main()
