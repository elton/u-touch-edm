#!/usr/bin/env python3
"""
测试动态分页功能
验证爬虫是否能正确跟随"下一页"链接

作者: Claude
日期: 2025-07-31
"""

from gai_rou_scraper import GaiRouScraper, color_log, Fore, Back, Style

def test_next_page_detection():
    """测试下一页链接检测功能"""
    
    print(f"\n{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}")
    print(f"{Fore.WHITE}{Back.BLUE}      🔍 测试动态分页功能      {Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}\n")
    
    scraper = GaiRouScraper()
    
    # 测试前几页的链接检测
    test_urls = [
        "https://www.gai-rou.com/shien_list/",
        "https://www.gai-rou.com/shien_list/page/2/",
        "https://www.gai-rou.com/shien_list/page/3/"
    ]
    
    for i, url in enumerate(test_urls, 1):
        color_log.processing(f"测试第 {i} 个URL: {url}")
        
        soup = scraper.get_page_content(url)
        if soup:
            # 检查机构数量
            organizations = scraper.extract_organization_list(soup)
            color_log.found(f"发现 {len(organizations)} 个机构")
            
            # 检查下一页链接
            next_url = scraper.get_next_page_url(soup)
            if next_url:
                color_log.success(f"✅ 成功找到下一页: {next_url}")
            else:
                color_log.warning("⚠️ 未找到下一页链接")
        else:
            color_log.error("❌ 获取页面失败")
        
        print()  # 空行分隔

def test_limited_pagination():
    """测试有限的分页爬取（只爬取前几页）"""
    
    print(f"{Fore.YELLOW}🧪 测试有限分页爬取 (前3页){Style.RESET_ALL}\n")
    
    scraper = GaiRouScraper()
    
    # 临时修改爬取逻辑，只处理前3页
    current_url = scraper.list_url
    page_number = 1
    max_test_pages = 3
    
    total_found = 0
    
    while current_url and page_number <= max_test_pages:
        color_log.processing(f"测试第 {page_number}/{max_test_pages} 页: {current_url}")
        
        soup = scraper.get_page_content(current_url)
        if not soup:
            color_log.error(f"获取第 {page_number} 页失败")
            break
        
        # 提取机构列表
        organizations = scraper.extract_organization_list(soup)
        color_log.found(f"第 {page_number} 页发现 {len(organizations)} 个机构")
        total_found += len(organizations)
        
        # 显示前3个机构名称
        if organizations:
            print(f"{Fore.WHITE}  前3个机构:{Style.RESET_ALL}")
            for j, org in enumerate(organizations[:3], 1):
                print(f"{Fore.CYAN}    {j}. {org['name'][:80]}...{Style.RESET_ALL}")
        
        # 查找下一页
        next_url = scraper.get_next_page_url(soup)
        if next_url and page_number < max_test_pages:
            current_url = next_url
            page_number += 1
        else:
            if page_number >= max_test_pages:
                color_log.info(f"已达到测试页数限制 ({max_test_pages} 页)")
            else:
                color_log.info("未找到下一页链接")
            break
        
        print()  # 空行分隔
    
    print(f"\n{Fore.WHITE}{Back.GREEN} 📊 测试结果 {Style.RESET_ALL}")
    print(f"{Fore.GREEN}测试页数: {page_number} 页{Style.RESET_ALL}")
    print(f"{Fore.CYAN}发现机构总数: {total_found} 个{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}平均每页: {total_found/page_number:.1f} 个机构{Style.RESET_ALL}")

if __name__ == "__main__":
    try:
        # 测试下一页检测
        test_next_page_detection()
        
        # 测试有限分页
        test_limited_pagination()
        
        print(f"\n{Fore.WHITE}{Back.GREEN} 🎉 分页测试完成! {Style.RESET_ALL}")
        
    except Exception as e:
        color_log.error(f"测试过程中出错: {e}")
        exit(1)