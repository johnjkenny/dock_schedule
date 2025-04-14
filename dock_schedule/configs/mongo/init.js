try {
  disableTelemetry();
  db = db.getSiblingDB("admin");
  db.runCommand({ setParameter: 1, diagnosticDataCollectionEnabled: false });

  db.createUser({
    user: "MONGO_USER",
    pwd: "MONGO_PASS",
    roles: [{ role: "readWriteAnyDatabase", db: "admin" }]
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
  db.jobs.createIndex({"expiry_time": 1}, {expireAfterSeconds: 0});

  print("User created successfully.");
  quit(0);
} catch (e) {
  print("Error creating user: " + e.message);
  quit(1);
}
