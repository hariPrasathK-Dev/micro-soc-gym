#!/bin/bash
# Easy: Attacker repeatedly requests for 404 paths while normal users browse normal pages

if [ -f /tmp/micro_soc_state.env ]; then
    source /tmp/micro_soc_state.env
else
    ATTACKER_IP="$((RANDOM % 255 + 1)).$((RANDOM % 255)).$((RANDOM % 255)).$((RANDOM % 255))"
    NORMAL_IPS=("$((RANDOM % 255 + 1)).$((RANDOM % 255)).$((RANDOM % 255)).$((RANDOM % 255))" "$((RANDOM % 255 + 1)).$((RANDOM % 255)).$((RANDOM % 255)).$((RANDOM % 255))")
fi

COUNTER=0
NORMAL_PATHS=("/" "/index.html" "/about" "/contact" "/products" "/favicon.ico")

echo "Starting easy scenario attack..."

while true; do
    # Attacker does rapid scan of suspicious paths
    curl -s -H "X-Forwarded-For: $ATTACKER_IP" http://localhost/admin > /dev/null
    curl -s -H "X-Forwarded-For: $ATTACKER_IP" http://localhost/.env > /dev/null
    curl -s -H "X-Forwarded-For: $ATTACKER_IP" http://localhost/wp-login.php > /dev/null
    curl -s -H "X-Forwarded-For: $ATTACKER_IP" http://localhost/phpmyadmin > /dev/null
    curl -s -H "X-Forwarded-For: $ATTACKER_IP" http://localhost/.git/config > /dev/null

    COUNTER=$((COUNTER + 1))

    # Every other cycle includes 1-2 normal user requests to mix in normal traffic
    if [ $((COUNTER % 2)) -eq 0 ]; then
        IP=${NORMAL_IPS[$((RANDOM % ${#NORMAL_IPS[@]}))]}
        PATH_=${NORMAL_PATHS[$((RANDOM % ${#NORMAL_PATHS[@]}))]}
        curl -s -H "X-Forwarded-For: $IP" "http://localhost${PATH_}" > /dev/null
        sleep 0.1
        IP2=${NORMAL_IPS[$((RANDOM % ${#NORMAL_IPS[@]}))]}
        PATH2=${NORMAL_PATHS[$((RANDOM % ${#NORMAL_PATHS[@]}))]}
        curl -s -H "X-Forwarded-For: $IP2" "http://localhost${PATH2}" > /dev/null
    fi

    sleep 0.3
done
