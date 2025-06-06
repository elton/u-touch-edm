import datetime
import json
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List

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

# 简报收件人列表
REPORT_RECIPIENTS = [
    "elton.zheng@u-touch.co.jp",
    "yuancw@u-touch.co.jp", 
    "xiaodi@u-touch.co.jp", 
    "shirasawa.t@u-touch.co.jp"
]

class EmailReporter:
    def __init__(self):
        """初始化邮件报告生成器"""
        # 从环境变量获取Gmail配置
        self.gmail_user = os.getenv("GMAIL_USER", "info@uforward.jp")
        self.gmail_password = os.getenv("GMAIL_PASSWORD", "pwqltfgitutzdxro")
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587

    def connect_to_database(self) -> pymysql.connections.Connection:
        """连接到MySQL数据库"""
        try:
            connection = pymysql.connect(
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", "3306")),
                database=os.getenv("DB_NAME", "edm"),
                user=os.getenv("DB_READONLY_USER", "edm-db"),
                password=os.getenv("DB_READONLY_PASSWORD", "yQQPFaTDGXBFjJWW"),
                charset="utf8mb4",
            )
            logging.info(f"成功连接到数据库 (环境: {ENVIRONMENT})")
            return connection
        except pymysql.Error as e:
            logging.error(f"数据库连接失败: {e}")
            raise

    def get_yesterday_log_data(self) -> Dict:
        """从日志文件中获取昨天的邮件发送记录"""
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        yesterday_date = yesterday.strftime("%Y-%m-%d")
        
        # 读取发送记录文件
        try:
            with open("email_send_history.json", "r", encoding="utf-8") as f:
                all_history = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            all_history = {}
        
        # 获取昨天的记录
        yesterday_data = all_history.get(yesterday_date, {
            "total_sent": 0,
            "success_count": 0,
            "fail_count": 0,
            "details": []
        })
        
        return {
            "date": yesterday_date,
            "data": yesterday_data
        }
    
    def get_prefecture_stats(self, details: List[Dict]) -> Dict[str, int]:
        """统计各地区的发送数量"""
        prefecture_stats = {}
        
        for detail in details:
            prefecture = detail.get("prefecture", "未知")
            prefecture_stats[prefecture] = prefecture_stats.get(prefecture, 0) + 1
        
        return prefecture_stats
    
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
        
        # 生成HTML报告
        html = f"""
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>邮件发送日报 - {date}</title>
            <style>
                body {{
                    font-family: 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .report-container {{
                    border: 1px solid #ddd;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 0 10px rgba(0,0,0,0.1);
                }}
                .report-header {{
                    background: linear-gradient(135deg, #0052cc, #007bff);
                    color: white;
                    padding: 20px;
                    text-align: center;
                }}
                .report-header h1 {{
                    margin: 0;
                    font-size: 24px;
                }}
                .report-header p {{
                    margin: 5px 0 0;
                    opacity: 0.9;
                }}
                .report-body {{
                    padding: 20px;
                    background-color: #fff;
                }}
                .stats-container {{
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 30px;
                    flex-wrap: wrap;
                }}
                .stat-box {{
                    flex: 1;
                    min-width: 150px;
                    background-color: #f8f9fa;
                    border-radius: 6px;
                    padding: 15px;
                    margin: 10px;
                    text-align: center;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                }}
                .stat-box.success {{
                    border-left: 4px solid #28a745;
                }}
                .stat-box.fail {{
                    border-left: 4px solid #dc3545;
                }}
                .stat-box.total {{
                    border-left: 4px solid #007bff;
                }}
                .stat-box.rate {{
                    border-left: 4px solid #fd7e14;
                }}
                .stat-value {{
                    font-size: 28px;
                    font-weight: bold;
                    margin: 10px 0;
                }}
                .stat-label {{
                    font-size: 14px;
                    color: #666;
                }}
                .section {{
                    margin-bottom: 30px;
                }}
                .section-title {{
                    font-size: 18px;
                    border-bottom: 2px solid #eee;
                    padding-bottom: 10px;
                    margin-bottom: 15px;
                    color: #0052cc;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                th, td {{
                    padding: 12px 15px;
                    text-align: left;
                    border-bottom: 1px solid #eee;
                }}
                th {{
                    background-color: #f8f9fa;
                    font-weight: 600;
                }}
                tr:hover {{
                    background-color: #f8f9fa;
                }}
                .chart {{
                    margin-top: 20px;
                    height: 200px;
                    display: flex;
                    align-items: flex-end;
                    justify-content: space-around;
                }}
                .chart-bar {{
                    background: linear-gradient(to top, #007bff, #00c6ff);
                    width: 40px;
                    border-radius: 4px 4px 0 0;
                    position: relative;
                    transition: height 0.5s;
                }}
                .chart-label {{
                    position: absolute;
                    bottom: -25px;
                    left: 50%;
                    transform: translateX(-50%);
                    font-size: 12px;
                    white-space: nowrap;
                }}
                .chart-value {{
                    position: absolute;
                    top: -25px;
                    left: 50%;
                    transform: translateX(-50%);
                    font-size: 12px;
                    font-weight: bold;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                    color: #777;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="report-container">
                <div class="report-header">
                    <h1>邮件发送日报</h1>
                    <p>{date} (环境: {ENVIRONMENT})</p>
                </div>
                <div class="report-body">
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
                    
                    <div class="section">
                        <h2 class="section-title">地区分布</h2>
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
            html += '</div>'
        else:
            html += '<p>无地区数据</p>'
            
        # 添加详细发送记录表格
        html += """
                    </div>
                    
                    <div class="section">
                        <h2 class="section-title">发送详情</h2>
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
        
        # 最多显示50条记录
        for detail in details[:50]:
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
            
        # 如果记录超过50条，显示省略提示
        if len(details) > 50:
            html += f"""
                <tr>
                    <td colspan="5" style="text-align: center; font-style: italic;">
                        ... 省略 {len(details) - 50} 条记录 ...
                    </td>
                </tr>
            """
            
        html += """
                            </tbody>
                        </table>
                    </div>
                    
                    <div class="footer">
                        <p>此报告由系统自动生成，请勿回复此邮件。如有问题，请联系管理员。</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def send_report_email(self, recipients: List[str], html_content: str, date: str) -> bool:
        """发送HTML格式的报告邮件"""
        try:
            # 创建邮件
            msg = MIMEMultipart()
            msg["From"] = self.gmail_user
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = f"【邮件发送日报】{date} - 发送统计"
            
            # 添加HTML内容
            msg.attach(MIMEText(html_content, "html"))
            
            # 连接到SMTP服务器并发送
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.gmail_user, self.gmail_password)
            server.send_message(msg)
            server.quit()
            
            logging.info(f"成功发送报告邮件到 {len(recipients)} 个收件人")
            return True
            
        except Exception as e:
            logging.error(f"发送报告邮件失败: {e}")
            return False
    
    def get_organization_details(self, email_list: List[Dict]) -> List[Dict]:
        """从数据库获取机构详细信息"""
        if not email_list:
            return []
            
        try:
            connection = self.connect_to_database()
            cursor = connection.cursor()
            
            # 获取所有发送过邮件的组织的详细信息
            email_addresses = [detail.get("email") for detail in email_list if "email" in detail]
            if not email_addresses:
                return []
                
            # 构建SQL查询
            placeholders = ", ".join(["%s"] * len(email_addresses))
            query = f"""
            SELECT email, organization_name, representative_name, prefecture
            FROM support_organization_registry
            WHERE email IN ({placeholders})
            """
            
            cursor.execute(query, email_addresses)
            results = cursor.fetchall()
            
            # 创建邮箱到详细信息的映射
            org_details = {}
            for email, org_name, rep_name, prefecture in results:
                org_details[email] = {
                    "organization_name": org_name,
                    "representative_name": rep_name,
                    "prefecture": prefecture
                }
            
            # 更新邮件列表中的组织详细信息
            for detail in email_list:
                email = detail.get("email")
                if email and email in org_details:
                    detail.update(org_details[email])
            
            return email_list
            
        except Exception as e:
            logging.error(f"获取组织详细信息失败: {e}")
            return email_list
        finally:
            if connection:
                cursor.close()
                connection.close()
    
    def generate_and_send_report(self):
        """生成并发送昨天的邮件发送报告"""
        try:
            # 获取昨天的发送记录
            report_data = self.get_yesterday_log_data()
            
            # 如果昨天没有发送记录，则不发送报告
            if report_data["data"]["total_sent"] == 0:
                logging.info(f"昨天 ({report_data['date']}) 没有邮件发送记录，不生成报告")
                return False
            
            # 补充组织详细信息
            details = report_data["data"]["details"]
            details_with_info = self.get_organization_details(details)
            report_data["data"]["details"] = details_with_info
            
            # 生成HTML报告
            html_content = self.generate_html_report(report_data)
            
            # 发送报告邮件
            return self.send_report_email(REPORT_RECIPIENTS, html_content, report_data["date"])
            
        except Exception as e:
            logging.error(f"生成和发送报告失败: {e}")
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
