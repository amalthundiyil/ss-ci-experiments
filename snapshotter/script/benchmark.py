#!/usr/bin/env python3

# Usage: python benchmark.py old_results.json

import subprocess
import datetime
import re
import json
import sys

def run_benchmark(image, snapshotter, task):
    print(f"Running benchmark with snapshotter: {snapshotter}, image: {image}, task: {task}")
    benchmark_start = datetime.datetime.now()
    pull_start = datetime.datetime.now()
    subprocess.run(f"sudo nerdctl pull --snapshotter={snapshotter} {image}", shell=True)
    pull_end = datetime.datetime.now()
    run_start = datetime.datetime.now()
    result = subprocess.run(f"sudo nerdctl run --rm --snapshotter={snapshotter} {image} /bin/bash -c \"{task}\"",
                            shell=True, capture_output=True, text=True)
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

if __name__ == "__main__":
    images = ["rootproject/root:6.32.02-ubuntu24.04"]
    task = "python3 -c 'import ROOT'"

    for image in images:
        new_results = run_benchmark(image, snapshotter, task)
        print(new_results)

    if len(sys.argv) >= 2:
        with open(sys.argv[1], 'r') as f:
            old_results = json.load(f)
        if perf_regression(old_results, new_results):
            sys.exit(1)

    with open('ew_benchmark_results.json', 'w') as f:
        json.dump(new_results, f, indent=4)
