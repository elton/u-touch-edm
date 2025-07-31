#!/usr/bin/env python3
"""
测试数据库连接配置
验证GAI-ROU爬虫的数据库连接是否正常

作者: Claude
日期: 2025-07-31
"""

import os
from dotenv import load_dotenv
import pymysql
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_database_connection():
    """测试数据库连接"""
    
    # 加载环境变量
    load_dotenv(override=False)
    
    # 获取数据库密码
    db_password = os.getenv('DB_APP_PASSWORD')
    if not db_password:
        print("❌ 缺少必需的环境变量 DB_APP_PASSWORD")
        print("请在 .env 文件中设置 DB_APP_PASSWORD")
        return False
    
    # 数据库配置
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'user': os.getenv('DB_APP_USER', 'edm_app_user'),
        'password': db_password,
        'database': os.getenv('DB_NAME', 'edm'),
        'charset': 'utf8mb4'
    }
    
    print("=== 数据库连接测试 ===")
    print(f"主机: {db_config['host']}")
    print(f"用户: {db_config['user']}")
    print(f"数据库: {db_config['database']}")
    print()
    
    try:
        # 尝试连接数据库
        print("正在连接数据库...")
        connection = pymysql.connect(**db_config)
        
        print("✅ 数据库连接成功!")
        
        # 测试查询
        cursor = connection.cursor()
        
        # 检查support_organization_registry表是否存在
        print("\n检查表结构...")
        cursor.execute("SHOW TABLES LIKE 'support_organization_registry'")
        table_exists = cursor.fetchone()
        
        if table_exists:
            print("✅ support_organization_registry 表存在")
            
            # 获取表结构
            cursor.execute("DESCRIBE support_organization_registry")
            columns = cursor.fetchall()
            
            print(f"\n📋 表结构 ({len(columns)} 个字段):")
            for column in columns:
                field_name = column[0]
                field_type = column[1]
                is_null = "NULL" if column[2] == "YES" else "NOT NULL"
                print(f"  • {field_name}: {field_type} {is_null}")
            
            # 检查是否有website字段
            column_names = [col[0] for col in columns]
            if 'website' in column_names:
                print("✅ website 字段已存在")
            else:
                print("⚠️  website 字段不存在，需要运行数据库更新脚本")
            
            if 'support_type' in column_names:
                print("✅ support_type 字段已存在")
            else:
                print("⚠️  support_type 字段不存在，需要运行数据库更新脚本")
            
            # 获取记录数量
            cursor.execute("SELECT COUNT(*) FROM support_organization_registry")
            count = cursor.fetchone()[0]
            print(f"\n📊 当前记录数量: {count}")
            
        else:
            print("❌ support_organization_registry 表不存在")
            return False
        
        connection.close()
        print("\n🎉 数据库连接测试完成!")
        return True
        
    except pymysql.Error as e:
        print(f"❌ 数据库连接失败: {e}")
        print("\n请检查:")
        print("1. .env 文件中的数据库配置是否正确")
        print("2. 数据库服务是否正在运行")
        print("3. 用户权限是否正确")
        return False
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        return False

if __name__ == "__main__":
    success = test_database_connection()
    exit(0 if success else 1)