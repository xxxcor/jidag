#!/usr/bin/env python3
"""
带 Cookie 测试价格接口
"""

import httpx
import json
import sys
import os

TEST_SKU = "100268293328"

def load_cookies():
    """加载 Cookie"""
    cookie_file = "config/cookies.txt"
    if os.path.exists(cookie_file):
        with open(cookie_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    return line
    return ""

def test():
    cookies = load_cookies()
    if not cookies:
        print("❌ 无法加载 Cookie，请确保 config/cookies.txt 存在")
        return
    
    print(f"测试商品: {TEST_SKU}")
    print(f"Cookie 长度: {len(cookies)} 字符")
    print("=" * 50)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Cookie": cookies,
    }
    
    # 测试1: item-soa 接口（带 Cookie）
    print("\n📌 测试1: item-soa.jd.com/getWareBusiness (带Cookie)")
    try:
        url = "https://item-soa.jd.com/getWareBusiness"
        params = {
            "skuId": TEST_SKU,
            "cat": "652,654,831",
            "area": "1_72_4137_0",
            "shopId": "1000627459",
            "venderId": "1000627459",
        }
        r = httpx.get(url, params=params, headers={
            **headers,
            "Referer": f"https://item.jd.com/{TEST_SKU}.html",
        }, timeout=15)
        
        print(f"   状态码: {r.status_code}")
        if r.status_code == 200:
            try:
                data = r.json()
                if "price" in data:
                    print(f"   ✅ 价格: {data['price']}")
                if "stockInfo" in data:
                    print(f"   ✅ 库存: {data['stockInfo']}")
                if "price" not in data and "stockInfo" not in data:
                    print(f"   响应: {json.dumps(data, ensure_ascii=False)[:400]}")
            except:
                print(f"   响应 (非JSON): {r.text[:300]}")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
    
    # 测试2: api.m.jd.com (带 Cookie)
    print("\n📌 测试2: api.m.jd.com (带Cookie)")
    try:
        url = "https://api.m.jd.com/client.action"
        params = {
            "functionId": "wareBusiness",
            "appid": "item-v3",
            "body": json.dumps({
                "skuId": TEST_SKU,
                "area": "1_72_4137_0",
                "shopId": "1000627459",
            }),
            "client": "wh5",
            "clientVersion": "1.0.0",
        }
        r = httpx.get(url, params=params, headers={
            **headers,
            "Referer": "https://item.m.jd.com/",
        }, timeout=15)
        
        print(f"   状态码: {r.status_code}")
        try:
            data = r.json()
            print(f"   响应: {json.dumps(data, ensure_ascii=False)[:400]}")
        except:
            print(f"   响应: {r.text[:300]}")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
    
    # 测试3: 从登录后的页面获取数据
    print("\n📌 测试3: 登录后的商品页面")
    try:
        url = f"https://item.jd.com/{TEST_SKU}.html"
        r = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        
        print(f"   状态码: {r.status_code}")
        html = r.text
        
        # 检查是否登录
        if "jd_username" in cookies or "pin" in cookies.lower():
            print("   Cookie 中有用户信息")
        
        # 查找价格区域
        import re
        price_area = re.search(r'class="p-price"[^>]*>(.*?)</div>', html, re.DOTALL)
        if price_area:
            print(f"   价格区域HTML: {price_area.group(1)[:200]}")
        
        # 查找库存关键词
        keywords = ["无货", "有货", "现货", "缺货", "加入购物车"]
        found = [kw for kw in keywords if kw in html]
        print(f"   发现关键词: {found}")
        
    except Exception as e:
        print(f"   ❌ 失败: {e}")
    
    # 测试4: wq.jd.com (带 Cookie)
    print("\n📌 测试4: wq.jd.com (带Cookie)")
    try:
        url = f"https://wq.jd.com/commodity/mbaseinfo/getxixiinfo"
        params = {
            "skuids": TEST_SKU,
            "callback": "cb",
        }
        r = httpx.get(url, params=params, headers={
            **headers,
            "Referer": "https://m.jd.com/",
        }, timeout=10)
        
        print(f"   状态码: {r.status_code}")
        print(f"   响应: {r.text[:300]}")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
    
    print("\n" + "=" * 50)
    print("测试完成!")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        TEST_SKU = sys.argv[1]
    test()
