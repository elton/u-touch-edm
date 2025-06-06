FROM python:3.13-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用程序代码
COPY *.py /app/
COPY templates/ /app/templates/

# 复制邮件附件
COPY attachment.pdf /app/

# 创建日志和数据目录
RUN mkdir -p /app/logs /app/data

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    DB_HOST=1Panel-mysql-UHRJ \
    DB_PORT=3306 \
    DB_NAME=edm \
    DB_READONLY_USER=edm-db \
    DB_READONLY_PASSWORD=yQQPFaTDGXBFjJWW \
    DB_APP_USER=edm-db \
    DB_APP_PASSWORD=yQQPFaTDGXBFjJWW

# 设置时区为日本时区
RUN apt-get update && apt-get install -y tzdata && \
    ln -fs /usr/share/zoneinfo/Asia/Tokyo /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 复制启动脚本
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# 设置容器启动命令
ENTRYPOINT ["/app/docker-entrypoint.sh"]
