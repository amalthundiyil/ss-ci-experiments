#!/bin/bash

set -e

log_error() {
    echo "ERROR: $1" >&2
}

sudo nerdctl container prune -f > /dev/null 2>&1
if [[ $? -ne 0 ]]; then
    log_error "Error pruning containers"
fi

image="$1"
sudo nerdctl rmi "$image" > /dev/null 2>&1
if [[ $? -ne 0 ]]; then
    log_error "Error removing image $image"
fi

services=("containerd" "cvmfs-snapshotter")

for service in "${services[@]}"; do
    sudo systemctl stop "$service" > /dev/null 2>&1
    if [[ $? -ne 0 ]]; then
        log_error "Error stopping $service"
    fi
done

sudo umount /cvmfs/unpacked.cern.ch > /dev/null 2>&1
if [[ $? -ne 0 ]]; then
    log_error "Error unmounting /cvmfs/unpacked.cern.ch"
fi

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

clear_cache "/var/lib/containerd"
clear_cache "/var/lib/containerd-cvmfs-grpc"

sudo cvmfs_config reload -c > /dev/null 2>&1
if [[ $? -ne 0 ]]; then
    log_error "Error reloading cvmfs_config"
fi

for service in "${services[@]}"; do
    sudo systemctl start "$service" > /dev/null 2>&1
    if [[ $? -ne 0 ]]; then
        log_error "Error starting $service"
    fi
done

sudo mount -t cvmfs unpacked.cern.ch /cvmfs/unpacked.cern.ch > /dev/null 2>&1
if [[ $? -ne 0 ]]; then
    log_error "Error mounting /cvmfs/unpacked.cern.ch"
fi

sudo cvmfs_config probe > /dev/null 2>&1
if [[ $? -ne 0 ]]; then
    log_error "Error probing cvmfs_config"
fi

sock_path="/run/containerd-cvmfs-grpc/containerd-cvmfs-grpc.sock"
if ! sudo test -S "$sock_path"; then
    log_error "$sock_path does not exist."
    exit 1
fi
