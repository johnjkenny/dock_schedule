#!/bin/bash

exec /opt/bitnami/nginx-exporter/bin/nginx-prometheus-exporter \
  --nginx.scrape-uri=https://proxy:9000/metrics \
  --web.listen-address=":9113" \
  --web.telemetry-path="/metrics" \
  --web.config.file="/opt/bitnami/web_config.yml" \
  --nginx.ssl-ca-cert="/opt/bitnami/dock-schedule-ca.crt" \
  --nginx.ssl-client-cert="/opt/bitnami/proxy_scraper.crt" \
  --nginx.ssl-client-key="/opt/bitnami/proxy_scraper.key"
