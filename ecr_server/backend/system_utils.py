import math

import psutil
import os


def get_cpu_and_ram():
    total_memory_gb = psutil.virtual_memory().total / (1024 ** 3)
    cpu_cores = os.cpu_count()
    return total_memory_gb, cpu_cores


def parse_time_command_output(output):
    def parse_wall_time(time_str):
        parts = time_str.split(":")
        parts = [float(p) for p in parts]
        if len(parts) == 3:
            h, m, s = parts
        elif len(parts) == 2:
            h = 0
            m, s = parts
        else:
            return 0
        return h * 3600 + m * 60 + s

    metrics = {}
    for line in output.splitlines():
        if "Maximum resident set size (kbytes):" in line:
            metrics["peak_memory_mb"] = int(line.split("Maximum resident set size (kbytes):")[1].strip()) / 1000
        if "Percent of CPU this job got:" in line:
            metrics["cpu_percent"] = int(line.split("Percent of CPU this job got:")[1].strip().strip("%"))
        if "Elapsed (wall clock) time (h:mm:ss or m:ss):" in line:
            wall_time_raw = line.split("Elapsed (wall clock) time (h:mm:ss or m:ss):")[1].strip()
            metrics["wall_time_raw"] = wall_time_raw
            metrics["wall_time"] = parse_wall_time(wall_time_raw)
        if "User time (seconds):" in line:
            metrics["user_time"] = float(line.split("User time (seconds):")[1].strip())
        if "System time (seconds):" in line:
            metrics["system_time"] = float(line.split("System time (seconds):")[1].strip())
    return metrics


print(get_cpu_and_ram())
