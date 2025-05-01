#!/bin/sh

MONGODB_USER=$(cat /run/secrets/mongo_user)
MONGODB_PASSWORD=$(cat /run/secrets/mongo_passwd)
MONGO_DB=$(cat /run/secrets/mongo_db)
export MONGODB_USER MONGODB_PASSWORD

cat /run/secrets/ca_crt > /opt/bitnami/ca.crt
cat /run/secrets/mongodb_scraper_crt > /opt/bitnami/host.crt
cat /run/secrets/mongodb_scraper_key > /opt/bitnami/host.key
cat /opt/bitnami/host.crt /opt/bitnami/host.key > /opt/bitnami/host.pem
chmod 440 /opt/bitnami/host.crt /opt/bitnami/host.key /opt/bitnami/host.pem /opt/bitnami/ca.crt

exec setpriv --reuid=1001 --regid=0 --clear-groups /opt/bitnami/mongodb-exporter/bin/mongodb_exporter \
  --mongodb.uri=mongodb://mongodb:27017/admin?ssl=true\&tlsCAFile=/opt/bitnami/ca.crt\&tlsCertificateKeyFile=/opt/bitnami/host.pem \
  --mongodb.indexstats-colls="$MONGO_DB" \
  --mongodb.collstats-colls="$MONGO_DB" \
  --web.config=/opt/bitnami/web_config.yml \
  --web.listen-address=":9216" \
  --web.telemetry-path="/metrics" \
  --collect-all
