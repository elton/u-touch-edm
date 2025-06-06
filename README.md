# U-Touch EDM 邮件系统

这是一个自动化邮件发送系统，用于定时发送邮件和生成每日邮件发送报告。系统已配置为 Docker 容器，可以在 1Panel 管理的服务器上运行。

## 功能特点

- 定时发送邮件，每天限制发送数量并均匀分布在 24 小时内
- 每天早上 9 点（日本时间）自动发送前一天的邮件发送报告
- 报告包含详细的发送统计信息、成功/失败率和地区分布
- 与 1Panel 管理的 MySQL 数据库集成

## Docker 部署说明

### 前提条件

- 已安装 1Panel 并配置了 MySQL 数据库
- MySQL 数据库连接信息：
  - 主机：1Panel-mysql-UHRJ
  - 端口：3306
  - 数据库名：edm
  - 用户名：edm-db
  - 密码：yQQPFaTDGXBFjJWW

### 部署步骤

1. **克隆代码库到服务器**

   ```bash
   git clone <repository-url> /path/to/u-touch-edm
   cd /path/to/u-touch-edm
   ```

2. **设置 Gmail 应用密码**

   创建一个 `.env` 文件，用于存储敏感信息：

   ```bash
   echo "GMAIL_PASSWORD=your_app_password" > .env
   ```

   请将 `your_app_password` 替换为实际的 Gmail 应用密码。

3. **构建并启动 Docker 容器**

   ```bash
   docker-compose up -d
   ```

   这将构建 Docker 镜像并在后台启动容器。

4. **查看日志**

   ```bash
   # 查看容器日志
   docker logs u-touch-edm
   
   # 查看邮件发送日志
   docker exec u-touch-edm cat /app/logs/cron_send.log
   
   # 查看报告发送日志
   docker exec u-touch-edm cat /app/logs/cron_report.log
   ```

### 在 1Panel 中管理容器

1. 登录 1Panel 管理界面
2. 导航到「应用」>「容器」
3. 您应该能看到名为 `u-touch-edm` 的容器
4. 可以通过界面查看容器状态、日志和执行命令

## 手动操作

如果需要手动执行某些操作，可以使用以下命令：

```bash
# 手动发送邮件报告
docker exec u-touch-edm python send_mail.py --mode report

# 手动执行定时发送任务
docker exec u-touch-edm python send_mail.py --mode scheduled --daily-limit 50

# 进入容器内部
docker exec -it u-touch-edm bash
```

## 数据持久化

Docker 容器配置了两个持久化卷：

- `./data:/app/data`：存储邮件发送历史和其他数据文件
- `./logs:/app/logs`：存储应用程序和 cron 任务的日志

## 环境变量配置

可以通过修改 `docker-compose.yml` 文件中的 `environment` 部分来配置环境变量：

```yaml
environment:
  - ENVIRONMENT=production
  - DB_HOST=1Panel-mysql-UHRJ
  - DB_PORT=3306
  - DB_NAME=edm
  - DB_READONLY_USER=edm-db
  - DB_READONLY_PASSWORD=yQQPFaTDGXBFjJWW
  - GMAIL_USER=info@uforward.jp
  - GMAIL_PASSWORD=${GMAIL_PASSWORD}
  - GA_TRACKING_ID=UA-172341524-1
```

## 故障排除

- **容器无法启动**：检查日志 `docker logs u-touch-edm`
- **邮件发送失败**：检查 Gmail 凭据和网络连接
- **数据库连接问题**：确认 MySQL 服务器正在运行，并且连接信息正确
- **时区问题**：容器已配置为日本时区 (Asia/Tokyo)，如需更改，请修改 Dockerfile 和 docker-compose.yml