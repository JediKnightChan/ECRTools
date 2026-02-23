import time
import json
import argparse
import os
from datetime import datetime
import docker

HOST_PROC = "/host_proc"
GAME_SERVER_IMAGE_NAME = os.getenv("GAME_SERVER_IMAGE_NAME")

docker_client = docker.DockerClient(base_url="unix://var/run/docker.sock")


def read_file(path):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return None


def host_path(path):
    return os.path.join(HOST_PROC, path.lstrip("/"))


def is_game_server_running():
    if not GAME_SERVER_IMAGE_NAME:
        return False
    try:
        containers = docker_client.containers.list()
        for c in containers:
            tags = c.image.tags
            if any(GAME_SERVER_IMAGE_NAME in tag for tag in tags):
                return True
    except Exception:
        pass
    return False


def get_cpu_times():
    data = read_file(host_path("/proc/stat"))
    if not data:
        return None, None
    parts = data.splitlines()[0].split()[1:]
    values = list(map(int, parts))
    return sum(values), values[3]


def get_softirq():
    data = read_file(host_path("/proc/stat"))
    if not data:
        return None
    for line in data.splitlines():
        if line.startswith("softirq"):
            return sum(map(int, line.split()[1:]))
    return None


def get_softnet_drops():
    data = read_file(host_path("/proc/net/softnet_stat"))
    if not data:
        return None
    drops = 0
    for line in data.splitlines():
        drops += int(line.split()[1], 16)
    return drops


def get_net_dev():
    data = read_file(host_path("/proc/net/dev"))
    if not data:
        return None
    result = {}
    for line in data.splitlines()[2:]:
        iface, stats = line.split(":")
        iface = iface.strip()
        parts = stats.split()
        result[iface] = {
            "rx_bytes": int(parts[0]),
            "tx_bytes": int(parts[8]),
        }
    return result


def get_loadavg():
    data = read_file(host_path("/proc/loadavg"))
    if not data:
        return None
    l = data.split()
    return {"load1": float(l[0]), "load5": float(l[1]), "load15": float(l[2])}


def get_meminfo():
    data = read_file(host_path("/proc/meminfo"))
    if not data:
        return None
    mem = {}
    for line in data.splitlines():
        k, v = line.split(":")
        mem[k] = int(v.strip().split()[0])
    return {
        "mem_total_kb": mem.get("MemTotal"),
        "mem_available_kb": mem.get("MemAvailable"),
    }


def get_conntrack():
    count = read_file(host_path("/proc/sys/net/netfilter/nf_conntrack_count"))
    maxv = read_file(host_path("/proc/sys/net/netfilter/nf_conntrack_max"))
    if count and maxv:
        return {"count": int(count), "max": int(maxv)}
    return None


def main(interval, logs_dir):
    prev_total, prev_idle = get_cpu_times()
    prev_softirq = get_softirq()

    current_date = None
    log_file = None

    while True:
        time.sleep(interval)

        if not is_game_server_running():
            continue

        now = datetime.utcnow()
        today_str = now.strftime("%Y-%m-%d")

        if current_date != today_str:
            if log_file:
                log_file.close()
            os.makedirs(logs_dir, exist_ok=True)
            file_path = os.path.join(logs_dir, f"host_monitor-{today_str}.log")
            log_file = open(file_path, "a")
            current_date = today_str

        total, idle = get_cpu_times()
        softirq = get_softirq()

        cpu_usage = None
        softirq_delta = None

        if prev_total and total:
            total_delta = total - prev_total
            idle_delta = idle - prev_idle
            if total_delta > 0:
                cpu_usage = 100.0 * (1 - idle_delta / total_delta)

        if prev_softirq and softirq:
            softirq_delta = softirq - prev_softirq

        prev_total, prev_idle = total, idle
        prev_softirq = softirq

        entry = {
            "timestamp": now.isoformat(),
            "cpu_percent": cpu_usage,
            "softirq_delta": softirq_delta,
            "softnet_drops": get_softnet_drops(),
            "network": get_net_dev(),
            "loadavg": get_loadavg(),
            "memory": get_meminfo(),
            "conntrack": get_conntrack(),
        }

        log_file.write(json.dumps(entry) + "\n")
        log_file.flush()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--logs_dir", type=str, default="/logs")
    args = parser.parse_args()

    main(args.interval, args.logs_dir)