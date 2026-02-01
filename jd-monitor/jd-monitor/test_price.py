#!/usr/bin/env python3
"""
测试从页面提取参数，用于调用价格接口
"""

import httpx
import re
import sys
import json

TEST_SKU = "100268293328"

def test():
    url = f"https://item.jd.com/{TEST_SKU}.html"
    
    print(f"请求商品页面: {url}")
    r = httpx.get(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }, timeout=30, follow_redirects=True)
    
    print(f"状态码: {r.status_code}\n")
    html = r.text
    
    # 提取关键参数
    params = {}
    
    # skuId
    skuid_match = re.search(r"skuid[:\s]*['\"]?(\d+)['\"]?", html, re.I)
    params['skuId'] = skuid_match.group(1) if skuid_match else TEST_SKU
    
    # venderId
    vender_match = re.search(r"venderId[:\s]*['\"]?(\d+)['\"]?", html, re.I)
    params['venderId'] = vender_match.group(1) if vender_match else "0"
    
    # cat (商品分类)
    cat_match = re.search(r"cat[:\s]*\[([^\]]+)\]", html)
    params['cat'] = cat_match.group(1).replace("'", "").replace('"', '') if cat_match else "0,0,0"
    
    print("=== 提取的参数 ===")
    for k, v in params.items():
        print(f"  {k}: {v}")
    
    # 尝试使用这些参数调用价格接口
    print("\n=== 测试价格接口 ===")
    
    # 方法1: 使用 item-soa 接口（京东自己的商品业务接口）
    price_url = f"https://item-soa.jd.com/getWareBusiness"
    price_params = {
        "skuId": params['skuId'],
        "cat": params['cat'],
        "area": "1_72_4137_0",
        "ch": "1"
    }
    
    try:
        r2 = httpx.get(price_url, params=price_params, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": url,
        }, timeout=15)
        print(f"\n📌 item-soa.jd.com/getWareBusiness")
        print(f"   状态码: {r2.status_code}")
        if r2.status_code == 200:
            try:
                data = r2.json()
                if 'price' in data:
                    print(f"   ✅ 价格数据: {json.dumps(data.get('price', {}), ensure_ascii=False)[:200]}")
                if 'stockInfo' in data:
                    print(f"   ✅ 库存数据: {json.dumps(data.get('stockInfo', {}), ensure_ascii=False)[:200]}")
            except:
                print(f"   响应: {r2.text[:300]}")
    except Exception as e:
        print(f"   ❌ 请求失败: {e}")
    
    # 方法2: 使用移动端接口
    mobile_url = f"https://item.m.jd.com/ware/detail.json"
    mobile_params = {
        "wareId": params['skuId'],
    }
    
    try:
        r3 = httpx.get(mobile_url, params=mobile_params, headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
            "Referer": "https://item.m.jd.com/",
        }, timeout=15)
        print(f"\n📌 item.m.jd.com/ware/detail.json")
        print(f"   状态码: {r3.status_code}")
        if r3.status_code == 200:
            try:
                data = r3.json()
                if 'ware' in data:
                    ware = data['ware']
                    print(f"   名称: {ware.get('wname', 'N/A')[:30]}")
                    print(f"   价格: {ware.get('jdPrice', 'N/A')}")
                    print(f"   原价: {ware.get('marketPrice', 'N/A')}")
            except:
                print(f"   响应: {r3.text[:300]}")
    except Exception as e:
        print(f"   ❌ 请求失败: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        TEST_SKU = sys.argv[1]
    test()
