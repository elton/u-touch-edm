#!/usr/bin/env python3
"""
GAI-ROU.COM 支援機関爬虫脚本
从 https://www.gai-rou.com/shien_list/ 爬取登录支援机关信息

作者: Claude
日期: 2025-07-31
"""

import requests
from bs4 import BeautifulSoup
import pymysql
import time
import logging
from urllib.parse import urljoin, urlparse
import re
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

# 颜色支持
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

# 加载环境变量
load_dotenv()

# 彩色日志类
class ColorLogger:
    @staticmethod
    def success(message):
        print(f"{Fore.GREEN}✅ {message}{Style.RESET_ALL}")
        logger.info(message)
    
    @staticmethod
    def error(message):
        print(f"{Fore.RED}❌ {message}{Style.RESET_ALL}")
        logger.error(message)
    
    @staticmethod
    def warning(message):
        print(f"{Fore.YELLOW}⚠️  {message}{Style.RESET_ALL}")
        logger.warning(message)
    
    @staticmethod
    def info(message):
        print(f"{Fore.CYAN}ℹ️  {message}{Style.RESET_ALL}")
        logger.info(message)
    
    @staticmethod
    def processing(message):
        print(f"{Fore.MAGENTA}🔄 {message}{Style.RESET_ALL}")
        logger.info(message)
    
    @staticmethod
    def found(message):
        print(f"{Fore.YELLOW}🔍 {message}{Style.RESET_ALL}")
        logger.info(message)

# 创建全局彩色日志实例
color_log = ColorLogger()

# 配置基础日志（后备）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/gai_rou_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GaiRouScraper:
    def __init__(self):
        """初始化爬虫"""
        self.base_url = "https://www.gai-rou.com"
        self.list_url = "https://www.gai-rou.com/shien_list/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # 数据库连接参数（与scraper_with_checkpoint.py保持一致）
        # 获取数据库密码
        db_password = os.getenv('DB_APP_PASSWORD')
        if not db_password:
            color_log.error("缺少必需的环境变量 DB_APP_PASSWORD")
            raise ValueError("DB_APP_PASSWORD environment variable is required")
            
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'user': os.getenv('DB_APP_USER', 'edm_app_user'),
            'password': db_password,
            'database': os.getenv('DB_NAME', 'edm'),
            'charset': 'utf8mb4'
        }
        
        self.scraped_count = 0
        self.error_count = 0
        
        # 显示数据库连接信息
        color_log.info(f"数据库配置:")
        print(f"{Fore.WHITE}  主机: {Fore.GREEN}{self.db_config['host']}{Style.RESET_ALL}")
        print(f"{Fore.WHITE}  用户: {Fore.GREEN}{self.db_config['user']}{Style.RESET_ALL}")
        print(f"{Fore.WHITE}  数据库: {Fore.GREEN}{self.db_config['database']}{Style.RESET_ALL}")

    def get_db_connection(self):
        """获取数据库连接"""
        try:
            return pymysql.connect(**self.db_config)
        except Exception as e:
            color_log.error(f"数据库连接失败: {e}")
            raise

    def get_page_content(self, url: str, max_retries: int = 3) -> Optional[BeautifulSoup]:
        """获取页面内容"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                response.encoding = 'utf-8'
                return BeautifulSoup(response.text, 'html.parser')
            except Exception as e:
                color_log.warning(f"第{attempt+1}次尝试获取页面失败 {url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    color_log.error(f"获取页面失败 {url}: {e}")
                    return None

    def extract_organization_list(self, soup: BeautifulSoup) -> List[Dict]:
        """从列表页提取机构信息"""
        organizations = []
        
        # GAI-ROU.COM 使用不同的结构，查找所有包含 /shien/ 链接的元素
        org_links = soup.find_all('a', href=re.compile(r'/shien/\d+/'))
        
        for link in org_links:
            try:
                href = link.get('href')
                # 提取机构ID
                match = re.search(r'/shien/(\d+)/', href)
                if not match:
                    continue
                    
                org_id = match.group(1)
                full_url = urljoin(self.base_url, href)
                
                # 提取链接文本作为机构名称
                org_name = link.get_text(strip=True)
                if not org_name:
                    org_name = f"Organization {org_id}"
                
                organizations.append({
                    'id': org_id,
                    'name': org_name,
                    'detail_url': full_url
                })
                
            except Exception as e:
                color_log.error(f"提取机构信息失败: {e}")
                continue
                
        # 去重
        seen_ids = set()
        unique_orgs = []
        for org in organizations:
            if org['id'] not in seen_ids:
                seen_ids.add(org['id'])
                unique_orgs.append(org)
                
        return unique_orgs

    def extract_organization_detail(self, detail_url: str, org_id: str) -> Dict:
        """从详情页提取详细信息"""
        soup = self.get_page_content(detail_url)
        if not soup:
            return {}
            
        detail_info = {}
        
        try:
            # GAI-ROU.COM 使用文本格式而非表格，需要解析文本内容
            page_text = soup.get_text()
            
            # 使用正则表达式提取各个字段
            patterns = {
                'registration_number': r'登録番号[：:\s]*([^\s\n]+)',
                'registration_date': r'登録年月日[：:\s]*([^\s\n]+)',
                'organization_name': r'機関名[：:\s]*([^\n]+)',
                'postal_code': r'郵便番号[：:\s]*([^\s\n]+)',
                'address': r'住所[：:\s]*([^\n]+)',
                'phone_number': r'電話番号[：:\s]*([^\s\n]+)',
                'website': r'ホームページ[：:\s]*([^\s\n]+)',
                'support_languages': r'対応言語[：:\s]*([^\n]+)',
                'support_content': r'支援業務の内容[：:\s]*([^\n]+)',
                'support_start_date': r'支援開始日[：:\s]*([^\s\n]+)'
            }
            
            for field, pattern in patterns.items():
                match = re.search(pattern, page_text)
                if match:
                    detail_info[field] = match.group(1).strip()
            
            # 额外的网站URL提取方法
            website_url = self.extract_website_url(soup, page_text)
            if website_url:
                detail_info['website'] = website_url
            
            # 从页面标题提取机构名称（备用）
            title = soup.find('title')
            if title and not detail_info.get('organization_name'):
                title_text = title.get_text(strip=True)
                if '|' in title_text:
                    detail_info['organization_name'] = title_text.split('|')[0].strip()
            
            # 判断支援类型
            support_type = self.determine_support_type(page_text)
            detail_info['support_type'] = support_type
            
        except Exception as e:
            color_log.error(f"提取详情信息失败 {detail_url}: {e}")
            
        return detail_info

    def extract_website_url(self, soup: BeautifulSoup, page_text: str) -> str:
        """从页面中提取网站URL"""
        website_url = ""
        
        try:
            # 方法1: 查找外部链接
            external_links = soup.find_all('a', href=True)
            for link in external_links:
                href = link.get('href')
                if href and any(domain in href for domain in ['http://', 'https://']):
                    # 排除gai-rou.com自身的链接
                    if 'gai-rou.com' not in href:
                        # 清理URL
                        cleaned_url = self.clean_website_url(href)
                        if cleaned_url:
                            website_url = cleaned_url
                            break
            
            # 方法2: 从文本中提取URL
            if not website_url:
                url_patterns = [
                    r'https?://[^\s\n<>"\']+',
                    r'www\.[^\s\n<>"\']+',
                    r'[a-zA-Z0-9.-]+\.(com|co\.jp|jp|org|net|info)[^\s\n<>"\']*'
                ]
                
                for pattern in url_patterns:
                    matches = re.findall(pattern, page_text, re.IGNORECASE)
                    for match in matches:
                        # 排除gai-rou.com的链接
                        if 'gai-rou.com' not in match.lower():
                            cleaned_url = self.clean_website_url(match)
                            if cleaned_url:
                                website_url = cleaned_url
                                break
                    if website_url:
                        break
                        
        except Exception as e:
            color_log.error(f"提取网站URL失败: {e}")
            
        return website_url

    def clean_website_url(self, url: str) -> str:
        """清理和标准化网站URL"""
        if not url:
            return ""
            
        try:
            # 移除前后空格和特殊字符
            url = url.strip().rstrip('.,;:!')
            
            # 如果URL不以http开头，添加https
            if not url.startswith(('http://', 'https://')):
                if url.startswith('www.'):
                    url = 'https://' + url
                elif '.' in url and not url.startswith('//'):
                    url = 'https://' + url
                else:
                    return ""
            
            # 验证URL格式
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if parsed.netloc and parsed.scheme in ['http', 'https']:
                return url
                
        except Exception as e:
            color_log.error(f"清理URL失败 '{url}': {e}")
            
        return ""

    def determine_support_type(self, page_text: str) -> str:
        """根据页面内容判断支援类型"""
        text_lower = page_text.lower()
        
        has_tokutei = any(keyword in text_lower for keyword in [
            '特定技能', 'tokutei', 'specified skilled worker'
        ])
        
        has_jisshu = any(keyword in text_lower for keyword in [
            '技能実習', '技能实习', 'jisshu', 'technical intern'
        ])
        
        if has_tokutei and has_jisshu:
            return 'both'
        elif has_tokutei:
            return 'tokutei_ginou'
        elif has_jisshu:
            return 'ginou_jisshuusei'
        else:
            return 'both'  # 默认两者都支持

    def extract_prefecture_from_address(self, address: str) -> str:
        """从地址中提取都道府县"""
        if not address:
            return ""
            
        prefectures = [
            '北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
            '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
            '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県', '岐阜県',
            '静岡県', '愛知県', '三重県', '滋賀県', '京都府', '大阪府', '兵庫県',
            '奈良県', '和歌山県', '鳥取県', '島根県', '岡山県', '広島県', '山口県',
            '徳島県', '香川県', '愛媛県', '高知県', '福岡県', '佐賀県', '長崎県',
            '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県'
        ]
        
        for prefecture in prefectures:
            if prefecture in address:
                return prefecture
                
        return ""

    def normalize_organization_name(self, name: str) -> str:
        """标准化机构名称用于重复检查"""
        if not name:
            return ""
            
        # 清理空格
        normalized = name.strip()
        if not normalized:
            return ""
        
        # 移除常见的公司前缀和后缀
        prefixes_to_remove = [
            '株式会社', '有限会社', '協同組合', '一般社団法人', '公益社団法人', 
            '一般財団法人', '公益財団法人', '合同会社', '合資会社', '合名会社'
        ]
        
        suffixes_to_remove = [
            '株式会社', '(株)', '有限会社', '(有)', '協同組合', '組合',
            'llc', 'inc', 'corp', 'co.,ltd', 'co.ltd', 'ltd'
        ]
        
        # 移除前缀
        for prefix in prefixes_to_remove:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):].strip()
                break
        
        # 移除后缀
        for suffix in suffixes_to_remove:
            if normalized.lower().endswith(suffix.lower()):
                normalized = normalized[:-len(suffix)].strip()
                break
        
        # 转换为小写并移除特殊字符（保留中日文字符）
        import re
        normalized = normalized.lower()
        normalized = re.sub(r'[^\w\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]', '', normalized)
        
        return normalized

    def check_organization_exists(self, org_data: Dict) -> bool:
        """检查机构是否已存在"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            org_name = org_data.get('organization_name', '').strip()
            if not org_name:
                return False
            
            # 标准化当前机构名称
            normalized_name = self.normalize_organization_name(org_name)
            if not normalized_name:
                return False
            
            # 获取所有现有机构名称进行比较
            cursor.execute("SELECT organization_name, registration_number FROM support_organization_registry")
            existing_orgs = cursor.fetchall()
            
            for existing_name, existing_reg_num in existing_orgs:
                if existing_name:
                    existing_normalized = self.normalize_organization_name(existing_name)
                    if existing_normalized == normalized_name:
                        color_log.info(f"发现重复机构名称: '{org_name}' 与现有 '{existing_name}' 匹配")
                        return True
            
            # 如果有登録番号，也检查登録番号
            if org_data.get('registration_number'):
                cursor.execute(
                    "SELECT organization_name FROM support_organization_registry WHERE registration_number = %s",
                    (org_data['registration_number'],)
                )
                if cursor.fetchone():
                    color_log.info(f"登録番号已存在: {org_data['registration_number']}")
                    return True
            
            return False
            
        except Exception as e:
            color_log.error(f"检查机构是否存在时出错: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()

    def save_organization(self, org_data: Dict) -> bool:
        """保存机构信息到数据库"""
        try:
            # 检查机构是否已存在
            if self.check_organization_exists(org_data):
                color_log.success(f"机构已存在，跳过: {org_data.get('organization_name', 'Unknown')}")
                return True
            
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # 提取都道府县
            prefecture = self.extract_prefecture_from_address(org_data.get('address', ''))
            
            # 插入数据
            sql = """
                INSERT INTO support_organization_registry 
                (registration_number, registration_date, organization_name, address, prefecture, 
                 phone_number, representative_name, support_type, email, website, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """
            
            values = (
                org_data.get('registration_number', ''),
                org_data.get('registration_date', None),
                org_data.get('organization_name', ''),
                org_data.get('address', ''),
                prefecture,
                org_data.get('phone_number', ''),
                org_data.get('representative_name', ''),
                org_data.get('support_type', 'both'),
                org_data.get('email', ''),
                org_data.get('website', '')
            )
            
            cursor.execute(sql, values)
            conn.commit()
            
            color_log.success(f"成功保存机构: {org_data.get('organization_name', 'Unknown')}")
            return True
            
        except Exception as e:
            color_log.error(f"保存机构信息失败: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()

    def get_next_page_url(self, soup: BeautifulSoup) -> Optional[str]:
        """从当前页面获取下一页的URL"""
        try:
            # 查找 "next page" 链接 - 根据你提供的HTML结构
            next_link = soup.find('a', class_='next page-numbers')
            if next_link and next_link.get('href'):
                next_url = next_link.get('href')
                # 转换为完整URL
                full_next_url = urljoin(self.base_url, next_url)
                color_log.found(f"发现下一页链接: {full_next_url}")
                return full_next_url
            
            # 备用方法：查找包含 ">" 或 "次へ" 的链接
            pagination_links = soup.find_all('a', href=re.compile(r'/page/\d+/'))
            for link in pagination_links:
                link_text = link.get_text(strip=True)
                if any(indicator in link_text for indicator in ['>', '次へ', 'Next', 'next']):
                    next_url = link.get('href')
                    full_next_url = urljoin(self.base_url, next_url)
                    color_log.found(f"通过文本匹配发现下一页链接: {full_next_url}")
                    return full_next_url
            
            color_log.info("未找到下一页链接，已到达最后一页")
            return None
            
        except Exception as e:
            color_log.error(f"查找下一页链接时出错: {e}")
            return None

    def get_total_pages(self) -> int:
        """获取总页数（已废弃，改用动态分页）"""
        color_log.warning("get_total_pages方法已废弃，现在使用动态分页")
        return 1

    def scrape_all_organizations(self):
        """爬取所有机构信息 - 使用动态分页"""
        print(f"\n{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}")
        print(f"{Fore.WHITE}{Back.BLUE}      🚀 GAI-ROU.COM 支援机关爬虫系统 (动态分页)      {Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}\n")
        
        color_log.info("开始爬取 GAI-ROU.COM 支援机关信息")
        color_log.info("使用动态分页模式，将跟随'下一页'链接直到结束")
        
        # 开始动态分页爬取
        current_url = self.list_url
        page_number = 1
        max_pages = 1000  # 设置最大页数限制，防止无限循环
        
        while current_url and page_number <= max_pages:
            try:
                color_log.processing(f"正在处理第 {page_number} 页: {current_url}")
                
                # 获取当前页面内容
                soup = self.get_page_content(current_url)
                if not soup:
                    color_log.error(f"获取第 {page_number} 页失败")
                    break
                
                # 提取机构列表
                organizations = self.extract_organization_list(soup)
                color_log.found(f"第 {page_number} 页发现 {len(organizations)} 个机构")
                
                # 如果当前页没有机构，可能已到达末尾
                if not organizations:
                    color_log.warning(f"第 {page_number} 页未发现任何机构，可能已到达末尾")
                    break
                
                # 处理每个机构
                page_success = 0
                page_failed = 0
                
                for i, org in enumerate(organizations, 1):
                    try:
                        color_log.processing(f"处理第 {page_number} 页第 {i}/{len(organizations)} 个机构: {org['name'][:50]}...")
                        
                        # 获取详细信息
                        detail_info = self.extract_organization_detail(org['detail_url'], org['id'])
                        
                        # 合并信息
                        org_data = {
                            'organization_name': detail_info.get('organization_name', org['name']),
                            'address': detail_info.get('address', ''),
                            'registration_number': detail_info.get('registration_number', ''),
                            'registration_date': detail_info.get('registration_date', None),
                            'phone_number': detail_info.get('phone_number', ''),
                            'representative_name': detail_info.get('representative_name', ''),
                            'support_type': detail_info.get('support_type', 'both'),
                            'email': detail_info.get('email', ''),
                            'website': detail_info.get('website', ''),
                            'support_languages': detail_info.get('support_languages', ''),
                            'postal_code': detail_info.get('postal_code', '')
                        }
                        
                        # 保存到数据库
                        if self.save_organization(org_data):
                            self.scraped_count += 1
                            page_success += 1
                        else:
                            self.error_count += 1
                            page_failed += 1
                            
                        # 延迟避免被封IP
                        time.sleep(1)
                        
                    except Exception as e:
                        color_log.error(f"处理机构失败 {org['name']}: {e}")
                        self.error_count += 1
                        page_failed += 1
                        continue
                
                # 页面处理完成统计
                color_log.success(f"第 {page_number} 页处理完成 - 成功: {page_success}, 失败: {page_failed}")
                
                # 查找下一页链接
                next_url = self.get_next_page_url(soup)
                if next_url:
                    current_url = next_url
                    page_number += 1
                    color_log.info(f"准备处理下一页 (第 {page_number} 页)")
                    time.sleep(3)  # 页面间延迟
                else:
                    color_log.success("已到达最后一页，爬取完成")
                    break
                
            except Exception as e:
                color_log.error(f"处理第 {page_number} 页时发生错误: {e}")
                # 尝试查找下一页继续
                if soup:
                    next_url = self.get_next_page_url(soup)
                    if next_url:
                        current_url = next_url
                        page_number += 1
                        continue
                break
        
        # 检查是否达到最大页数限制
        if page_number > max_pages:
            color_log.warning(f"已达到最大页数限制 ({max_pages} 页)，停止爬取")
        
        # 最终统计
        print(f"\n{Fore.WHITE}{Back.GREEN} 🎉 爬取完成! {Style.RESET_ALL}")
        print(f"{Fore.CYAN}📊 处理页数: {page_number - 1} 页{Style.RESET_ALL}")
        print(f"{Fore.GREEN}✅ 成功: {self.scraped_count}{Style.RESET_ALL}")
        print(f"{Fore.RED}❌ 失败: {self.error_count}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📈 总计: {self.scraped_count + self.error_count}{Style.RESET_ALL}")
        
        if self.scraped_count + self.error_count > 0:
            success_rate = (self.scraped_count / (self.scraped_count + self.error_count)) * 100
            print(f"{Fore.MAGENTA}📈 成功率: {success_rate:.1f}%{Style.RESET_ALL}")
        
        color_log.success(f"动态分页爬取完成! 处理 {page_number - 1} 页，成功: {self.scraped_count}, 失败: {self.error_count}")

def main():
    """主函数"""
    scraper = GaiRouScraper()
    scraper.scrape_all_organizations()

if __name__ == "__main__":
    main()