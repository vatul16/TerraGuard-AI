const pool = require("../config/database");

class User {
  static async findAll() {
    const result = await pool.query(
      "SELECT id, name, email, created_at FROM users ORDER BY created_at DESC",
    );
    return result.rows;
  }

  static async findById(id) {
    const result = await pool.query(
      "SELECT id, name, email, created_at FROM users WHERE id = $1",
      [id],
    );
    return result.rows[0];
  }

  static async create(name, email) {
    const result = await pool.query(
      "INSERT INTO users (name, email) VALUES ($1, $2) RETURNING id, name, email, created_at",
      [name, email],
    );
    return result.rows[0];
  }

  static async update(id, name, email) {
    const result = await pool.query(
      "UPDATE users SET name = $1, email = $2, updated_at = CURRENT_TIMESTAMP WHERE id = $3 RETURNING id, name, email, created_at",
      [name, email, id],
    );
    return result.rows[0];
  }

  static async delete(id) {
    await pool.query("DELETE FROM users WHERE id = $1", [id]);
    return true;
  }
}

module.exports = User;
