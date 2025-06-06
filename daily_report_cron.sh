#!/bin/bash
# 每天早上日本时间9点发送前一天的邮件发送简报
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

# 记录开始时间
echo "===== $(date '+%Y-%m-%d %H:%M:%S') 开始发送每日邮件报告 ====="

# 运行报告发送程序
python send_mail.py --mode report

# 记录结束时间
echo "===== $(date '+%Y-%m-%d %H:%M:%S') 邮件报告发送完成 ====="
