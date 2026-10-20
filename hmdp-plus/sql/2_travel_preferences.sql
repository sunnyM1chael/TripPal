-- Execute before restarting Java with the new ShardingSphere rule.
-- Additive only: no existing table or user data is changed.
USE hmdp_0;
CREATE TABLE IF NOT EXISTS tb_travel_preference_0 (
  user_id BIGINT NOT NULL PRIMARY KEY,
  default_city VARCHAR(40) NULL,
  budget_per_person DECIMAL(12,2) NULL,
  cuisines_json VARCHAR(5000) NOT NULL DEFAULT '[]',
  dietary_notes_json VARCHAR(5000) NOT NULL DEFAULT '[]',
  transport VARCHAR(16) NULL,
  revision BIGINT NOT NULL DEFAULT 0,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS tb_travel_preference_1 LIKE tb_travel_preference_0;

USE hmdp_1;
CREATE TABLE IF NOT EXISTS tb_travel_preference_0 (
  user_id BIGINT NOT NULL PRIMARY KEY,
  default_city VARCHAR(40) NULL,
  budget_per_person DECIMAL(12,2) NULL,
  cuisines_json VARCHAR(5000) NOT NULL DEFAULT '[]',
  dietary_notes_json VARCHAR(5000) NOT NULL DEFAULT '[]',
  transport VARCHAR(16) NULL,
  revision BIGINT NOT NULL DEFAULT 0,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS tb_travel_preference_1 LIKE tb_travel_preference_0;
