#!/bin/bash
# P0 Lustre 설정 조회 (읽기 전용)
s() { if [ -n "$SUDO_PW" ]; then echo "$SUDO_PW" | sudo -S -p '' "$@"; else sudo -n "$@"; fi; }
sec() { echo; echo "===== $1"; }
g() { for p in "$@"; do s lctl get_param "$p" 2>/dev/null; done; }
sec client;      g 'llite.*.max_cached_mb' 'llite.*.max_read_ahead_mb' 'osc.*.checksums' 'osc.*.checksum_type' 'osc.*.max_rpcs_in_flight' 'osc.*.max_pages_per_rpc' 'osc.*.max_dirty_mb'
sec jobid;       g jobid_var jobid_name
sec oss_cache;   g 'osd-ldiskfs.*.read_cache_enable' 'osd-ldiskfs.*.writethrough_cache_enable' 'osd-ldiskfs.*.readcache_max_filesize' 'obdfilter.*.read_cache_enable' 'obdfilter.*.writethrough_cache_enable'
sec oss_nrs;     g 'ost.OSS.ost_io.nrs_policies'
sec oss_threads; g 'ost.OSS.ost_io.threads_started' 'ost.OSS.ost_io.threads_max' 'ost.OSS.ost.threads_started'
sec jobstats;    g 'obdfilter.*.job_stats' | head -5; g 'obdfilter.*.job_cleanup_interval'
sec brw;         g 'obdfilter.*.brw_size'
sec mdt;         g 'mdt.*.md_stats' | head -12; g 'mdt.*.job_stats' | head -3
sec cpt;         g cpu_partition_table; cat /sys/module/libcfs/parameters/cpu_npartitions /sys/module/libcfs/parameters/cpu_pattern 2>/dev/null
sec lustre_modules_loaded; lsmod | awk '{print $1}' | grep -E '^(lustre|osc|mdc|lov|lmv)$' | tr '\n' ' '; echo
