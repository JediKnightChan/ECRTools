import os
import time
import json
import argparse
import datetime
import docker


GAME_SERVER_IMAGE_NAME = os.getenv("GAME_SERVER_IMAGE_NAME")

if not GAME_SERVER_IMAGE_NAME:
    raise RuntimeError("GAME_SERVER_IMAGE_NAME env var must be set")

HOST_PROC = "/host_proc"

# =========================

def host_path(path):
    return os.path.join(HOST_PROC, path.lstrip("/"))

def read_file(path):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return None


# =========================
# Docker check
# =========================

def is_game_server_running():
    try:
        client = docker.DockerClient(base_url="unix://var/run/docker.sock")
        containers = client.containers.list()
        for c in containers:
            tags = c.image.tags or []
            for tag in tags:
                if GAME_SERVER_IMAGE_NAME in tag:
                    return True
        return False
    except Exception:
        return False


# =========================
# CPU
# =========================

def get_cpu_times():
    data = read_file(host_path("/stat"))
    if not data:
        return None, None

    for line in data.splitlines():
        if line.startswith("cpu "):
            parts = line.split()
            values = list(map(int, parts[1:]))
            idle = values[3] + values[4]
            total = sum(values)
            return total, idle
    return None, None


# =========================
# SoftIRQ
# =========================

def get_softirq():
    data = read_file(host_path("/softirqs"))
    if not data:
        return None

    for line in data.splitlines():
        line = line.strip()
        if line.startswith("NET_RX"):
            parts = line.split()[1:]
            return sum(map(int, parts))
    return None


# =========================
# Softnet drops
# =========================

def get_softnet_drops():
    data = read_file(host_path("/net/softnet_stat"))
    if not data:
        return None

    total = 0
    for line in data.splitlines():
        parts = line.split()
        if len(parts) > 1:
            total += int(parts[1], 16)
    return total


# =========================
# Network bytes
# =========================

def get_network_bytes():
    data = read_file(host_path("/net/dev"))
    if not data:
        return None

    total_rx = 0
    total_tx = 0

    lines = data.splitlines()[2:]
    for line in lines:
        parts = line.split()
        if len(parts) >= 17:
            total_rx += int(parts[1])
            total_tx += int(parts[9])

    return {"rx": total_rx, "tx": total_tx}


# =========================
# Loadavg
# =========================

def get_loadavg():
    data = read_file(host_path("/loadavg"))
    if not data:
        return None

    parts = data.split()
    return {
        "l1": float(parts[0]),
        "l5": float(parts[1]),
        "l15": float(parts[2])
    }


# =========================
# Memory
# =========================

def get_memory():
    data = read_file(host_path("/meminfo"))
    if not data:
        return None

    mem = {}
    for line in data.splitlines():
        parts = line.split()
        key = parts[0].rstrip(":")
        mem[key] = int(parts[1])

    if "MemTotal" in mem and "MemAvailable" in mem:
        used = mem["MemTotal"] - mem["MemAvailable"]
        return {
            "total_kb": mem["MemTotal"],
            "used_kb": used
        }

    return None


# =========================
# Conntrack
# =========================

def get_conntrack():
    count = read_file(host_path("/sys/net/netfilter/nf_conntrack_count"))
    maxv = read_file(host_path("/sys/net/netfilter/nf_conntrack_max"))

    if count and maxv:
        return {
            "count": int(count),
            "max": int(maxv)
        }
    return None


# =========================
# Logging
# =========================

def get_log_file(log_dir):
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, f"host-monitor-{today}.log")


# =========================
# Main loop
# =========================

def main(interval, logs_dir):
    prev_total = None
    prev_idle = None
    prev_softirq = None
    prev_net = None

    while True:
        if not is_game_server_running():
            time.sleep(interval)
            continue

        now = datetime.datetime.utcnow().isoformat()

        total, idle = get_cpu_times()
        softirq = get_softirq()
        softnet = get_softnet_drops()
        net = get_network_bytes()
        load = get_loadavg()
        mem = get_memory()
        conntrack = get_conntrack()

        cpu_percent = None
        softirq_delta = None
        net_rate = None

        # CPU
        if (
            prev_total is not None and
            total is not None and
            prev_idle is not None and
            idle is not None
        ):
            delta_total = total - prev_total
            delta_idle = idle - prev_idle
            if delta_total > 0:
                cpu_percent = 100.0 * (delta_total - delta_idle) / delta_total

        # Softirq delta
        if prev_softirq is not None and softirq is not None:
            softirq_delta = softirq - prev_softirq

        # Network rate
        if prev_net is not None and net is not None:
            net_rate = {
                "rx_per_sec": (net["rx"] - prev_net["rx"]) / interval,
                "tx_per_sec": (net["tx"] - prev_net["tx"]) / interval
            }

        # Save previous
        prev_total = total
        prev_idle = idle
        prev_softirq = softirq
        prev_net = net

        record = {
            "ts": now,
            "cpu": cpu_percent,
            "softirq": softirq_delta,
            "softnet_drops": softnet,
            "net": net_rate,
            "load": load,
            "mem": mem,
            "conntrack": conntrack
        }

        with open(get_log_file(logs_dir), "a") as f:
            f.write(json.dumps(record) + "\n")

        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--logs_dir", type=str, default="/logs")
    args = parser.parse_args()

    main(args.interval, args.logs_dir)
