#!/bin/bash

MONGODB_USER=$(cat /run/secrets/mongo_user)
MONGODB_PASSWORD=$(cat /run/secrets/mongo_passwd)
MONGO_DB=$(cat /run/secrets/mongo_db)
export MONGODB_USER MONGODB_PASSWORD

exec /opt/bitnami/mongodb-exporter/bin/mongodb_exporter \
    --mongodb.uri=mongodb://mongodb:27017/admin?ssl=true\&tlsCAFile=/opt/bitnami/dock-schedule-ca.crt\&tlsCertificateKeyFile=/opt/bitnami/mongodb_scraper.pem \
    --mongodb.indexstats-colls="$MONGO_DB" \
    --mongodb.collstats-colls="$MONGO_DB" \
    --web.config=/opt/bitnami/web_config.yml \
    --web.listen-address=":9216" \
    --web.telemetry-path="/metrics" \
    --collect-all
