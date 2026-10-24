#!/usr/bin/env bash
# Install Home-Rank on Proxmox VE in a new LXC container: run as root on the Proxmox host.
#
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/januhrhammer/Home-Rank/main/docker/proxmox-lxc.sh)"
#
# Creates an unprivileged Debian 13 container with Docker in it, downloads the latest release's
# compose.yaml and env.example to /opt/home-rank, fills in the required settings and starts
# Home-Rank. Asks for each setting, with a default; Enter keeps the default. Every setting can
# also be given beforehand as a variable, e.g. CTID=120 MEMORY=8192 bash -c "$(curl ...)".
#
# A container rather than a virtual machine: it sees the host's CPU as it is, so Stockfish uses
# its fastest instructions, and cores given to it are shared with the host, not reserved.
set -euo pipefail

RELEASE_URL="https://github.com/januhrhammer/Home-Rank/releases/latest/download"

if ! command -v pct > /dev/null; then
    echo "This script runs on a Proxmox VE host (pct not found)." >&2
    exit 1
fi
if [[ $EUID -ne 0 ]]; then
    echo "Run this script as root." >&2
    exit 1
fi

# ask NAME "Question" DEFAULT: sets the variable NAME, unless it is set already.
ask() {
    local name=$1 question=$2 default=$3 answer
    if [[ -n ${!name:-} ]]; then
        return
    fi
    read -rp "$question [$default]: " answer < /dev/tty
    printf -v "$name" '%s' "${answer:-$default}"
}

echo "Home-Rank in a new Proxmox container. Press Enter to keep a default."
ask CTID "Container ID" "$(pvesh get /cluster/nextid)"
ask CT_HOSTNAME "Host name" "home-rank"
# All the host's cores: a container only uses them while it works, e.g. analysing games.
ask CORES "CPU cores" "$(nproc)"
ask MEMORY "Memory in MB" "4096"
# Reference databases need about 1 GB per million games on top of this.
ask DISK "Disk size in GB" "32"
ask STORAGE "Storage for the container's disk" "local-lvm"
ask TEMPLATE_STORAGE "Storage for the Debian template" "local"
ask BRIDGE "Network bridge" "vmbr0"
ask IP "IP address with prefix, e.g. 192.168.1.50/24, or dhcp" "dhcp"
if [[ $IP != dhcp ]]; then
    ask GATEWAY "Gateway" "${IP%.*}.1"
fi

# The newest Debian 13 template, downloaded unless it is there already.
pveam update > /dev/null
template=$(pveam available --section system | awk '/debian-13-standard/ {print $2}' | sort -V | tail -n 1)
if [[ -z $template ]]; then
    echo "No Debian 13 template found (pveam available --section system)." >&2
    exit 1
fi
if ! pveam list "$TEMPLATE_STORAGE" | grep -F "$template" > /dev/null; then
    echo "Downloading $template ..."
    pveam download "$TEMPLATE_STORAGE" "$template"
fi

net="name=eth0,bridge=$BRIDGE,ip=$IP"
if [[ $IP != dhcp ]]; then
    net+=",gw=$GATEWAY"
fi

echo "Creating container $CTID ..."
# nesting and keyctl let Docker run inside an unprivileged container.
pct create "$CTID" "$TEMPLATE_STORAGE:vztmpl/$template" \
    --hostname "$CT_HOSTNAME" \
    --cores "$CORES" \
    --memory "$MEMORY" \
    --swap 512 \
    --rootfs "$STORAGE:$DISK" \
    --net0 "$net" \
    --unprivileged 1 \
    --features nesting=1,keyctl=1 \
    --onboot 1 \
    --description "Home-Rank: https://github.com/januhrhammer/Home-Rank"
pct start "$CTID"

echo "Waiting for the network ..."
for _ in $(seq 60); do
    if pct exec "$CTID" -- getent hosts deb.debian.org > /dev/null 2>&1; then
        break
    fi
    sleep 2
done
address=$(pct exec "$CTID" -- hostname -I | awk '{print $1}')
if [[ -z $address ]]; then
    echo "The container got no IP address; check the bridge and IP settings." >&2
    exit 1
fi

# Runs inside the container. $1 is the address Home-Rank is reached at, $2 the host name.
read -r -d '' install_script << 'EOF' || true
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "Installing Docker ..."
apt-get update -qq
apt-get install -y -qq ca-certificates curl openssl > /dev/null
# Docker's own repository, as in https://docs.docker.com/engine/install/debian/
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $VERSION_CODENAME stable" \
    > /etc/apt/sources.list.d/docker.list
apt-get update -qq
apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin > /dev/null

echo "Downloading Home-Rank ..."
mkdir -p /opt/home-rank
cd /opt/home-rank
curl -fsSLO "$RELEASE_URL/compose.yaml"
curl -fsSL -o .env.example "$RELEASE_URL/env.example"

# The four required settings; everything else keeps its default (see .env.example).
sed -e "s/^SECRET_KEY=.*/SECRET_KEY=$(openssl rand -hex 32)/" \
    -e "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" \
    -e "s/^ALLOWED_HOSTS=.*/ALLOWED_HOSTS=$1,$2/" \
    -e "s/^HTTPS=.*/HTTPS=false/" \
    .env.example > .env
chmod 600 .env

echo "Starting Home-Rank (the first start downloads about 1 GB) ..."
docker compose up -d --wait
EOF

pct exec "$CTID" -- env RELEASE_URL="$RELEASE_URL" bash -c "$install_script" _ "$address" "$CT_HOSTNAME"

cat << EOF

Home-Rank is running in container $CTID at http://$address:8000

Create your account (passwords need at least 15 characters):

  pct enter $CTID
  cd /opt/home-rank && docker compose exec web python manage.py createsuperuser

Settings are in /opt/home-rank/.env in the container; docs/self-hosting.md explains them, and
how to update, back up and add HTTPS.
EOF
if [[ $IP == dhcp ]]; then
    echo
    echo "The address came from DHCP: reserve it in your router, as ALLOWED_HOSTS in .env names it."
fi
