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

#fio --directory=/mnt/client/fio1 --size=4G \
#    --ioengine=libaio --direct=0 --name=fffio33 --bs=1m --rw=write --numjobs=1 --iodepth=128


# Parameters
TOTAL_SIZE_GB=4        # Total size (4GB)
#FILE_SIZE=256K         # Each small file is 256KB
#FILE_SIZE=2M         # Each small file is 256KB
#FILE_SIZE=32M         # Each small file is 256KB
#FILE_SIZE=256M         # Each small file is 256KB
#FILE_SIZE=1G         # Each small file is 256KB
FILE_SIZE=4G         # Each small file is 256KB
#BLOCK_SIZE=4K          # Block size for I/O operations

# Calculate number of files: 4GB / 256KB = 16384
NUM_FILES=$(( (TOTAL_SIZE_GB * 1024 * 1024) / (1024*1024*4) ))

fio --directory=/mnt/client/fio1/4g --size=4G --filesize=$FILE_SIZE --nrfiles=$NUM_FILES \
	--ioengine=libaio --direct=0 --name=testing111111223 --bs=1m --rw=write --numjobs=1 --iodepth=1 --openfiles=1

#fio --directory=/mnt/client/fio1/4g --size=4G \
#	--ioengine=libaio --direct=0 --name=sm222 --bs=1m --filesize=$FILE_SIZE --nrfiles=$NUM_FILES \
#       	--numjobs=1 
