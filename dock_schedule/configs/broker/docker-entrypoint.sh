#!/bin/bash

RABBITMQ_DEFAULT_USER=$(cat /run/secrets/broker_user)
RABBITMQ_DEFAULT_PASS=$(cat /run/secrets/broker_passwd)
RABBITMQ_DEFAULT_VHOST=$(cat /run/secrets/broker_vhost)
export RABBITMQ_DEFAULT_USER RABBITMQ_DEFAULT_PASS RABBITMQ_DEFAULT_VHOST

exec /bin/bash /usr/local/bin/docker-entrypoint.sh rabbitmq-server
exit $?
