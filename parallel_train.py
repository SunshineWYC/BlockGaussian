import time
import argparse
import subprocess


num_tasks = 6  # block numbers
num_gpus = 6   # visible gpu numbers
base_command = "CUDA_VISIBLE_DEVICES={} python train.py -b {}"
memory_threshold = 2048  # VRAM threshold
block_ids = list(range(0, num_tasks))
gpu_tasks = {gpu_id: None for gpu_id in range(num_gpus)}


def get_gpu_memory_usage():
    result = subprocess.run(
        ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
        stdout=subprocess.PIPE
    )
    memory_usage = list(map(int, result.stdout.decode('utf-8').strip().split('\n')))
    return memory_usage


def is_gpu_available(gpu_id):
    memory_usage = get_gpu_memory_usage()
    return memory_usage[gpu_id] < memory_threshold


def run_task_on_gpu(gpu_id, task_id):
    command = base_command.format(gpu_id, task_id)
    print(f"Running task {task_id} on GPU {gpu_id}: ", command)
    process = subprocess.Popen(command, shell=True)
    gpu_tasks[gpu_id] = (task_id, process)


def check_and_launch_tasks():
    for task_id in block_ids:
        while True:
            for gpu_id in range(num_gpus):
                if gpu_tasks[gpu_id] is None or gpu_tasks[gpu_id][1].poll() is not None:
                    if is_gpu_available(gpu_id):
                        run_task_on_gpu(gpu_id, task_id)
                        break
            else:
                time.sleep(10)
                continue
            break

def wait_for_all_tasks_to_complete():
    while True:
        all_tasks_completed = True
        for gpu_id in range(num_gpus):
            if gpu_tasks[gpu_id] is not None and gpu_tasks[gpu_id][1].poll() is None:
                all_tasks_completed = False
                break
        if all_tasks_completed:
            print("All tasks completed.")
            break
        time.sleep(10)


if __name__ == "__main__":
    check_and_launch_tasks()
    wait_for_all_tasks_to_complete()
