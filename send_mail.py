import argparse
import datetime
import json
import logging
import os
import smtplib
import time
import uuid
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional, Tuple

import pymysql
from dotenv import load_dotenv

# 加载环境变量，设置override=False，这样系统环境变量会优先于.env文件中的变量
load_dotenv(override=False)

# 判断当前环境
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
logging.info(f"当前运行环境: {ENVIRONMENT}")

# 如果是生产环境，输出一个提示
if ENVIRONMENT == "production":
    logging.info("正在使用生产环境配置")
else:
    logging.info("正在使用开发环境配置")

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("email_sender.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


class EmailSender:
    def __init__(
        self,
        gmail_user: str,
        gmail_password: str,
        ga_tracking_id: Optional[str] = None,
    ):
        """
        初始化邮件发送器

        Args:
            gmail_user: Gmail邮箱地址
            gmail_password: Gmail应用密码（不是账户密码）
            ga_tracking_id: Google Analytics 4 跟踪ID (如: G-XXXXXXXXXX)
        """
        self.gmail_user = gmail_user
        self.gmail_password = gmail_password
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.ga_tracking_id = ga_tracking_id

        # 邮件发送历史记录文件
        self.history_file = "email_send_history.json"

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
            logging.error(
                f"数据库连接信息：host={os.getenv('DB_HOST', 'localhost')}, port={os.getenv('DB_PORT', '3306')}, db={os.getenv('DB_NAME', 'edm')}, user={os.getenv('DB_READONLY_USER', 'edm-db')}, password={os.getenv('DB_READONLY_PASSWORD', 'yQQPFaTDGXBFjJWW')}"
            )
            logging.error(f"数据库连接失败: {e}")
            raise

    def fetch_recipients(self) -> List[Tuple[str, str, str]]:
        """从数据库获取收件人信息"""
        connection = None
        try:
            connection = self.connect_to_database()
            cursor = connection.cursor()

            query = """
            SELECT organization_name, representative_name, email 
            FROM support_organization_registry 
            WHERE (prefecture = '東京都' OR prefecture = '神奈川県')
            AND email IS NOT NULL AND email != '' AND email LIKE '%@%'
            ORDER BY id
            """

            cursor.execute(query)
            recipients = cursor.fetchall()

            logging.info(f"从数据库获取到 {len(recipients)} 个收件人")
            return recipients

        except pymysql.Error as e:
            logging.error(f"查询数据库失败: {e}")
            raise
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
                logging.info("数据库连接已关闭")

    def create_email_content(
        self,
        organization_name: str,
        representative_name: str,
        tracking_id: Optional[str] = None,
    ) -> str:
        """创建HTML格式的邮件内容"""
        # 如果代表者姓名为空，使用机构名称
        display_name = representative_name if representative_name else organization_name

        # 生成唯一的跟踪ID
        if not tracking_id:
            tracking_id = str(uuid.uuid4())

        # Google Analytics跟踪代码
        ga_head_script = ""
        ga_body_script = ""
        ga_custom_event = ""

        if self.ga_tracking_id:
            # GA头部脚本
            ga_head_script = f"""
    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id={self.ga_tracking_id}"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());

      gtag('config', '{self.ga_tracking_id}');
    </script>"""

            # 自定义事件跟踪，使用GA4事件跟踪方式
            ga_custom_event = f"""
    <script>
    // 确保ataLayer存在并添加gtag函数
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    
    // 跟踪邮件打开事件
    gtag('event', 'email_open', {{
      'email_organization': '{organization_name}',
      'email_tracking_id': '{tracking_id}',
      'email_representative': '{representative_name or ""}',
      'email_category': 'edm'
    }});
    
    // 跟踪页面浏览
    gtag('event', 'page_view', {{
      'page_title': '特定技能支援機関向けITツールサービスのご案内',
      'organization_name': '{organization_name}',
      'tracking_id': '{tracking_id}'
    }});
    </script>"""

        html_template = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>特定技能支援機関向けITツールサービスのご案内</title>
    {ga_head_script}
    <style>
        body {{
            font-family: 'Helvetica Neue', Arial, 'Hiragino Kaku Gothic ProN', 'Hiragino Sans', Meiryo, sans-serif;
            line-height: 1.6;
            color: #333333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }}
        .email-container {{
            background-color: #ffffff;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header {{
            border-bottom: 2px solid #0066cc;
            padding-bottom: 15px;
            margin-bottom: 25px;
        }}
        .greeting {{
            font-size: 16px;
            font-weight: bold;
            color: #0066cc;
            margin-bottom: 10px;
        }}
        .content {{
            font-size: 14px;
            line-height: 1.8;
            margin-bottom: 20px;
        }}
        .highlight {{
            background-color: #f0f8ff;
            padding: 15px;
            border-left: 4px solid #0066cc;
            margin: 20px 0;
        }}
        .signature {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eeeeee;
            font-size: 14px;
        }}
        .company-name {{
            font-weight: bold;
            color: #0066cc;
        }}
        .contact-info {{
            color: #666666;
            font-size: 13px;
        }}
        .footer {{
            margin-top: 20px;
            font-size: 12px;
            color: #999999;
            text-align: center;
        }}
        .cta-button {{
            display: inline-block;
            background-color: #0066cc;
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 5px;
            margin: 10px 0;
            font-weight: bold;
        }}
        .cta-button:hover {{
            background-color: #0056b3;
        }}
    </style>
</head>
<body>
    {ga_body_script}
    
    <div class="email-container">
        <div class="header">
        <p>{organization_name}株式会社</p>
        <p>代表取締役</p>
            <div class="greeting">{display_name}様</div>
        </div>
        
        <div class="content">
            <p>お世話になっております。<a href="https://u-touch.co.jp/" style="text-decoration: none;"><span class="company-name">株式会社ユー・タチ</span></a>の白澤です。</p>
            
            <div class="highlight">
                <p><strong>弊社は特定技能支援機関向けに、一括管理用ITツールサービスを提供しております。</strong></p>
                <p>特に、ビザ申請上に更新期間知らせ、提出書類作成、オンライン申請、定期管理記録、
顧客管理など煩雑な業務を簡単に管理し、円滑に業務が進むようなシステムなります。
また、社内管理においても作業の仕分け、進捗管理などもシステム上で一括管理可能です。
添付にて、説明資料を送り致します。ご査収ください。</p>
            </div>     
            <p>機能がたくさんあるので、可能であれば一度お時間を頂きご挨拶も含めて
システムの説明と業界の情報もご提供させていただければ幸いです</p>
            <p>何卒、宜しくお願い致します。</p>
        </div>
        
        <div class="signature">
            <div class="company-name"><a href="https://u-touch.co.jp/" style="text-decoration: none; color: #0066cc;">株式会社ユー・タチ</a></div>
            
            <div class="contact-info">
            <p>白澤　武文（シラサワ タケフミ）</p>
            <p>MOB：080－9971-6888</p>
            <p>Email:
                <a href="mailto:shirasawa.t@u-touch.co.jp" 
                   style="color: #0066cc;"
                   onclick="if(typeof gtag === 'function') gtag('event', 'click', {{'event_category': 'email', 'event_label': 'email_link', 'organization': '{organization_name}', 'tracking_id': '{tracking_id}'}});">
                   shirasawa.t@u-touch.co.jp
                </a></p>
                <p>Homepage： <a href="http://www.u-touch.co.jp" 
                   style="color: #0066cc;">http://www.u-touch.co.jp</a></p>
                   <p>東京本社：</p>
                   <p>〒111-0053　東京都台東区浅草橋2－29－11　マルケービル9F</p>
                   <p>TEL：03－4362－0813</p>
                   <p>金沢支社：</p>
                   <p>〒920-0869　石川県金沢市上堤町1－35　オリンピアビル8F・9F</p>
                   <p>TEL：076－204－8669</p>
            </div>

        </div>
        
        <div class="footer">
            <p>本メールは{organization_name}様宛に送信されました。</p>
            <p>トラッキングID: {tracking_id}</p>
        </div>
    </div>
    
    {ga_custom_event}
</body>
</html>
        """

        return html_template.strip()

    def send_email(
        self,
        to_email: str,
        organization_name: str,
        representative_name: str,
        attachment_path: Optional[str] = None,
        tracking_id: Optional[str] = None,
    ) -> bool:
        """发送邮件"""
        try:
            # 生成唯一跟踪ID
            if not tracking_id:
                tracking_id = str(uuid.uuid4())

            # 创建邮件内容
            subject = "【U-Touch】外国人材紹介サービスのご案内"
            html_content = self.create_email_content(
                organization_name, representative_name, tracking_id
            )

            # 发送邮件
            msg = MIMEMultipart()
            msg["From"] = self.gmail_user
            msg["To"] = to_email
            msg["Subject"] = subject

            # 添加HTML内容
            msg.attach(MIMEText(html_content, "html"))

            # 添加附件
            if attachment_path and os.path.exists(attachment_path):
                with open(attachment_path, "rb") as attachment:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={os.path.basename(attachment_path)}",
                )
                msg.attach(part)

            # 连接到SMTP服务器并发送
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.gmail_user, self.gmail_password)
            server.send_message(msg)
            server.quit()

            logging.info(
                f"邮件成功发送到: {to_email} ({organization_name}) - 跟踪ID: {tracking_id}"
            )

            # 记录发送成功的邮件
            self.record_email_send(
                to_email, True, organization_name, representative_name
            )

            return True

        except Exception as e:
            logging.error(f"发送邮件到 {to_email} ({organization_name}) 失败: {e}")

            # 记录发送失败的邮件
            self.record_email_send(
                to_email, False, organization_name, representative_name
            )

            return False

    def record_email_send(
        self,
        email: str,
        success: bool,
        organization_name: str = "",
        representative_name: str = "",
    ):
        """记录邮件发送历史

        Args:
            email: 收件人邮箱
            success: 是否发送成功
            organization_name: 组织名称
            representative_name: 代表者姓名
        """
        try:
            # 获取当前日期作为记录键
            today = datetime.datetime.now().strftime("%Y-%m-%d")

            # 读取现有历史记录
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                history = {}

            # 初始化当天的记录
            if today not in history:
                history[today] = {
                    "total_sent": 0,
                    "success_count": 0,
                    "fail_count": 0,
                    "details": [],
                }

            # 更新统计数据
            history[today]["total_sent"] += 1
            if success:
                history[today]["success_count"] += 1
            else:
                history[today]["fail_count"] += 1

            # 添加详细记录
            history[today]["details"].append(
                {
                    "email": email,
                    "success": success,
                    "organization_name": organization_name,
                    "representative_name": representative_name,
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

            # 保存更新后的历史记录
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logging.error(f"记录邮件发送历史失败: {e}")

    def send_bulk_emails(
        self,
        attachment_path: Optional[str] = None,
        delay_seconds: int = 2,
        max_emails: Optional[int] = None,
        distribute_over_hours: Optional[float] = None,
    ) -> Tuple[int, int]:
        """批量发送邮件

        Args:
            attachment_path: 附件路径
            delay_seconds: 发送间隔秒数
            max_emails: 最大发送邮件数量
            distribute_over_hours: 将发送过程分布在多少小时内，如果设置，会覆盖delay_seconds
        """
        # 获取收件人列表
        recipients = self.fetch_recipients()
        if not recipients:
            logging.error("未获取到收件人信息")
            return 0, 0

        # 如果设置了最大发送数量，则截取列表
        if max_emails is not None and max_emails > 0:
            recipients = recipients[:max_emails]

        total_recipients = len(recipients)
        logging.info(f"开始发送邮件，共 {total_recipients} 个收件人")

        # 如果需要在指定时间内分布发送，计算每封邮件的间隔时间
        if distribute_over_hours is not None and distribute_over_hours > 0:
            # 计算总秒数并均分
            total_seconds = distribute_over_hours * 3600
            if total_recipients > 1:
                # 间隔时间 = 总时间 / (邮件数量 - 1)
                delay_seconds = total_seconds / (total_recipients - 1)
            logging.info(
                f"邮件将在 {distribute_over_hours} 小时内发送完毕，每封邮件间隔 {delay_seconds:.2f} 秒"
            )

        success_count = 0
        fail_count = 0

        for i, (organization_name, representative_name, email) in enumerate(
            recipients, 1
        ):
            try:
                current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logging.info(
                    f"[{i}/{total_recipients}] {current_time} 正在发送邮件到 {email} ({organization_name})..."
                )
                self.send_email(
                    to_email=email,
                    organization_name=organization_name,
                    representative_name=representative_name,
                    attachment_path=attachment_path,
                )
                success_count += 1
                logging.info(f"邮件发送成功: {email}")

                # 添加延迟，避免被邮件服务器标记为垃圾邮件
                if i < total_recipients:
                    next_time = datetime.datetime.now() + datetime.timedelta(
                        seconds=delay_seconds
                    )
                    logging.info(
                        f"等待 {delay_seconds:.2f} 秒后发送下一封邮件... 预计发送时间: {next_time.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    time.sleep(delay_seconds)

            except Exception as e:
                fail_count += 1
                logging.error(f"发送邮件到 {email} 失败: {e}")

        logging.info(f"邮件发送完成。成功: {success_count}, 失败: {fail_count}")
        return success_count, fail_count

    def send_test_emails(
        self,
        test_recipients: List[Tuple[str, str, str]],
        attachment_path: Optional[str] = None,
        delay_seconds: int = 2,
    ):
        """发送测试邮件

        Args:
            test_recipients: 测试收件人列表 [(organization_name, representative_name, email), ...]
            attachment_path: 附件路径
            delay_seconds: 发送间隔秒数
        """
        success_count = 0
        fail_count = 0

        logging.info(f"开始发送测试邮件，共 {len(test_recipients)} 个收件人")

        for i, (organization_name, representative_name, email) in enumerate(
            test_recipients, 1
        ):
            logging.info(f"正在发送第 {i}/{len(test_recipients)} 封测试邮件到: {email}")

            # 为测试邮件生成特殊的跟踪ID
            test_tracking_id = f"TEST_{uuid.uuid4()}"

            success = self.send_email(
                email,
                organization_name,
                representative_name,
                attachment_path,
                test_tracking_id,
            )

            if success:
                success_count += 1
            else:
                fail_count += 1

            # 添加延迟
            if i < len(test_recipients):
                time.sleep(delay_seconds)

        logging.info(f"测试邮件发送完成: 成功 {success_count}, 失败 {fail_count}")
        return success_count, fail_count


def get_test_recipients() -> List[Tuple[str, str, str]]:
    """获取测试邮件收件人列表

    Returns:
        测试收件人列表 [(organization_name, representative_name, email), ...]
    """
    test_recipients = [
        ("CVCTOKYO事业协同组合", "松島力哉", "elton.zheng@u-touch.co.jp"),
        # ("CVCTOKYO事业协同组合", "松島力哉", "yuancw@u-touch.co.jp"),
        # ("CVCTOKYO事业协同组合", "松島力哉", "xiaodi@u-touch.co.jp"),
        # ("CVCTOKYO事业协同组合", "松島力哉", "shirasawa.t@u-touch.co.jp"),
    ]

    print("=== 测试邮件收件人列表 ===")
    for i, (org, rep, email) in enumerate(test_recipients, 1):
        print(f"{i}. {org} - {rep or '(代表者名なし)'} - {email}")
    print()

    return test_recipients


def test_mode():
    """测试模式"""
    print("=" * 50)
    print("           测试模式")
    print(f"           环境: {ENVIRONMENT}")
    print("=" * 50)

    # 获取测试收件人
    test_recipients = get_test_recipients()

    # 确认是否继续
    response = (
        input(f"是否向以上 {len(test_recipients)} 个测试邮箱发送邮件？(y/N): ")
        .strip()
        .lower()
    )
    if response != "y":
        print("测试取消")
        return

    # 从环境变量获取配置参数
    GMAIL_USER = os.getenv("GMAIL_USER", "info@uforward.jp")
    GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD", "pwqltfgitutzdxro")
    GA_TRACKING_ID = os.getenv("GA_TRACKING_ID", "G-YT3RDQ5MGT")
    ATTACHMENT_PATH = "./attachment.pdf"  # 测试时可以不添加附件
    DELAY_SECONDS = 1  # 测试时较短间隔

    # 检查Gmail配置
    if GMAIL_USER == "your_email@gmail.com" or GMAIL_PASSWORD == "your_app_password":
        print("请先在脚本中配置Gmail用户名和应用密码！")
        return

    try:
        # 创建邮件发送器
        sender = EmailSender(GMAIL_USER, GMAIL_PASSWORD, GA_TRACKING_ID)

        # 发送测试邮件
        success_count, fail_count = sender.send_test_emails(
            test_recipients=test_recipients,
            attachment_path=ATTACHMENT_PATH,
            delay_seconds=DELAY_SECONDS,
        )

        print(f"\n测试结果: 成功 {success_count}, 失败 {fail_count}")

    except Exception as e:
        logging.error(f"测试执行失败: {e}")
        print(f"测试失败: {e}")


def scheduled_mode(daily_limit: int = 50):
    """定时发送模式，将指定数量的邮件均匀分布在24小时内发送"""
    print("=" * 50)
    print(f"           定时发送模式 (环境: {ENVIRONMENT})")
    print(f"           每日发送数量: {daily_limit}")
    print("=" * 50)

    # 从环境变量获取配置参数
    GMAIL_USER = os.getenv("GMAIL_USER", "info@uforward.jp")
    GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD", "pwqltfgitutzdxro")
    GA_TRACKING_ID = os.getenv("GA_TRACKING_ID", "G-YT3RDQ5MGT")
    ATTACHMENT_PATH = "./attachment.pdf"  # 如果有附件，请提供文件路径

    # 检查Gmail配置
    if GMAIL_USER == "your_email@gmail.com" or GMAIL_PASSWORD == "your_app_password":
        logging.error("请先配置Gmail用户名和应用密码！")
        return

    try:
        # 创建邮件发送器
        sender = EmailSender(GMAIL_USER, GMAIL_PASSWORD, GA_TRACKING_ID)

        # 将邮件发送均匀分布在24小时内
        hours_to_distribute = 24.0

        # 发送邮件
        sender.send_bulk_emails(
            attachment_path=ATTACHMENT_PATH,
            max_emails=daily_limit,
            distribute_over_hours=hours_to_distribute,
        )

    except Exception as e:
        logging.error(f"程序执行失败: {e}")


def send_daily_report():
    """发送每日邮件发送报告"""
    print("=" * 50)
    print(f"           日报发送模式 (环境: {ENVIRONMENT})")
    print("=" * 50)

    # 从环境变量获取Gmail配置
    GMAIL_USER = os.getenv("GMAIL_USER", "info@uforward.jp")
    GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD", "pwqltfgitutzdxro")

    # 检查Gmail配置
    if not GMAIL_USER or not GMAIL_PASSWORD:
        logging.error("请先配置Gmail用户名和应用密码！")
        return False

    try:
        # 导入邮件报告模块
        from email_report import EmailReporter

        reporter = EmailReporter()
        success = reporter.generate_and_send_report()

        if success:
            logging.info("每日邮件发送报告已成功发送")
        else:
            logging.warning("每日邮件发送报告发送失败")

        return success
    except Exception as e:
        logging.error(f"发送每日报告时出错: {e}")
        return False


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="邮件发送程序")
    parser.add_argument(
        "--mode",
        choices=["normal", "test", "scheduled", "report"],
        default="normal",
        help="运行模式: normal=正常模式, test=测试模式, scheduled=定时发送模式, report=发送日报",
    )
    parser.add_argument(
        "--daily-limit", type=int, default=50, help="定时发送模式下，每天发送的邮件数量"
    )
    args = parser.parse_args()

    if args.mode == "test":
        test_mode()
    elif args.mode == "scheduled":
        scheduled_mode(daily_limit=args.daily_limit)
    elif args.mode == "report":
        send_daily_report()
    else:
        print("=" * 50)
        print(f"           正常模式 (环境: {ENVIRONMENT})")
        print("=" * 50)

        # 从环境变量获取配置参数
        GMAIL_USER = os.getenv("GMAIL_USER", "info@uforward.jp")
        GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD", "pwqltfgitutzdxro")
        GA_TRACKING_ID = os.getenv("GA_TRACKING_ID", "G-YT3RDQ5MGT")
        ATTACHMENT_PATH = "./attachment.pdf"  # 如果有附件，请提供文件路径
        DELAY_SECONDS = 2 if ENVIRONMENT == "production" else 1  # 生产环境间隔长一些
        MAX_EMAILS = None  # 限制发送邮件数量，None表示发送全部

        # 检查Gmail配置
        if (
            GMAIL_USER == "your_email@gmail.com"
            or GMAIL_PASSWORD == "your_app_password"
        ):
            print("请先配置Gmail用户名和应用密码！")
            print("注意：需要使用Gmail应用密码，不是账户密码")
            print("应用密码设置：https://support.google.com/accounts/answer/185833")
            return

        try:
            # 创建邮件发送器
            sender = EmailSender(GMAIL_USER, GMAIL_PASSWORD, GA_TRACKING_ID)

            # 发送邮件
            sender.send_bulk_emails(
                attachment_path=ATTACHMENT_PATH,
                delay_seconds=DELAY_SECONDS,
                max_emails=MAX_EMAILS,
            )

        except Exception as e:
            logging.error(f"程序执行失败: {e}")


if __name__ == "__main__":
    main()
