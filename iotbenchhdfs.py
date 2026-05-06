#!/usr/bin/env python3
"""
iotBenchHDFS_v3.py — Python-based HDFS I/O benchmark (spawn-safe) with metadata & I/O latency metrics.

- --datasets accepts one or two indices (single or concurrent run).
- Records metadata latency (mkdir/open/close): reports p95 + ops/sec.
- Records I/O write latency per write(): reports p95 + ops/sec.
- Reports per-dataset throughput and aggregate throughput.

Requires: pip install pyarrow
"""

import argparse, os, sys, time, re
from typing import List, Optional, Tuple
from urllib.parse import urlparse
import multiprocessing as mp

try:
    from pyarrow import fs as pafs
except ImportError:
    print("ERROR: pyarrow is required. Install with: pip install pyarrow", file=sys.stderr)
    sys.exit(1)

def human_to_bytes(s: Optional[str]) -> Optional[int]:
    if s is None: return None
    s = s.strip()
    m = re.match(r'^(\d+)([KMG]i?B?)?$', s, re.IGNORECASE)
    if not m: raise ValueError(f"Invalid size: {s}")
    value = int(m.group(1)); unit = (m.group(2) or '').upper()
    if unit in ("",): return value
    if unit in ("K","KB"): return value*1000
    if unit in ("KI","KIB"): return value*1024
    if unit in ("M","MB"): return value*(1000**2)
    if unit in ("MI","MIB"): return value*(1024**2)
    if unit in ("G","GB"): return value*(1000**3)
    if unit in ("GI","GIB"): return value*(1024**3)
    raise ValueError(f"Unknown unit: {unit}")

def list_datasets(base_dir: str) -> List[str]:
    return sorted([d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))])

def walk_files(root: str) -> List[str]:
    files = []
    for dp, _, fns in os.walk(root):
        for fn in fns:
            files.append(os.path.join(dp, fn))
    return files

def normalize_host_port(host_arg: str, port_arg: int) -> Tuple[str,int]:
    host, port = host_arg, port_arg
    if host.startswith(("hdfs://","HDFS://")):
        u = urlparse(host)
        if u.hostname: host = u.hostname
        if u.port: port = u.port
    return host, port

def percentile(values: List[float], p: float) -> float:
    if not values: return 0.0
    v = sorted(values)
    idx = max(0, min(len(v)-1, int(round((p/100.0)*(len(v)-1)))))
    return v[idx]

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
    """
    Streams all files under local_root to HDFS under hdfs_base/dataset_name.
    Collects metadata latencies (mkdir/open/close) and I/O write latencies.
    """
    total_bytes = 0
    MAX_BYTES = 4 * 1024**3  # 4 GiB

    meta_lat, io_lat = [], []
    meta_ops, io_ops = 0, 0
    t_dataset_start = time.time()
    try:
        extra_conf = {}
        if blocksize is not None:   extra_conf["dfs.blocksize"]   = str(blocksize)
        if replication is not None: extra_conf["dfs.replication"] = str(replication)

        # connect (count as metadata)
        t0 = time.monotonic()
        hdfs = pafs.HadoopFileSystem(host=host, port=port, user=user, extra_conf=extra_conf)
        meta_lat.append(time.monotonic() - t0); meta_ops += 1

        # dataset directory (metadata)
        hdfs_dataset_dir = os.path.join(hdfs_base.rstrip("/"), dataset_name)
        t0 = time.monotonic()
        try: hdfs.create_dir(hdfs_dataset_dir, recursive=True)
        except Exception: pass
        meta_lat.append(time.monotonic() - t0); meta_ops += 1

        local_files = walk_files(local_root)
        buf = bytearray(buffer_size)

        for lf in local_files:
            if total_bytes >= MAX_BYTES:
                #print(f"[{dataset_name}] Reached 4 GiB limit, stopping further writes.")
                break

            rel = os.path.relpath(lf, start=local_root)
            hdfs_path = os.path.join(hdfs_dataset_dir, rel).replace("\\","/")
            parent = os.path.dirname(hdfs_path)

            # ensure parent (metadata)
            t0 = time.monotonic()
            try: hdfs.create_dir(parent, recursive=True)
            except Exception: pass
            meta_lat.append(time.monotonic() - t0); meta_ops += 1

            # open (metadata)
            t0 = time.monotonic()
            dst = hdfs.open_output_stream(hdfs_path)
            meta_lat.append(time.monotonic() - t0); meta_ops += 1

            # write (I/O)
            with open(lf, "rb") as src:
                while True:
                    n = src.readinto(buf)
                    if not n: break
                    
                    if total_bytes + n > MAX_BYTES:
                        n = MAX_BYTES - total_bytes
                        t1 = time.monotonic()
                        dst.write(memoryview(buf)[:n])
                        t2 = time.monotonic()
                        io_lat.append(t2 - t1); io_ops += 1
                        total_bytes += n
                        break

                    t1 = time.monotonic()
                    dst.write(memoryview(buf)[:n])
                    t2 = time.monotonic()
                    io_lat.append(t2 - t1); io_ops += 1
                    total_bytes += n

                    if total_bytes >= MAX_BYTES:
                        #print(f"[{dataset_name}] Reached 4 GiB limit during file write, stopping.")
                        break

            # close (metadata)
            t0 = time.monotonic()
            dst.close()
            meta_lat.append(time.monotonic() - t0); meta_ops += 1

    except Exception as e:
        elapsed = max(time.time() - t_dataset_start, 1e-9)
        q.put({"dataset": dataset_name, "status":"error", "error":str(e), "elapsed":elapsed})
        return
    else:
        elapsed = max(time.time() - t_dataset_start, 1e-9)
        io_ops_sec = io_ops / elapsed
        meta_ops_sec = meta_ops / elapsed
        io_p95_ms = percentile(io_lat, 95) * 1000.0
        meta_p95_ms = percentile(meta_lat, 95) * 1000.0
        mib = total_bytes / (1024**2)
        thr = mib / elapsed
        q.put({
            "dataset": dataset_name, "status":"ok",
            "bytes": total_bytes, "elapsed": elapsed, "throughput_mib_s": thr,
            "io_ops": io_ops, "io_ops_sec": io_ops_sec, "io_p95_ms": io_p95_ms,
            "meta_ops": meta_ops, "meta_ops_sec": meta_ops_sec, "meta_p95_ms": meta_p95_ms
        })

def main():
    ap = argparse.ArgumentParser(description="HDFS writer with per-dataset metadata & I/O latency metrics.")
    #ap.add_argument("--base-dir", required=True, help="Local base directory containing dataset subdirectories")
    ap.add_argument("--datasets", nargs='+', type=int, metavar=("IDX","IDX"),
                    help="One or two dataset indices (e.g., --datasets 0 or --datasets 0 1)")
    ap.add_argument("--hdfs-host", default="sdc3")
    ap.add_argument("--hdfs-port", type=int, default=8020)
    ap.add_argument("--hdfs-base", default="/bench", help="HDFS base directory")
    ap.add_argument("--buffer-size", default="4MiB")
    ap.add_argument("--blocksize", default=None)
    ap.add_argument("--replication", default=None)
    ap.add_argument("--user", default=None)
    args = ap.parse_args()

    base_dir = "/home/dcslab/iot/datasets/"

    datasets = list_datasets(base_dir)
    if not datasets:
        print(f"No dataset directories under {base_dir}", file=sys.stderr); sys.exit(2)
    print("Datasets:")
    for i,d in enumerate(datasets): print(f"  {i}: {d}")

    if not args.datasets:
        sel_idx = [0] if len(datasets)==1 else [0,1]
        print("No --datasets provided; defaulting to:", sel_idx)
    else:
        if len(args.datasets) not in (1,2):
            print("--datasets accepts 1 or 2 indices", file=sys.stderr); sys.exit(3)
        sel_idx = args.datasets

    try:
        selected = [datasets[i] for i in sel_idx]
    except Exception:
        print(f"Invalid indices {sel_idx}. Valid: 0..{len(datasets)-1}", file=sys.stderr); sys.exit(4)

    host, port = normalize_host_port(args.hdfs_host, args.hdfs_port)
    buffer_bytes = human_to_bytes(args.buffer_size)
    block_bytes = human_to_bytes(args.blocksize) if args.blocksize else None
    repl = int(args.replication) if args.replication else None

    print("\n=== Run configuration ===")
    print(f"HDFS: hdfs://{host}:{port}{args.hdfs_base}")
    print(f"Selected datasets: {selected}")
    print(f"Buffer size: {buffer_bytes} bytes")
    if block_bytes: print(f"Override blocksize: {block_bytes} bytes")
    if repl is not None: print(f"Override replication: {repl}")
    print("=========================\n")

    ctx = mp.get_context("spawn")
    q = ctx.Queue()

    procs = []
    t0 = time.time()
    for ds in selected:
        local_root = os.path.join(base_dir, ds)
        p = ctx.Process(target=write_dataset_to_hdfs,
                        args=(ds, local_root, args.hdfs_base, host, port,
                              buffer_bytes, block_bytes, repl, q, args.user))
        p.start(); procs.append(p)

    results = [q.get() for _ in range(len(procs))]
    for p in procs: p.join()

    total_bytes = 0
    for r in results:
        if r.get("status") != "ok":
            print(f"[{r.get('dataset')}] ERROR: {r.get('error')}"); continue
        total_bytes += r["bytes"]
        print(f"[{r['dataset']}] bytes={r['bytes']}  time={r['elapsed']:.3f}s  thr={r['throughput_mib_s']:.2f} MiB/s")
        print(f"  I/O:   ops={r['io_ops']}  ops/s={r['io_ops_sec']:.1f}  p95={r['io_p95_ms']:.2f} ms")
        print(f"  Meta:  ops={r['meta_ops']}  ops/s={r['meta_ops_sec']:.1f}  p95={r['meta_p95_ms']:.2f} ms")

    wall = max(time.time() - t0, 1e-9)
    agg_thr = (total_bytes/(1024**2))/wall
    print(f"\nAggregate: bytes={total_bytes}  walltime={wall:.3f}s  throughput={agg_thr:.2f} MiB/s")

if __name__ == "__main__":
    try:
        mp.set_start_method("spawn", force=True)
    except RuntimeError:
        pass
    main()
