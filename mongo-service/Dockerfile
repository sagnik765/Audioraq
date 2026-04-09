FROM mongo:7

EXPOSE 27017

CMD ["mongod", "--ipv6", "--bind_ip", "::,0.0.0.0", "--setParameter", "diagnosticDataCollectionEnabled=false"]
