#fio --name=storage_test --directory=/mnt/ssd1/fio --size=34G \
#           --ioengine=libaio --direct=1 --bs=1m --rw=write --numjobs=1 --iodepth=32

#fio --name=storage_test --directory=/mnt/ssd1/fio --size=2G --filesize=200k --nrfiles=50000 \
	#           --ioengine=libaio --direct=1 --bs=16k --rw=write --numjobs=1 --iodepth=32 --openfiles=1

#fio --name=storage_test --directory=/mnt/ssd1 --size=1G \
	#           --ioengine=libaio --direct=1 --bs=4k --rw=write --numjobs=1

#fio  --name=storage_test  --directory=/mnt/ssd1/fio --filesize=20k-800k \
	#           --ioengine=libaio --direct=1 --bs=4k --rw=write --numjobs=1 --nrfiles=1000 --filename_format=storage_file.\$filenum 



#fio --name=storage_test --directory=/mnt/ssd1/fio --size=3G --filesize=2560080B --nrfiles=1033 \
	#           --ioengine=libaio --direct=1 --bs=1m --rw=write --numjobs=1 --iodepth=32 --openfiles=1




#fio --name=storage_test --directory=/mnt/client/fio --size=10G \
#	    --ioengine=libaio --direct=1 --bs=1m --rw=write --numjobs=1 --iodepth=32


#fio --name=storage_test --directory=/mnt/client/fio --size=25G \
#	    --ioengine=libaio --direct=0 --bs=1m --rw=write --numjobs=1 --iodepth=128

#fio --group_reporting --name=jsm --directory=/mnt/client/fio --rw=write --numjobs=1 --size=10GB --bs=64KB --iodepth=128 --ioengine=posixaio


fio --directory=/mnt/client/fio --size=5G --filesize=256k --nrfiles=20480 \
    --ioengine=libaio --direct=0 --name=strtest333 --bs=256k --rw=write --numjobs=1 --iodepth=1 --openfiles=1

#fio --directory=/mnt/client/fio --size=5G --filesize=2m --nrfiles=2500 \
#    --ioengine=libaio --direct=0 --name=strtest33333333 --bs=1m --rw=write --numjobs=1 --iodepth=32 --openfiles=1

#fio --directory=/mnt/client/fio --size=5G --filesize=48m --nrfiles=750 \
#    --ioengine=libaio --direct=0 --name=strtest3 --bs=1m --rw=write --numjobs=1 --iodepth=32 --openfiles=1

#fio --directory=/mnt/client/fio --size=5G --filesize=128m --nrfiles=40 \
#    --ioengine=libaio --direct=0 --name=strtest3 --bs=1m --rw=write --numjobs=1 --iodepth=32 --openfiles=1

#fio --directory=/mnt/client/fio --size=5G --filesize=1g --nrfiles=5 \
#    --ioengine=libaio --direct=0 --name=strtest323333333 --bs=1m --rw=write --numjobs=1 --iodepth=32 --openfiles=1

#fio --directory=/mnt/client/fio --size=4G --filesize=4g --nrfiles=1 \
#    --ioengine=libaio --direct=0 --name=strtest3333333333333333344 --bs=1m --rw=write --numjobs=1 --iodepth=32 --openfiles=1
