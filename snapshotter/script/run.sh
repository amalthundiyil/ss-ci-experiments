#!/bin/bash

set -e

snapshotter="cvmfs-snapshotter"
image="docker.io/rootproject/root:6.32.02-ubuntu24.04"
iterations=5
output_file="benchmark_results.json"

echo "[]" > "$output_file"

tasks=(
    "/bin/bash"
    "python -c 'print(\"done\")'"
    "python -c 'import ROOT; print(\"done\")'"
    "python /opt/root/tutorials/pyroot/fillrandom.py"
)

for task in "${tasks[@]}"; do
    for ((i = 1; i <= $iterations; i++)); do
        echo "Running task: $task (Iteration $i)"

        benchmark_start=$(date +%s%N)

        pull_start=$(date +%s%N)
        sudo nerdctl pull --snapshotter=$snapshotter $image
        pull_end=$(date +%s%N)

        run_start=$(date +%s%N)
        container_output=$(sudo nerdctl --debug-full run --snapshotter=$snapshotter $image /bin/bash -c "\
            echo container_start: \$(date +%s%N); \
            $task; \
            echo container_end: \$(date +%s%N)")

        container_start=$(echo "$container_output" | grep "container_start" | awk '{print $2}')
        container_end=$(echo "$container_output" | grep "container_end" | awk '{print $2}')
        run_end=$(date +%s%N)

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
        echo

        result_json=$(jq -n \
            --arg task "$task" \
            --argjson iteration "$i" \
            --argjson pull_time "$pull_time" \
            --argjson creation_time "$creation_time" \
            --argjson execution_time "$execution_time" \
            --argjson total_time "$total_time" \
            '{
                "task": $task,
                "iteration": $iteration,
                "pull_time": $pull_time,
                "creation_time": $creation_time,
                "execution_time": $execution_time,
                "total_time": $total_time
            }')

        jq ". += [$result_json]" "$output_file" > tmp.$$.json && mv tmp.$$.json "$output_file"

        bash clear.sh
    done
done
