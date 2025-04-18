#!/bin/bash

RABBITMQ_DEFAULT_USER=$(cat /run/secrets/broker_user)
RABBITMQ_DEFAULT_PASS=$(cat /run/secrets/broker_passwd)
RABBITMQ_DEFAULT_VHOST=$(cat /run/secrets/broker_vhost)
export RABBITMQ_DEFAULT_USER RABBITMQ_DEFAULT_PASS RABBITMQ_DEFAULT_VHOST

cat /run/secrets/ca_crt > /etc/rabbitmq/ca.crt
cat /run/secrets/broker_crt > /etc/rabbitmq/host.crt
cat /run/secrets/broker_key > /etc/rabbitmq/host.key
chmod 440 /etc/rabbitmq/host.crt /etc/rabbitmq/host.key /etc/rabbitmq/ca.crt
chown -R rabbitmq:root /etc/rabbitmq/host.crt /etc/rabbitmq/host.key /etc/rabbitmq/ca.crt

exec /bin/bash /usr/local/bin/docker-entrypoint.sh rabbitmq-server
exit $?
