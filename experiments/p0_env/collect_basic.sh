#!/bin/bash
# P0 기본 정보 수집 (읽기 전용).
# sudo가 필요한 조회는 환경 변수 SUDO_PW가 있으면 사용한다. 비밀번호는 파일에 기록하지 않는다.
s() { if [ -n "$SUDO_PW" ]; then echo "$SUDO_PW" | sudo -S -p '' "$@"; else sudo -n "$@"; fi; }
sec() { echo; echo "===== $1"; }

sec hostname;        hostname; uname -a; uptime
sec model;           tr -d '\0' < /proc/device-tree/model; echo
sec l4t;             cat /etc/nv_tegra_release 2>/dev/null; dpkg-query -W -f='nvidia-jetpack ${Version}\n' nvidia-jetpack 2>/dev/null
sec nvpmodel;        s nvpmodel -q 2>&1
sec default_target;  systemctl get-default
sec memory;          free -m; swapon --show; zramctl 2>/dev/null
sec meminfo;         grep -E 'MemTotal|MemAvailable|^Cached|SwapTotal' /proc/meminfo
sec disks;           lsblk -o NAME,SIZE,MODEL,MOUNTPOINT,FSTYPE
sec df;              df -hT -x tmpfs -x devtmpfs
sec nvme;            s nvme list 2>&1 || echo "nvme-cli not available"
sec cpu;             nproc; lscpu | grep -E 'Model name|CPU max MHz|^CPU\(s\)'
sec tegrastats;      s timeout 3 tegrastats --interval 1000 2>&1 | head -2
sec python;          python3 --version; python3 -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available())" 2>&1 | tail -1
sec cuda;            ls -d /usr/local/cuda* 2>/dev/null; /usr/local/cuda/bin/nvcc --version 2>/dev/null | tail -1
sec lustre_mounts;   mount -t lustre
sec lustre_modules;  lsmod | grep -E '^(lustre|lnet|ldiskfs|osd_|ost|mdt|mgs|ksocklnd|obdclass|ptlrpc)' ; modinfo lustre 2>/dev/null | grep -E '^(version|filename)'
sec lustre_version;  s lctl get_param -n version 2>&1
sec lctl_dl;         s lctl dl 2>&1
sec nids;            s lctl list_nids 2>&1
sec lnet;            s lnetctl net show 2>&1
sec net_addr;        ip -br addr
sec net_route;       ip route
sec time;            timedatectl 2>/dev/null | head -8; chronyc tracking 2>/dev/null | head -5
