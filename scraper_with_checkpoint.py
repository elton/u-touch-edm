import argparse
import hashlib
import logging
import os
import random
import re
import signal
import sys
import time
from datetime import datetime
from typing import List, Optional, Tuple, Dict
from urllib.parse import quote, urljoin, urlparse

import pymysql
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
try:
    from colorama import Fore, Back, Style, init
    # 初始化colorama，支持Windows系统
    init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    # 如果colorama不可用，定义空的样式
    class MockStyle:
        RESET_ALL = ''
    class MockFore:
        GREEN = RED = YELLOW = CYAN = MAGENTA = WHITE = ''
    class MockBack:
        GREEN = BLUE = ''
    
    Fore = MockFore()
    Back = MockBack()
    Style = MockStyle()
    COLORAMA_AVAILABLE = False

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
        """信息日志 - 青色 + ℹ️"""
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

# 断点续抓管理类
class CheckpointManager:
    def __init__(self, db_config: dict):
        self.db_config = db_config
        self.session_id = None
        self.checkpoint_data = None
        self.interrupted = False
        
        # 注册信号处理器，优雅处理中断
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """处理中断信号"""
        color_log.warning(f"接收到中断信号 {signum}，正在保存进度...")
        self.interrupted = True
        if self.session_id:
            self.update_status('paused', '用户中断')
        sys.exit(0)
    
    def generate_session_id(self) -> str:
        """生成会话ID"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        random_str = hashlib.md5(str(random.random()).encode()).hexdigest()[:8]
        return f"scraper_{timestamp}_{random_str}"
    
    def get_db_connection(self):
        """获取数据库连接"""
        try:
            return pymysql.connect(**self.db_config)
        except pymysql.Error as err:
            color_log.error(f"数据库连接错误: {err}")
            return None
    
    def create_checkpoint(self, total_records: int, resume_from: Optional[str] = None) -> str:
        """创建新的检查点或恢复现有检查点"""
        connection = self.get_db_connection()
        if not connection:
            return None
        
        try:
            cursor = connection.cursor()
            
            if resume_from:
                # 恢复现有会话
                cursor.execute(
                    "SELECT * FROM scraper_checkpoint WHERE session_id = %s AND status IN ('running', 'paused')",
                    (resume_from,)
                )
                result = cursor.fetchone()
                if result:
                    self.session_id = resume_from
                    self.checkpoint_data = {
                        'id': result[0],
                        'session_id': result[1],
                        'last_processed_id': result[2],
                        'total_records': result[3],
                        'processed_records': result[4],
                        'success_count': result[5],
                        'failed_count': result[6],
                        'status': result[7]
                    }
                    # 更新状态为运行中
                    cursor.execute(
                        "UPDATE scraper_checkpoint SET status = 'running', last_update_time = NOW() WHERE session_id = %s",
                        (self.session_id,)
                    )
                    connection.commit()
                    color_log.success(f"恢复会话: {self.session_id}, 从记录ID {self.checkpoint_data['last_processed_id']} 继续")
                    return self.session_id
                else:
                    color_log.error(f"未找到可恢复的会话: {resume_from}")
                    return None
            else:
                # 创建新会话
                self.session_id = self.generate_session_id()
                cursor.execute(
                    """
                    INSERT INTO scraper_checkpoint 
                    (session_id, last_processed_id, total_records, processed_records, success_count, failed_count, status, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (self.session_id, 0, total_records, 0, 0, 0, 'running', '新会话开始')
                )
                connection.commit()
                self.checkpoint_data = {
                    'last_processed_id': 0,
                    'total_records': total_records,
                    'processed_records': 0,
                    'success_count': 0,
                    'failed_count': 0,
                    'status': 'running'
                }
                color_log.success(f"创建新会话: {self.session_id}")
                return self.session_id
                
        except pymysql.Error as err:
            color_log.error(f"创建检查点错误: {err}")
            return None
        finally:
            if connection:
                cursor.close()
                connection.close()
    
    def update_progress(self, last_processed_id: int, success_count: int, failed_count: int):
        """更新进度"""
        if not self.session_id or self.interrupted:
            return
        
        connection = self.get_db_connection()
        if not connection:
            return
        
        try:
            cursor = connection.cursor()
            processed_records = success_count + failed_count
            cursor.execute(
                """
                UPDATE scraper_checkpoint 
                SET last_processed_id = %s, processed_records = %s, success_count = %s, failed_count = %s, last_update_time = NOW()
                WHERE session_id = %s
                """,
                (last_processed_id, processed_records, success_count, failed_count, self.session_id)
            )
            connection.commit()
            
            # 更新本地缓存
            self.checkpoint_data.update({
                'last_processed_id': last_processed_id,
                'processed_records': processed_records,
                'success_count': success_count,
                'failed_count': failed_count
            })
            
        except pymysql.Error as err:
            color_log.error(f"更新进度错误: {err}")
        finally:
            if connection:
                cursor.close()
                connection.close()
    
    def update_status(self, status: str, notes: str = ''):
        """更新状态"""
        if not self.session_id:
            return
        
        connection = self.get_db_connection()
        if not connection:
            return
        
        try:
            cursor = connection.cursor()
            end_time = 'NOW()' if status in ['completed', 'failed'] else 'NULL'
            cursor.execute(
                f"""
                UPDATE scraper_checkpoint 
                SET status = %s, notes = %s, end_time = {end_time}, last_update_time = NOW()
                WHERE session_id = %s
                """,
                (status, notes, self.session_id)
            )
            connection.commit()
            
        except pymysql.Error as err:
            color_log.error(f"更新状态错误: {err}")
        finally:
            if connection:
                cursor.close()
                connection.close()
    
    def get_resume_point(self) -> int:
        """获取恢复点"""
        if self.checkpoint_data:
            return self.checkpoint_data['last_processed_id']
        return 0
    
    def get_progress_info(self) -> dict:
        """获取进度信息"""
        return self.checkpoint_data if self.checkpoint_data else {}
    
    def list_sessions(self):
        """列出所有会话"""
        connection = self.get_db_connection()
        if not connection:
            return
        
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT session_id, total_records, processed_records, success_count, failed_count, 
                       status, start_time, last_update_time, notes
                FROM scraper_checkpoint 
                ORDER BY start_time DESC
                LIMIT 20
                """
            )
            results = cursor.fetchall()
            
            if results:
                print(f"\n{Fore.CYAN}📋 最近的抓取会话:{Style.RESET_ALL}")
                print(f"{Fore.WHITE}{'会话ID':<30} {'状态':<10} {'进度':<15} {'成功/失败':<12} {'开始时间':<20}{Style.RESET_ALL}")
                print("-" * 90)
                
                for row in results:
                    session_id, total, processed, success, failed, status, start_time, update_time, notes = row
                    progress = f"{processed}/{total}" if total > 0 else "0/0"
                    success_fail = f"{success}/{failed}"
                    
                    status_color = {
                        'running': Fore.GREEN,
                        'paused': Fore.YELLOW,
                        'completed': Fore.CYAN,
                        'failed': Fore.RED
                    }.get(status, Fore.WHITE)
                    
                    print(f"{session_id:<30} {status_color}{status:<10}{Style.RESET_ALL} {progress:<15} {success_fail:<12} {start_time}")
            else:
                color_log.info("没有找到任何抓取会话")
                
        except pymysql.Error as err:
            color_log.error(f"查询会话错误: {err}")
        finally:
            if connection:
                cursor.close()
                connection.close()

class SupportOrganizationScraper:
    def __init__(self, resume_session: Optional[str] = None):
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
        
        # 初始化检查点管理器
        self.checkpoint_manager = CheckpointManager(self.db_config)
        self.resume_session = resume_session

    def get_db_connection(self):
        """获取数据库连接"""
        try:
            connection = pymysql.connect(**self.db_config)
            color_log.success(f"成功连接到数据库 (环境: {ENVIRONMENT})")
            return connection
        except pymysql.Error as err:
            color_log.error(f"数据库连接错误: {err}")
            return None

    def fetch_organizations(self, resume_from_id: int = 0) -> List[Tuple]:
        """从数据库获取全日本的机构信息"""
        connection = self.get_db_connection()
        if not connection:
            return []

        try:
            cursor = connection.cursor()
            # 如果有恢复点，从该点继续
            where_clause = "WHERE (email IS NULL OR email = '') AND id > %s" if resume_from_id > 0 else "WHERE email IS NULL OR email = ''"
            query = f"""
            SELECT id, registration_number, organization_name, email, prefecture
            FROM support_organization_registry 
            {where_clause}
            ORDER BY id
            """
            
            if resume_from_id > 0:
                cursor.execute(query, (resume_from_id,))
                color_log.info(f"从记录ID {resume_from_id} 恢复抓取")
            else:
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
    
    def get_total_records_count(self) -> int:
        """获取总记录数"""
        connection = self.get_db_connection()
        if not connection:
            return 0
        
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM support_organization_registry WHERE email IS NULL OR email = ''")
            count = cursor.fetchone()[0]
            return count
        except pymysql.Error as err:
            color_log.error(f"查询记录总数错误: {err}")
            return 0
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
    
    def _estimate_remaining_time(self, completed: int, total: int, elapsed_time: float) -> str:
        """估算剩余时间"""
        if completed == 0:
            return "未知"
        
        avg_time_per_item = elapsed_time / completed
        remaining_items = total - completed
        remaining_seconds = avg_time_per_item * remaining_items
        
        if remaining_seconds < 60:
            return f"{remaining_seconds:.0f}秒"
        elif remaining_seconds < 3600:
            return f"{remaining_seconds/60:.1f}分钟"
        else:
            hours = remaining_seconds // 3600
            minutes = (remaining_seconds % 3600) // 60
            return f"{hours:.0f}小时{minutes:.0f}分钟"

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
        # 初始化检查点
        total_records = self.get_total_records_count()
        if total_records == 0:
            color_log.info("没有需要处理的记录")
            return
        
        # 创建或恢复检查点
        session_id = self.checkpoint_manager.create_checkpoint(total_records, self.resume_session)
        if not session_id:
            color_log.error("无法创建或恢复检查点")
            return
        
        # 获取恢复点和进度信息
        resume_from_id = self.checkpoint_manager.get_resume_point()
        progress_info = self.checkpoint_manager.get_progress_info()
        
        # 获取机构列表（从恢复点开始）
        organizations = self.fetch_organizations(resume_from_id)
        if not organizations:
            if resume_from_id > 0:
                color_log.success("所有记录已处理完成")
                self.checkpoint_manager.update_status('completed', '所有记录处理完成')
            else:
                color_log.error("未获取到任何机构数据")
            return

        # 初始化计数器（考虑恢复的情况）
        success_count = progress_info.get('success_count', 0)
        failed_count = progress_info.get('failed_count', 0)
        processed_count = 0
        current_batch_count = 0  # 当前批次计数器
        
        # 计算总体进度信息
        already_processed = progress_info.get('processed_records', 0)
        current_batch_size = len(organizations)
        
        color_log.info(f"开始处理 {current_batch_size} 条记录 (会话: {session_id})")
        color_log.info(f"📊 总体进度: 已完成 {already_processed}/{total_records} ({(already_processed/total_records*100):.1f}%)")
        if resume_from_id > 0:
            color_log.info(f"📈 累计统计: 成功 {success_count}, 失败 {failed_count}")

        # 记录批次开始时间
        self._batch_start_time = time.time()
        
        try:
            for (
                org_id,
                registration_number,
                organization_name,
                current_email,
                prefecture,
            ) in organizations:
                # 检查是否被中断
                if self.checkpoint_manager.interrupted:
                    break
                
                processed_count += 1
                current_batch_count += 1
                
                # 计算当前整体进度
                current_total_processed = already_processed + current_batch_count
                overall_progress = (current_total_processed / total_records) * 100
                batch_progress = (current_batch_count / current_batch_size) * 100
                
                color_log.processing(
                    f"🔄 [{current_batch_count}/{current_batch_size}] ({batch_progress:.1f}%) | 总进度: [{current_total_processed}/{total_records}] ({overall_progress:.1f}%) | {organization_name} ({prefecture})"
                )

                # 检查是否已经有有效的email地址
                if current_email and current_email.strip():
                    color_log.info(
                        f"⏭️  机构 {organization_name} 已有email地址: {current_email}，跳过"
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

                    # 每处理5条记录更新一次进度
                    if current_batch_count % 5 == 0:
                        self.checkpoint_manager.update_progress(org_id, success_count, failed_count)
                        current_total_processed = already_processed + current_batch_count
                        overall_progress = (current_total_processed / total_records) * 100
                        success_rate = (success_count / (success_count + failed_count) * 100) if (success_count + failed_count) > 0 else 0
                        
                        print(f"\n{Fore.CYAN}📊 进度报告 - 批次: {current_batch_count}/{current_batch_size} | 总体: {current_total_processed}/{total_records} ({overall_progress:.1f}%){Style.RESET_ALL}")
                        print(f"{Fore.GREEN}   ✅ 成功: {success_count} | {Fore.RED}❌ 失败: {failed_count} | {Fore.YELLOW}📈 成功率: {success_rate:.1f}%{Style.RESET_ALL}")
                        print(f"{Fore.MAGENTA}   ⏱️  预计剩余: {self._estimate_remaining_time(current_batch_count, current_batch_size, time.time() - getattr(self, '_batch_start_time', time.time()))}{Style.RESET_ALL}\n")

                    # 添加随机延迟避免过于频繁的请求
                    delay = random.uniform(0.5, 2.0)
                    time.sleep(delay)

                except Exception as e:
                    color_log.error(f"处理机构 {organization_name} 时出错: {e}")
                    failed_count += 1
                    continue

        except KeyboardInterrupt:
            color_log.warning("接收到中断信号，正在保存进度...")
            self.checkpoint_manager.update_progress(org_id, success_count, failed_count)
            self.checkpoint_manager.update_status('paused', f'用户中断，已处理{processed_count}条记录')
            return
        except Exception as e:
            color_log.error(f"处理过程中发生错误: {e}")
            self.checkpoint_manager.update_status('failed', f'处理错误: {str(e)}')
            return
        
        # 最终更新进度
        if organizations:
            last_id = organizations[-1][0] if current_batch_count == len(organizations) else org_id
            self.checkpoint_manager.update_progress(last_id, success_count, failed_count)
            
            # 显示最终批次统计
            batch_time = time.time() - self._batch_start_time
            avg_time_per_record = batch_time / current_batch_count if current_batch_count > 0 else 0
            color_log.info(f"📋 批次完成统计: 处理 {current_batch_count} 条记录，耗时 {batch_time:.1f} 秒，平均 {avg_time_per_record:.2f} 秒/条")

        # 最终结果统计
        total_this_session = current_batch_count
        total_overall = success_count + failed_count
        success_rate = (success_count / total_overall * 100) if total_overall > 0 else 0
        current_total_processed = already_processed + current_batch_count
        overall_completion = (current_total_processed / total_records) * 100
        
        # 判断是否完成所有记录
        if len(organizations) < 100:  # 如果返回的记录少于预期，可能已经完成
            remaining_records = self.get_total_records_count()
            if remaining_records == 0:
                self.checkpoint_manager.update_status('completed', f'所有记录处理完成')
                status_text = "🎉 全部完成"
                status_color = Fore.GREEN
            else:
                self.checkpoint_manager.update_status('paused', f'本次处理完成，还有{remaining_records}条记录待处理')
                status_text = "⏸️ 批次完成"
                status_color = Fore.YELLOW
        else:
            self.checkpoint_manager.update_status('paused', f'处理了{total_this_session}条记录')
            status_text = "⏸️ 批次完成" 
            status_color = Fore.YELLOW
        
        print(f"\n{Fore.WHITE}{Back.GREEN} {status_text} {Style.RESET_ALL}")
        print(f"{Fore.CYAN}📅 会话ID: {session_id}{Style.RESET_ALL}")
        print(f"{Fore.MAGENTA}📊 总体进度: {current_total_processed}/{total_records} ({overall_completion:.1f}%){Style.RESET_ALL}")
        print(f"{Fore.GREEN}✅ 本次成功: {success_count - progress_info.get('success_count', 0)} | 累计成功: {success_count}{Style.RESET_ALL}")
        print(f"{Fore.RED}❌ 本次失败: {failed_count - progress_info.get('failed_count', 0)} | 累计失败: {failed_count}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📈 总体成功率: {success_rate:.1f}%{Style.RESET_ALL}")
        if overall_completion < 100:
            print(f"{Fore.YELLOW}🔄 要继续处理，请使用: python scraper_with_checkpoint.py --resume {session_id}{Style.RESET_ALL}")
        
        color_log.success(f"处理完成！本次: {total_this_session}条, 总进度: {overall_completion:.1f}%, 累计成功: {success_count}, 失败: {failed_count}, 成功率: {success_rate:.1f}%")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='EDM邮件地址抓取程序 - 支持断点续抓')
    parser.add_argument('--resume', type=str, help='恢复指定会话ID的抓取')
    parser.add_argument('--list-sessions', action='store_true', help='列出所有抓取会话')
    parser.add_argument('--no-color', action='store_true', help='禁用彩色输出')
    
    args = parser.parse_args()
    
    if args.no_color or not COLORAMA_AVAILABLE:
        # 禁用彩色输出
        global Fore, Back, Style
        Fore = Back = Style = type('MockColor', (), {'__getattr__': lambda s, n: ''})()
    
    print(f"\n{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}")
    print(f"{Fore.WHITE}{Back.BLUE}      🚀 EDM邮件地址抓取程序 (环境: {ENVIRONMENT}) - 支持断点续抓      {Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}\n")
    
    scraper = SupportOrganizationScraper(resume_session=args.resume)
    
    # 处理列出会话命令
    if args.list_sessions:
        scraper.checkpoint_manager.list_sessions()
        return

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
    print(f"{Fore.WHITE}  • 💾 断点续抓支持{Style.RESET_ALL}")
    print(f"{Fore.WHITE}  • 📊 进度实时保存{Style.RESET_ALL}")
    
    if args.resume:
        print(f"\n{Fore.GREEN}🔄 恢复会话: {args.resume}{Style.RESET_ALL}")
        response = "y"
    else:
        response = input(f"\n{Fore.CYAN}🚀 是否开始处理? (y/N): {Style.RESET_ALL}").strip().lower()
    
    if response != "y":
        print(f"{Fore.YELLOW}⏹️ 操作取消{Style.RESET_ALL}")
        return

    # 开始处理
    action_text = "恢复抓取" if args.resume else "开始抓取"
    print(f"\n{Fore.GREEN}🎯 {action_text}邮件地址...{Style.RESET_ALL}\n")
    
    # 显示使用提示
    if not args.resume:
        print(f"{Fore.YELLOW}💡 提示:{Style.RESET_ALL}")
        print(f"{Fore.WHITE}  • 使用 Ctrl+C 可以安全中断并保存进度{Style.RESET_ALL}")
        print(f"{Fore.WHITE}  • 使用 python scraper_with_checkpoint.py --list-sessions 查看所有会话{Style.RESET_ALL}")
        print(f"{Fore.WHITE}  • 使用 python scraper_with_checkpoint.py --resume <会话ID> 恢复抓取{Style.RESET_ALL}\n")
    
    scraper.process_organizations()


if __name__ == "__main__":
    main()