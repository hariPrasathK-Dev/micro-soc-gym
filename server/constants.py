SCENARIOS = ["easy", "medium", "hard"]

ACCESS_LOG_PATH = "/var/log/nginx/access.log"
AUTH_LOG_PATH = "/var/log/auth.log"
IP_BLOCKLIST_PATH = "/etc/nginx/blocklist.conf"
WEBROOT_PATH = "/var/www/html"
BACKDOOR_FILE_NAMES = [
    "backdoor.php",
    "shell.php",
    "cmd.php",
    "wp-config.php.bak",
    "admin_helper.php",
]

PID_FILE_PATH = "/tmp/.hard_attack_pid"
HARD_ATTACK_FLAG_FILE_PATH = "/tmp/.hard_attack_active"

MAX_STEPS = 8

CORRECT_ACTION_REWARD = 0.50
CORRECT_INVESTIGATIVE_DIRECTION_REWARD = 0.25
CORRECT_TOOL_WRONG_TARGET_REWARD = 0.10

NON_INVESTIGATIVE_REMEDIATION_ACTION_PENALTY = -1.00
ADMIN_IP_BLOCK_PENALTY = -1.00
WRONG_FILE_DELETION_PENALTY = -0.75
WRONG_TOOL_PENALTY = -0.50
UNWARRANTED_ACTION_REPEAT_PENALTY = -0.30
ACTION_TO_STALL_PENALTY = -0.25
PROCESS_KILL_FAIL_PENALTY = -0.20
