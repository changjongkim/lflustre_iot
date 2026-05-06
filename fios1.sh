#fio --directory=/mnt/client/fio --size=5G --filesize=256k --nrfiles=20480 \
#    --ioengine=libaio --direct=0 --name=strtest333 --bs=256k --rw=write --numjobs=1 --iodepth=1 --openfiles=1

#fio --directory=/mnt/client/fio --size=5G --filesize=2m --nrfiles=2500 \
#    --ioengine=libaio --direct=0 --name=strtest33333333 --bs=1m --rw=write --numjobs=1 --iodepth=32 --openfiles=1

#fio --directory=/mnt/client/fio --size=5G --filesize=48m --nrfiles=750 \
#    --ioengine=libaio --direct=0 --name=strtest3 --bs=1m --rw=write --numjobs=1 --iodepth=32 --openfiles=1

#fio --directory=/mnt/client/fio --size=5G --filesize=128m --nrfiles=40 \
#    --ioengine=libaio --direct=0 --name=strtest3 --bs=1m --rw=write --numjobs=1 --iodepth=32 --openfiles=1

#fio --directory=/mnt/client/fio --size=5G --filesize=1g --nrfiles=5 \
#    --ioengine=libaio --direct=0 --name=strtest323333333 --bs=1m --rw=write --numjobs=1 --iodepth=32 --openfiles=1

#fio --directory=/mnt/client/fio1 --size=16G --filesize=4G --nrfiles=4 \
#    --ioengine=libaio --direct=0 --name=strtest44 --bs=1m --rw=write --numjobs=1 --iodepth=32 --openfiles=1

#fio --directory=/mnt/client/fio1 --filesize=32G \
#    --ioengine=libaio --direct=0 --name=fffio3 --bs=1m --rw=write --numjobs=2 --iodepth=256 --openfiles=1

fio --directory=/mnt/client/fio1 --size=32G \
    --ioengine=libaio --direct=0 --name=fffio33 --bs=1m --rw=write --numjobs=2 --iodepth=256 --openfiles=1
