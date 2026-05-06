import os
import shutil
import time
import sys
from multiprocessing import Pool
import threading


def list_datasets(base_dir):
    """List directories in the base directory (assumed to be dataset folders)."""
    dataset_dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
    #print("Available datasets:")
    #for idx, dataset in enumerate(dataset_dirs):
    #    print(f"{idx}: {dataset}")
    return dataset_dirs

def select_dataset(dataset_dirs, selection):
    """Select dataset directory based on user input."""
    if selection < 0 or selection >= len(dataset_dirs):
        raise ValueError("Invalid dataset selection.")
    return dataset_dirs[selection]


def benchmark_write_helper(args_list):
    for root, _, files in os.walk(src_dir):
        for file in files:
            src_file = os.path.join(root, file)

            threads = []

            with open(src_file, 'rb') as fsrc:
                for i in range(2):
                    thread = threading.Thread(target=benchmark_write, args=(fsrc, file, src_file, args_list[i]))
                    threads.append(thread)
                    thread.start()

                for thread in threads:
                    thread.join()



#def benchmark_write(src_dir, dest_dir, selected_dataset, buffer_size=64*1024, nameadd2):
def benchmark_write(fsrc, file, src_file, nameadd2):
    """Benchmark writing files from src_dir to dest_dir."""
    total_size = 0
    start_time = time.time()

    # Ensure the destination directory exists
    new_dest_dir = dest_dir+selected_dataset+str(nameadd2)
    os.makedirs(new_dest_dir, exist_ok=True)

    dest_file1 = os.path.join(new_dest_dir, str(nameadd) + "_" + str(nameadd2) + "_" + "EPIC_audio.hdf")

    file_size = os.path.getsize(src_file)
    total_size += file_size

    with open(dest_file1, 'wb') as fdest1:
         while True:
             buf = fsrc.read(buffer_size)

             if not buf:
                 break

             fdest1.write(buf)

    # Iterate over each file in the source directory
#    for root, _, files in os.walk(src_dir):
#        for file in files:
#            src_file = os.path.join(root, file)
#
#            dest_file1 = os.path.join(new_dest_dir, str(nameadd) + "_" + str(nameadd2) + "_" + file)
#
#            # Calculate file size and add to total
#            file_size = os.path.getsize(src_file)
#            total_size += file_size
#
#            with open(dest_file1, 'wb') as fdest1:
#                while True:
#                    buf = fsrc.read(buffer_size)
#
#                    output_paths = [fdest1, fdest2]
#
#                    if not buf:
#                        break
#                    fdest1.write(buf)
#
#                # buf = fsrc.read()
#                # fdest.write(buf)
#
#                # Flush the written data to disk immediately
#                #fdest.flush()
#                #os.fsync(fdest.fileno())  # Force the OS to write to disk
#

    # Measure elapsed time
    elapsed_time = time.time() - start_time

    # Calculate throughput (MB/s)
    throughput = (total_size / (1024 * 1024)) / elapsed_time

    with open("output"+"_"+str(nameadd2)+".txt", "a") as f:
        print(f"Total data written: {total_size / (1024 * 1024):.2f} MB", file=f)
        print(f"Time taken: {elapsed_time:.2f} seconds", file=f)
        print(f"Write throughput: {throughput:.2f} MB/s", file=f)


if __name__ == "__main__":
    # if len(sys.argv) < 3:
    #     print("Usage: python io_benchmark.py <base_dir> <dataset_index> <target_dir>")
    #     sys.exit(1)

    # Parse command-line arguments
    # base_dir = sys.argv[1]
    # dataset_index = int(sys.argv[2])
    # target_dir = sys.argv[3]

    #Available datasets:
    # 0: widar
    # 1: mimii
    # 2: visdrone
    # 3: epicsound
    nameadd = int(sys.argv[1])
    base_dir = "/home/dcslab/iot/datasets/"
    dataset_index = 3
    #target_dir = "/mnt/juicefs/"
    target_dir = "/mnt/client/"
    dest_dir = target_dir
    #target_dir = "/home/dcslab/iot/temp/"
    #bufss = int(sys.argv[1])
    #bufss = 1024 
    bufss = 4
    buffer_size = bufss * 1024

    print("{} {} {}".format(base_dir, dataset_index, target_dir))

    # List and select dataset directory
    # dataset_dirs = list_datasets(base_dir)
    # selected_dataset = select_dataset(dataset_dirs, dataset_index)
    # src_dir = os.path.join(base_dir, selected_dataset)

    dataset_dirs = list_datasets(base_dir)
    selected_dataset = select_dataset(dataset_dirs, dataset_index)
    src_dir = os.path.join(base_dir, selected_dataset)

    # # Benchmark write throughput
    #benchmark_write(src_dir, target_dir, selected_dataset, buffer_size)

    #benchmark_write(src_dir, dest_dir, selected_dataset, buffer_size=64*1024, nameadd2):
    args_list = [1, 2]

    benchmark_write_helper(args_list)

        #try:
        #    real_result = result.get()
        #    pool.close()
        #    pool.join()


    # files_data, total_size = read_all_files(src_dir, buffer_size=64 * 1024)  # Set buffer to 64KB
    # write_all_files(files_data, target_dir)




