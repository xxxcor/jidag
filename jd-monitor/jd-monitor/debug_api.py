#!/usr/bin/env python3
"""
京东 API 调试脚本
用于诊断价格和库存接口的问题
"""

import httpx
import asyncio
import json
import sys

# 测试商品 SKU（你可以换成自己监控的商品）
TEST_SKU = "100268293328"

async def test_network():
    """测试基本网络连接"""
    print("\n" + "=" * 50)
    print("1. 测试基本网络连接")
    print("=" * 50)
    
    test_urls = [
        ("京东主站", "https://www.jd.com"),
        ("商品详情页", f"https://item.jd.com/{TEST_SKU}.html"),
        ("移动端商品页", f"https://item.m.jd.com/product/{TEST_SKU}.html"),
    ]
    
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for name, url in test_urls:
            try:
                r = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                print(f"✅ {name}: 状态码={r.status_code}, 长度={len(r.text)} 字节")
            except Exception as e:
                print(f"❌ {name}: {type(e).__name__} - {e}")

async def test_price_api():
    """测试价格 API"""
    print("\n" + "=" * 50)
    print("2. 测试价格 API")
    print("=" * 50)
    
    price_urls = [
        ("p.3.cn", f"https://p.3.cn/prices/mgets?skuIds=J_{TEST_SKU}"),
        ("pe.3.cn", f"https://pe.3.cn/prices/mgets?skuIds=J_{TEST_SKU}"),
        ("cd.jd.com", f"https://cd.jd.com/prices/mgets?skuIds=J_{TEST_SKU}"),
    ]
    
    async with httpx.AsyncClient(timeout=15) as client:
        for name, url in price_urls:
            try:
                r = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://item.jd.com/"
                })
                print(f"\n📌 {name}")
                print(f"   状态码: {r.status_code}")
                print(f"   响应体: {r.text[:300]}")
                
                if r.status_code == 200:
                    try:
                        data = r.json()
                        if data and len(data) > 0:
                            price = data[0].get("p", "无")
                            print(f"   ✅ 价格: ¥{price}")
                    except:
                        print(f"   ⚠️ 非 JSON 格式")
            except Exception as e:
                print(f"❌ {name}: {type(e).__name__} - {e}")

async def test_stock_api():
    """测试库存 API"""
    print("\n" + "=" * 50)
    print("3. 测试库存 API")
    print("=" * 50)
    
    stock_urls = [
        ("c0.3.cn", f"https://c0.3.cn/stocks?skuId={TEST_SKU}&area=1_72_4137_0&venderId=0&cat=0,0,0"),
        ("cd.jd.com", f"https://cd.jd.com/stocks?skuId={TEST_SKU}&area=1_72_4137_0&venderId=0&cat=0,0,0"),
    ]
    
    async with httpx.AsyncClient(timeout=15) as client:
        for name, url in stock_urls:
            try:
                r = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": f"https://item.jd.com/{TEST_SKU}.html"
                })
                print(f"\n📌 {name}")
                print(f"   状态码: {r.status_code}")
                print(f"   响应体: {r.text[:300]}")
                
                if r.status_code == 200:
                    try:
                        data = r.json()
                        state = data.get("StockState", "无")
                        name_str = data.get("StockStateName", "无")
                        print(f"   ✅ 库存状态: {state} ({name_str})")
                    except:
                        print(f"   ⚠️ 非 JSON 格式")
            except Exception as e:
                print(f"❌ {name}: {type(e).__name__} - {e}")

async def test_item_page_parsing():
    """测试从商品页面解析信息"""
    print("\n" + "=" * 50)
    print("4. 测试页面解析")
    print("=" * 50)
    
    import re
    
    url = f"https://item.jd.com/{TEST_SKU}.html"
    
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        try:
            r = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9",
            })
            
            print(f"状态码: {r.status_code}")
            html = r.text
            
            # 提取标题
            title_match = re.search(r'<title>(.*?)</title>', html)
            if title_match:
                print(f"商品标题: {title_match.group(1)[:50]}...")
            
            # 检查库存关键词
            keywords = ["无货", "有货", "现货", "缺货", "预约", "抢购", "加入购物车", "到货通知"]
            for kw in keywords:
                if kw in html:
                    print(f"✅ 发现关键词: {kw}")
            
            # 检查页面中是否有价格相关的 JavaScript 配置
            if "pageConfig" in html:
                print("✅ 发现 pageConfig")
            if "window.initData" in html:
                print("✅ 发现 initData")
                
        except Exception as e:
            print(f"❌ 页面请求失败: {type(e).__name__} - {e}")

async def main():
    print("=" * 50)
    print("京东 API 调试工具")
    print(f"测试商品 SKU: {TEST_SKU}")
    print("=" * 50)
    
    await test_network()
    await test_price_api()
    await test_stock_api()
    await test_item_page_parsing()
    
    print("\n" + "=" * 50)
    print("调试完成！请将以上结果发给我分析。")
    print("=" * 50)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        TEST_SKU = sys.argv[1]
    asyncio.run(main())
