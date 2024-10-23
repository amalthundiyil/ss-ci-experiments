#!/usr/bin/env python3

import subprocess
import time
import re
import json
import sys
import os
import logging
import statistics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def run_benchmark(iteration, image, snapshotter, task):
    logging.info(
        f"Benchmark run #{iteration} - snapshotter: {snapshotter}, image: {image}, task: {task}"
    )

    benchmark_start = time.time_ns()
    pull_start = time.time_ns()
    pull_result = subprocess.run(
        f"sudo nerdctl pull --snapshotter={snapshotter} {image}",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    pull_end = time.time_ns()
    print("pull_end - pull_start = ", (pull_end - pull_start) / 1_000_000_000)

    if logging.getLogger().level == logging.ERROR:
        logging.debug(f"Pull stdout: {pull_result.stdout}")
        logging.error(f"Pull stderr: {pull_result.stderr}")


    run_start = time.time_ns()
    result = subprocess.run(
        f"""sudo nerdctl run --rm --snapshotter={snapshotter} {image} /bin/bash -c "\
        echo container_start: '$(date +%s%N)'; \
        {task}; \
        echo container_end: '$(date +%s%N)'"
        """,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    benchmark_end = time.time_ns()
    print("benchmark_end - run_start = ", (benchmark_end - run_start) / 1_000_000_000)

    if logging.getLogger().level == logging.DEBUG:
        logging.error(f"Error running task {task} on {image}: {result.stderr}") # always logged in github actions even if not an error
        logging.debug(f"Run stdout: {result.stdout}")

    output = result.stdout
    container_start_match = re.search(r"container_start: ([\d]+)", output)
    container_end_match = re.search(r"container_end: ([\d]+)", output)

    if not container_start_match or not container_end_match:
        sys.exit(
            "Error: container_start or container_end timestamp not found in the output."
        )

    container_start = int(container_start_match.group(1))
    container_end = int(container_end_match.group(1))

    pull_time = (pull_end - pull_start) / 1_000_000_000
    creation_time = (container_start - run_start) / 1_000_000_000
    execution_time = (container_end - container_start) / 1_000_000_000
    total_time = (benchmark_end - benchmark_start) / 1_000_000_000

    return pull_time, creation_time, execution_time, total_time


def perf_regression(old_results, new_results, threshold=0.05):
    for key in old_results:
        old_time = old_results[key]
        new_time = new_results[key]
        percentage_diff = (new_time - old_time) / old_time
        logging.info(
            f"{key}: old={old_time}, new={new_time}, diff={percentage_diff*100:.2f}%"
        )
        if percentage_diff > threshold:
            logging.warning(f"Performance regression detected in {key}")
            return True
    return False


def cleanup(image):
    result = subprocess.run(
        ["sudo", "nerdctl", "rmi", image],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.stderr:
        logging.error(f"Error removing image {image}: {result.stderr}")

    services = ["containerd", "cvmfs-snapshotter"]

    for service in services:
        result = subprocess.run(
            ["sudo", "systemctl", "stop", service],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.stderr:
            logging.error(f"Error stopping {service}: {result.stderr}")

    result = subprocess.run(
        ["sudo", "umount", "/cvmfs/unpacked.cern.ch"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.stderr:
        logging.error(f"Error unmounting /cvmfs/unpacked.cern.ch: {result.stderr}")
    if logging.getLogger().level == logging.ERROR:
        logging.debug(f"umount stdout: {result.stdout}")

    def clear_cache(path):
        if os.path.exists(path):
            result = subprocess.run(
                ["sudo", "rm", "-rf", path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if result.stderr:
                logging.error(f"Error removing {path}: {result.stderr}")

        result = subprocess.run(
            ["sudo", "mkdir", "-p", path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.stderr:
            logging.error(f"Error creating {path}: {result.stderr}")
        result = subprocess.run(
            ["sudo", "chmod", "755", path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.stderr:
            logging.error(f"Error setting permissions on {path}: {result.stderr}")

    clear_cache("/var/lib/containerd")
    clear_cache("/var/lib/containerd-cvmfs-grpc")

    result = subprocess.run(
        "sudo cvmfs_config reload -c",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.stderr:
        logging.error(f"Error reloading cvmfs_config: {result.stderr}")

    for service in services:
        result = subprocess.run(
            ["sudo", "systemctl", "start", service],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.stderr:
            logging.error(f"Error starting {service}: {result.stderr}")

    result = subprocess.run(
        [
            "sudo",
            "mount",
            "-t",
            "cvmfs",
            "unpacked.cern.ch",
            "/cvmfs/unpacked.cern.ch",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if logging.getLogger().level == logging.ERROR:
        logging.error(f"mount stderr: {result.stderr}")
        logging.debug(f"mount stdout: {result.stdout}")

    result = subprocess.run(
        "sudo cvmfs_config probe",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.stderr:
        logging.error(f"Error probing cvmfs_config: {result.stderr}")

    
    try:
        sock_path = "/run/containerd-cvmfs-grpc/containerd-cvmfs-grpc.sock"
        subprocess.run(["sudo", "test", "-S", sock_path], check=True)
    except subprocess.CalledProcessError:
        raise AssertionError(f"{sock_path} does not exist.")


if __name__ == "__main__":
    data = [
        {
            "image": "docker.io/rootproject/root:6.32.02-ubuntu24.04",
            "tasks": [
                "/bin/bash",
                r"python -c 'print(\"done\")'",
                r"python -c 'import ROOT; print(\"done\")'",
                "python /opt/root/tutorials/pyroot/fillrandom.py",
            ],
        }
    ]

    snapshotter = "cvmfs-snapshotter"
    results = []

    num_runs = 5  # Number of times to run each task

    for entry in data:
        image, tasks = entry["image"], entry["tasks"]
        for task in tasks:
            pull_times = []
            creation_times = []
            execution_times = []
            total_times = []

            for i in range(num_runs):
                pull_time, creation_time, execution_time, total_time = run_benchmark(i + 1, image, snapshotter, task)
                pull_times.append(pull_time)
                creation_times.append(creation_time)
                execution_times.append(execution_time)
                total_times.append(total_time)
                cleanup(image)

            results.append({
                "image": image,
                "snapshotter": snapshotter,
                "task": task,
                "pull_time_mean": statistics.mean(pull_times),
                "pull_time_median": statistics.median(pull_times),
                "pull_time_stddev": statistics.stdev(pull_times),
                "creation_time_mean": statistics.mean(creation_times),
                "creation_time_median": statistics.median(creation_times),
                "creation_time_stddev": statistics.stdev(creation_times),
                "execution_time_mean": statistics.mean(execution_times),
                "execution_time_median": statistics.median(execution_times),
                "execution_time_stddev": statistics.stdev(execution_times),
                "total_time_mean": statistics.mean(total_times),
                "total_time_median": statistics.median(total_times),
                "total_time_stddev": statistics.stdev(total_times),
            })

    logging.info("Benchmark results:")
    logging.info(json.dumps(results, indent=4))

    with open("benchmark_results.json", "w") as f:
        json.dump(results, f, indent=4)
