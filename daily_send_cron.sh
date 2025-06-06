#!/bin/bash
# 每天凌晨1点运行定时发送任务，发送50封邮件，均匀分布在24小时内
# 此脚本应该由cron任务调用

# 设置工作目录
cd "$(dirname "$0")"

# 设置环境变量
export ENVIRONMENT="${ENVIRONMENT:-production}"
export DB_HOST="${DB_HOST:-1Panel-mysql-UHRJ}"
export DB_PORT="${DB_PORT:-3306}"
export DB_NAME="${DB_NAME:-edm}"
export DB_READONLY_USER="${DB_READONLY_USER:-edm-db}"
export DB_READONLY_PASSWORD="${DB_READONLY_PASSWORD:-yQQPFaTDGXBFjJWW}"
export DB_APP_USER="${DB_APP_USER:-edm-db}"
export DB_APP_PASSWORD="${DB_APP_PASSWORD:-yQQPFaTDGXBFjJWW}"
export GMAIL_USER="${GMAIL_USER:-info@uforward.jp}"
export GMAIL_PASSWORD="${GMAIL_PASSWORD:-your_app_password}"
export GA_TRACKING_ID="${GA_TRACKING_ID:-UA-172341524-1}"

# 设置每日发送邮件数量
DAILY_LIMIT=50

# 记录开始时间
echo "===== $(date '+%Y-%m-%d %H:%M:%S') 开始定时发送邮件任务 ====="
echo "每日发送限制: $DAILY_LIMIT 封邮件"

# 运行定时发送程序
python send_mail.py --mode scheduled --daily-limit $DAILY_LIMIT

# 记录结束时间
echo "===== $(date '+%Y-%m-%d %H:%M:%S') 定时发送邮件任务完成 ====="
