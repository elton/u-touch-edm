#!/usr/bin/env python3
"""
仅测试机构名称标准化功能（无需数据库连接）

作者: Claude
日期: 2025-07-31
"""

from gai_rou_scraper import GaiRouScraper

def test_name_normalization():
    """测试机构名称标准化功能"""
    scraper = GaiRouScraper()
    
    test_cases = [
        # 日文公司名称测试
        ("株式会社テスト", "テスト"),
        ("テスト株式会社", "テスト"),
        ("テスト協同組合", "テスト"),
        ("一般社団法人テスト機関", "テスト機関"),
        ("テスト(株)", "テスト"),
        ("北陸国際協同組合", "北陸国際"),
        
        # 英文公司名称测试
        ("Test Corp", "test"),
        ("Test Co.,Ltd", "test"),
        ("ABC Inc", "abc"),
        ("XYZ LLC", "xyz"),
        
        # 边界情况测试
        ("", ""),
        ("   ", ""),
        ("株式会社", ""),
        ("Test   ", "test"),
        ("テスト　株式会社", "テスト"),  # 全角空格
        
        # 复杂案例
        ("協同組合北陸国際", "北陸国際"),
        ("株式会社ABC商事", "abc商事"),
    ]
    
    print("=== 机构名称标准化测试 ===")
    all_passed = True
    
    for original, expected in test_cases:
        normalized = scraper.normalize_organization_name(original)
        if normalized == expected:
            print(f"✅ '{original}' -> '{normalized}'")
        else:
            print(f"❌ '{original}' -> '{normalized}' (期望: '{expected}')")
            all_passed = False
    
    print(f"\n测试结果: {'✅ 全部通过' if all_passed else '❌ 部分失败'}")
    return all_passed

if __name__ == "__main__":
    test_name_normalization()