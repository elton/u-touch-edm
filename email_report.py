import base64
import datetime
import io
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import pymysql
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=False)

# 判断当前环境
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("email_report.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

# 设置matplotlib字体 - 优先使用系统可用字体
def setup_matplotlib_fonts():
    """设置matplotlib字体配置，优先使用可用字体"""
    try:
        import matplotlib.font_manager as fm
        # 获取系统可用字体
        available_fonts = [f.name for f in fm.fontManager.ttflist]
        
        # 按优先级设置字体列表（中文字体 -> 英文字体）
        preferred_fonts = [
            "Noto Sans CJK JP",  # Google Noto 中日韩字体
            "Noto Sans CJK SC",  # Google Noto 简体中文
            "WenQuanYi Micro Hei",  # 文泉驿微米黑
            "SimHei",  # 黑体（Windows）
            "Hiragino Sans GB",  # 苹果中文字体
            "DejaVu Sans",  # DejaVu（通常在Linux中可用）
            "Liberation Sans",  # Liberation（开源字体）
            "Arial",  # Arial
            "sans-serif"  # 系统默认无衬线字体
        ]
        
        # 找到第一个可用的字体
        selected_fonts = []
        for font in preferred_fonts:
            if font in available_fonts or font == "sans-serif":
                selected_fonts.append(font)
        
        if not selected_fonts:
            selected_fonts = ["sans-serif"]  # 最后的备选
            
        plt.rcParams["font.sans-serif"] = selected_fonts
        plt.rcParams["axes.unicode_minus"] = False
        
        logging.info(f"matplotlib字体设置: {selected_fonts[:3]}")  # 只显示前3个
        
    except Exception as e:
        # 如果字体设置失败，使用默认配置
        logging.warning(f"字体设置失败，使用默认配置: {e}")
        plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "sans-serif"]
        plt.rcParams["axes.unicode_minus"] = False

# 初始化字体设置
setup_matplotlib_fonts()

# 配置常量
class Config:
    # 图表配置
    CHART_TOP_N = 10  # 显示前N个地区
    CHART_FIGURE_SIZE = (10, 6)  # 图表尺寸
    CHART_DPI = 100  # 图表分辨率
    
    # 报告配置
    DETAILS_LIMIT = 50  # 详情表格最大显示条数
    WEEK_DAYS = 7  # 一周天数
    
    # 颜色配置
    COLORS = {
        "primary": "#1f77b4",
        "secondary": "#ff7f0e", 
        "success": "#28a745",
        "chart_alpha": 0.7
    }
    
    # SMTP配置
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587

# 简报收件人列表
REPORT_RECIPIENTS = [
    "elton.zheng@u-touch.co.jp",
    "yuancw@u-touch.co.jp",
    "xiaodi@u-touch.co.jp",
    "shirasawa.t@u-touch.co.jp",
]


class EmailReporter:
    def __init__(self):
        """初始化邮件报告生成器"""
        # 从环境变量获取Gmail配置
        self.gmail_user = os.getenv("GMAIL_USER", "info@uforward.jp")
        self.gmail_password = os.getenv("GMAIL_PASSWORD")
        if not self.gmail_password:
            raise ValueError("GMAIL_PASSWORD environment variable is required")
        self.smtp_server = Config.SMTP_SERVER
        self.smtp_port = Config.SMTP_PORT

    def connect_to_database(self) -> pymysql.connections.Connection:
        """连接到MySQL数据库"""
        try:
            db_password = os.getenv("DB_READONLY_PASSWORD")
            if not db_password:
                raise ValueError("DB_READONLY_PASSWORD environment variable is required")
            
            connection = pymysql.connect(
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", "3306")),
                database=os.getenv("DB_NAME", "edm"),
                user=os.getenv("DB_READONLY_USER", "edm-db"),
                password=db_password,
                charset="utf8mb4",
            )
            logging.info(f"成功连接到数据库 (环境: {ENVIRONMENT})")
            return connection
        except pymysql.Error as e:
            logging.error(f"数据库连接失败: {e}")
            raise
    
    def execute_query(self, query: str, params: tuple = None, operation_name: str = "数据库操作") -> List[Dict]:
        """通用数据库查询方法"""
        connection = None
        cursor = None
        results = []
        
        try:
            connection = self.connect_to_database()
            cursor = connection.cursor(pymysql.cursors.DictCursor)
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            results = cursor.fetchall()
            logging.info(f"{operation_name}成功，获取到 {len(results)} 条记录")
            
        except pymysql.Error as e:
            logging.error(f"{operation_name}失败: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
                
        return results

    def get_yesterday_log_data(self) -> Dict:
        """从数据库获取昨天的邮件发送记录"""
        today = datetime.datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        yesterday_start = today - datetime.timedelta(days=1)
        yesterday_end = today - datetime.timedelta(microseconds=1)  # End of yesterday

        yesterday_date_str = yesterday_start.strftime("%Y-%m-%d")

        # 获取昨天所有的发送记录（包括成功和失败的）
        # 发送状态由sent_at字段是否为空来判断
        query = """
        SELECT email, organization_name, representative_name, prefecture, sent_at
        FROM support_organization_registry
        WHERE sent_at >= %s AND sent_at <= %s
        ORDER BY sent_at DESC
        """

        try:
            results = self.execute_query(
                query, 
                (yesterday_start, yesterday_end),
                f"获取昨天的邮件发送记录 ({yesterday_date_str})"
            )

            details = []
            total_sent = len(results)
            success_count = 0
            fail_count = 0

            for row in results:
                is_success = row["sent_at"] is not None
                if is_success:
                    success_count += 1
                else:
                    fail_count += 1

                details.append(
                    {
                        "email": row["email"],
                        "organization_name": row["organization_name"],
                        "representative_name": row["representative_name"],
                        "prefecture": row["prefecture"],
                        "sent_time": (
                            row["sent_at"].strftime("%Y-%m-%d %H:%M:%S")
                            if row["sent_at"]
                            else "N/A"
                        ),
                        "success": is_success,  # 根据sent_at是否为空判断成功或失败
                    }
                )

            logging.info(f"成功: {success_count}，失败: {fail_count}")

        except Exception as e:
            logging.error(f"获取昨天邮件发送记录失败: {e}")
            details = []
            total_sent = 0
            success_count = 0
            fail_count = 0

        return {
            "date": yesterday_date_str,
            "data": {
                "total_sent": total_sent,
                "success_count": success_count,
                "fail_count": fail_count,
                "details": details,
            },
        }

    def get_prefecture_stats(self, details: List[Dict]) -> Dict[str, int]:
        """统计各地区的发送数量"""
        prefecture_stats = {}

        for detail in details:
            prefecture = detail.get("prefecture", "未知")
            prefecture_stats[prefecture] = prefecture_stats.get(prefecture, 0) + 1

        return prefecture_stats

    def get_weekly_stats(self) -> Tuple[Dict[str, int], Dict[str, Dict[str, int]]]:
        """获取最近一周的发送统计数据"""
        today = datetime.datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        week_start = today - datetime.timedelta(days=Config.WEEK_DAYS)

        # 获取最近一周的发送记录
        query = """
        SELECT prefecture, sent_at
        FROM support_organization_registry
        WHERE sent_at >= %s AND sent_at < %s
        ORDER BY sent_at DESC
        """

        try:
            results = self.execute_query(
                query, 
                (week_start, today),
                "获取最近一周的发送统计数据"
            )

            prefecture_stats = {}
            success_stats = {}

            for row in results:
                prefecture = row["prefecture"] or "未知"
                is_success = row["sent_at"] is not None

                # 统计地区分布
                prefecture_stats[prefecture] = prefecture_stats.get(prefecture, 0) + 1

                # 统计成功率
                if prefecture not in success_stats:
                    success_stats[prefecture] = {"success": 0, "total": 0}

                success_stats[prefecture]["total"] += 1
                if is_success:
                    success_stats[prefecture]["success"] += 1

        except Exception as e:
            logging.error(f"获取一周统计数据失败: {e}")
            prefecture_stats = {}
            success_stats = {}

        return prefecture_stats, success_stats

    def get_cumulative_stats(self) -> Tuple[Dict[str, int], Dict[str, Dict[str, int]]]:
        """获取累计发送统计数据"""
        # 获取所有发送记录
        query = """
        SELECT prefecture, sent_at
        FROM support_organization_registry
        WHERE sent_at IS NOT NULL
        ORDER BY sent_at DESC
        """

        try:
            results = self.execute_query(query, None, "获取累计发送统计数据")

            prefecture_stats = {}
            success_stats = {}

            for row in results:
                prefecture = row["prefecture"] or "未知"

                # 统计地区分布
                prefecture_stats[prefecture] = prefecture_stats.get(prefecture, 0) + 1

                # 统计成功率（已发送的都算成功）
                if prefecture not in success_stats:
                    success_stats[prefecture] = {"success": 0, "total": 0}

                success_stats[prefecture]["total"] += 1
                success_stats[prefecture]["success"] += 1

        except Exception as e:
            logging.error(f"获取累计统计数据失败: {e}")
            prefecture_stats = {}
            success_stats = {}

        return prefecture_stats, success_stats

    def _create_chart_base64(self, fig) -> str:
        """将matplotlib图表转换为base64编码的PNG"""
        buffer = None
        try:
            buffer = io.BytesIO()
            fig.savefig(buffer, format="png", dpi=Config.CHART_DPI, bbox_inches="tight")
            buffer.seek(0)
            image_png = buffer.getvalue()
            graphic = base64.b64encode(image_png)
            return f"data:image/png;base64,{graphic.decode('utf-8')}"
        except Exception as e:
            logging.error(f"图表转换为base64失败: {e}")
            return ""
        finally:
            if buffer:
                buffer.close()
            plt.close(fig)

    def create_chart(
        self, data: Dict[str, int], title: str, color: str = "#1f77b4"
    ) -> str:
        """创建图表并返回base64编码的PNG图片"""
        if not data:
            logging.warning(f"图表 '{title}' 数据为空，跳过生成")
            return ""

        try:
            fig, ax = plt.subplots(figsize=Config.CHART_FIGURE_SIZE)

            # 按数量排序并限制显示前N个
            sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)[:Config.CHART_TOP_N]

            if not sorted_data:
                logging.warning(f"图表 '{title}' 排序后数据为空")
                plt.close(fig)
                return ""

            prefectures = [item[0] for item in sorted_data]
            counts = [item[1] for item in sorted_data]

            bars = ax.bar(prefectures, counts, color=color, alpha=Config.COLORS["chart_alpha"])

            ax.set_title(title, fontsize=14, fontweight="bold")
            ax.set_xlabel("地区", fontsize=12)
            ax.set_ylabel("数量", fontsize=12)
            ax.tick_params(axis='x', rotation=45, labelsize=10)

            # 在柱状图上方显示数值
            for bar, count in zip(bars, counts):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max(counts) * 0.01,  # 动态调整位置
                    str(count),
                    ha="center",
                    va="bottom",
                    fontsize=10,
                )

            plt.tight_layout()
            logging.info(f"成功生成图表: {title}")
            return self._create_chart_base64(fig)

        except Exception as e:
            logging.error(f"生成图表 '{title}' 失败: {e}")
            return ""

    def _generate_css_styles(self) -> str:
        """生成CSS样式"""
        return """
                body {
                    font-family: 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }
                .report-container {
                    border: 1px solid #ddd;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 0 10px rgba(0,0,0,0.1);
                }
                .report-header {
                    background: linear-gradient(135deg, #0052cc, #007bff);
                    color: white;
                    padding: 20px;
                    text-align: center;
                }
                .report-header h1 {
                    margin: 0;
                    font-size: 24px;
                }
                .report-header p {
                    margin: 5px 0 0;
                    opacity: 0.9;
                }
                .report-body {
                    padding: 20px;
                    background-color: #fff;
                }
                .stats-container {
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 30px;
                    flex-wrap: wrap;
                }
                .stat-box {
                    flex: 1;
                    min-width: 150px;
                    background-color: #f8f9fa;
                    border-radius: 6px;
                    padding: 15px;
                    margin: 10px;
                    text-align: center;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                }
                .stat-box.success {
                    border-left: 4px solid #28a745;
                }
                .stat-box.fail {
                    border-left: 4px solid #dc3545;
                }
                .stat-box.total {
                    border-left: 4px solid #007bff;
                }
                .stat-box.rate {
                    border-left: 4px solid #fd7e14;
                }
                .stat-value {
                    font-size: 28px;
                    font-weight: bold;
                    margin: 10px 0;
                }
                .stat-label {
                    font-size: 14px;
                    color: #666;
                }
                .section {
                    margin-bottom: 30px;
                }
                .section-title {
                    font-size: 18px;
                    border-bottom: 2px solid #eee;
                    padding-bottom: 10px;
                    margin-bottom: 15px;
                    color: #0052cc;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                }
                th, td {
                    padding: 12px 15px;
                    text-align: left;
                    border-bottom: 1px solid #eee;
                }
                th {
                    background-color: #f8f9fa;
                    font-weight: 600;
                }
                tr:hover {
                    background-color: #f8f9fa;
                }
                .chart {
                    margin-top: 20px;
                    height: 200px;
                    display: flex;
                    align-items: flex-end;
                    justify-content: space-around;
                }
                .chart-bar {
                    background: linear-gradient(to top, #007bff, #00c6ff);
                    width: 40px;
                    border-radius: 4px 4px 0 0;
                    position: relative;
                    transition: height 0.5s;
                }
                .chart-label {
                    position: absolute;
                    bottom: -25px;
                    left: 50%;
                    transform: translateX(-50%);
                    font-size: 12px;
                    white-space: nowrap;
                }
                .chart-value {
                    position: absolute;
                    top: -25px;
                    left: 50%;
                    transform: translateX(-50%);
                    font-size: 12px;
                    font-weight: bold;
                }
                .chart-image {
                    width: 100%;
                    max-width: 800px;
                    height: auto;
                    border-radius: 8px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    margin: 20px 0;
                }
                .chart-grid {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 30px;
                    margin: 30px 0;
                }
                @media (max-width: 768px) {
                    .chart-grid {
                        grid-template-columns: 1fr;
                    }
                }
                .footer {
                    text-align: center;
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                    color: #777;
                    font-size: 12px;
                }
        """

    def _generate_stats_section(self, total_sent: int, success_count: int, fail_count: int, success_rate: float) -> str:
        """生成统计数据区域"""
        return f"""
                    <div class="stats-container">
                        <div class="stat-box total">
                            <div class="stat-label">总发送数</div>
                            <div class="stat-value">{total_sent}</div>
                        </div>
                        <div class="stat-box success">
                            <div class="stat-label">成功发送</div>
                            <div class="stat-value">{success_count}</div>
                        </div>
                        <div class="stat-box fail">
                            <div class="stat-label">发送失败</div>
                            <div class="stat-value">{fail_count}</div>
                        </div>
                        <div class="stat-box rate">
                            <div class="stat-label">成功率</div>
                            <div class="stat-value">{success_rate:.1f}%</div>
                        </div>
                    </div>
        """

    def _generate_yesterday_chart_section(self, prefecture_stats: Dict[str, int]) -> str:
        """生成昨日地区分布图表区域"""
        html = """
                    <div class="section">
                        <h2 class="section-title">昨日地区分布</h2>
        """

        # 添加地区统计图表
        if prefecture_stats:
            html += '<div class="chart">'
            max_value = max(prefecture_stats.values()) if prefecture_stats else 0
            for prefecture, count in prefecture_stats.items():
                # 计算柱状图高度，最大值为180px
                height = 180 * count / max_value if max_value > 0 else 0
                html += f"""
                <div class="chart-bar" style="height: {height}px;">
                    <span class="chart-value">{count}</span>
                    <span class="chart-label">{prefecture}</span>
                </div>
                """
            html += "</div>"
        else:
            html += "<p>无地区数据</p>"

        html += "</div>"
        return html

    def _generate_weekly_stats_section(self, weekly_region_chart: str, weekly_success_chart: str) -> str:
        """生成最近7天统计区域"""
        html = """
                    <div class="section">
                        <h2 class="section-title">最近7天统计</h2>
                        <div class="chart-grid">
                            <div>
                                <h3 style="text-align: center; color: #0052cc; margin-bottom: 15px;">地区分布</h3>
        """

        if weekly_region_chart:
            html += f'<img src="{weekly_region_chart}" alt="最近7天地区分布" class="chart-image">'
        else:
            html += '<p style="text-align: center; color: #666;">无数据</p>'

        html += """
                            </div>
                            <div>
                                <h3 style="text-align: center; color: #0052cc; margin-bottom: 15px;">成功率分布</h3>
        """

        if weekly_success_chart:
            html += f'<img src="{weekly_success_chart}" alt="最近7天成功率" class="chart-image">'
        else:
            html += '<p style="text-align: center; color: #666;">无数据</p>'

        html += """
                            </div>
                        </div>
                    </div>
        """
        return html

    def _generate_cumulative_stats_section(self, cumulative_region_chart: str, cumulative_success_chart: str) -> str:
        """生成累计统计区域"""
        html = """
                    <div class="section">
                        <h2 class="section-title">累计统计</h2>
                        <div class="chart-grid">
                            <div>
                                <h3 style="text-align: center; color: #0052cc; margin-bottom: 15px;">地区分布</h3>
        """

        if cumulative_region_chart:
            html += f'<img src="{cumulative_region_chart}" alt="累计地区分布" class="chart-image">'
        else:
            html += '<p style="text-align: center; color: #666;">无数据</p>'

        html += """
                            </div>
                            <div>
                                <h3 style="text-align: center; color: #0052cc; margin-bottom: 15px;">成功率分布</h3>
        """

        if cumulative_success_chart:
            html += f'<img src="{cumulative_success_chart}" alt="累计成功率" class="chart-image">'
        else:
            html += '<p style="text-align: center; color: #666;">无数据</p>'

        html += """
                            </div>
                        </div>
                    </div>
        """
        return html

    def _generate_details_table(self, details: List[Dict]) -> str:
        """生成发送详情表格"""
        html = """
                    <div class="section">
                        <h2 class="section-title">昨日发送详情</h2>
                        <table>
                            <thead>
                                <tr>
                                    <th>机构名称</th>
                                    <th>代表者</th>
                                    <th>地区</th>
                                    <th>邮箱</th>
                                    <th>状态</th>
                                </tr>
                            </thead>
                            <tbody>
        """

        # 最多显示指定条数记录
        for detail in details[:Config.DETAILS_LIMIT]:
            # 根据sent_at是否为空判断成功或失败
            status_color = "#28a745" if detail.get("success", False) else "#dc3545"
            status_text = "成功" if detail.get("success", False) else "失败"

            html += f"""
                <tr>
                    <td>{detail.get("organization_name", "")}</td>
                    <td>{detail.get("representative_name", "")}</td>
                    <td>{detail.get("prefecture", "")}</td>
                    <td>{detail.get("email", "")}</td>
                    <td style="color: {status_color}; font-weight: bold;">{status_text}</td>
                </tr>
            """

        # 如果记录超过限制条数，显示省略提示
        if len(details) > Config.DETAILS_LIMIT:
            html += f"""
                <tr>
                    <td colspan="5" style="text-align: center; font-style: italic; color: #666;">
                        ... 省略 {len(details) - Config.DETAILS_LIMIT} 条记录，仅显示前{Config.DETAILS_LIMIT}条 ...
                    </td>
                </tr>
            """

        html += """
                            </tbody>
                        </table>
                    </div>
        """
        return html

    def create_success_rate_chart(
        self, success_data: Dict[str, Dict[str, int]], title: str
    ) -> str:
        """创建成功率图表并返回base64编码的PNG图片"""
        if not success_data:
            logging.warning(f"成功率图表 '{title}' 数据为空，跳过生成")
            return ""

        try:
            # 计算成功率
            rate_data = {}
            for prefecture, stats in success_data.items():
                if stats["total"] > 0:
                    rate_data[prefecture] = (stats["success"] / stats["total"]) * 100

            if not rate_data:
                logging.warning(f"成功率图表 '{title}' 计算后数据为空")
                return ""

            fig, ax = plt.subplots(figsize=Config.CHART_FIGURE_SIZE)

            # 按成功率排序并限制显示前N个
            sorted_data = sorted(rate_data.items(), key=lambda x: x[1], reverse=True)[:Config.CHART_TOP_N]

            prefectures = [item[0] for item in sorted_data]
            rates = [item[1] for item in sorted_data]

            bars = ax.bar(prefectures, rates, color=Config.COLORS["success"], alpha=Config.COLORS["chart_alpha"])

            ax.set_title(title, fontsize=14, fontweight="bold")
            ax.set_xlabel("地区", fontsize=12)
            ax.set_ylabel("成功率 (%)", fontsize=12)
            ax.tick_params(axis='x', rotation=45, labelsize=10)
            ax.set_ylim(0, 100)

            # 在柱状图上方显示数值
            for bar, rate in zip(bars, rates):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 2,  # 固定位置偏移
                    f"{rate:.1f}%",
                    ha="center",
                    va="bottom",
                    fontsize=10,
                )

            plt.tight_layout()
            logging.info(f"成功生成成功率图表: {title}")
            return self._create_chart_base64(fig)

        except Exception as e:
            logging.error(f"生成成功率图表 '{title}' 失败: {e}")
            return ""

    def generate_html_report(self, report_data: Dict) -> str:
        """生成HTML格式的邮件发送报告"""
        date = report_data["date"]
        data = report_data["data"]
        total_sent = data["total_sent"]
        success_count = data["success_count"]
        fail_count = data["fail_count"]
        details = data["details"]

        # 计算成功率
        success_rate = 0 if total_sent == 0 else (success_count / total_sent) * 100

        # 获取地区统计
        prefecture_stats = self.get_prefecture_stats(details)

        # 获取一周统计数据
        weekly_prefecture_stats, weekly_success_stats = self.get_weekly_stats()

        # 获取累计统计数据
        cumulative_prefecture_stats, cumulative_success_stats = (
            self.get_cumulative_stats()
        )

        # 生成图表
        weekly_region_chart = self.create_chart(
            weekly_prefecture_stats, "最近7天地区分布", Config.COLORS["primary"]
        )
        weekly_success_chart = self.create_success_rate_chart(
            weekly_success_stats, "最近7天成功率"
        )
        cumulative_region_chart = self.create_chart(
            cumulative_prefecture_stats, "累计地区分布", Config.COLORS["secondary"]
        )
        cumulative_success_chart = self.create_success_rate_chart(
            cumulative_success_stats, "累计成功率"
        )

        # 组装完整HTML报告
        html = f"""
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>邮件发送日报 - {date}</title>
            <style>
                {self._generate_css_styles()}
            </style>
        </head>
        <body>
            <div class="report-container">
                <div class="report-header">
                    <h1>邮件发送日报</h1>
                    <p>{date} (环境: {ENVIRONMENT})</p>
                </div>
                <div class="report-body">
                    {self._generate_stats_section(total_sent, success_count, fail_count, success_rate)}
                    {self._generate_yesterday_chart_section(prefecture_stats)}
                    {self._generate_weekly_stats_section(weekly_region_chart, weekly_success_chart)}
                    {self._generate_cumulative_stats_section(cumulative_region_chart, cumulative_success_chart)}
                    {self._generate_details_table(details)}
                    
                    <div class="footer">
                        <p>此报告由U-Touch EDM系统自动生成，请勿回复此邮件。</p>
                        <p>如有问题，请联系管理员。生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def send_report_email(
        self, recipients: List[str], html_content: str, date: str
    ) -> bool:
        """发送HTML格式的报告邮件"""
        server = None
        try:
            logging.info(f"开始发送报告邮件到 {len(recipients)} 个收件人")
            
            # 创建邮件
            msg = MIMEMultipart()
            msg["From"] = self.gmail_user
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = f"【U-Touch EDM日报】{date} - 邮件发送统计及分析"

            # 添加HTML内容
            msg.attach(MIMEText(html_content, "html"))
            logging.info("邮件内容构建完成")

            # 连接到SMTP服务器并发送
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            logging.info("SMTP连接建立，开始认证")
            
            server.login(self.gmail_user, self.gmail_password)
            logging.info("SMTP认证成功，开始发送邮件")
            
            server.send_message(msg)
            logging.info(f"成功发送报告邮件到 {len(recipients)} 个收件人: {', '.join(recipients)}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logging.error(f"SMTP认证失败: {e}. 请检查Gmail用户名和密码")
            return False
        except smtplib.SMTPConnectError as e:
            logging.error(f"SMTP连接失败: {e}. 请检查网络连接和SMTP服务器设置")
            return False
        except smtplib.SMTPRecipientsRefused as e:
            logging.error(f"收件人被拒绝: {e}. 请检查收件人邮箱地址")
            return False
        except Exception as e:
            logging.error(f"发送报告邮件失败 (未知错误): {e}")
            return False
        finally:
            if server:
                try:
                    server.quit()
                    logging.info("SMTP连接已关闭")
                except Exception as e:
                    logging.warning(f"关闭SMTP连接时出现警告: {e}")

    def generate_and_send_report(self):
        """生成并发送昨天的邮件发送报告"""
        try:
            logging.info("开始生成和发送邮件报告")
            
            # 获取昨天的发送记录
            report_data = self.get_yesterday_log_data()

            # 如果昨天没有发送记录，则不发送报告
            if report_data["data"]["total_sent"] == 0:
                logging.info(
                    f"昨天 ({report_data['date']}) 没有邮件发送记录，跳过报告生成"
                )
                return False

            logging.info(f"昨天共发送 {report_data['data']['total_sent']} 封邮件，开始生成报告")

            # 生成HTML报告
            html_content = self.generate_html_report(report_data)
            logging.info("HTML报告生成完成")

            # 验证收件人列表
            if not REPORT_RECIPIENTS:
                logging.error("收件人列表为空，无法发送报告")
                return False

            # 发送报告邮件
            result = self.send_report_email(
                REPORT_RECIPIENTS, html_content, report_data["date"]
            )
            
            if result:
                logging.info("邮件报告生成和发送流程完成")
            else:
                logging.error("邮件报告发送失败")
            
            return result

        except ValueError as e:
            logging.error(f"配置错误: {e}")
            return False
        except Exception as e:
            logging.error(f"生成和发送报告失败 (未知错误): {e}")
            import traceback
            logging.error(f"详细错误信息: {traceback.format_exc()}")
            return False


def main():
    """主函数"""
    reporter = EmailReporter()
    success = reporter.generate_and_send_report()

    if success:
        print("报告邮件发送成功")
    else:
        print("报告邮件发送失败，请查看日志获取详细信息")


if __name__ == "__main__":
    main()
