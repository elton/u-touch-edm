import smtplib


def test_gmail_connection():
    # 要测试的Gmail凭据
    gmail_user = "info@uforward.jp"
    gmail_password = "pwqltfgitutzdxro"

    try:
        # 连接到Gmail SMTP服务器
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.ehlo()

        # 尝试登录
        server.login(gmail_user, gmail_password)
        print("连接成功！凭据有效。")
        server.quit()
        return True
    except Exception as e:
        print(f"连接失败: {e}")
        return False


# 运行测试
test_gmail_connection()
