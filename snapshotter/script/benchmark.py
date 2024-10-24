#!/usr/bin/env python3

import subprocess
import re
import json
import sys
import logging
import statistics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

def run_command(command, check=True):
    result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if check and result.returncode != 0:
        logging.error(f"Command failed: {command}\nError: {result.stderr.strip()}")
        sys.exit(1)
    return result.stdout.strip()

def clear_cache(path):
    if subprocess.run(["test", "-d", path]).returncode == 0:
        run_command(f"sudo rm -rf {path}")
    run_command(f"sudo mkdir -p {path}")
    run_command(f"sudo chmod 755 {path}")

def cleanup(image):
    run_command("sudo nerdctl container prune -f")
    images_output = run_command("sudo nerdctl images --format '{{.Repository}}:{{.Tag}}'")
    if image in images_output:
        run_command(f"sudo nerdctl rmi {image}")

    services = ["containerd", "cvmfs-snapshotter"]
    for service in services:
        run_command(f"sudo systemctl stop {service}")

    run_command("sudo umount /cvmfs/unpacked.cern.ch")
    clear_cache("/var/lib/containerd")
    clear_cache("/var/lib/containerd-cvmfs-grpc")
    run_command("sudo cvmfs_config reload -c")

    for service in services:
        run_command(f"sudo systemctl start {service}")

    run_command("sudo mount -t cvmfs unpacked.cern.ch /cvmfs/unpacked.cern.ch")
    run_command("sudo cvmfs_config probe")

    sock_path = "/run/containerd-cvmfs-grpc/containerd-cvmfs-grpc.sock"
    if not subprocess.run(["test", "-S", sock_path]).returncode == 0:
        logging.error(f"{sock_path} does not exist.")
        sys.exit(1)


def run_benchmark(iteration, image, snapshotter, task):
    logging.info(f"Benchmark run #{iteration} - snapshotter: {snapshotter}, image: {image}, task: {task}")

    result = subprocess.run(
        f"""
            echo benchmark_start: $(date +%s%N); \
            echo pull_start: $(date +%s%N); \
            sudo nerdctl pull --snapshotter={snapshotter} {image}; \
            echo pull_end: $(date +%s%N); \
            echo run_start: $(date +%s%N); \
            sudo nerdctl run --snapshotter={snapshotter} {image} /bin/bash -c "\
            echo container_start: \$(date +%s%N); \
            {task}; \
            echo container_end: \$(date +%s%N)"; \
            echo run_end: $(date +%s%N)
        """,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if logging.getLogger().level == logging.ERROR:
        logging.debug(f"Run stdout: {result.stdout}")
        logging.error(f"Run stderr: {result.stderr}")

    output = result.stdout

    benchmark_start_match = re.search(r"benchmark_start: ([\d]+)", output)
    pull_start_match = re.search(r"pull_start: ([\d]+)", output)
    pull_end_match = re.search(r"pull_end: ([\d]+)", output)
    container_start_match = re.search(r"container_start: ([\d]+)", output)
    container_end_match = re.search(r"container_end: ([\d]+)", output)
    run_end_match = re.search(r"run_end: ([\d]+)", output)

    if not all([benchmark_start_match, pull_start_match, pull_end_match,
                container_start_match, container_end_match, run_end_match]):
        sys.exit("Error: One or more timestamps not found in the output.")

    benchmark_start = int(benchmark_start_match.group(1))
    pull_start = int(pull_start_match.group(1))
    pull_end = int(pull_end_match.group(1))
    container_start = int(container_start_match.group(1))
    container_end = int(container_end_match.group(1))
    run_end = int(run_end_match.group(1))

    pull_time = (pull_end - pull_start) / 1e9
    creation_time = (container_start - pull_end) / 1e9
    execution_time = (container_end - container_start) / 1e9
    total_time = (run_end - benchmark_start) / 1e9

    return pull_time, creation_time, execution_time, total_time

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
    num_runs = 5

    for entry in data:
        image, tasks = entry["image"], entry["tasks"]
        for task in tasks:
            pull_times = []
            creation_times = []
            execution_times = []
            total_times = []

            for i in range(num_runs):
                cleanup(image)
                pull_time, creation_time, execution_time, total_time = run_benchmark(i + 1, image, snapshotter, task)
                pull_times.append(pull_time)
                creation_times.append(creation_time)
                execution_times.append(execution_time)
                total_times.append(total_time)

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
