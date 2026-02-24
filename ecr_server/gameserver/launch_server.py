import logging
import subprocess
import os
import sys

from pathlib import Path

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def get_env_var_or_exit(env_var):
    value = os.getenv(env_var, None)
    if value is None:
        logger.critical(f"Env var {env_var} is not set, exiting...")
        sys.exit(1)
    return value


def main():
    if os.getenv("DONT_LAUNCH_GAME", None) is not None:
        logger.debug("Test container run without launching game detected (DONT_LAUNCH_GAME set), exiting...")
        sys.exit(0)

    wants_launch_with_time = os.getenv("LAUNCH_WITH_TIME", None) == "1"

    map = get_env_var_or_exit("MAP")
    mode = get_env_var_or_exit("MODE")
    mission = get_env_var_or_exit("MISSION")
    region = get_env_var_or_exit("REGION")
    epic_app = get_env_var_or_exit("EPIC_APP")
    analytics_key = get_env_var_or_exit("GAME_ANALYTICS_KEY")
    log_file = get_env_var_or_exit("LOG")
    match_id = get_env_var_or_exit("MATCH_ID")
    faction_setup = get_env_var_or_exit("FACTIONS")
    max_team_size = get_env_var_or_exit("MAX_TEAM_SIZE")
    want_trace = get_env_var_or_exit("WANT_TRACE") == "1"

    game_port = get_env_var_or_exit("PORT")

    current_file_dir = Path(__file__).resolve().parent

    executable_dev = "./LinuxServer/ECR/Binaries/Linux/ECRServer"
    executable_prod = "./LinuxServer/ECR/Binaries/Linux/ECRServer-Linux-Shipping"

    if os.path.exists(os.path.join(current_file_dir, executable_prod)):
        executable = executable_prod
    elif os.path.exists(os.path.join(current_file_dir, executable_dev)):
        executable = executable_dev
    else:
        raise Exception("Couldn't find neither prod nor dev executable")

    if want_trace:
        # Enable profiling by Unreal Insights and Network Profiler
        trace_file = log_file.replace(".log", ".utrace")
        trace_part = f"-tracefile={trace_file} -trace=cpu,frame,net,replication -NetTrace=1 networkprofiler=true"
    else:
        # Still possible that net tracing could be requested by GM in game chat
        trace_part = "-NetTrace=1"

    launch_command = f"{executable} ECR {map} -mode={mode}" \
                     f" -mission={mission} -region={region} -epicapp={epic_app}" \
                     f" -analytics-key={analytics_key} -log={log_file} -matchid={match_id} -factions={faction_setup}" \
                     f" -maxteamsize={max_team_size} -port={game_port} {trace_part}"

    launch_command_with_time = f"/usr/bin/time -v {launch_command}"

    if wants_launch_with_time:
        command = launch_command_with_time
        logger.debug(f"Launch with /usr/bin/time requested, command: {command}")
    else:
        command = launch_command
        logger.debug(f"Launching without /usr/bin/time, command: {command}")

    subprocess.run(command, shell=True)


if __name__ == '__main__':
    main()
