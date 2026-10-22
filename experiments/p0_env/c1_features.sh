#!/bin/bash
# P0 C1: Lustre 기능 시험. 테스트 디렉터리 안에서만 파일을 만들고 지운다.
T=${T:-/mnt/lustrefs/llmio_test/c1}
sec() { echo; echo "===== $1"; }
ok() { if [ $? -eq 0 ]; then echo "RESULT $1: PASS"; else echo "RESULT $1: FAIL"; fi; }
mkdir -p $T && cd $T || exit 1
rm -rf $T/* 2>/dev/null

sec "1 per-OST placement"
for i in 0 1 2; do lfs setstripe -c 1 -i $i f_ost$i && dd if=/dev/zero of=f_ost$i bs=1M count=8 status=none && echo "f_ost$i -> obdidx $(lfs getstripe -i f_ost$i)"; done; ok per_ost

sec "2 directory default layout inheritance"
mkdir -p d_ost2 && lfs setstripe -c 1 -i 2 d_ost2 && touch d_ost2/child && echo "child stripe index: $(lfs getstripe -i d_ost2/child)"; [ "$(lfs getstripe -i d_ost2/child)" = "2" ]; ok dir_inherit

sec "3 PFL composite layout"
lfs setstripe -E 64M -c 1 -i 0 -E -1 -c 1 -i 1 f_pfl && dd if=/dev/zero of=f_pfl bs=1M count=80 status=none && lfs getstripe f_pfl | grep -E "lcme_extent|l_ost_idx" | head -8; ok pfl

sec "4 FLR mirror create / extend / resync / verify"
lfs mirror create -N -i 0 -N -i 1 f_flr && dd if=/dev/zero of=f_flr bs=1M count=8 conv=notrunc status=none; lfs mirror resync f_flr; lfs mirror verify -v f_flr; ok flr_create
lfs mirror extend -N -i 2 f_flr; ok flr_extend
lfs getstripe f_flr | grep -E "lcm_mirror_count|l_ost_idx"

sec "5 migrate keeps path"
lfs migrate -c 1 -i 2 f_ost0 && echo "f_ost0 now obdidx $(lfs getstripe -i f_ost0)"; [ "$(lfs getstripe -i f_ost0)" = "2" ]; ok migrate

sec cleanup
cd / && rm -rf $T && echo "removed $T"
