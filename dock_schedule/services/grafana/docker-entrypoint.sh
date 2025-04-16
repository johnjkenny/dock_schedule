#!/bin/bash

CA_CONTENT=$(sed ':a;N;$!ba;s/\n/@@@/g' /etc/grafana/dock-schedule-ca.crt)
CERT_CONTENT=$(sed ':a;N;$!ba;s/\n/@@@/g' /etc/grafana/grafana.crt)
KEY_CONTENT=$(sed ':a;N;$!ba;s/\n/@@@/g' /etc/grafana/grafana.key)
sed -i "s|CA_CERT|$CA_CONTENT|g" /etc/grafana/provisioning/datasources/datasources.yml
sed -i "s|CLIENT_CERT|$CERT_CONTENT|g" /etc/grafana/provisioning/datasources/datasources.yml
sed -i "s|CLIENT_KEY|$KEY_CONTENT|g" /etc/grafana/provisioning/datasources/datasources.yml
sed -i 's|@@@|\'$'\n        |g' /etc/grafana/provisioning/datasources/datasources.yml

exec /run.sh
