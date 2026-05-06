fio --name=storage_test22 --directory=/mnt/client/fio --size=25G \
	    --ioengine=libaio --direct=0 --bs=1m --rw=write --numjobs=1 --iodepth=128

