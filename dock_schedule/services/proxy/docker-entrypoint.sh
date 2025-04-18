#!/bin/bash

cat /run/secrets/ca_crt > /etc/nginx/ca.crt
cat /run/secrets/proxy_crt > /etc/nginx/host.crt
cat /run/secrets/proxy_key > /etc/nginx/host.key
chown nginx:root /etc/nginx/ca.crt /etc/nginx/host.crt /etc/nginx/host.key
chmod 440 /etc/nginx/ca.crt /etc/nginx/host.crt /etc/nginx/host.key

exec /docker-entrypoint.sh nginx -g "daemon off;"
