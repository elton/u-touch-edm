import logging
import os
import random
import re
import time
from typing import List, Optional, Tuple
from urllib.parse import quote, urljoin, urlparse

import pymysql
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from colorama import Fore, Back, Style, init

# 初始化colorama，支持Windows系统
init(autoreset=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 彩色日志工具类
class ColorLogger:
    @staticmethod
    def success(message: str):
        """成功日志 - 绿色 + ✅"""
        print(f"{Fore.GREEN}✅ {message}{Style.RESET_ALL}")
        logger.info(message)
    
    @staticmethod
    def error(message: str):
        """错误日志 - 红色 + ❌"""
        print(f"{Fore.RED}❌ {message}{Style.RESET_ALL}")
        logger.error(message)
    
    @staticmethod
    def warning(message: str):
        """警告日志 - 黄色 + ⚠️"""
        print(f"{Fore.YELLOW}⚠️  {message}{Style.RESET_ALL}")
        logger.warning(message)
    
    @staticmethod
    def info(message: str):
        """信息日志 - 蓝色 + ℹ️"""
        print(f"{Fore.CYAN}ℹ️  {message}{Style.RESET_ALL}")
        logger.info(message)
    
    @staticmethod
    def processing(message: str):
        """处理中日志 - 紫色 + 🔄"""
        print(f"{Fore.MAGENTA}🔄 {message}{Style.RESET_ALL}")
        logger.info(message)
    
    @staticmethod
    def found(message: str):
        """发现日志 - 黄色 + 🔍"""
        print(f"{Fore.YELLOW}🔍 {message}{Style.RESET_ALL}")
        logger.info(message)

# 创建全局彩色日志实例
color_log = ColorLogger()

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
        # 验证必需的环境变量
        db_password = os.getenv('DB_APP_PASSWORD')
        if not db_password:
            color_log.error("DB_APP_PASSWORD environment variable is required")
            raise ValueError("DB_APP_PASSWORD environment variable is required")
            
        self.db_config = {
            "host": os.getenv('DB_HOST', 'localhost'),
            "user": os.getenv('DB_APP_USER', 'edm_app_user'),
            "password": db_password,
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
            color_log.success(f"成功连接到数据库 (环境: {ENVIRONMENT})")
            return connection
        except pymysql.Error as err:
            color_log.error(f"数据库连接错误: {err}")
            return None

    def fetch_organizations(self) -> List[Tuple]:
        """从数据库获取全日本的机构信息"""
        connection = self.get_db_connection()
        if not connection:
            return []

        try:
            cursor = connection.cursor()
            query = """
            SELECT id, registration_number, organization_name, email, prefecture
            FROM support_organization_registry 
            WHERE email IS NULL OR email = ''
            ORDER BY id
            """
            cursor.execute(query)
            results = cursor.fetchall()
            color_log.info(f"从数据库获取到 {len(results)} 条需要抓取邮件的记录")
            return results
        except pymysql.Error as err:
            color_log.error(f"查询数据库错误: {err}")
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
            color_log.processing(f"搜索URL: {search_url}")

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
                    color_log.found(f"找到详情页面链接: {href}")
                    return href

            # 如果没有找到完整URL，尝试查找相对路径
            relative_pattern = re.compile(r"/shien/(\d+)/?")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                match = relative_pattern.match(href)
                if match:
                    full_url = urljoin(self.base_url, href)
                    color_log.found(f"找到详情页面链接 (相对路径): {full_url}")
                    return full_url

            color_log.warning(f"未找到 {registration_number} 的详情页面链接")
            return None

        except requests.RequestException as e:
            color_log.error(f"请求搜索页面失败 {registration_number}: {e}")
            return None
        except Exception as e:
            color_log.error(f"搜索过程出错 {registration_number}: {e}")
            return None

    def extract_email_and_website(self, detail_url: str) -> Tuple[Optional[str], Optional[str]]:
        """从详情页面提取email地址和网站URL"""
        try:
            color_log.processing(f"获取详情页面: {detail_url}")
            response = self.session.get(detail_url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")
            email = None
            website_url = None

            # 1. 首先尝试提取email地址
            email = self.extract_email_from_page(soup)
            
            # 2. 提取网站URL
            website_url = self.extract_website_from_page(soup)
            
            return email, website_url

        except requests.RequestException as e:
            color_log.error(f"请求详情页面失败 {detail_url}: {e}")
            return None, None
        except Exception as e:
            color_log.error(f"提取信息过程出错 {detail_url}: {e}")
            return None, None
    
    def extract_email_from_page(self, soup: BeautifulSoup) -> Optional[str]:
        """从页面中提取email地址的优化算法"""
        # 方法1: 查找包含"メールアドレス"、"E-mail"、"Email"等关键词的元素
        email_keywords = ["メールアドレス", "E-mail", "Email", "email", "連絡先"]
        
        for keyword in email_keywords:
            email_elements = soup.find_all(text=re.compile(keyword, re.IGNORECASE))
            for element in email_elements:
                parent = element.parent
                if parent:
                    # 在父元素及其兄弟元素中查找email
                    for sibling in parent.find_next_siblings(limit=3):
                        email = self.find_email_in_element(sibling)
                        if email:
                            color_log.found(f"通过关键词'{keyword}'找到email: {email}")
                            return email
                    
                    # 在父元素的下一个兄弟元素中查找
                    next_sibling = parent.find_next_sibling()
                    if next_sibling:
                        email = self.find_email_in_element(next_sibling)
                        if email:
                            color_log.found(f"通过关键词'{keyword}'在兄弟元素中找到email: {email}")
                            return email
        
        # 方法2: 查找所有链接中的mailto链接
        mailto_links = soup.find_all('a', href=re.compile(r'^mailto:', re.IGNORECASE))
        for link in mailto_links:
            href = link.get('href', '')
            if href.startswith('mailto:'):
                email = href.replace('mailto:', '').split('?')[0]  # 移除查询参数
                if self.validate_email(email):
                    color_log.found(f"从mailto链接找到email: {email}")
                    return email
        
        # 方法3: 在整个页面文本中搜索email模式（但排除常见的无用email）
        page_text = soup.get_text()
        email = self.find_email_in_text(page_text)
        if email and not self.is_generic_email(email):
            color_log.found(f"在页面文本中找到email: {email}")
            return email
        
        return None
    
    def extract_website_from_page(self, soup: BeautifulSoup) -> Optional[str]:
        """从页面中提取网站URL"""
        # 查找包含"ホームページ"、"ウェブサイト"、"URL"等关键词的元素
        website_keywords = ["ホームページ", "ウェブサイト", "URL", "Website", "サイト"]
        
        for keyword in website_keywords:
            website_elements = soup.find_all(text=re.compile(keyword, re.IGNORECASE))
            for element in website_elements:
                parent = element.parent
                if parent:
                    # 在父元素及其兄弟元素中查找URL
                    for sibling in parent.find_next_siblings(limit=3):
                        url = self.find_url_in_element(sibling)
                        if url:
                            color_log.found(f"通过关键词'{keyword}'找到网站: {url}")
                            return url
        
        # 查找所有外部链接
        links = soup.find_all('a', href=True)
        for link in links:
            href = link.get('href', '')
            if self.is_external_website(href):
                color_log.found(f"找到外部网站链接: {href}")
                return href
        
        return None
    
    def find_url_in_element(self, element) -> Optional[str]:
        """在HTML元素中查找URL"""
        if element:
            # 先检查是否是链接元素
            if element.name == 'a' and element.get('href'):
                href = element.get('href')
                if self.is_external_website(href):
                    return href
            
            # 在文本中查找URL
            text = element.get_text()
            url = self.find_url_in_text(text)
            if url:
                return url
        return None
    
    def find_url_in_text(self, text: str) -> Optional[str]:
        """在文本中查找URL"""
        url_pattern = re.compile(
            r'https?://[\w\-\.]+(:[0-9]+)?(/[\w\-\._~:/?#[\]@!$&\'()*+,;=]*)?',
            re.IGNORECASE
        )
        matches = url_pattern.findall(text)
        
        for match in matches:
            if isinstance(match, tuple):
                url = match[0] + (match[1] if match[1] else '') + (match[2] if match[2] else '')
            else:
                url = match
            
            if self.is_external_website(url):
                return url
        return None
    
    def is_external_website(self, url: str) -> bool:
        """判断是否是外部网站URL"""
        if not url or not url.startswith(('http://', 'https://')):
            return False
        
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # 排除gai-rou.com域名
            if 'gai-rou.com' in domain:
                return False
            
            # 排除常见的社交媒体和搜索引擎
            excluded_domains = [
                'facebook.com', 'twitter.com', 'instagram.com', 'youtube.com',
                'google.com', 'yahoo.co.jp', 'bing.com'
            ]
            
            for excluded in excluded_domains:
                if excluded in domain:
                    return False
            
            return True
        except:
            return False
    
    def is_generic_email(self, email: str) -> bool:
        """判断是否是通用邮箱地址（需要排除的）"""
        generic_patterns = [
            r'.*@(example|test|sample)\.com',
            r'.*@gmail\.com',  # 可选择是否排除gmail
            r'.*@yahoo\.(com|co\.jp)',
            r'.*@hotmail\.com',
            r'noreply@.*',
            r'no-reply@.*'
        ]
        
        for pattern in generic_patterns:
            if re.match(pattern, email.lower()):
                return True
        return False
    
    def scrape_email_from_website(self, website_url: str, max_pages: int = 3) -> Optional[str]:
        """从公司官网抓取邮件地址"""
        if not website_url:
            return None
        
        try:
            color_log.processing(f"开始从官网抓取邮件: {website_url}")
            
            # 要检查的页面列表（按优先级排序）
            pages_to_check = []
            
            # 1. 主页
            pages_to_check.append(website_url.rstrip('/'))
            
            # 2. 常见的联系页面
            contact_paths = [
                '/contact', '/contact.html', '/contact.php', '/contact.htm',
                '/お問い合わせ', '/コンタクト',
                '/about', '/about.html', '/about.php', '/about.htm',
                '/company', '/company.html', '/company.php',
                '/access', '/access.html'
            ]
            
            base_url = website_url.rstrip('/')
            for path in contact_paths[:max_pages-1]:  # 除了主页外的其他页面
                pages_to_check.append(base_url + path)
            
            # 检查每个页面
            for page_url in pages_to_check:
                email = self.extract_email_from_website_page(page_url)
                if email:
                    color_log.success(f"在官网页面找到邮件: {email} (页面: {page_url})")
                    return email
                
                # 每个页面之间添加小的延迟
                time.sleep(random.uniform(0.2, 0.5))
            
            color_log.warning(f"未在官网找到邮件地址: {website_url}")
            return None
            
        except Exception as e:
            color_log.error(f"从官网抓取邮件时出错 {website_url}: {e}")
            return None
    
    def extract_email_from_website_page(self, page_url: str) -> Optional[str]:
        """从单个网站页面提取邮件地址"""
        try:
            logger.debug(f"检查页面: {page_url}")
            response = self.session.get(page_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, "html.parser")
            
            # 使用相同的邮件提取算法
            email = self.extract_email_from_page(soup)
            
            if email and not self.is_generic_email(email):
                return email
            
            return None
            
        except requests.RequestException as e:
            logger.debug(f"请求页面失败 {page_url}: {e}")
            return None
        except Exception as e:
            logger.debug(f"处理页面时出错 {page_url}: {e}")
            return None
    
    def retry_request(self, func, *args, max_retries: int = 3, **kwargs):
        """重试机制装饰器"""
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = random.uniform(1, 3) * (attempt + 1)
                    color_log.warning(f"请求失败，{wait_time:.1f}秒后重试 (第{attempt + 1}次): {e}")
                    time.sleep(wait_time)
                else:
                    color_log.error(f"重试{max_retries}次后仍然失败: {e}")
                    raise e
            except Exception as e:
                color_log.error(f"非网络错误，不重试: {e}")
                raise e
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
                color_log.success(f"成功更新机构ID {org_id} 的email: {email}")
                return True
            else:
                color_log.warning(f"更新机构ID {org_id} 的email失败：未找到记录")
                return False

        except pymysql.Error as err:
            color_log.error(f"更新数据库错误: {err}")
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
            color_log.error("未获取到任何机构数据")
            return

        success_count = 0
        failed_count = 0

        for (
            org_id,
            registration_number,
            organization_name,
            current_email,
            prefecture,
        ) in organizations:
            color_log.processing(
                f"处理机构: ID={org_id}, 登録番号={registration_number}, 名称={organization_name}, 都道府県={prefecture}"
            )

            # 检查是否已经有有效的email地址
            if current_email and current_email.strip():
                color_log.info(
                    f"机构 {organization_name} 已有email地址: {current_email}，跳过"
                )
                continue

            try:
                # 搜索机构详情页面
                detail_url = self.retry_request(self.search_organization, registration_number)
                if not detail_url:
                    color_log.warning(f"未找到机构 {organization_name} 的详情页面")
                    failed_count += 1
                    continue

                # 从 gai-rou.com 提取email和网站
                email, website_url = self.retry_request(self.extract_email_and_website, detail_url)
                
                # 如果在 gai-rou.com 没找到email，尝试从官网抓取
                if not email and website_url:
                    color_log.info(f"在gai-rou.com未找到email，尝试从官网抓取: {website_url}")
                    email = self.scrape_email_from_website(website_url)
                
                if not email:
                    color_log.error(f"未找到机构 {organization_name} 的email地址")
                    failed_count += 1
                    continue

                # 更新数据库
                if self.update_email_in_db(org_id, email):
                    success_count += 1
                    source = "gai-rou.com" if not website_url else "官网"
                    color_log.success(f"✨ 成功处理机构 {organization_name}: {email} (来源: {source})")
                else:
                    failed_count += 1
                    color_log.error(f"更新机构 {organization_name} 的email失败")

                # 添加随机延迟避免过于频繁的请求
                delay = random.uniform(0.5, 2.0)
                logger.debug(f"等待 {delay:.2f} 秒")
                time.sleep(delay)

            except Exception as e:
                color_log.error(f"处理机构 {organization_name} 时出错: {e}")
                failed_count += 1

        # 最终结果统计
        total = success_count + failed_count
        success_rate = (success_count / total * 100) if total > 0 else 0
        
        print(f"\n{Fore.WHITE}{Back.GREEN} 处理完成 {Style.RESET_ALL}")
        print(f"{Fore.GREEN}✅ 成功: {success_count}{Style.RESET_ALL}")
        print(f"{Fore.RED}❌ 失败: {failed_count}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📊 成功率: {success_rate:.1f}%{Style.RESET_ALL}")
        
        color_log.success(f"处理完成！成功: {success_count}, 失败: {failed_count}, 成功率: {success_rate:.1f}%")


def main():
    """主函数"""
    print(f"\n{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}")
    print(f"{Fore.WHITE}{Back.BLUE}           🚀 EDM邮件地址抓取程序 (环境: {ENVIRONMENT})           {Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}\n")
    
    scraper = SupportOrganizationScraper()

    # 显示当前数据库配置
    print(f"{Fore.YELLOW}📋 当前数据库配置:{Style.RESET_ALL}")
    print(f"{Fore.WHITE}  • 主机: {Fore.GREEN}{os.getenv('DB_HOST', 'localhost')}{Style.RESET_ALL}")
    print(f"{Fore.WHITE}  • 数据库: {Fore.GREEN}{os.getenv('DB_NAME', 'edm')}{Style.RESET_ALL}")
    print(f"{Fore.WHITE}  • 用户: {Fore.GREEN}{os.getenv('DB_APP_USER', 'edm_app_user')}{Style.RESET_ALL}")
    
    # 确认是否继续
    print(f"\n{Fore.YELLOW}⚡ 功能特性:{Style.RESET_ALL}")
    print(f"{Fore.WHITE}  • 🌏 支持全日本地区抓取{Style.RESET_ALL}")
    print(f"{Fore.WHITE}  • 🔄 智能重试机制{Style.RESET_ALL}")
    print(f"{Fore.WHITE}  • 🌐 官网备用抓取{Style.RESET_ALL}")
    print(f"{Fore.WHITE}  • 🎯 随机请求间隔{Style.RESET_ALL}")
    
    response = input(f"\n{Fore.CYAN}🚀 是否开始处理? (y/N): {Style.RESET_ALL}").strip().lower()
    if response != "y":
        print(f"{Fore.YELLOW}⏹️  操作取消{Style.RESET_ALL}")
        return

    # 开始处理
    print(f"\n{Fore.GREEN}🎯 开始抓取邮件地址...{Style.RESET_ALL}\n")
    scraper.process_organizations()


if __name__ == "__main__":
    main()
