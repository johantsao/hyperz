-- SQLite
CREATE TABLE IF NOT EXISTS system_addresses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT UNIQUE,
    monitor_ratio REAL DEFAULT 1.0
);
