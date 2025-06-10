ALTER TABLE support_organization_registry
ADD COLUMN sent_at TIMESTAMP NULL DEFAULT NULL COMMENT '邮件发送时间'
AFTER representative_name;