# 使用 Cron 定时发送邮件

本文档说明如何设置 cron 任务，以便每天定时发送指定数量的邮件，并将发送过程均匀分布在 24 小时内。

## 定时发送模式说明

我们在 `send_mail.py` 中添加了一个新的 `scheduled_mode` 模式，该模式可以：

1. 每次运行时发送指定数量的邮件（默认 50 封）
2. 将发送过程均匀分布在 24 小时内
3. 自动计算每封邮件之间的间隔时间

## 命令行参数

`send_mail.py` 现在支持以下命令行参数：

```bash
python send_mail.py --mode [normal|test|scheduled] --daily-limit <数量>
```

参数说明：
- `--mode`: 运行模式
  - `normal`: 正常模式，一次性发送所有邮件（默认）
  - `test`: 测试模式，发送到测试收件人
  - `scheduled`: 定时发送模式，将指定数量的邮件均匀分布在 24 小时内
- `--daily-limit`: 在 scheduled 模式下，每天发送的邮件数量（默认 50）

## 设置 Cron 任务

### 生产环境

在生产服务器上，您可以设置一个每天运行一次的 cron 任务：

1. 编辑 crontab：
   ```bash
   crontab -e
   ```

2. 添加以下内容（每天凌晨 1 点运行）：
   ```
   # 设置环境变量
   ENVIRONMENT=production
   DB_HOST=生产数据库主机
   DB_NAME=生产数据库名
   DB_READONLY_USER=生产只读用户
   DB_READONLY_PASSWORD=生产密码
   DB_APP_USER=生产应用用户
   DB_APP_PASSWORD=生产应用密码
   GMAIL_USER=您的邮箱
   GMAIL_PASSWORD=您的应用密码
   GA_TRACKING_ID=您的GA跟踪ID
   
   # 每天凌晨1点运行，发送50封邮件，均匀分布在24小时内
   0 1 * * * cd /path/to/u-touch-edm && /usr/bin/python send_mail.py --mode scheduled --daily-limit 50 >> /path/to/u-touch-edm/cron_mail.log 2>&1
   ```

### 开发环境

在开发环境中，您可以设置一个测试用的 cron 任务：

```
# 每天凌晨1点运行，发送5封测试邮件
0 1 * * * cd /path/to/u-touch-edm && /usr/bin/python send_mail.py --mode scheduled --daily-limit 5 >> /path/to/u-touch-edm/cron_mail_dev.log 2>&1
```

## 日志查看

程序运行日志将保存在以下文件中：
- 邮件发送日志：`email_sender.log`
- Cron 任务日志：`cron_mail.log`

您可以通过以下命令查看日志：
```bash
tail -f email_sender.log
tail -f cron_mail.log
```

## 注意事项

1. 确保服务器时间正确设置
2. 确保 `.env` 文件中的配置正确，或在 cron 中设置了正确的环境变量
3. 如果您需要更改每日发送的邮件数量，只需修改 cron 任务中的 `--daily-limit` 参数
4. 程序会自动计算发送间隔，确保邮件均匀分布在 24 小时内
