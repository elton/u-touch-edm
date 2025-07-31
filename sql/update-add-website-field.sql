-- Add website field to support_organization_registry table
-- This field stores the company's website URL

ALTER TABLE `support_organization_registry` 
ADD COLUMN `website` VARCHAR(255) 
DEFAULT NULL 
COMMENT '公司网站地址'
AFTER `email`;

-- Add index for better query performance
ALTER TABLE `support_organization_registry` 
ADD INDEX `idx_website` (`website`);