#!/bin/bash

cat /run/secrets/ca_crt > /etc/prometheus/ca.crt
cat /run/secrets/node_scraper_crt > /etc/prometheus/host.crt
cat /run/secrets/node_scraper_key > /etc/prometheus/host.key
chmod 440 /etc/prometheus/ca.crt /etc/prometheus/host.crt /etc/prometheus/host.key

exec /bin/node_exporter \
  --path.rootfs="/rootfs" \
  --path.procfs="/host/proc" \
  --path.sysfs="/host/sys" \
  --collector.filesystem.mount-points-exclude="^/(sys|proc|dev|host|etc)($$|/)" \
  --web.telemetry-path="/metrics" \
  --web.listen-address=":9100" \
  --web.config.file="/etc/prometheus/web_config.yml"
