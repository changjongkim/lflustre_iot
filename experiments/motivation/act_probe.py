#!/usr/bin/env python3
"""stage 사이 activation 전달 모사 (M9). Qwen3-4B hidden 2560, FP16 → 토큰당 5,120B.
prefill 경계 묶음(토큰 수 × 5,120B)과 decode 토큰 단위 메시지(5,120B)를 TCP로 보내고 수신 확인까지의 시간을 잰다.
사용: 수신 노드  python3 act_probe.py serve <port>
      송신 노드  python3 act_probe.py burst <host> <port> <label> <tokens> <count> [interval_s]
                python3 act_probe.py ping  <host> <port> <label> <count> [interval_s]
출력(TSV, 송신 노드 stdout): label, mode, bytes, i, ms"""
import socket, struct, sys, threading, time

TOKEN_BYTES = 2560 * 2

def recv_exact(conn, n):
    b = b""
    while len(b) < n:
        k = conn.recv(n - len(b))
        if not k: raise ConnectionError
        b += k
    return b

def handle(conn):
    buf = bytearray(1 << 20)
    try:
        while True:
            (n,) = struct.unpack("!Q", recv_exact(conn, 8))
            left = n
            while left:
                k = conn.recv_into(buf, min(left, len(buf)))
                if k == 0: raise ConnectionError
                left -= k
            conn.sendall(b"k")
    except ConnectionError:
        conn.close()

def serve(port):
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port)); s.listen(4)
    while True:
        c, _ = s.accept(); c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        threading.Thread(target=handle, args=(c,), daemon=True).start()

def send(host, port, label, mode, size, count, interval):
    c = socket.create_connection((host, port)); c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    payload = struct.pack("!Q", size) + bytes(size)
    for i in range(count):
        t0 = time.perf_counter()
        c.sendall(payload)
        if c.recv(1) != b"k": raise ConnectionError
        print(f"{label}\t{mode}\t{size}\t{i}\t{(time.perf_counter()-t0)*1e3:.3f}", flush=True)
        time.sleep(interval)
    c.close()

if __name__ == "__main__":
    a = sys.argv
    if a[1] == "serve":
        serve(int(a[2]))
    elif a[1] == "burst":
        send(a[2], int(a[3]), a[4], "burst", int(a[5]) * TOKEN_BYTES, int(a[6]), float(a[7]) if len(a) > 7 else 1.0)
    elif a[1] == "ping":
        send(a[2], int(a[3]), a[4], "ping", TOKEN_BYTES, int(a[5]), float(a[6]) if len(a) > 6 else 0.05)
