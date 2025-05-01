#!/bin/bash

MONGO_USER=$(cat /run/secrets/mongo_user)
MONGO_PASS=$(cat /run/secrets/mongo_passwd)
MONGO_DB=$(cat /run/secrets/mongo_db)
export MONGO_USER MONGO_PASS MONGO_DB

cat /run/secrets/ca_crt > /etc/mongo/ca.crt
cat /run/secrets/mongodb_crt /run/secrets/mongodb_key > /etc/mongo/host.pem
chmod 440 /etc/mongo/host.pem /etc/mongo/ca.crt
chown -R mongodb:mongodb /etc/mongo/host.pem /etc/mongo/ca.crt

sed -i "s/MONGO_USER/$MONGO_USER/g" /docker-entrypoint-initdb.d/init.js
sed -i "s/MONGO_PASS/$MONGO_PASS/g" /docker-entrypoint-initdb.d/init.js
sed -i "s/MONGO_DB/$MONGO_DB/g" /docker-entrypoint-initdb.d/init.js

exec su -s /bin/bash -c "python3 /usr/local/bin/docker-entrypoint.py mongod --config /etc/mongod.conf" mongodb
