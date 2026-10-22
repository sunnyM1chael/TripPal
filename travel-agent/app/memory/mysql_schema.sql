-- Run in the dedicated travel_agent database, never in hmdp_0/hmdp_1.
CREATE TABLE IF NOT EXISTS memory_schema_version (
    version INT NOT NULL PRIMARY KEY,
    installed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS memory_owners (
    owner VARCHAR(80) COLLATE utf8mb4_bin NOT NULL PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS conversations (
    id CHAR(36) COLLATE utf8mb4_bin NOT NULL PRIMARY KEY,
    owner VARCHAR(80) COLLATE utf8mb4_bin NOT NULL,
    title VARCHAR(160) NOT NULL,
    created DOUBLE NOT NULL,
    updated DOUBLE NOT NULL,
    lease CHAR(36) NULL,
    lease_until DOUBLE NOT NULL DEFAULT 0,
    summary MEDIUMTEXT NOT NULL,
    summarized_through BIGINT NOT NULL DEFAULT 0,
    INDEX conversations_owner(owner, updated),
    FOREIGN KEY (owner) REFERENCES memory_owners(owner)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS turns (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    conversation_id CHAR(36) COLLATE utf8mb4_bin NOT NULL,
    prompt TEXT NOT NULL,
    output MEDIUMTEXT NOT NULL,
    tools MEDIUMTEXT NOT NULL,
    mode VARCHAR(32) NOT NULL,
    stopped BOOLEAN NOT NULL,
    created DOUBLE NOT NULL,
    INDEX turns_conversation(conversation_id,id),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS request_limits (
    owner VARCHAR(80) COLLATE utf8mb4_bin NOT NULL,
    bucket BIGINT NOT NULL,
    request_count INT NOT NULL,
    PRIMARY KEY(owner,bucket)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS sqlite_imports (
    conversation_id CHAR(36) COLLATE utf8mb4_bin NOT NULL PRIMARY KEY,
    source_digest CHAR(64) NOT NULL,
    imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT IGNORE INTO memory_schema_version(version) VALUES (1);
CREATE TABLE IF NOT EXISTS itineraries (
    id CHAR(36) COLLATE utf8mb4_bin NOT NULL PRIMARY KEY,
    owner VARCHAR(80) COLLATE utf8mb4_bin NOT NULL,
    revision BIGINT NOT NULL,
    document MEDIUMTEXT NOT NULL,
    created DOUBLE NOT NULL,
    updated DOUBLE NOT NULL,
    INDEX itineraries_owner(owner, updated)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT IGNORE INTO memory_schema_version(version) VALUES (2);
CREATE TABLE IF NOT EXISTS notifications (
    id CHAR(36) COLLATE utf8mb4_bin NOT NULL PRIMARY KEY,
    owner VARCHAR(80) COLLATE utf8mb4_bin NOT NULL,
    title VARCHAR(160) NOT NULL,
    body TEXT NOT NULL,
    itinerary_id CHAR(36) COLLATE utf8mb4_bin NULL,
    is_read BOOLEAN NOT NULL DEFAULT 0,
    created DOUBLE NOT NULL,
    INDEX notifications_owner(owner, is_read, created)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT IGNORE INTO memory_schema_version(version) VALUES (3);
