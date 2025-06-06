-- =====================================================
-- EDM数据库完整部署脚本
-- Step 5: 创建登录支援机关登录簿表
CREATE TABLE IF NOT EXISTS `support_organization_registry` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `registration_number` VARCHAR(15) NOT NULL COMMENT '登录番号',
  `registration_date` DATE COMMENT '登录年月日',
  `organization_name` VARCHAR(100) NOT NULL COMMENT '机构名称或姓名',
  `address` VARCHAR(80) NOT NULL COMMENT '地址',
  `prefecture` VARCHAR(50) COMMENT '都道府县（检索用）',
  `phone_number` VARCHAR(30) COMMENT '电话号码',
  `representative_name` VARCHAR(80) COMMENT '代表者姓名',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  -- 添加索引以提高查询性能
  INDEX `idx_registration_number` (`registration_number`),
  INDEX `idx_prefecture` (`prefecture`),
  INDEX `idx_organization_name` (`organization_name`),
  INDEX `idx_registration_date` (`registration_date`),
  -- 添加唯一约束防止重复数据
  UNIQUE KEY `uk_registration_number` (`registration_number`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '登录支援机关登录簿';