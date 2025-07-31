# GAI-ROU.COM 支援機関爬虫工具

本工具用于从 https://www.gai-rou.com/shien_list/ 爬取日本登录支援机关信息。

## 功能特性

- 📊 **全站数据爬取**: 动态跟随"下一页"链接，自动爬取所有页面的支援机关信息
- 🏢 **详细信息提取**: 提取机构名称、地址、联系方式、支援类型等完整信息  
- 🗄️ **数据库集成**: 直接保存到MySQL数据库中的 `support_organization_registry` 表
- 🎯 **支援类型识别**: 自动判断机构是否支持特定技能、技能实习生或两者
- 🔄 **智能去重**: 通过机构名称标准化比较，防止重复插入相同机构
- 🎨 **彩色日志**: 使用颜色和emoji提供清晰的视觉反馈
- 📝 **详细日志**: 完整的爬取过程记录和错误处理

## 数据库更新

首先需要更新数据库架构，添加支援类型和网站字段：

```bash
# 应用数据库更新
mysql -h 1Panel-mysql-UHRJ -u edm -p edm-db < sql/update-add-support-type.sql
mysql -h 1Panel-mysql-UHRJ -u edm -p edm-db < sql/update-add-website-field.sql
```

## 使用方法

### 1. 测试爬虫功能

```bash
# 测试数据库连接
python test_db_connection.py

# 测试单个页面提取
python test_scraper.py

# 测试机构名称标准化功能
python test_name_normalization_only.py

# 测试彩色日志输出
python test_colorful_output.py

# 测试动态分页功能
python test_pagination.py
```

### 2. 演示模式（推荐新手）

```bash
# 安全演示模式，处理前2页，每页2个机构
python run_scraper_demo.py
```

### 3. 完整爬取

```bash
# 爬取所有支援机关数据（动态分页，谨慎使用）
python gai_rou_scraper.py
```

**注意**: 完整爬取将使用动态分页，自动跟随每页的"下一页"链接直到没有更多页面为止。这可能需要较长时间完成。

## 配置要求

### 环境变量
项目的 `.env` 文件已包含所需的配置：

```env
# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_NAME=edm
# 应用用户 - 用于爬虫更新数据
DB_APP_USER=edm_app_user
DB_APP_PASSWORD=EdmApp2024!@#

# 环境设置
ENVIRONMENT=development
TZ=Asia/Tokyo
```

GAI-ROU爬虫使用 `DB_APP_USER` 账户进行数据库写入操作。

### Python依赖
```bash
pip install -r requirements.txt
# 或单独安装
pip install requests beautifulsoup4 pymysql python-dotenv colorama
```

## 数据结构

爬取的数据将保存到 `support_organization_registry` 表，包含以下字段：

- `registration_number`: 登録番号
- `registration_date`: 登録年月日  
- `organization_name`: 机构名称
- `address`: 地址
- `prefecture`: 都道府县（自动提取）
- `phone_number`: 电话号码
- `representative_name`: 代表者姓名
- `support_type`: 支援类型
  - `tokutei_ginou`: 仅支持特定技能
  - `ginou_jisshuusei`: 仅支持技能实习生
  - `both`: 两者都支持（默认）
- `email`: 邮箱地址
- `website`: 公司网站地址
- `created_at`: 创建时间
- `updated_at`: 更新时间

## 去重机制

### 智能机构名称比较
系统采用高级的机构名称标准化算法：

- **前后缀清理**: 自动移除 "株式会社"、"協同組合"、"Inc"、"Corp" 等常见公司后缀
- **大小写标准化**: 统一转换为小写进行比较
- **特殊字符清理**: 移除空格、标点符号等非关键字符
- **中日英文支持**: 正确处理中文、日文、英文机构名称

### 重复检查流程
1. 首先通过标准化后的机构名称进行比较
2. 其次通过登録番号进行检查（如果存在）
3. 发现重复时自动跳过，避免数据冗余

## 注意事项

⚠️ **重要提醒**:

1. **合规使用**: 请遵守网站的robots.txt和使用条款
2. **频率控制**: 脚本内置了延迟机制，避免对服务器造成压力
3. **数据验证**: 建议先用演示模式测试，确认数据质量后再进行完整爬取
4. **备份数据**: 大量爬取前请备份现有数据库数据
5. **重复运行安全**: 可以安全地多次运行爬虫，系统会自动跳过已存在的机构

## 日志文件

爬取过程日志保存在：
- `logs/gai_rou_scraper.log`: 详细爬取日志

## 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查 `.env` 文件配置
   - 确认数据库服务运行状态

2. **网站访问失败**  
   - 检查网络连接
   - 确认目标网站可访问

3. **数据提取不完整**
   - 网站结构可能发生变化
   - 需要更新解析规则

### 调试模式

启用详细日志输出：
```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

## 开发信息

- **作者**: Claude
- **创建日期**: 2025-07-31
- **Python版本**: 3.13+
- **依赖**: requests, beautifulsoup4, pymysql, python-dotenv