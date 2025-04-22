#!/bin/bash

cat /run/secrets/ca_crt > /opt/bitnami/ca.crt
cat /run/secrets/container_scraper_crt > /opt/bitnami/host.crt
cat /run/secrets/container_scraper_key > /opt/bitnami/host.key
chmod 440 /opt/bitnami/host.crt /opt/bitnami/host.key /opt/bitnami/ca.crt

#while true; do
#  sleep 5
#done

exec /opt/bitnami/cadvisor/bin/cadvisor \
  -port=8070 \
  -prometheus_endpoint="/metrics" \
  -disable_metrics=percpu,process,disk,diskIO,network,tcp,udp,referenced_memory,cpuLoad,pressure \
  -docker_only=true 

exit $?

  #-docker-tls \
  #-docker-tls-ca= \
  #-docker-tls-cert= \
  #-docker-tls-key= \
