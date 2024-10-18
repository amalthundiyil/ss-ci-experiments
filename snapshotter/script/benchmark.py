#!/usr/bin/env python3

import subprocess
import datetime
import re
import json
import sys
import os
import shutil
import pprint

def run_benchmark(image, snapshotter, task):
    print(f"Running benchmark with snapshotter: {snapshotter}, image: {image}, task: {task}")
    benchmark_start = datetime.datetime.now()
    pull_start = datetime.datetime.now()
    subprocess.run(f"sudo nerdctl pull --snapshotter={snapshotter} {image}", shell=True)
    pull_end = datetime.datetime.now()
    run_start = datetime.datetime.now()
    result = subprocess.run(f"""sudo nerdctl run --rm  --snapshotter={snapshotter} {image} /bin/bash -c "\
echo container_start: "'$(date -Ins)'"
{task}
echo container_end: "'$(date -Ins)'"
"
""", shell=True, capture_output=True, text=True)

    run_end = datetime.datetime.now()
    output = result.stdout
    container_start_match = re.search(r'container_start: ([\d\-T:\.\+]+)', output)
    container_end_match = re.search(r'container_end: ([\d\-T:\.\+]+)', output)

    if not container_start_match or not container_end_match:
        sys.exit("Error: container_start or container_end timestamp not found in the output.")

    container_start = datetime.datetime.fromisoformat(container_start_match.group(1))
    container_end = datetime.datetime.fromisoformat(container_end_match.group(1))
    benchmark_end = datetime.datetime.now()

    pull_time = (pull_end - pull_start).total_seconds()
    creation_time = (container_start - run_start).total_seconds()
    execution_time = (container_end - container_start).total_seconds()
    total_time = (benchmark_end - benchmark_start).total_seconds()

    return {
        "image": image,
        "snapshotter": snapshotter,
        "task": task,
        "pull_time": pull_time,
        "creation_time": creation_time,
        "execution_time": execution_time,
        "total_time": total_time
    }

def perf_regression(old_results, new_results, threshold=0.05):
    for key in old_results:
        old_time = old_results[key]
        new_time = new_results[key]
        percentage_diff = (new_time - old_time) / old_time
        print(f"{key}: old={old_time}, new={new_time}, diff={percentage_diff*100:.2f}%")
        if percentage_diff > threshold:
            print(f"Performance regression detected in {key}")
            return True
    return False

def cleanup():
    # stop services
    subprocess.run(['sudo', 'systemctl', 'stop', 'containerd'], check=True)
    subprocess.run(['sudo', 'systemctl', 'stop', 'cvmfs-snapshotter'], check=True)
    subprocess.run(['sudo', 'systemctl', 'stop', 'autofs'], check=True)

    # unmount repo
    subprocess.run(['sudo', 'umount', "/cvmfs/unpacked.cern.ch"], check=True)

    # clear cache
    def clear_cache(path):
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path, mode=0o755, exist_ok=True)

    clear_cache("/var/lib/containerd")
    clear_cache("/var/lib/containerd-cvmfs-grpc")
    subprocess.run("sudo cvmfs_config reload -c", shell=True, capture_output=True, text=True)

    # start services
    subprocess.run(['sudo', 'systemctl', 'start', 'containerd'], check=True)
    subprocess.run(['sudo', 'systemctl', 'start', 'cvmfs-snapshotter'], check=True)
    subprocess.run(['sudo', 'systemctl', 'start', 'autofs'], check=True)

    # mount and check
    subprocess.run(['sudo', 'mount', '-t', 'cvmfs', "unpacked.cern.ch", "/cvmfs/unpacked.cern.ch"], check=True)
    subprocess.run("sudo cvmfs_config probe", shell=True, capture_output=True, text=True)
    cvmfs_sock_exists = os.path.exists("/run/containerd-cvmfs-grpc/containerd-cvmfs-grpc.sock")
    if not cvmfs_sock_exists:
        raise AssertionError("containerd-cvmfs-grpc.sock does not exist.")

if __name__ == "__main__":
    images = ["rootproject/root:6.32.02-ubuntu24.04"]
    data = [ 
        {
            "image": "rootproject/root:6.32.02-ubuntu24.04",
            "tasks": [
                "/bin/bash", 
                "python -c 'print(\"# Hello World\")'", 
                "python -c 'import ROOT; print(\"# import root complete\")'", 
                "python /opt/root/tutorials/pyroot/fillrandom.py"
            ]
        }
    ]

    snapshotter = "cvmfs-snapshotter"

    results = []

    for entry in data:
        image, tasks = entry['image'], entry['tasks']
        for task in tasks:
            results.append(run_benchmark(image, snapshotter, task))
            cleanup()
    
    pprint.pprint(results)

    # if len(sys.argv) >= 2:
    #     with open(sys.argv[1], 'r') as f:
    #         old_results = json.load(f)
    #     if perf_regression(old_results, new_results):
    #         sys.exit(1)

    with open('benchmark_results.json', 'w') as f:
        json.dump(results, f, indent=4)
