#!/bin/bash
set -e

# 设置日志文件
EMAIL_LOG_FILE="/app/email_sender.log"
touch $EMAIL_LOG_FILE

# 创建 cron 任务
echo "设置 cron 任务..."
cat > /etc/cron.d/edm-cron << EOF
# 环境变量设置
ENVIRONMENT=${ENVIRONMENT}
DB_HOST=${DB_HOST}
DB_PORT=${DB_PORT}
DB_NAME=${DB_NAME}
DB_USER=${DB_USER:-${DB_APP_USER}}
DB_PASSWORD=${DB_PASSWORD:-${DB_APP_PASSWORD}}
DB_READONLY_USER=${DB_READONLY_USER}
DB_READONLY_PASSWORD=${DB_READONLY_PASSWORD}
DB_APP_USER=${DB_APP_USER}
DB_APP_PASSWORD=${DB_APP_PASSWORD}
GMAIL_USER=${GMAIL_USER}
GMAIL_PASSWORD=${GMAIL_PASSWORD}
GA_TRACKING_ID=${GA_TRACKING_ID}

# 每天凌晨1点运行定时发送任务，发送50封邮件，均匀分布在24小时内
0 1 * * * root cd /app && /usr/local/bin/python send_mail.py --mode scheduled --daily-limit 50 >> /app/logs/cron_send.log 2>&1

# 每天早上日本时间9点发送前一天的邮件发送简报
0 9 * * * root cd /app && /usr/local/bin/python send_mail.py --mode report >> /app/logs/cron_report.log 2>&1
EOF

# 设置 cron 任务权限
chmod 0644 /etc/cron.d/edm-cron

# 启动 cron 服务
echo "启动 cron 服务..."
cron

# 如果有命令行参数，则执行它们
if [ $# -gt 0 ]; then
    echo "执行命令: $@"
    exec "$@"
else
    # 默认行为：输出日志并保持容器运行
    echo "容器已启动，cron 任务已设置"
    echo "查看邮件发送日志: tail -f /app/email_sender.log"
    
    # 保持容器运行并实时显示邮件发送日志
    tail -f $EMAIL_LOG_FILE
fi
