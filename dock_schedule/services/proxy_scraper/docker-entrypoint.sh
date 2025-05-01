#!/bin/bash

cat /run/secrets/ca_crt > /opt/bitnami/ca.crt
cat /run/secrets/proxy_scraper_crt > /opt/bitnami/host.crt
cat /run/secrets/proxy_scraper_key > /opt/bitnami/host.key
chmod 440 /opt/bitnami/host.crt /opt/bitnami/host.key /opt/bitnami/ca.crt

exec setpriv --reuid=1001 --regid=0 --clear-groups /opt/bitnami/nginx-exporter/bin/nginx-prometheus-exporter \
  --nginx.scrape-uri=https://proxy:9000/metrics \
  --web.listen-address=":9113" \
  --web.telemetry-path="/metrics" \
  --web.config.file="/opt/bitnami/web_config.yml" \
  --nginx.ssl-ca-cert="/opt/bitnami/ca.crt" \
  --nginx.ssl-client-cert="/opt/bitnami/host.crt" \
  --nginx.ssl-client-key="/opt/bitnami/host.key"
