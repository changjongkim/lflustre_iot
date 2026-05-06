#fio --directory=/mnt/client/fio2 --size=15G --filesize=48m --nrfiles=2250 \
#    --ioengine=libaio --direct=0 --name=strtest5555555 --bs=256k --rw=write --numjobs=1 --iodepth=1 --openfiles=1

#fio --directory=/mnt/client/fio2 --size=8G --filesize=256k --nrfiles=32768 \
#    --ioengine=libaio --direct=0 --name=strtest5 --bs=256k --rw=write --numjobs=1 --iodepth=1 --openfiles=1

#fio --directory=/mnt/client/fio2 --size=16G --filesize=2m --nrfiles=8000 \
#    --ioengine=libaio --direct=0 --name=strtest3 --bs=1m --rw=write --numjobs=1 --iodepth=32 --openfiles=1

#fio --directory=/mnt/client/fio2 --size=16G --filesize=4G --nrfiles=4 \
#	    --ioengine=libaio --direct=0 --name=strtest33333 --bs=1m --rw=write --numjobs=1 --iodepth=32 --openfiles=1


fio --directory=/mnt/client/fio2 --size=4G --filesize=256k --nrfiles=16384 \
    --ioengine=libaio --direct=0 --name=strtest55 --bs=256k --rw=write --numjobs=1 --iodepth=1 --openfiles=1
