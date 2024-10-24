#!/bin/bash

image="docker.io/rootproject/root:6.32.02-ubuntu24.04"
sudo nerdctl container prune -f
sudo nerdctl rmi "$image"

sudo systemctl stop "containerd"
sudo systemctl stop "cvmfs-snapshotter"

sudo umount /cvmfs/unpacked.cern.ch 

clear_cache() {
    local path=$1
    sudo rm -rf "$path" 
    sudo mkdir -p "$path" 
    sudo chmod 755 "$path"
}
clear_cache "/var/lib/containerd"
clear_cache "/var/lib/containerd-cvmfs-grpc"

sudo cvmfs_config reload -c 

sudo systemctl start "containerd"
sudo systemctl start "cvmfs-snapshotter"

sudo mount -t cvmfs unpacked.cern.ch /cvmfs/unpacked.cern.ch
sudo cvmfs_config probe 

sudo test -S "/run/containerd-cvmfs-grpc/containerd-cvmfs-grpc.sock"