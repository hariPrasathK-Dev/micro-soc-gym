#!/bin/bash
# Easy: Noisy scanner - rapid 404 spam from a fixed fake IP
# Injects fake IP into logs via X-Forwarded-For so agent sees 10.0.0.1
echo "Starting easy attack (noisy scanner)..."
while true; do
    curl -s \
        -H "X-Forwarded-For: 10.0.0.1" \
        http://localhost/admin > /dev/null
    curl -s \
        -H "X-Forwarded-For: 10.0.0.1" \
        http://localhost/.env > /dev/null
    curl -s \
        -H "X-Forwarded-For: 10.0.0.1" \
        http://localhost/wp-login.php > /dev/null
    sleep 0.3
done