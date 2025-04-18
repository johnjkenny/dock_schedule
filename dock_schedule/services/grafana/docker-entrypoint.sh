#!/bin/bash

cat /run/secrets/ca_crt > /etc/grafana/ca.crt
cat /run/secrets/grafana_crt > /etc/grafana/host.crt
cat /run/secrets/grafana_key > /etc/grafana/host.key
chmod 440 /etc/grafana/host.crt /etc/grafana/host.key /etc/grafana/ca.crt
chown -R grafana:root /etc/grafana/host.crt /etc/grafana/host.key /etc/grafana/ca.crt

CA_CONTENT=$(sed ':a;N;$!ba;s/\n/@@@/g' /etc/grafana/ca.crt)
CERT_CONTENT=$(sed ':a;N;$!ba;s/\n/@@@/g' /etc/grafana/host.crt)
KEY_CONTENT=$(sed ':a;N;$!ba;s/\n/@@@/g' /etc/grafana/host.key)
sed -i "s|CA_CERT|$CA_CONTENT|g" /etc/grafana/provisioning/datasources/datasources.yml
sed -i "s|CLIENT_CERT|$CERT_CONTENT|g" /etc/grafana/provisioning/datasources/datasources.yml
sed -i "s|CLIENT_KEY|$KEY_CONTENT|g" /etc/grafana/provisioning/datasources/datasources.yml
sed -i 's|@@@|\'$'\n        |g' /etc/grafana/provisioning/datasources/datasources.yml

exec /run.sh
