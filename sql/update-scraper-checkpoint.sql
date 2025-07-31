-- 创建爬虫检查点表，用于记录抓取进度
CREATE TABLE IF NOT EXISTS scraper_checkpoint (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64) UNIQUE NOT NULL COMMENT '抓取会话ID',
    last_processed_id INT NOT NULL COMMENT '最后处理的记录ID',
    total_records INT NOT NULL COMMENT '总记录数',
    processed_records INT NOT NULL DEFAULT 0 COMMENT '已处理记录数',
    success_count INT NOT NULL DEFAULT 0 COMMENT '成功抓取数',
    failed_count INT NOT NULL DEFAULT 0 COMMENT '失败数',
    status ENUM('running', 'paused', 'completed', 'failed') DEFAULT 'running' COMMENT '状态',
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '开始时间',
    last_update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
    end_time TIMESTAMP NULL COMMENT '结束时间',
    notes TEXT COMMENT '备注信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='爬虫抓取进度检查点表';

-- 创建索引
CREATE INDEX idx_session_id ON scraper_checkpoint(session_id);
CREATE INDEX idx_status ON scraper_checkpoint(status);
CREATE INDEX idx_last_update_time ON scraper_checkpoint(last_update_time);

-- 插入示例数据（可选）
-- INSERT INTO scraper_checkpoint (session_id, last_processed_id, total_records, status, notes) 
-- VALUES ('test-session-001', 0, 1000, 'running', '测试会话');