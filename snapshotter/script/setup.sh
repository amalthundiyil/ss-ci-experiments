#/bin/bash

# cvmfs
sudo apt install lsb-release -y
if [ ! -f /tmp/cvmfs-release-latest_all.deb ]; then
            wget https://ecsft.cern.ch/dist/cvmfs/cvmfs-release/cvmfs-release-latest_all.deb -O /tmp/cvmfs-release-latest_all.deb
fi
sudo dpkg -i /tmp/cvmfs-release-latest_all.deb
sudo apt update
sudo apt install -y cvmfs
sudo cvmfs_config setup 
sudo sh -c "echo "CVMFS_HTTP_PROXY=DIRECT" > /etc/cvmfs/default.local"
sudo sh -c "echo "CVMFS_DEBUGLOG=/tmp/cvmfs.log" >> /etc/cvmfs/default.local"
sudo cvmfs_config reload

# go
if [ ! -f /tmp/go1.22.0.linux-amd64.tar.gz ]; then
            sudo wget https://go.dev/dl/go1.22.0.linux-amd64.tar.gz -P /tmp
fi
sudo tar -C /usr/local -xvf /tmp/go1.22.0.linux-amd64.tar.gz

echo "export GOPATH=$HOME/go" >> ~/.bashrc
echo "export PATH=\$PATH:/usr/local/go/bin:\$GOPATH/bin" >> ~/.bashrc
source ~/.bashrc

# nerdctl
if [ ! -f /tmp/nerdctl-full-1.7.6-linux-amd64.tar.gz ]; then
    wget https://github.com/containerd/nerdctl/releases/download/v1.7.6/nerdctl-full-1.7.6-linux-amd64.tar.gz -P /tmp
fi
sudo tar Cxzvvf /usr/local /tmp/nerdctl-full-1.7.6-linux-amd64.tar.gz
sudo systemctl enable --now containerd

# cvmfs-snapshotter
if [ ! -d /tmp/cvmfs ]; then
            git clone https://github.com/cvmfs/cvmfs /tmp/cvmfs
fi
cd /tmp/cvmfs/snapshotter
/usr/local/go/bin/go build -o out/cvmfs_snapshotter -ldflags '-X main.Version=2.11'
cp /tmp/cvmfs/snapshotter/out/cvmfs_snapshotter /usr/local/bin/cvmfs_snapshotter
cp /tmp/cvmfs/snapshotter/script/config/etc/systemd/system/cvmfs-snapshotter.service /etc/systemd/system
mkdir -p /etc/containerd-cvmfs-grpc && touch /etc/containerd-cvmfs-grpc/config.toml

sudo systemctl daemon-reload
sudo systemctl start cvmfs-snapshotter

 
sudo mkdir -p /etc/containerd
sudo tee /etc/containerd/config.toml > /dev/null <<EOL
version = 2

[plugins."io.containerd.grpc.v1.cri".containerd]
    snapshotter = "cvmfs-snapshotter"
    disable_snapshot_annotations = false

[proxy_plugins]
    [proxy_plugins.cvmfs-snapshotter]
        type = "snapshot"
        address = "/run/containerd-cvmfs-grpc/containerd-cvmfs-grpc.sock"
EOL
sudo systemctl start cvmfs-snapshotter
sudo systemctl restart containerd


sudo systemctl stop autofs
mkdir -p /cvmfs/unpacked.cern.ch
mount -t cvmfs unpacked.cern.ch /cvmfs/unpacked.cern.ch

CVMFS_SOCK="/run/containerd-cvmfs-grpc/containerd-cvmfs-grpc.sock"
if [ -S "$CVMFS_SOCK" ]; then
    echo "$CVMFS_SOCK exists."
else
    echo "$CVMFS_SOCK does not exist."
    exit 1
fi


