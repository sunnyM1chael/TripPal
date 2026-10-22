-- Execute on the physical database configured as ds_0 before restarting Java.
-- Additive migration: no existing tables or records are modified.
CREATE TABLE IF NOT EXISTS tb_city_work (
 id VARCHAR(36) PRIMARY KEY, author_id BIGINT NOT NULL, author_name VARCHAR(80) NOT NULL,
 city VARCHAR(40) NOT NULL, theme VARCHAR(8) NOT NULL, status VARCHAR(12) NOT NULL,
 source_id VARCHAR(36), content LONGTEXT NOT NULL, version INT NOT NULL DEFAULT 0,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_discovery (city, theme, status, updated_at), INDEX idx_author (author_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS tb_city_save (
 user_id BIGINT NOT NULL, work_id VARCHAR(36) NOT NULL,
 PRIMARY KEY (user_id, work_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS tb_city_trip (
 id VARCHAR(36) PRIMARY KEY, user_id BIGINT NOT NULL, work_id VARCHAR(36) NOT NULL,
 snapshot LONGTEXT NOT NULL, stops LONGTEXT NOT NULL, completed LONGTEXT NOT NULL,
 version INT NOT NULL DEFAULT 0, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uk_user_work (user_id, work_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS tb_city_feedback (
 id VARCHAR(36) PRIMARY KEY, user_id BIGINT NOT NULL, author_name VARCHAR(80) NOT NULL,
 work_id VARCHAR(36) NOT NULL, trip_id VARCHAR(36) NOT NULL, stop_index INT NOT NULL,
 stop_name VARCHAR(80) NOT NULL, verdict VARCHAR(16) NOT NULL, note VARCHAR(1000),
 actual_cost DECIMAL(10,2), created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uk_trip_stop (trip_id, stop_index), INDEX idx_work (work_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
