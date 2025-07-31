-- Add support type field to support_organization_registry table
-- This field indicates the type of support services offered by the organization

ALTER TABLE `support_organization_registry` 
ADD COLUMN `support_type` ENUM('tokutei_ginou', 'ginou_jisshuusei', 'both') 
DEFAULT NULL 
COMMENT '支援类型: tokutei_ginou=特定技能, ginou_jisshuusei=技能实习生, both=两者都支持'
AFTER `representative_name`;

-- Add index for better query performance
ALTER TABLE `support_organization_registry` 
ADD INDEX `idx_support_type` (`support_type`);