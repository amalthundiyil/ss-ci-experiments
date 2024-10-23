#!/bin/bash

snapshotter="cvmfs-snapshotter"
image="docker.io/rootproject/root:6.32.02-ubuntu24.04"

benchmark_start=$(date +%s%N)
echo "benchmark_start: $benchmark_start"

pull_start=$(date +%s%N)
echo "pull_start: $pull_start"

sudo nerdctl pull --snapshotter=$snapshotter $image

pull_end=$(date +%s%N)
echo "pull_end: $pull_end"

run_start=$(date +%s%N)
echo "run_start: $run_start"

container_output=$(sudo nerdctl --debug-full run --snapshotter=$snapshotter $image /bin/bash -c "\
    echo container_start: \$(date +%s%N); \
    python -c 'import ROOT; print(\"done\")'; \
    echo container_end: \$(date +%s%N)")

container_start=$(echo "$container_output" | grep "container_start" | awk '{print $2}')
container_end=$(echo "$container_output" | grep "container_end" | awk '{print $2}')

echo "container_start: $container_start"
echo "container_end: $container_end"

run_end=$(date +%s%N)
echo "run_end: $run_end"

if [[ -z "$pull_start" || -z "$pull_end" || -z "$container_start" || -z "$container_end" || -z "$run_end" ]]; then
    echo "Error: One or more required timestamps are empty."
    exit 1
fi

pull_time=$(echo "scale=9; ($pull_end - $pull_start) / 1000000000" | bc -l)
creation_time=$(echo "scale=9; ($container_start - $pull_end) / 1000000000" | bc -l)
execution_time=$(echo "scale=9; ($container_end - $container_start) / 1000000000" | bc -l)
total_time=$(echo "scale=9; ($run_end - $benchmark_start) / 1000000000" | bc -l)

echo "pull_time: $pull_time seconds"
echo "creation_time: $creation_time seconds"
echo "execution_time: $execution_time seconds"
echo "total_time: $total_time seconds"

