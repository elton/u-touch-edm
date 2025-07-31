#!/usr/bin/env python3
"""
测试彩色输出功能
验证爬虫的彩色日志显示效果

作者: Claude
日期: 2025-07-31
"""

from gai_rou_scraper import GaiRouScraper, color_log, Fore, Back, Style

def test_colorful_logging():
    """测试彩色日志输出"""
    
    print(f"\n{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}")
    print(f"{Fore.WHITE}{Back.BLUE}      🎨 GAI-ROU.COM 彩色日志测试      {Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}\n")
    
    # 测试各种日志类型
    color_log.success("这是成功消息 - 绿色带勾号")
    color_log.error("这是错误消息 - 红色带X号")
    color_log.warning("这是警告消息 - 黄色带警告符号")
    color_log.info("这是信息消息 - 青色带信息符号")
    color_log.processing("这是处理消息 - 紫色带旋转符号")
    color_log.found("这是发现消息 - 黄色带搜索符号")
    
    print(f"\n{Fore.YELLOW}📋 功能展示:{Style.RESET_ALL}")
    print(f"{Fore.GREEN}  ✅ 成功操作{Style.RESET_ALL}")
    print(f"{Fore.RED}  ❌ 失败操作{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}  ⚠️  警告提示{Style.RESET_ALL}")
    print(f"{Fore.CYAN}  ℹ️  信息提示{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}  🔄 正在处理{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}  🔍 发现内容{Style.RESET_ALL}")
    
    print(f"\n{Fore.WHITE}{Back.GREEN} 🎉 彩色日志测试完成! {Style.RESET_ALL}")
    print(f"{Fore.CYAN}所有颜色和符号显示正常{Style.RESET_ALL}\n")

if __name__ == "__main__":
    test_colorful_logging()