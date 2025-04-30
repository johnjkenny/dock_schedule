try {
  disableTelemetry();
  db = db.getSiblingDB("admin");
  db.runCommand({ setParameter: 1, diagnosticDataCollectionEnabled: false });

  db.createUser({
    user: "MONGO_USER",
    pwd: "MONGO_PASS",
    roles: [
      { role: "readWriteAnyDatabase", db: "admin" },
      { role: "clusterMonitor", db: "admin" },
      { role: "read", db:"local"}
    ]
  });

  db = db.getSiblingDB("MONGO_DB");
  db.createUser({
    user: "MONGO_USER",
    pwd: "MONGO_PASS",
    roles: [{ role: "readWrite", db: "MONGO_DB" }]
  });

  db.createCollection("jobs");
  db.jobs.createIndex({"name": 1});
  db.jobs.createIndex({"result": 1});
  db.jobs.createIndex({"expiryTime": 1}, {expireAfterSeconds: 0});

  db.createCollection("crons");
  db.crons.createIndex({"name": 1});
  db.crons.createIndex({"disabled": 1});

  print("User created successfully.");
  quit(0);
} catch (e) {
  print("Error creating user: " + e.message);
  quit(1);
}
