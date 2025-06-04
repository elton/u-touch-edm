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

    def connect_to_database(self) -> pymysql.connections.Connection:
        """连接到MySQL数据库"""
        try:
            connection = pymysql.connect(
                host="localhost",
                database="edm",
                user="edm_readonly_user",
                password="EdmRead2024!@#",
                charset="utf8mb4",
            )
            logging.info("成功连接到数据库")
            return connection
        except pymysql.Error as e:
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
            <div class="greeting">{display_name}様</div>
        </div>
        
        <div class="content">
            <p>お世話になっております。<a href="https://u-touch.co.jp/" style="text-decoration: none;"><span class="company-name">㈱ユー・タチ</span></a>の白澤です。</p>
            
            <p>先ほど、お忙しいところ電話をご対応していただき、ありがとうございます。</p>
            
            <div class="highlight">
                <p><strong>弊社は特定技能支援機関向けに、一括管理用ITツールサービスを提供しております。</strong></p>
                <p>特に、ビザ申請上に更新期間知らせ、提出書類作成、オンライン申請、定期管理記録、顧客管理など煩雑な業務を簡単に管理し、円滑に業務が進むようなシステムなります。</p>
            </div>
            
            <p>添付にて、説明資料を送り致します。<br>
            ご査収ください。</p>
            
            <p>また、機能がたくさんあるので、可能であれば一度お時間を頂きご挨拶も含めて<br>
            システムの説明と業界の情報もご提供させていただければ幸いです。</p>
            
            <!-- 追加: CTA按钮，便于跟踪点击事件 -->
            <p style="text-align: center; margin: 30px 0;">
                <a href="https://u-touch.co.jp/contact" 
                   class="cta-button"
                   onclick="if(typeof gtag === 'function') gtag('event', 'click', {{'event_category': 'email', 'event_label': 'contact_button', 'organization': '{{organization_name}}', 'tracking_id': '{{tracking_id}}'}})">
                   お問い合わせはこちら
                </a>
            </p>
            
            <p>何卒、宜しくお願い致します。</p>
        </div>
        
        <div class="signature">
            <div class="company-name"><a href="https://u-touch.co.jp/" style="text-decoration: none; color: #0066cc;">㈱ユー・タチ</a></div>
            <div>白澤</div>
            <div class="contact-info">
                <a href="mailto:shirasawa.t@u-touch.co.jp" 
                   style="color: #0066cc;"
                   onclick="if(typeof gtag === 'function') gtag('event', 'click', {{'event_category': 'email', 'event_label': 'email_link', 'organization': '{organization_name}', 'tracking_id': '{tracking_id}'}});">
                   shirasawa.t@u-touch.co.jp
                </a>
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

            # 创建邮件 - 使用混合类型，支持HTML和附件
            msg = MIMEMultipart()
            msg["From"] = self.gmail_user
            msg["To"] = to_email
            msg["Subject"] = "特定技能支援機関向けITツールサービスのご案内"

            # 创建alternative部分用于纯文本和HTML版本
            alt_part = MIMEMultipart("alternative")

            # 添加纯文本版本（作为备用）
            text_content = "お世話になっております。㈱ユー・タチの白澤です。\n\n特定技能支援機関向けITツールサービスのご案内\n\nお問い合わせ: https://u-touch.co.jp/contact"
            alt_part.attach(MIMEText(text_content, "plain", "utf-8"))

            # HTML邮件正文
            html_body = self.create_email_content(
                organization_name, representative_name, tracking_id
            )
            alt_part.attach(MIMEText(html_body, "html", "utf-8"))

            # 将alternative部分添加到主消息
            msg.attach(alt_part)

            # 添加附件（如果提供）
            if attachment_path and os.path.exists(attachment_path):
                with open(attachment_path, "rb") as attachment:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment.read())

                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename= {os.path.basename(attachment_path)}",
                )
                msg.attach(part)

            # 配置SMTP服务器 - 使用STARTTLS适用于Gmail端口587
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.ehlo()
            server.starttls()
            server.ehlo()

            # 登录
            server.login(self.gmail_user, self.gmail_password)

            text = msg.as_string()
            server.sendmail(self.gmail_user, to_email, text)
            server.quit()

            logging.info(
                f"邮件成功发送到: {to_email} ({organization_name}) - 跟踪ID: {tracking_id}"
            )
            return True

        except Exception as e:
            logging.error(f"发送邮件失败 {to_email}: {e}")
            return False

    def send_bulk_emails(
        self,
        attachment_path: Optional[str] = None,
        delay_seconds: int = 2,
        max_emails: Optional[int] = None,
    ):
        """批量发送邮件"""
        recipients = self.fetch_recipients()

        if max_emails:
            recipients = recipients[:max_emails]

        success_count = 0
        fail_count = 0

        logging.info(f"开始发送邮件，共 {len(recipients)} 个收件人")

        for i, (organization_name, representative_name, email) in enumerate(
            recipients, 1
        ):
            logging.info(f"正在发送第 {i}/{len(recipients)} 封邮件到: {email}")

            success = self.send_email(
                email, organization_name, representative_name, attachment_path
            )

            if success:
                success_count += 1
            else:
                fail_count += 1

            # 添加延迟以避免被Gmail限制
            if i < len(recipients):  # 最后一封邮件后不需要延迟
                time.sleep(delay_seconds)

        logging.info(f"邮件发送完成: 成功 {success_count}, 失败 {fail_count}")

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
        ("CVCTOKYO事业协同组合", "松島力哉", "shirasawa.t@u-touch.co.jp"),
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

    # 配置参数
    GMAIL_USER = "info@uforward.jp"  # 替换为您的Gmail地址
    GMAIL_PASSWORD = "pwqltfgitutzdxro"  # 替换为您的Gmail应用密码
    GA_TRACKING_ID = "G-YT3RDQ5MGT"  # Google Analytics 4 跟踪ID
    ATTACHMENT_PATH = "./attachment.pdf"  # 测试时可以不添加附件
    DELAY_SECONDS = 1  # 测试时较短间隔

    # 检查Gmail配置
    if GMAIL_USER == "your_email@gmail.com" or GMAIL_PASSWORD == "your_app_password":
        print("请先在脚本中配置Gmail用户名和应用密码！")
        return

    # 检查GA配置
    if GA_TRACKING_ID == "G-YT3RDQ5MGT":
        print("注意：当前使用的是示例GA跟踪ID，请替换为您实际的GA ID")

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


def main():
    """主函数"""
    # 配置参数
    GMAIL_USER = "info@uforward.jp"  # 替换为您的Gmail地址
    GMAIL_PASSWORD = "pwqltfgitutzdxro"  # 替换为您的Gmail应用密码
    GA_TRACKING_ID = "G-YT3RDQ5MGT"  # Google Analytics 4 跟踪ID
    ATTACHMENT_PATH = "./attachment.pdf"  # 如果有附件，请提供文件路径
    DELAY_SECONDS = 2  # 发送邮件间隔秒数
    MAX_EMAILS = None  # 限制发送邮件数量，None表示发送全部

    # 检查Gmail配置
    if GMAIL_USER == "your_email@gmail.com" or GMAIL_PASSWORD == "your_app_password":
        print("请先配置Gmail用户名和应用密码！")
        print("注意：需要使用Gmail应用密码，不是账户密码")
        print("应用密码设置：https://support.google.com/accounts/answer/185833")
        return

    # 检查GA配置
    if GA_TRACKING_ID == "G-YT3RDQ5MGT":
        print("注意：当前使用的是示例GA跟踪ID，请替换为您实际的GA ID")

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
    import sys

    # 检查是否为测试模式
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_mode()
    else:
        print("使用方法:")
        print("  正常模式: python script.py")
        print("  测试模式: python script.py test")
        print()

        mode = input("选择模式 (1: 正常模式, 2: 测试模式): ").strip()
        if mode == "2":
            test_mode()
        elif mode == "1":
            main()
        else:
            print("无效选择")
