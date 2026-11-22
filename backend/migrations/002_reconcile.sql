-- 两路归还联：柜机流水与纸联进入同一张台账，按站点/日/小时对账。
-- 纸联可能缺日期（只剩小时和件数）或缺少站点，因此 station_code 与 day 允许为空。
CREATE TABLE import_batches (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    channel ENUM('cabinet','paper') NOT NULL,
    filename VARCHAR(120) NOT NULL,
    checksum CHAR(64) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    actor VARCHAR(40) NOT NULL,
    rows_total INT UNSIGNED NOT NULL,
    rows_inserted INT UNSIGNED NOT NULL,
    rows_duplicate INT UNSIGNED NOT NULL,
    rows_unresolved INT UNSIGNED NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_import_checksum (checksum),
    FOREIGN KEY (actor) REFERENCES users(username)
) CHARACTER SET utf8mb4;

-- 先建替代索引，再放开可空列并换掉旧的站点/日/小时唯一键：
-- 旧唯一键是外键 fk_return_station 的支撑索引，不能先删。
ALTER TABLE return_records
    ADD KEY idx_station_code (station_code);

ALTER TABLE return_records
    MODIFY station_code VARCHAR(12) CHARACTER SET ascii COLLATE ascii_bin NULL,
    MODIFY day DATE NULL,
    ADD COLUMN channel ENUM('manual','cabinet','paper') NOT NULL DEFAULT 'manual' FIRST,
    ADD COLUMN batch_id BIGINT NULL AFTER source,
    ADD COLUMN row_no INT UNSIGNED NULL AFTER batch_id,
    DROP INDEX station_code,
    ADD UNIQUE KEY uq_channel_slot (channel, station_code, day, hour),
    ADD KEY idx_batch (batch_id),
    ADD CONSTRAINT fk_return_batch FOREIGN KEY (batch_id) REFERENCES import_batches(id);
