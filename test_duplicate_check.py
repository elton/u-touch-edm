#!/usr/bin/env python3
"""
测试重复检查功能
验证机构名称标准化和重复检测逻辑

作者: Claude
日期: 2025-07-31
"""

from gai_rou_scraper import GaiRouScraper

def test_name_normalization():
    """测试机构名称标准化功能"""
    scraper = GaiRouScraper()
    
    test_cases = [
        ("株式会社テスト", "テスト"),
        ("テスト株式会社", "テスト"),
        ("テスト協同組合", "テスト"),
        ("一般社団法人テスト", "テスト"),
        ("テスト(株)", "テスト"),
        ("Test Corp", "test"),
        ("Test Co.,Ltd", "test"),
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
    
    return all_passed

def test_duplicate_detection():
    """测试重复检测功能"""
    scraper = GaiRouScraper()
    
    print("\n=== 重复检测测试 ===")
    
    # 测试数据
    test_org = {
        'organization_name': '北陸国際協同組合',
        'registration_number': '20登-004748',
        'address': '富山県富山市本宮2番地106',
        'phone_number': '0764811132',
        'support_type': 'both',
        'website': 'https://ascope.net/foreignemployment/'
    }
    
    try:
        # 第一次保存
        print("第一次保存机构...")
        result1 = scraper.save_organization(test_org)
        print(f"第一次保存结果: {'成功' if result1 else '失败'}")
        
        # 第二次保存（应该被跳过）
        print("\n第二次保存相同机构...")
        result2 = scraper.save_organization(test_org)
        print(f"第二次保存结果: {'成功(被跳过)' if result2 else '失败'}")
        
        # 测试变体名称
        test_org_variant = test_org.copy()
        test_org_variant['organization_name'] = '北陸国際協同組合株式会社'  # 添加后缀
        
        print("\n保存名称变体...")
        result3 = scraper.save_organization(test_org_variant)
        print(f"变体保存结果: {'成功(被跳过)' if result3 else '失败'}")
        
        return result1 and result2 and result3
        
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        return False

def test_check_organization_exists():
    """测试机构存在检查功能"""
    scraper = GaiRouScraper()
    
    print("\n=== 机构存在检查测试 ===")
    
    test_org = {
        'organization_name': '北陸国際協同組合',
        'registration_number': '20登-004748'
    }
    
    try:
        exists = scraper.check_organization_exists(test_org)
        print(f"机构是否存在: {'是' if exists else '否'}")
        
        # 测试不存在的机构
        non_existing_org = {
            'organization_name': '不存在的测试机构12345',
            'registration_number': '99登-999999'
        }
        
        not_exists = scraper.check_organization_exists(non_existing_org)
        print(f"不存在机构检查: {'存在(错误)' if not_exists else '不存在(正确)'}")
        
        return not not_exists  # 应该返回False（不存在）
        
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        return False

if __name__ == "__main__":
    print("=== GAI-ROU.COM 重复检查测试 ===\n")
    
    # 测试名称标准化
    norm_test = test_name_normalization()
    
    # 测试重复检测
    dup_test = test_duplicate_detection()
    
    # 测试存在检查
    exist_test = test_check_organization_exists()
    
    print(f"\n=== 测试总结 ===")
    print(f"名称标准化: {'✅ 通过' if norm_test else '❌ 失败'}")
    print(f"重复检测: {'✅ 通过' if dup_test else '❌ 失败'}")
    print(f"存在检查: {'✅ 通过' if exist_test else '❌ 失败'}")
    
    if norm_test and dup_test and exist_test:
        print("\n🎉 所有测试通过!")
    else:
        print("\n⚠️ 部分测试失败，请检查代码")