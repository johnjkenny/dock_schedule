#!/bin/bash

cat /run/secrets/ca_crt > /app/ca.crt
cat /run/secrets/worker_crt > /app/host.crt
cat /run/secrets/worker_key > /app/host.key
cat /app/host.crt /app/host.key > /app/host.pem
chmod 440 /app/host.crt /app/host.key /app/host.pem /app/ca.crt

exec python3 /app/worker.py
exit $?
