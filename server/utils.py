import os
import time
import subprocess
import random
from server.constants import IP_BLOCKLIST_PATH


def random_ip():
    return f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}"


def clear_file(path: str) -> None:
    try:
        with open(path, "w") as f:
            f.write("")
    except Exception:
        pass


def nginx_reload() -> None:
    try:
        subprocess.run(["nginx", "-s", "reload"], capture_output=True, timeout=5)
    except Exception:
        pass


def block_ip(ip: str) -> None:
    try:
        with open(IP_BLOCKLIST_PATH, "a") as f:
            f.write(f"deny {ip};\n")
        nginx_reload()
    except Exception:
        pass


def is_ip_blocked(ip: str) -> bool:
    try:
        with open(IP_BLOCKLIST_PATH, "r") as f:
            return f"deny {ip};" in f.read()
    except Exception:
        return False


def restart_attacker(scenario: str, scenarios: list) -> None:
    for s in scenarios:
        try:
            subprocess.run(
                ["supervisorctl", "stop", f"{s}_attack"], capture_output=True, timeout=5
            )
        except Exception:
            pass
    try:
        subprocess.run(
            ["supervisorctl", "start", f"{scenario}_attack"],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass


def kill_process(pid: int) -> bool:
    try:
        proc_status = f"/proc/{pid}/status"

        if not os.path.exists(proc_status):
            return False

        import signal

        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

        time.sleep(1.0)

        if not os.path.exists(proc_status):
            return True

        try:
            with open(proc_status) as f:
                state_line = next((l for l in f if l.startswith("State:")), "")
            return "Z" in state_line
        except OSError:
            return True

    except Exception:
        return False


def read_logs(file_path: str) -> str:
    try:
        result = subprocess.run(
            ["tail", "-n", "50", file_path], capture_output=True, text=True, timeout=5
        )
        return result.stdout or "(log empty - attacker may not have fired yet)"
    except Exception:
        return "(could not read log file)"


def check_hard_attack_process() -> bool:
    return os.path.exists("/tmp/.hard_attack_active")
