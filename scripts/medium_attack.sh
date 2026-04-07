#!/bin/bash
# Medium: Stealthy SSH brute force - writes directly to auth.log
# Attacker IP: 10.0.0.2  |  Whitelisted admin IP: 10.0.0.100
# Decoy: 10.0.0.100 makes occasional legitimate logins to confuse naive agents
echo "Starting medium attack (brute force)..."
COUNTER=0
while true; do
    # Attacker: repeated failed passwords
    echo "$(date '+%b %d %H:%M:%S') myhost sshd[1234]: Failed password for root from 10.0.0.2 port 54321 ssh2" >> /var/log/auth.log
    COUNTER=$((COUNTER + 1))

    # Every 3 attacker entries, add one legitimate admin login from whitelisted IP
    if [ $((COUNTER % 3)) -eq 0 ]; then
        echo "$(date '+%b %d %H:%M:%S') myhost sshd[2200]: Accepted password for admin from 10.0.0.100 port 22 ssh2" >> /var/log/auth.log
    fi

    sleep 4
done