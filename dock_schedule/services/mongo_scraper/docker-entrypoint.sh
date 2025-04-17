#!/bin/bash

MONGODB_USER=$(cat /run/secrets/mongo_user)
MONGODB_PASSWORD=$(cat /run/secrets/mongo_passwd)
MONGO_DB=$(cat /run/secrets/mongo_db)
export MONGODB_USER MONGODB_PASSWORD

exec /opt/bitnami/mongodb-exporter/bin/mongodb_exporter \
    --mongodb.uri=mongodb://mongodb:27017/?ssl=true\&tlsCAFile=/opt/bitnami/dock-schedule-ca.crt\&tlsCertificateKeyFile=/opt/bitnami/mongodb_scraper.pem \
    --mongodb.collstats-colls="$MONGO_DB".jobs \
    --web.config=/opt/bitnami/web_config.yml
