#!/bin/bash

MONGO_USER=$(cat /run/secrets/mongo_user)
MONGO_PASS=$(cat /run/secrets/mongo_passwd)
MONGO_DB=$(cat /run/secrets/mongo_db)
export MONGO_USER MONGO_PASS MONGO_DB

sed -i "s/MONGO_USER/$MONGO_USER/g" /docker-entrypoint-initdb.d/init.js
sed -i "s/MONGO_PASS/$MONGO_PASS/g" /docker-entrypoint-initdb.d/init.js
sed -i "s/MONGO_DB/$MONGO_DB/g" /docker-entrypoint-initdb.d/init.js

exec python3 /usr/local/bin/docker-entrypoint.py mongod
