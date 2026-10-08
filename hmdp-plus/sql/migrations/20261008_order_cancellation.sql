-- Run once before deploying the new consumer. Both databases need both physical tables.

USE hmdp_0;
CREATE TABLE IF NOT EXISTS tb_voucher_order_cancellation_0 (
    order_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    voucher_id BIGINT NOT NULL,
    trace_id BIGINT NOT NULL,
    state VARCHAR(16) NOT NULL,
    reason VARCHAR(255) NOT NULL,
    message_json LONGTEXT NOT NULL,
    update_time DATETIME NOT NULL,
    PRIMARY KEY (order_id),
    KEY idx_recovery (state, update_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS tb_voucher_order_cancellation_1 (
    order_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    voucher_id BIGINT NOT NULL,
    trace_id BIGINT NOT NULL,
    state VARCHAR(16) NOT NULL,
    reason VARCHAR(255) NOT NULL,
    message_json LONGTEXT NOT NULL,
    update_time DATETIME NOT NULL,
    PRIMARY KEY (order_id),
    KEY idx_recovery (state, update_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

USE hmdp_1;
CREATE TABLE IF NOT EXISTS tb_voucher_order_cancellation_0 (
    order_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    voucher_id BIGINT NOT NULL,
    trace_id BIGINT NOT NULL,
    state VARCHAR(16) NOT NULL,
    reason VARCHAR(255) NOT NULL,
    message_json LONGTEXT NOT NULL,
    update_time DATETIME NOT NULL,
    PRIMARY KEY (order_id),
    KEY idx_recovery (state, update_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS tb_voucher_order_cancellation_1 (
    order_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    voucher_id BIGINT NOT NULL,
    trace_id BIGINT NOT NULL,
    state VARCHAR(16) NOT NULL,
    reason VARCHAR(255) NOT NULL,
    message_json LONGTEXT NOT NULL,
    update_time DATETIME NOT NULL,
    PRIMARY KEY (order_id),
    KEY idx_recovery (state, update_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
