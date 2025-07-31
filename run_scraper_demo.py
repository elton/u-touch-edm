#!/usr/bin/env python3
"""
GAI-ROU.COM 爬虫演示脚本
安全地运行爬虫，处理少量页面进行演示

作者: Claude
日期: 2025-07-31
"""

from gai_rou_scraper import GaiRouScraper
import logging

def run_demo_scrape(max_pages=2, max_orgs_per_page=2):
    """运行演示爬取，限制页面数和每页处理的机构数量"""
    
    print(f"=== GAI-ROU.COM 爬虫演示 ===")
    print(f"将处理最多 {max_pages} 页，每页最多 {max_orgs_per_page} 个机构")
    print()
    
    scraper = GaiRouScraper()
    saved_count = 0
    skipped_count = 0
    
    # 使用动态分页演示
    current_url = scraper.list_url
    page_number = 1
    
    while current_url and page_number <= max_pages:
        try:
            page_url = current_url
                
            print(f"📄 处理第 {page_number} 页: {page_url}")
            
            soup = scraper.get_page_content(page_url)
            if not soup:
                print(f"❌ 获取第 {page_number} 页失败")
                break
            
            # 提取机构列表
            organizations = scraper.extract_organization_list(soup)
            print(f"🔍 发现 {len(organizations)} 个机构")
            
            # 限制处理数量
            limited_orgs = organizations[:max_orgs_per_page]
            print(f"📋 处理前 {len(limited_orgs)} 个机构")
            
            for i, org in enumerate(limited_orgs, 1):
                try:
                    print(f"  {i}. 正在处理: {org['name']}")
                    
                    # 获取详细信息
                    detail_info = scraper.extract_organization_detail(org['detail_url'], org['id'])
                    
                    if detail_info:
                        print(f"     ✅ 提取成功")
                        print(f"     📋 登録番号: {detail_info.get('registration_number', 'N/A')}")
                        print(f"     🏢 机构名称: {detail_info.get('organization_name', org['name'])}")
                        print(f"     📍 地址: {detail_info.get('address', 'N/A')}")
                        print(f"     🎯 支援类型: {detail_info.get('support_type', 'N/A')}")
                        print(f"     🌐 网站: {detail_info.get('website', 'N/A')}")
                        
                        # 检查机构是否已存在
                        exists = scraper.check_organization_exists({
                            'organization_name': detail_info.get('organization_name', org['name']),
                            'registration_number': detail_info.get('registration_number', '')
                        })
                        
                        if exists:
                            print(f"     🔄 状态: 已存在，将跳过")
                            skipped_count += 1
                        else:
                            print(f"     💾 状态: 新机构，将保存")
                            saved_count += 1
                        print()
                    else:
                        print(f"     ❌ 提取失败")
                        
                except Exception as e:
                    print(f"     ❌ 处理机构失败: {e}")
                    continue
            
            print(f"✅ 第 {page_number} 页处理完成")
            
            # 查找下一页
            next_url = scraper.get_next_page_url(soup)
            if next_url and page_number < max_pages:
                current_url = next_url
                page_number += 1
                print(f"🔄 准备处理下一页 (第 {page_number} 页)\n")
            else:
                if page_number >= max_pages:
                    print(f"ℹ️ 已达到演示页数限制 ({max_pages} 页)")
                else:
                    print("ℹ️ 未找到下一页链接")
                break
            
        except Exception as e:
            print(f"❌ 处理第 {page_number} 页失败: {e}")
            break
    
    print("🎉 演示完成!")
    print(f"\n📊 统计信息:")
    print(f"   💾 新机构: {saved_count}")
    print(f"   🔄 已存在: {skipped_count}")
    print(f"   📈 总处理: {saved_count + skipped_count}")

if __name__ == "__main__":
    # 设置日志级别为WARNING以减少输出
    logging.getLogger().setLevel(logging.WARNING)
    
    run_demo_scrape(max_pages=2, max_orgs_per_page=2)