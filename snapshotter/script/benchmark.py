#!/usr/bin/env python3

# Usage: python benchmark.py old_results.json

import subprocess
import datetime
import re
import json
import sys

def run_benchmark(image, snapshotter, task):
    print(f"\n=== Starting Benchmark ===")
    print(f"Snapshotter: {snapshotter}")
    print(f"Image: {image}")
    print(f"Task: {task}")
    
    benchmark_start = datetime.datetime.now()
    print(f"Benchmark start time: {benchmark_start}")

    pull_start = datetime.datetime.now()
    print(f"\nPulling image: {image} (Started at {pull_start})")
    subprocess.run(f"sudo nerdctl pull --snapshotter={snapshotter} {image}", shell=True)
    pull_end = datetime.datetime.now()
    print(f"Image pull completed at: {pull_end}, Duration: {(pull_end - pull_start).total_seconds()} seconds")

    run_start = datetime.datetime.now()
    print(f"\nRunning container task (Started at {run_start})")
    result = subprocess.run(f"sudo nerdctl run --rm --snapshotter={snapshotter} {image} /bin/bash -c \"{task}\"",
                            shell=True, capture_output=True, text=True)
    run_end = datetime.datetime.now()
    print(f"Container run completed at: {run_end}")

    output = result.stdout
    print(f"\nTask output:\n{output}")

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

    print(f"\n=== Benchmark Results ===")
    print(f"Pull time: {pull_time} seconds")
    print(f"Container creation time: {creation_time} seconds")
    print(f"Task execution time: {execution_time} seconds")
    print(f"Total benchmark time: {total_time} seconds\n")

    return {
        "pull_time": pull_time,
        "creation_time": creation_time,
        "execution_time": execution_time,
        "total_time": total_time
    }

def perf_regression(old_results, new_results, threshold=0.05):
    print(f"\n=== Performance Comparison ===")
    for key in old_results:
        old_time = old_results[key]
        new_time = new_results[key]
        percentage_diff = (new_time - old_time) / old_time
        print(f"{key}: old={old_time}, new={new_time}, diff={percentage_diff*100:.2f}%")
        if percentage_diff > threshold:
            print(f"Performance regression detected in {key}")
            return True
    return False

if __name__ == "__main__":
    images = ["rootproject/root:6.32.02-ubuntu24.04"]
    task = "python3 -c 'import ROOT'"
    snapshotter = "cvmfs-snapshotter"

    for image in images:
        print(f"\n=== Benchmarking Image: {image} ===")
        new_results = run_benchmark(image, snapshotter, task)
        print(f"\nNew benchmark results: {new_results}")

    if len(sys.argv) >= 2:
        print(f"\nLoading old results from {sys.argv[1]} for comparison...")
        with open(sys.argv[1], 'r') as f:
            old_results = json.load(f)
        if perf_regression(old_results, new_results):
            sys.exit(1)

    print(f"\nSaving new benchmark results to 'new_benchmark_results.json'")
    with open('new_benchmark_results.json', 'w') as f:
        json.dump(new_results, f, indent=4)
    print("Results saved.")
