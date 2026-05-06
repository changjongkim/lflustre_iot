# test versus iot1.py 
fio --directory=/mnt/client/fio0320 --filesize=32G\
    --ioengine=libaio --direct=0 --name=fffio11112976 --bs=1m --rw=write --numjobs=4 --iodepth=256 --openfiles=1


# test with iot1.py 
#fio --directory=/mnt/client/fio0320 --filesize=32G\
#    --ioengine=libaio --direct=0 --name=fffio222 --bs=1m --rw=write --numjobs=4 --iodepth=256 --openfiles=1

##########################################################################
##########################################################################
# numjobs Test 1
#fio --directory=/mnt/client/fio0320 --filesize=32G\
#    --ioengine=libaio --direct=0 --name=fffio3 --bs=1m --rw=write --numjobs=1 --iodepth=256 --openfiles=1


# numjobs Test 4
#fio --directory=/mnt/client/fio0320 --filesize=32G\
#    --ioengine=libaio --direct=0 --name=fffio332123 --bs=1m --rw=write --numjobs=4 --iodepth=256 --openfiles=1


# numjobs Test 4 - size Test 5G
#fio --directory=/mnt/client/fio0320 --size=5G --filesize=32G\
#    --ioengine=libaio --direct=0 --name=fffio33111 --bs=1m --rw=write --numjobs=4 --iodepth=256 --openfiles=1


# numjobs Test 4 - size Test 16G
#fio --directory=/mnt/client/fio0320 --size=16G --filesize=32G\
#    --ioengine=libaio --direct=0 --name=fffio3313 --bs=1m --rw=write --numjobs=4 --iodepth=256 --openfiles=1


# numjobs Test 8
#fio --directory=/mnt/client/fio0320 --filesize=32G\
#    --ioengine=libaio --direct=0 --name=fffio3331 --bs=1m --rw=write --numjobs=8 --iodepth=256 --openfiles=1


# numjobs Test 16 
#fio --directory=/mnt/client/fio0320 --filesize=32G\
#    --ioengine=libaio --direct=0 --name=fffio33331 --bs=1m --rw=write --numjobs=16 --iodepth=256 --openfiles=1

#file size Change Test
#fio --directory=/mnt/client/fio0320 --filesize=2m\
#    --ioengine=libaio --direct=0 --name=fffio2 --bs=1m --rw=write --numjobs=4 --iodepth=256 --openfiles=1


#file size Change Test 2
#fio --directory=/mnt/client/fio0320 --filesize=48m\
#    --ioengine=libaio --direct=0 --name=fffio221 --bs=1m --rw=write --numjobs=4 --iodepth=256 --openfiles=1


#file size Change Test 3
#fio --directory=/mnt/client/fio0320 --filesize=128m\
#    --ioengine=libaio --direct=0 --name=fffio222 --bs=1m --rw=write --numjobs=4 --iodepth=256 --openfiles=1


#file size Change Test 4
#fio --directory=/mnt/client/fio0320 --filesize=1G\
#    --ioengine=libaio --direct=0 --name=fffio2222 --bs=1m --rw=write --numjobs=4 --iodepth=256 --openfiles=1


#file size Change Test 5
#fio --directory=/mnt/client/fio0320 --filesize=4G\
#    --ioengine=libaio --direct=0 --name=fffio22222 --bs=1m --rw=write --numjobs=4 --iodepth=256 --openfiles=1


#file size Change Test 6
#fio --directory=/mnt/client/fio0320 --filesize=16G\
#    --ioengine=libaio --direct=0 --name=fffio22222 --bs=1m --rw=write --numjobs=4 --iodepth=256 --openfiles=1


#file size Change Test 7
#fio --directory=/mnt/client/fio0320 --filesize=32G\
#    --ioengine=libaio --direct=0 --name=fffio222222 --bs=1m --rw=write --numjobs=4 --iodepth=256 --openfiles=1


#file size Change Test 8
#fio --directory=/mnt/client/fio0320 --filesize=64G\
#    --ioengine=libaio --direct=0 --name=fffio222222672 --bs=1m --rw=write --numjobs=4 --iodepth=256 --openfiles=1


#file size Change Test 8 -numjobsX4 filesize/4 
#fio --directory=/mnt/client/fio0320 --filesize=16G\
#    --ioengine=libaio --direct=0 --name=fffio22222228 --bs=1m --rw=write --numjobs=16 --iodepth=256 --openfiles=1


#file size Change Test 9
#fio --directory=/mnt/client/fio0320 --filesize=128G\
#    --ioengine=libaio --direct=0 --name=fffio22222222 --bs=1m --rw=write --numjobs=4 --iodepth=256 --openfiles=1


#file size Change Test 10
#fio --directory=/mnt/client/fio0320 --filesize=256G\
#    --ioengine=libaio --direct=0 --name=fffio222222222 --bs=1m --rw=write --numjobs=4 --iodepth=256 --openfiles=1


#file size Change Test 11
#fio --directory=/mnt/client/fio0320 --filesize=512G\
#    --ioengine=libaio --direct=0 --name=fffio2222222222 --bs=1m --rw=write --numjobs=4 --iodepth=256 --openfiles=1

