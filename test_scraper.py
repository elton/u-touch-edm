#!/usr/bin/env python3
"""
GAI-ROU.COM 爬虫测试脚本
测试单个页面的数据提取功能

作者: Claude
日期: 2025-07-31
"""

from gai_rou_scraper import GaiRouScraper
import json

def test_single_organization():
    """测试单个机构页面的数据提取"""
    scraper = GaiRouScraper()
    
    # 测试详情页提取
    test_url = "https://www.gai-rou.com/shien/33127/"
    print(f"测试详情页: {test_url}")
    
    detail_info = scraper.extract_organization_detail(test_url, "33127")
    print("提取的详情信息:")
    print(json.dumps(detail_info, indent=2, ensure_ascii=False))
    
    # 特别检查网站字段
    if detail_info.get('website'):
        print(f"\n✅ 成功提取网站: {detail_info['website']}")
    else:
        print(f"\n⚠️  未找到网站信息")
    
    return detail_info

def test_list_page():
    """测试列表页的机构链接提取"""
    scraper = GaiRouScraper()
    
    # 测试列表页提取
    list_url = "https://www.gai-rou.com/shien_list/"
    print(f"\n测试列表页: {list_url}")
    
    soup = scraper.get_page_content(list_url)
    if soup:
        organizations = scraper.extract_organization_list(soup)
        print(f"找到 {len(organizations)} 个机构链接")
        
        # 显示前5个
        for i, org in enumerate(organizations[:5]):
            print(f"{i+1}. {org['name']} - {org['detail_url']}")
    
    return organizations[:5] if soup else []

def test_pagination():
    """测试分页功能"""
    scraper = GaiRouScraper()
    
    total_pages = scraper.get_total_pages()
    print(f"\n总页数: {total_pages}")
    
    return total_pages

if __name__ == "__main__":
    print("=== GAI-ROU.COM 爬虫测试 ===")
    
    # 测试详情页提取
    detail_info = test_single_organization()
    
    # 测试列表页提取
    organizations = test_list_page()
    
    # 测试分页
    total_pages = test_pagination()
    
    print(f"\n=== 测试总结 ===")
    print(f"详情页提取字段数: {len(detail_info)}")
    print(f"列表页机构数量: {len(organizations)}")
    print(f"总页数: {total_pages}")
    
    if detail_info and organizations and total_pages > 0:
        print("✅ 所有测试通过!")
    else:
        print("❌ 部分测试失败，请检查代码")