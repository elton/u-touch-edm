ALTER TABLE support_organization_registry
ADD COLUMN email_sent BOOLEAN DEFAULT FALSE COMMENT '邮件是否已发送'
AFTER representative_name;