#!/bin/bash

cat /run/secrets/ca_crt > /etc/prometheus/ca.crt
cat /run/secrets/prometheus_crt > /etc/prometheus/host.crt
cat /run/secrets/prometheus_key > /etc/prometheus/host.key
chmod 440 /etc/prometheus/ca.crt /etc/prometheus/host.crt /etc/prometheus/host.key

exec /bin/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --web.config.file=/etc/prometheus/web_config.yml
