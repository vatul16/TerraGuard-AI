const { Pool } = require("pg");
require("dotenv").config();

const pool = new Pool({
  host: process.env.DB_HOST || "localhost",
  port: parseInt(process.env.DB_PORT) || 5432,
  database: process.env.DB_NAME || "terraguard",
  user: process.env.DB_USER || "terraguard_admin",
  password: process.env.DB_PASSWORD,
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

// Test connection on startup
pool.connect((err, client, release) => {
  if (err) {
    console.error("❌ Database connection failed:", err.message);
    console.error("   Check DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD");
    return;
  }
  console.log("✅ PostgreSQL connected successfully");
  release();
});

module.exports = pool;
