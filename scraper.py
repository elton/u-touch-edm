import logging
import os
import re
import time
from typing import List, Optional, Tuple
from urllib.parse import quote, urljoin

import pymysql
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 加载环境变量，设置override=False，这样系统环境变量会优先于.env文件中的变量
load_dotenv(override=False)

# 判断当前环境
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
logger.info(f"当前运行环境: {ENVIRONMENT}")

# 如果是生产环境，输出一个提示
if ENVIRONMENT == 'production':
    logger.info("正在使用生产环境配置")
else:
    logger.info("正在使用开发环境配置")


class SupportOrganizationScraper:
    def __init__(self):
        # 数据库连接配置 - 从环境变量获取
        self.db_config = {
            "host": os.getenv('DB_HOST', 'localhost'),
            "user": os.getenv('DB_APP_USER', 'edm_app_user'),
            "password": os.getenv('DB_APP_PASSWORD', 'EdmApp2024!@#'),
            "database": os.getenv('DB_NAME', 'edm'),
            "charset": "utf8mb4",
        }

        # 网站基础URL
        self.base_url = "https://www.gai-rou.com"
        self.search_url = "https://www.gai-rou.com/?s={}"

        # 请求头，模拟浏览器
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        # 创建会话
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def get_db_connection(self):
        """获取数据库连接"""
        try:
            connection = pymysql.connect(**self.db_config)
            logger.info(f"成功连接到数据库 (环境: {ENVIRONMENT})")
            return connection
        except pymysql.Error as err:
            logger.error(f"数据库连接错误: {err}")
            return None

    def fetch_organizations(self) -> List[Tuple]:
        """从数据库获取东京都和神奈川县的机构信息"""
        connection = self.get_db_connection()
        if not connection:
            return []

        try:
            cursor = connection.cursor()
            query = """
            SELECT id, registration_number, organization_name, email 
            FROM support_organization_registry 
            WHERE prefecture='東京都' OR prefecture='神奈川県'
            ORDER BY id
            """
            cursor.execute(query)
            results = cursor.fetchall()
            logger.info(f"从数据库获取到 {len(results)} 条记录")
            return results
        except pymysql.Error as err:
            logger.error(f"查询数据库错误: {err}")
            return []
        finally:
            if connection:
                cursor.close()
                connection.close()

    def search_organization(self, registration_number: str) -> Optional[str]:
        """在网站上搜索机构并获取详情页面URL"""
        try:
            # 构建搜索URL
            search_url = self.search_url.format(quote(registration_number))
            logger.info(f"搜索URL: {search_url}")

            # 请求搜索页面
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()

            # 解析HTML
            soup = BeautifulSoup(response.content, "html.parser")

            # 使用正则表达式查找详情页面链接
            # 寻找类似 https://www.gai-rou.com/shien/数字/ 的链接
            detail_pattern = re.compile(r"https://www\.gai-rou\.com/shien/(\d+)/?")

            # 在所有链接中搜索
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if detail_pattern.match(href):
                    logger.info(f"找到详情页面链接: {href}")
                    return href

            # 如果没有找到完整URL，尝试查找相对路径
            relative_pattern = re.compile(r"/shien/(\d+)/?")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                match = relative_pattern.match(href)
                if match:
                    full_url = urljoin(self.base_url, href)
                    logger.info(f"找到详情页面链接 (相对路径): {full_url}")
                    return full_url

            logger.warning(f"未找到 {registration_number} 的详情页面链接")
            return None

        except requests.RequestException as e:
            logger.error(f"请求搜索页面失败 {registration_number}: {e}")
            return None
        except Exception as e:
            logger.error(f"搜索过程出错 {registration_number}: {e}")
            return None

    def extract_email(self, detail_url: str) -> Optional[str]:
        """从详情页面提取email地址"""
        try:
            logger.info(f"获取详情页面: {detail_url}")
            response = self.session.get(detail_url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # 查找包含"メールアドレス"的元素
            email_elements = soup.find_all(text=re.compile(r"メールアドレス"))

            for element in email_elements:
                # 获取父元素和兄弟元素
                parent = element.parent
                if parent:
                    # 在父元素及其兄弟元素中查找email
                    for sibling in parent.find_next_siblings():
                        email = self.find_email_in_element(sibling)
                        if email:
                            return email

                    # 在父元素的文本中查找email
                    email = self.find_email_in_text(parent.get_text())
                    if email:
                        return email

            # 如果上述方法没找到，在整个页面中搜索email模式
            page_text = soup.get_text()
            email = self.find_email_in_text(page_text)
            if email:
                logger.info(f"在页面文本中找到email: {email}")
                return email

            logger.warning(f"未在详情页面找到email地址: {detail_url}")
            return None

        except requests.RequestException as e:
            logger.error(f"请求详情页面失败 {detail_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"提取email过程出错 {detail_url}: {e}")
            return None

    def find_email_in_element(self, element) -> Optional[str]:
        """在HTML元素中查找email地址"""
        if element:
            text = element.get_text()
            return self.find_email_in_text(text)
        return None

    def find_email_in_text(self, text: str) -> Optional[str]:
        """在文本中查找email地址"""
        # email正则表达式
        email_pattern = re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        )
        matches = email_pattern.findall(text)

        if matches:
            # 返回第一个找到的email地址
            email = matches[0]
            if self.validate_email(email):
                return email
        return None

    def validate_email(self, email: str) -> bool:
        """验证email地址的合法性"""
        pattern = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$")
        return bool(pattern.match(email))

    def update_email_in_db(self, org_id: int, email: str) -> bool:
        """更新数据库中的email地址"""
        connection = self.get_db_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()
            query = "UPDATE support_organization_registry SET email = %s WHERE id = %s"
            cursor.execute(query, (email, org_id))
            connection.commit()

            if cursor.rowcount > 0:
                logger.info(f"成功更新机构ID {org_id} 的email: {email}")
                return True
            else:
                logger.warning(f"更新机构ID {org_id} 的email失败：未找到记录")
                return False

        except pymysql.Error as err:
            logger.error(f"更新数据库错误: {err}")
            connection.rollback()
            return False
        finally:
            if connection:
                cursor.close()
                connection.close()

    def process_organizations(self):
        """处理所有机构的主流程"""
        # 获取机构列表
        organizations = self.fetch_organizations()
        if not organizations:
            logger.error("未获取到任何机构数据")
            return

        success_count = 0
        failed_count = 0

        for (
            org_id,
            registration_number,
            organization_name,
            current_email,
        ) in organizations:
            logger.info(
                f"处理机构: ID={org_id}, 登録番号={registration_number}, 名称={organization_name}"
            )

            # 如果已经有email地址，跳过
            if current_email:
                logger.info(
                    f"机构 {organization_name} 已有email地址: {current_email}，跳过"
                )
                continue

            try:
                # 搜索机构详情页面
                detail_url = self.search_organization(registration_number)
                if not detail_url:
                    logger.warning(f"未找到机构 {organization_name} 的详情页面")
                    failed_count += 1
                    continue

                # 提取email地址
                email = self.extract_email(detail_url)
                if not email:
                    logger.warning(f"未找到机构 {organization_name} 的email地址")
                    failed_count += 1
                    continue

                # 更新数据库
                if self.update_email_in_db(org_id, email):
                    success_count += 1
                    logger.info(f"成功处理机构 {organization_name}: {email}")
                else:
                    failed_count += 1
                    logger.error(f"更新机构 {organization_name} 的email失败")

                # 添加延迟避免过于频繁的请求
                time.sleep(2)

            except Exception as e:
                logger.error(f"处理机构 {organization_name} 时出错: {e}")
                failed_count += 1
                continue

        logger.info(f"处理完成！成功: {success_count}, 失败: {failed_count}")


def main():
    """主函数"""
    print("=" * 50)
    print(f"           爬虫程序 (环境: {ENVIRONMENT})")
    print("=" * 50)
    
    scraper = SupportOrganizationScraper()

    # 显示当前数据库配置
    print("当前数据库配置:")
    print(f"- 主机: {os.getenv('DB_HOST', 'localhost')}")
    print(f"- 数据库: {os.getenv('DB_NAME', 'edm')}")
    print(f"- 用户: {os.getenv('DB_APP_USER', 'edm_app_user')}")
    
    # 确认是否继续
    response = input("是否开始处理? (y/N): ").strip().lower()
    if response != "y":
        print("操作取消")
        return

    # 开始处理
    scraper.process_organizations()


if __name__ == "__main__":
    main()
