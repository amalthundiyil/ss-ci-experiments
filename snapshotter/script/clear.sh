#!/bin/bash

# Function to log error messages
log_error() {
    echo "ERROR: $1" >&2
}

# Prune containers
sudo nerdctl container prune -f > /dev/null 2>&1
if [[ $? -ne 0 ]]; then
    log_error "Error pruning containers"
fi

# Remove specified image
image="docker.io/rootproject/root:6.32.02-ubuntu24.04"
sudo nerdctl rmi "$image" > /dev/null 2>&1
if [[ $? -ne 0 ]]; then
    log_error "Error removing image $image"
fi

# Services to stop and start later
services=("containerd" "cvmfs-snapshotter")

# Stop services
for service in "${services[@]}"; do
    sudo systemctl stop "$service" > /dev/null 2>&1
    if [[ $? -ne 0 ]]; then
        log_error "Error stopping $service"
    fi
done

# Unmount the CVMFS path
sudo umount /cvmfs/unpacked.cern.ch > /dev/null 2>&1
if [[ $? -ne 0 ]]; then
    log_error "Error unmounting /cvmfs/unpacked.cern.ch"
fi

# Clear cache function
clear_cache() {
    local path=$1
    if [[ -d "$path" ]]; then
        sudo rm -rf "$path" > /dev/null 2>&1
        if [[ $? -ne 0 ]]; then
            log_error "Error removing $path"
        fi
    fi

    sudo mkdir -p "$path" > /dev/null 2>&1
    if [[ $? -ne 0 ]]; then
        log_error "Error creating $path"
    fi

    sudo chmod 755 "$path" > /dev/null 2>&1
    if [[ $? -ne 0 ]]; then
        log_error "Error setting permissions on $path"
    fi
}

# Clear containerd and grpc cache
clear_cache "/var/lib/containerd"
clear_cache "/var/lib/containerd-cvmfs-grpc"

# Reload CVMFS config
sudo cvmfs_config reload -c > /dev/null 2>&1
if [[ $? -ne 0 ]]; then
    log_error "Error reloading cvmfs_config"
fi

# Start services
for service in "${services[@]}"; do
    sudo systemctl start "$service" > /dev/null 2>&1
    if [[ $? -ne 0 ]]; then
        log_error "Error starting $service"
    fi
done

# Mount CVMFS unpacked
sudo mount -t cvmfs unpacked.cern.ch /cvmfs/unpacked.cern.ch > /dev/null 2>&1
if [[ $? -ne 0 ]]; then
    log_error "Error mounting /cvmfs/unpacked.cern.ch"
fi

# Probe CVMFS config
sudo cvmfs_config probe > /dev/null 2>&1
if [[ $? -ne 0 ]]; then
    log_error "Error probing cvmfs_config"
fi

# Check if the CVMFS gRPC socket exists
sock_path="/run/containerd-cvmfs-grpc/containerd-cvmfs-grpc.sock"
if [[ ! -S "$sock_path" ]]; then
    log_error "$sock_path does not exist."
    exit 1
fi

echo "Cleanup complete!"

