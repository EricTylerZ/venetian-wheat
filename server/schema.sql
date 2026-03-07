-- Venetian Wheat — MySQL Schema
-- Run this in cPanel > phpMyAdmin > your wheat database
-- Or via SSH: mysql -u cpanelusername_wheat -p cpanelusername_wheat < schema.sql

-- ============================================================
-- ACCESS LOGS — every visitor IP, page, event
-- ============================================================
CREATE TABLE IF NOT EXISTS access_log (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    ip          VARCHAR(45)  NOT NULL,          -- IPv4 or IPv6
    page        VARCHAR(500) NOT NULL DEFAULT '',
    referrer    VARCHAR(500) NOT NULL DEFAULT '',
    user_agent  VARCHAR(500) NOT NULL DEFAULT '',
    domain      VARCHAR(100) NOT NULL DEFAULT '',
    event       VARCHAR(50)  NOT NULL DEFAULT 'pageview',
    user_hash   VARCHAR(64)  NOT NULL DEFAULT '', -- hashed session, not raw PII
    created_at  DATETIME     NOT NULL,
    INDEX idx_ip         (ip),
    INDEX idx_domain     (domain),
    INDEX idx_created_at (created_at),
    INDEX idx_event      (event)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- BLOCKED IPs — manual or auto-block list
-- ============================================================
CREATE TABLE IF NOT EXISTS blocked_ips (
    id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    ip         VARCHAR(45)  NOT NULL UNIQUE,
    reason     VARCHAR(255) NOT NULL DEFAULT '',
    blocked_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME     NULL,                -- NULL = permanent
    INDEX idx_ip (ip)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- SHARED DATA — key/value store shared across domains/subdomains
-- Use this for feature flags, config, shared state
-- ============================================================
CREATE TABLE IF NOT EXISTS shared_data (
    id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `key`      VARCHAR(255) NOT NULL,
    `value`    MEDIUMTEXT   NOT NULL DEFAULT '',
    domain     VARCHAR(100) NOT NULL DEFAULT '',  -- '' = global, 'acme.com' = domain-scoped
    updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_key_domain (`key`, domain)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- WHEAT PROJECTS — mirrors your git branches/clients.json
-- ============================================================
CREATE TABLE IF NOT EXISTS wheat_projects (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    client_id   VARCHAR(100) NOT NULL UNIQUE,
    name        VARCHAR(255) NOT NULL DEFAULT '',
    branch      VARCHAR(255) NOT NULL DEFAULT '',
    last_commit VARCHAR(40)  NOT NULL DEFAULT '',
    status      VARCHAR(50)  NOT NULL DEFAULT 'active',
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
