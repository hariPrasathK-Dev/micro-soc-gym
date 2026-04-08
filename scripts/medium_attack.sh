#!/bin/bash
# Medium: Brute force attack attempt

if [ -f /tmp/micro_soc_state.env ]; then
    source /tmp/micro_soc_state.env
    ATTACKER_IP=$MEDIUM_ATTACKER_IP
    ADMIN_IP=$MEDIUM_ADMIN_IP
else
    ATTACKER_IP="$((RANDOM % 255 + 1)).$((RANDOM % 255)).$((RANDOM % 255)).$((RANDOM % 255))"
    ADMIN_IP="$((RANDOM % 255 + 1)).$((RANDOM % 255)).$((RANDOM % 255)).$((RANDOM % 255))"
fi

USERS=("root" "admin" "ubuntu" "pi" "user" "deploy" "git")
PORTS=(51234 52891 53007 54321 55102 56777 57438)
COUNTER=2

echo "Starting medium scenario attack from $ATTACKER_IP... (whitelisted IP: $ADMIN_IP)"

while true; do
    # 5-8 failed attempts per cycle
    BURST=$((RANDOM % 4 + 5))
    for i in $(seq 1 $BURST); do
        USER=${USERS[$((RANDOM % ${#USERS[@]}))]}
        PORT=${PORTS[$((RANDOM % ${#PORTS[@]}))]}
        echo "$(date '+%b %d %H:%M:%S') myhost sshd[$((RANDOM % 9000 + 1000))]: Failed password for $USER from $ATTACKER_IP port $PORT ssh2" >> /var/log/auth.log
        sleep 0.2
    done

    COUNTER=$((COUNTER + 1))

    # Every 3 cycles adds an admin login from the whitelisted IP
    if [ $((COUNTER % 3)) -eq 0 ]; then
        echo "$(date '+%b %d %H:%M:%S') myhost sshd[2200]: Accepted password for admin from $ADMIN_IP port 22 ssh2" >> /var/log/auth.log
    fi

    sleep 3
done