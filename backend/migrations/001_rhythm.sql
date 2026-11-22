CREATE TABLE users (
    username VARCHAR(40) PRIMARY KEY,
    display_name VARCHAR(40) NOT NULL,
    role ENUM('analyst','admin','observer') NOT NULL,
    password_hash VARCHAR(200) NOT NULL
) CHARACTER SET utf8mb4;

CREATE TABLE stations (
    code VARCHAR(12) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    name VARCHAR(60) NOT NULL,
    address VARCHAR(100) NOT NULL,
    steward VARCHAR(40) NOT NULL
) CHARACTER SET utf8mb4;

CREATE TABLE return_records (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    station_code VARCHAR(12) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    day DATE NOT NULL,
    hour TINYINT UNSIGNED NOT NULL CHECK (hour < 24),
    quantity SMALLINT UNSIGNED NOT NULL CHECK (quantity BETWEEN 1 AND 9999),
    source VARCHAR(80) NOT NULL,
    revision INT UNSIGNED NOT NULL DEFAULT 1,
    CONSTRAINT fk_return_station FOREIGN KEY (station_code) REFERENCES stations(code),
    UNIQUE (station_code, day, hour),
    INDEX (day, station_code)
) CHARACTER SET utf8mb4;

CREATE TABLE runs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(80) NOT NULL,
    creator VARCHAR(40) NOT NULL,
    status ENUM('queued','running','ready','published','failed') NOT NULL DEFAULT 'queued',
    snapshot JSON NOT NULL,
    checksum CHAR(64) NOT NULL,
    result JSON,
    failure VARCHAR(200),
    decision JSON,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_at DATETIME,
    FOREIGN KEY (creator) REFERENCES users(username),
    INDEX (status, id)
) CHARACTER SET utf8mb4;

CREATE TABLE audit_events (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    actor VARCHAR(40) NOT NULL,
    action VARCHAR(32) NOT NULL,
    entity_key VARCHAR(80) NOT NULL,
    payload JSON NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4;
