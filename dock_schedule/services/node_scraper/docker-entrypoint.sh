#!/bin/sh

cat /run/secrets/ca_crt > /opt/bitnami/ca.crt
cat /run/secrets/node_scraper_crt > /opt/bitnami/host.crt
cat /run/secrets/node_scraper_key > /opt/bitnami/host.key
chmod 440 /opt/bitnami/ca.crt /opt/bitnami/host.crt /opt/bitnami/host.key

exec setpriv --reuid=1001 --regid=0 --clear-groups /opt/bitnami/node-exporter/bin/node_exporter \
  --path.rootfs="/rootfs" \
  --path.procfs="/host/proc" \
  --path.sysfs="/host/sys" \
  --collector.filesystem.mount-points-exclude="^/(sys|proc|dev|host|etc)($$|/)" \
  --web.telemetry-path="/metrics" \
  --web.listen-address=":9100" \
  --web.config.file="/opt/bitnami/web_config.yml"
