import os
import time
import random
import subprocess

from server.constants import IP_BLOCKLIST_PATH, PID_FILE_PATH


# Generates a random IP address (randomises all 4 octets)
def random_ip():
    return f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}"


# Clears the contents of a file
def clear_file(path: str) -> None:
    try:
        with open(path, "w") as f:
            f.write("")
    except Exception:
        pass

# Reloads nginx to apply changes to config like blocklist
def nginx_reload() -> None:
    try:
        subprocess.run(["nginx", "-s", "reload"], capture_output=True, timeout=5)
    except Exception:
        pass


# Adds an IP address to the nginx blocklist and reloads nginx
def block_ip(ip: str) -> None:
    try:
        with open(IP_BLOCKLIST_PATH, "a") as f:
            f.write(f"deny {ip};\n") # Writes "deny {ip};" to block it
        nginx_reload()
    except Exception:
        pass


# Checks if an IP address is already in the nginx blocklist
def is_ip_blocked(ip: str) -> bool:
    try:
        with open(IP_BLOCKLIST_PATH, "r") as f:
            return f"deny {ip};" in f.read() # Checks if "deny {ip};" is in it
    except Exception:
        return False


# Restarts the attacker process controlled by supervisord for a given scenario
def restart_attacker(scenario: str, scenarios: list) -> None:
    for s in scenarios:
        # If the scenario's attack script is already running, stop it
        try:
            subprocess.run(
                ["supervisorctl", "stop", f"{s}_attack"], capture_output=True, timeout=5
            )
        except Exception:
            pass
    try:
        # Start the attack script for the scenario
        subprocess.run(
            ["supervisorctl", "start", f"{scenario}_attack"],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass


# Kills a process by its PID
def kill_process(pid: int) -> bool:
    try:
        proc_status = f"/proc/{pid}/status" # Path to check process status on Linux

        # Checks if the process exists by checking its respective process dir
        if not os.path.exists(proc_status):
            return False

        import signal

        try:
            os.kill(pid, signal.SIGKILL) # Send a SIGKILL signal to the process
            
            if os.path.exists(PID_FILE_PATH):
                try:
                    with open(PID_FILE_PATH) as f:
                        stored = int(f.read().strip()) # Get stored attacker PID in PID_FILE_PATH

                    # If the PID to be killed is same as attacker PID, then remove file at PID_FILE_PATH
                    if stored == pid:
                        os.remove(PID_FILE_PATH)
                except Exception:
                    pass
        except ProcessLookupError:
            pass

        time.sleep(1.0) # Wait to let killing of process complete

        # Return True if process no longer exists
        if not os.path.exists(proc_status):
            return True

        try:
            # Check if process is a zombie if it still exists, if yes then send True, else process killing failed
            with open(proc_status) as f:
                state_line = next((l for l in f if l.startswith("State:")), "")
            return "Z" in state_line
        except OSError:
            return True

    except Exception:
        return False


# Reads the last 50 logs of the specified logfile
def read_logs(file_path: str) -> str:
    try:
        result = subprocess.run(
            ["tail", "-n", "50", file_path], capture_output=True, text=True, timeout=5
        )
        return result.stdout or "(log empty - attacker may not have fired yet)"
    except Exception:
        return "(could not read log file)"


# Checks if the hard attack process is running
def check_hard_attack_process():
    if not os.path.exists(PID_FILE_PATH): # If PID file doesn't exist, then process is killed
        return False
    with open(PID_FILE_PATH) as f:
        pid = int(f.read().strip())
    try:
        os.kill(pid, 0) # Checks if process with given PID exists and is running
        return True
    except ProcessLookupError:
        return False
