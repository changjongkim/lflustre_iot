#!/bin/bash
# P0 네트워크 점검 (읽기 전용): 유선 경로, NIC 속도, LNet 피어, iperf3 존재 여부
s() { if [ -n "$SUDO_PW" ]; then echo "$SUDO_PW" | sudo -S -p '' "$@"; else sudo -n "$@"; fi; }
sec() { echo; echo "===== $1"; }
sec route_get
for ip in 192.168.0.50 192.168.0.51 192.168.0.52 192.168.0.53 192.168.0.100 192.168.0.60; do ip route get $ip | head -1; done
sec ethtool
for ifc in enP8p1s0 wlP1p1s0; do echo "-- $ifc"; s ethtool $ifc 2>/dev/null | grep -E 'Speed|Duplex|Link detected'; ip link show $ifc | grep -o 'mtu [0-9]*'; done
sec lnet_peers
s lnetctl peer show 2>&1 | grep -E 'primary nid|nid:' | sort -u
sec mgc_import
s lctl get_param -n mgc.*.import 2>&1 | grep -E 'target|connection|current_connection|state:' | head -20
sec tcp_conn_to_lustre
ss -tn 2>/dev/null | awk 'NR==1 || /:988 /'
sec iperf3
command -v iperf3 || echo "iperf3 not installed"
sec fio
command -v fio || echo "fio not installed"
