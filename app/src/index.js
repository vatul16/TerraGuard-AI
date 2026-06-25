const express = require("express");
const cors = require("cors");
const userRoutes = require("./routes/userRoutes");
require("dotenv").config();

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Request logging middleware
app.use((req, res, next) => {
  console.log(`${req.method} ${req.path}`);
  next();
});

// Routes
app.use("/api", userRoutes);

// Root endpoint
app.get("/", (req, res) => {
  res.json({
    name: "TerraGuard AI Demo App",
    version: "1.0.0",
    status: "running",
    endpoints: {
      health: "GET /api/health",
      users: "GET /api/users",
      userById: "GET /api/users/:id",
      createUser: "POST /api/users",
      updateUser: "PUT /api/users/:id",
      deleteUser: "DELETE /api/users/:id",
    },
  });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({
    success: false,
    message: "Route not found",
  });
});

// Error handler
app.use((err, req, res, next) => {
  console.error("Unhandled error:", err);
  res.status(500).json({
    success: false,
    message: "Internal server error",
    error: err.message,
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`🚀 Server running on port ${PORT}`);
  console.log(`   Health check: http://localhost:${PORT}/api/health`);
  console.log(`   Users: http://localhost:${PORT}/api/users`);
});
