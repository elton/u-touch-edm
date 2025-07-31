# 断点续抓邮件地址功能使用指南

## 🚀 新功能特性

- ✅ **断点续抓**: 支持在任意时刻中断抓取，下次运行时从中断位置继续
- 📊 **进度追踪**: 实时保存抓取进度到数据库，包括成功/失败统计
- 🔄 **会话管理**: 每次抓取创建独立会话ID，便于管理和恢复
- ⚡ **智能恢复**: 自动识别未完成的抓取任务并提供恢复选项
- 🎯 **安全中断**: 使用 `Ctrl+C` 安全中断，自动保存当前进度

## 📋 数据库准备

首先需要运行数据库迁移脚本创建检查点表：

```bash
# 连接到MySQL数据库并执行迁移脚本
mysql -h your_host -u your_user -p your_database < sql/update-scraper-checkpoint.sql
```

## 🛠️ 使用方法

### 1. 启动新的抓取任务

```bash
# 基础用法
python scraper_with_checkpoint.py

# 禁用彩色输出（适合日志记录）
python scraper_with_checkpoint.py --no-color
```

### 2. 查看所有抓取会话

```bash
python scraper_with_checkpoint.py --list-sessions
```

输出示例：
```
📋 最近的抓取会话:
会话ID                          状态       进度            成功/失败     开始时间            
------------------------------------------------------------------------------------------
scraper_20231201_143052_a7b8c9d  paused     150/1000       120/30       2023-12-01 14:30:52
scraper_20231201_120000_f1e2d3c  completed  500/500        480/20       2023-12-01 12:00:00
```

### 3. 恢复抓取任务

```bash
# 恢复指定会话ID的抓取
python scraper_with_checkpoint.py --resume scraper_20231201_143052_a7b8c9d
```

### 4. 安全中断抓取

在抓取过程中，使用 `Ctrl+C` 可以安全中断：
- 自动保存当前进度
- 更新会话状态为"已暂停"
- 显示恢复命令

## 📊 会话状态说明

| 状态 | 描述 | 颜色标识 |
|------|------|----------|
| `running` | 正在运行中 | 🟢 绿色 |
| `paused` | 已暂停（可恢复） | 🟡 黄色 |
| `completed` | 已完成 | 🔵 蓝色 |
| `failed` | 运行失败 | 🔴 红色 |

## 🔧 技术特性

### 进度保存机制
- 每处理10条记录自动保存一次进度
- 记录最后处理的记录ID
- 统计成功/失败数量和成功率

### 恢复机制
- 从上次中断的记录ID+1开始继续
- 保持累计统计数据
- 自动跳过已处理的记录

### 会话管理
- 每个会话有唯一ID：`scraper_YYYYMMDD_HHMMSS_随机字符`
- 支持多个并发会话（不同时间段）
- 自动清理过期会话数据

## 📈 实际使用场景

### 场景1: 大批量抓取
```bash
# 启动大批量抓取
python scraper_with_checkpoint.py

# 运行一段时间后需要停止维护服务器
# 使用 Ctrl+C 安全中断

# 维护完成后恢复抓取
python scraper_with_checkpoint.py --resume <会话ID>
```

### 场景2: 分批处理
```bash
# 每天处理一批数据
python scraper_with_checkpoint.py

# 第二天继续处理
python scraper_with_checkpoint.py --list-sessions  # 查看昨天的会话
python scraper_with_checkpoint.py --resume <昨天的会话ID>
```

### 场景3: 错误恢复
```bash
# 如果程序因为网络问题中断
python scraper_with_checkpoint.py --list-sessions

# 找到最后一个paused状态的会话并恢复
python scraper_with_checkpoint.py --resume <会话ID>
```

## 🚨 注意事项

1. **数据库连接**: 确保数据库连接稳定，进度保存依赖数据库
2. **会话ID管理**: 保存重要的会话ID，便于后续恢复
3. **并发限制**: 避免同时运行多个相同类型的抓取任务
4. **磁盘空间**: 检查点数据会占用一定磁盘空间，定期清理完成的会话
5. **环境变量**: 确保所有必需的环境变量正确配置

## 📝 日志和监控

### 彩色日志输出
- ✅ 绿色：成功操作
- ❌ 红色：错误信息  
- ⚠️ 黄色：警告信息
- ℹ️ 青色：一般信息
- 🔄 紫色：处理中状态
- 🔍 黄色：发现/找到信息

### 进度报告
- 每10条记录显示一次进度
- 显示百分比、成功率等统计信息
- 最终显示完整的处理结果

## 🔄 数据库表结构

```sql
CREATE TABLE scraper_checkpoint (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64) UNIQUE NOT NULL,
    last_processed_id INT NOT NULL,
    total_records INT NOT NULL,
    processed_records INT DEFAULT 0,
    success_count INT DEFAULT 0,
    failed_count INT DEFAULT 0,
    status ENUM('running', 'paused', 'completed', 'failed'),
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    end_time TIMESTAMP NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

## 💡 最佳实践

1. **定期备份**: 定期备份`scraper_checkpoint`表数据
2. **监控日志**: 关注错误日志，及时处理网络或权限问题  
3. **资源管理**: 合理设置抓取间隔，避免对目标网站造成压力
4. **数据验证**: 定期验证抓取到的邮件地址质量
5. **清理维护**: 定期清理已完成的旧会话数据

---

**版本**: v1.0  
**更新日期**: 2024-01-31  
**兼容性**: Python 3.7+, MySQL 5.7+