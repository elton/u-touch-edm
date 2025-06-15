#!/usr/bin/env python3
"""
字体测试工具 - 验证matplotlib字体配置
用于检查Docker容器中是否正确安装了中文字体
"""

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

def list_available_fonts():
    """列出系统可用字体"""
    print("🔍 检查系统可用字体...")
    
    all_fonts = [f.name for f in fm.fontManager.ttflist]
    unique_fonts = sorted(set(all_fonts))
    
    # 筛选中文相关字体
    chinese_fonts = [font for font in unique_fonts 
                    if any(keyword in font.lower() for keyword in 
                          ['noto', 'cjk', 'han', 'hei', 'song', 'kai', 'liberation'])]
    
    print(f"📊 总字体数量: {len(unique_fonts)}")
    print(f"🈳 中文相关字体: {len(chinese_fonts)}")
    
    if chinese_fonts:
        print("\n✅ 找到的中文字体:")
        for font in chinese_fonts[:10]:  # 只显示前10个
            print(f"  • {font}")
        if len(chinese_fonts) > 10:
            print(f"  ... 还有 {len(chinese_fonts) - 10} 个字体")
    else:
        print("\n❌ 未找到中文字体")
    
    return chinese_fonts

def test_font_rendering():
    """测试字体渲染效果"""
    print("\n🎨 测试字体渲染...")
    
    try:
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # 测试文本
        test_texts = [
            "English Text - Arial",
            "中文测试 - 地区分布",
            "日本語テスト - 成功率",
            "한국어 테스트 - 统计图表"
        ]
        
        y_positions = [0.8, 0.6, 0.4, 0.2]
        
        for text, y in zip(test_texts, y_positions):
            ax.text(0.1, y, text, fontsize=14, transform=ax.transAxes)
        
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_title("字体渲染测试", fontsize=16, fontweight='bold')
        ax.axis('off')
        
        # 保存测试图片（如果需要的话）
        # plt.savefig('/app/font_test.png', dpi=100, bbox_inches='tight')
        
        plt.close(fig)
        print("✅ 字体渲染测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 字体渲染测试失败: {e}")
        return False

def get_current_font_config():
    """获取当前matplotlib字体配置"""
    print("\n⚙️ 当前matplotlib字体配置:")
    
    sans_serif = plt.rcParams.get('font.sans-serif', [])
    print(f"  sans-serif: {sans_serif}")
    
    unicode_minus = plt.rcParams.get('axes.unicode_minus', True)
    print(f"  unicode_minus: {unicode_minus}")
    
    default_font = fm.findfont(fm.FontProperties())
    print(f"  默认字体路径: {default_font}")

def main():
    """主测试函数"""
    print("🚀 开始字体环境检测...\n")
    
    # 1. 列出可用字体
    chinese_fonts = list_available_fonts()
    
    # 2. 显示当前配置
    get_current_font_config()
    
    # 3. 测试渲染
    rendering_ok = test_font_rendering()
    
    # 4. 总结
    print("\n📋 检测总结:")
    if chinese_fonts:
        print("✅ 中文字体: 已安装")
    else:
        print("❌ 中文字体: 未安装")
        
    if rendering_ok:
        print("✅ 字体渲染: 正常")
    else:
        print("❌ 字体渲染: 异常")
    
    # 5. 建议
    if not chinese_fonts:
        print("\n💡 建议:")
        print("  1. 确保Dockerfile中安装了字体包:")
        print("     fonts-noto-cjk fonts-wqy-microhei")
        print("  2. 运行 fc-cache -fv 更新字体缓存")
        print("  3. 重启容器")

if __name__ == "__main__":
    main()