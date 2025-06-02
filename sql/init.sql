-- =====================================================
-- EDM数据库完整部署脚本
-- 执行顺序：用户创建 -> 数据库创建 -> 表创建
-- =====================================================
-- Step 1: 创建EDM数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS `edm` DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_unicode_ci;
-- Step 2: 创建用户账户
-- 数据导入专用用户（推荐给Python脚本使用）
CREATE USER IF NOT EXISTS 'edm_import_user' @'localhost' IDENTIFIED BY 'EdmImport2024!@#';
-- 应用程序完整权限用户
CREATE USER IF NOT EXISTS 'edm_app_user' @'localhost' IDENTIFIED BY 'EdmApp2024!@#';
-- 只读用户
CREATE USER IF NOT EXISTS 'edm_readonly_user' @'localhost' IDENTIFIED BY 'EdmRead2024!@#';
-- Step 3: 分配权限
-- 给数据导入用户分配最小权限
GRANT SELECT,
  INSERT,
  DELETE ON edm.support_organization_registry TO 'edm_import_user' @'localhost';
-- 给应用用户分配完整权限
GRANT SELECT,
  INSERT,
  UPDATE,
  DELETE,
  CREATE,
  DROP,
  ALTER,
  INDEX ON edm.* TO 'edm_app_user' @'localhost';
-- 给只读用户分配查询权限
GRANT SELECT ON edm.* TO 'edm_readonly_user' @'localhost';
-- Step 4: 使用EDM数据库
USE edm;
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
-- Step 6: 刷新权限
FLUSH PRIVILEGES;
-- =====================================================
-- 验证部署结果
-- =====================================================
-- 验证数据库创建
SHOW DATABASES LIKE 'edm';
-- 验证用户创建  
SELECT User,
  Host
FROM mysql.user
WHERE User LIKE 'edm_%';
-- 验证表创建
SHOW TABLES
FROM edm;
-- 验证表结构
DESCRIBE edm.support_organization_registry;
-- 验证索引
SHOW INDEX
FROM edm.support_organization_registry;
-- 验证用户权限
SHOW GRANTS FOR 'edm_import_user' @'localhost';
-- =====================================================
-- 部署完成提示
-- =====================================================
SELECT 'EDM数据库部署完成！' as message,
  'Python脚本可以使用 edm_import_user 连接数据库' as note,
  'host: localhost, database: edm' as connection_info;