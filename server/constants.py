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

MAX_STEPS = 8

CORRECT_ACTION_REWARD = 0.50
PARTIAL_ACTION_REWARD = 0.25
WRONG_TOOL_PENALTY = -0.50
FATAL_ACTION_PENALTY = -1.00
