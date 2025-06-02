#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excel数据导入MySQL脚本
用于将登录支援机关登录簿Excel文件导入到MySQL数据库
"""

import logging
import os
import sys

import pandas as pd
import pymysql

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ExcelToMySQLImporter:
    def __init__(self, db_config):
        """
        初始化数据库连接配置

        Args:
            db_config (dict): 数据库连接配置
        """
        self.db_config = db_config
        self.connection = None

    def connect_database(self):
        """连接数据库"""
        try:
            self.connection = pymysql.connect(
                host=self.db_config["host"],
                user=self.db_config["user"],
                password=self.db_config["password"],
                database=self.db_config["database"],
                charset="utf8mb4",
                autocommit=False,
            )
            logger.info("数据库连接成功")
            return True
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            return False

    def close_connection(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            logger.info("数据库连接已关闭")

    def read_excel_file(self, file_path):
        """
        读取Excel文件

        Args:
            file_path (str): Excel文件路径

        Returns:
            pandas.DataFrame: 处理后的数据
        """
        try:
            # 读取Excel文件，跳过前2行，使用第3行作为表头
            df = pd.read_excel(file_path, header=2, sheet_name=0)

            # 重命名列为英文（方便处理）
            column_mapping = {
                "１　登録番号": "registration_number",
                "２　登録年月日": "registration_date",
                "３　氏名又は名称": "organization_name",
                "住所": "address",
                "住所(検索用）": "prefecture",
                "電話番号": "phone_number",
                "５　代表者氏名": "representative_name",
            }

            df = df.rename(columns=column_mapping)

            # 删除所有列都为空的行
            df = df.dropna(how="all")

            # 处理日期列
            if "registration_date" in df.columns:
                df["registration_date"] = pd.to_datetime(
                    df["registration_date"], errors="coerce"
                ).dt.date

            # 处理字符串列，去除前后空格并处理NaN值
            string_columns = [
                "registration_number",
                "organization_name",
                "address",
                "prefecture",
                "phone_number",
                "representative_name",
            ]
            for col in string_columns:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.strip()
                    df[col] = df[col].replace("nan", None)
                    df[col] = df[col].replace("", None)

            logger.info(f"成功读取Excel文件，共{len(df)}行数据")
            return df

        except Exception as e:
            logger.error(f"读取Excel文件失败: {e}")
            return None

    def insert_data(self, df):
        """
        将数据插入数据库

        Args:
            df (pandas.DataFrame): 要插入的数据

        Returns:
            bool: 插入是否成功
        """
        if self.connection is None:
            logger.error("数据库未连接")
            return False

        try:
            cursor = self.connection.cursor()

            # 准备插入SQL语句
            insert_sql = """
            INSERT INTO support_organization_registry 
            (registration_number, registration_date, organization_name, address, prefecture, phone_number, representative_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """

            # 批量插入数据
            insert_count = 0
            error_count = 0

            for index, row in df.iterrows():
                try:
                    # 准备数据
                    data = (
                        row.get("registration_number"),
                        row.get("registration_date"),
                        row.get("organization_name"),
                        row.get("address"),
                        row.get("prefecture"),
                        row.get("phone_number"),
                        row.get("representative_name"),
                    )

                    # 跳过registration_number为空的行
                    if not data[0] or data[0] == "None":
                        continue

                    cursor.execute(insert_sql, data)
                    insert_count += 1

                    # 每1000条记录提交一次
                    if insert_count % 1000 == 0:
                        self.connection.commit()
                        logger.info(f"已插入{insert_count}条记录")

                except Exception as e:
                    error_count += 1
                    logger.warning(f"插入第{index+1}行数据失败: {e}")
                    continue

            # 提交剩余的事务
            self.connection.commit()
            cursor.close()

            logger.info(
                f"数据插入完成！成功插入{insert_count}条记录，失败{error_count}条"
            )
            return True

        except Exception as e:
            logger.error(f"数据插入失败: {e}")
            if self.connection:
                self.connection.rollback()
            return False

    def clear_table(self):
        """清空表数据（可选操作）"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM support_organization_registry")
            self.connection.commit()
            cursor.close()
            logger.info("表数据已清空")
            return True
        except Exception as e:
            logger.error(f"清空表数据失败: {e}")
            return False

    def run_import(self, excel_file_path, clear_existing_data=False):
        """
        执行完整的导入流程

        Args:
            excel_file_path (str): Excel文件路径
            clear_existing_data (bool): 是否清空现有数据
        """
        logger.info("开始导入流程...")

        # 检查文件是否存在
        if not os.path.exists(excel_file_path):
            logger.error(f"Excel文件不存在: {excel_file_path}")
            return False

        # 连接数据库
        if not self.connect_database():
            return False

        try:
            # 可选：清空现有数据
            if clear_existing_data:
                self.clear_table()

            # 读取Excel文件
            df = self.read_excel_file(excel_file_path)
            if df is None:
                return False

            # 插入数据
            success = self.insert_data(df)

            return success

        finally:
            self.close_connection()


def main():
    """主函数"""
    # 数据库连接配置
    db_config = {
        "host": "localhost",  # 数据库主机
        "user": "edm_import_user",  # 数据导入专用用户
        "password": "EdmImport2024!@#",  # 请根据实际情况修改密码
        "database": "edm",  # EDM数据库
    }

    # Excel文件路径
    excel_file_path = "list.xlsx"  # 请根据实际情况修改路径

    # 创建导入器实例
    importer = ExcelToMySQLImporter(db_config)

    # 执行导入（设置clear_existing_data=True会清空现有数据）
    success = importer.run_import(excel_file_path, clear_existing_data=False)

    if success:
        print("数据导入成功完成！")
        sys.exit(0)
    else:
        print("数据导入失败！")
        sys.exit(1)


if __name__ == "__main__":
    main()
