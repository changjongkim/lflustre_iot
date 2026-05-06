import os
import shutil
import time
import sys
import subprocess


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


def benchmark_read(src_dir, dest_dir, selected_dataset, buffer_size=64*1024):
    total_size = 0
    start_time = time.time()

    new_dest_dir = dest_dir+selected_dataset+str(nameadd)

    for root, _, files in os.walk(new_dest_dir):
        for file in files:
            src_file = os.path.join(root, file)
            file_size = os.path.getsize(src_file)
            total_size += file_size

            with open(src_file, 'rb') as fsrc:
                #while True:
                #    buf = fsrc.read(buffer_size)
        
                fsrc.read()
    
    elapsed_time = time.time() - start_time

    # Calculate throughput (MB/s)
    throughput = (total_size / (1024 * 1024)) / elapsed_time
    print(f"Total data read: {total_size / (1024 * 1024):.2f} MB")
    print(f"Time taken: {elapsed_time:.2f} seconds")
    print(f"Read throughput: {throughput:.2f} MB/s")

def benchmark_write(src_dir, dest_dir, selected_dataset, buffer_size=64*1024):
    """Benchmark writing files from src_dir to dest_dir."""
    total_size = 0
    start_time = time.time()

    # Ensure the destination directory exists
    new_dest_dir = dest_dir+selected_dataset+str(nameadd)
    os.makedirs(new_dest_dir, exist_ok=True)

    # Iterate over each file in the source directory
    for root, _, files in os.walk(src_dir):
        for file in files:
            src_file = os.path.join(root, file)
            # dest_file = os.path.join(dest_dir, file)
            dest_file = os.path.join(new_dest_dir, str(nameadd) + "_" + file)
            #dest_file = os.path.join(new_dest_dir, file)

            # Calculate file size and add to total
            file_size = os.path.getsize(src_file)
            total_size += file_size

            # Copy the file to destination directory
            #
            #shutil.copy2(src_file, dest_file)

            #
            # with open(src_file, 'rb') as fsrc, open(dest_file, 'wb') as fdest:
            #     shutil.copyfileobj(fsrc, fdest, length=buffer_size)

            with open(src_file, 'rb') as fsrc, open(dest_file, 'wb') as fdest:
                while True:
                    buf = fsrc.read(buffer_size)
                    #buf = fsrc.read()
                    if not buf:
                        break
                    fdest.write(buf)

                # buf = fsrc.read()
                # fdest.write(buf)

                # Flush the written data to disk immediately
                #fdest.flush()
                #os.fsync(fdest.fileno())  # Force the OS to write to disk


    # Measure elapsed time
    elapsed_time = time.time() - start_time

    # Calculate throughput (MB/s)
    throughput = (total_size / (1024 * 1024)) / elapsed_time
    print(f"Total data written: {total_size / (1024 * 1024):.2f} MB")
    print(f"Time taken: {elapsed_time:.2f} seconds")
    print(f"Write throughput: {throughput:.2f} MB/s")


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
    print("Available datasets:")
    print("0: botiot")
    print("1: widar")
    print("2: mimii")
    print("3: visdrone")
    print("4: epicsound")
    print("5: loed")

    base_dir = "/home/dcslab/iot/datasets/"
    target_dir = "/mnt/client/"
    bufss = 4
    buffer_size = bufss * 1024

    dataType = ""
    # dataset_index = int(sys.argv[1])
    # nameadd = int(sys.argv[2])

    print("Please type dataset you want (0,1,2, or 3)")
    input0 = input()

    dataset_index = int(input0)

    if dataset_index == 0:
        dataType = "botiot"
    elif dataset_index == 1:
        dataType = "widar"
    elif dataset_index == 2:
        dataType = "mimii"
    elif dataset_index == 3:
        dataType = "visdrone"
    elif dataset_index == 4:
        dataType = "epicsound"
    elif dataset_index == 5:
        dataType = "loed"

    print("Please type int to int to directory name")
    input00 = input()

    nameadd = int(input00)

    dataset_dirs = list_datasets(base_dir)
    selected_dataset = select_dataset(dataset_dirs, dataset_index)

    #print(dataType)
    print("Are you Reading files from /mnt/client/{}{}? (y or n)".format(dataType, str(nameadd)))

    input1 = input()

    if input1 != "y":
        sys.exit()

    #print("{} {} {}".format(base_dir, dataset_index, target_dir))

    # List and select dataset directory
    # dataset_dirs = list_datasets(base_dir)
    # selected_dataset = select_dataset(dataset_dirs, dataset_index)
    # src_dir = os.path.join(base_dir, selected_dataset)

    dataset_dirs = list_datasets(base_dir)
    selected_dataset = select_dataset(dataset_dirs, dataset_index)
    src_dir = os.path.join(base_dir, selected_dataset)

    # # Benchmark write throughput
    benchmark_read(src_dir, target_dir, selected_dataset, buffer_size)





