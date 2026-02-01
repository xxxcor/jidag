#!/usr/bin/env python3
"""
深度测试价格获取 - 测试所有可能的方法
"""

import httpx
import re
import sys
import json

TEST_SKU = "100268293328"

def test():
    print("=" * 60)
    print(f"深度测试商品价格获取 - SKU: {TEST_SKU}")
    print("=" * 60)
    
    # 1. 请求商品页面
    url = f"https://item.jd.com/{TEST_SKU}.html"
    print(f"\n1. 请求商品页面: {url}")
    
    r = httpx.get(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }, timeout=30, follow_redirects=True)
    
    print(f"   状态码: {r.status_code}")
    html = r.text
    
    # 2. 提取页面中的所有关键参数
    print("\n2. 从页面提取参数:")
    
    # 更多提取模式
    patterns = {
        'venderId': [
            r"venderId\s*[=:]\s*['\"]?(\d+)",
            r'"venderId"\s*:\s*"?(\d+)"?',
            r"'venderId'\s*:\s*'?(\d+)'?",
        ],
        'cat': [
            r"cat\s*:\s*\[([^\]]+)\]",
            r'"cat"\s*:\s*\[([^\]]+)\]',
            r"categoryId\s*[=:]\s*['\"]?([^'\"]+)",
        ],
        'shopId': [
            r"shopId\s*[=:]\s*['\"]?(\d+)",
            r'"shopId"\s*:\s*"?(\d+)"?',
        ],
    }
    
    params = {'skuId': TEST_SKU}
    for key, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, html, re.I)
            if match:
                params[key] = match.group(1).replace("'", "").replace('"', '').strip()
                print(f"   ✅ {key}: {params[key]}")
                break
        else:
            params[key] = "0"
            print(f"   ❌ {key}: 未找到")
    
    # 3. 测试各种价格接口
    print("\n3. 测试价格接口:")
    
    # 方法 A: 使用 callback 方式（JSONP）
    print("\n   📌 方法A: JSONP 价格接口")
    try:
        jsonp_url = "https://p.3.cn/prices/mgets"
        jsonp_params = {
            "skuIds": f"J_{TEST_SKU}",
            "type": "1",
            "callback": "jQuery12345",
        }
        r1 = httpx.get(jsonp_url, params=jsonp_params, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": url,
        }, timeout=15)
        print(f"      状态码: {r1.status_code}")
        print(f"      响应: {r1.text[:200]}")
    except Exception as e:
        print(f"      ❌ 失败: {e}")
    
    # 方法 B: 使用商品详情 API (需要完整参数)
    print("\n   📌 方法B: getWareBusiness 接口 (带完整参数)")
    try:
        api_url = "https://item-soa.jd.com/getWareBusiness"
        api_params = {
            "skuId": TEST_SKU,
            "cat": params.get('cat', '0,0,0'),
            "area": "1_72_4137_0",
            "shopId": params.get('shopId', ''),
            "venderId": params.get('venderId', ''),
            "paramJson": json.dumps({"platform2": "1"}),
        }
        r2 = httpx.get(api_url, params=api_params, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": url,
            "Origin": "https://item.jd.com",
        }, timeout=15, follow_redirects=True)
        print(f"      状态码: {r2.status_code}")
        if r2.status_code == 200:
            try:
                data = r2.json()
                print(f"      price: {data.get('price', {})}")
                print(f"      stock: {data.get('stockInfo', {})}")
            except:
                print(f"      响应: {r2.text[:300]}")
        else:
            print(f"      响应: {r2.text[:200]}")
    except Exception as e:
        print(f"      ❌ 失败: {e}")
    
    # 方法 C: 直接从移动端页面解析
    print("\n   📌 方法C: 移动端页面解析")
    try:
        m_url = f"https://item.m.jd.com/product/{TEST_SKU}.html"
        r3 = httpx.get(m_url, headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        }, timeout=15, follow_redirects=True)
        print(f"      状态码: {r3.status_code}")
        m_html = r3.text
        
        # 尝试提取 window.__INIT_DATA__
        init_data_match = re.search(r'window\.__INIT_DATA__\s*=\s*(\{.+?\});?\s*</script>', m_html, re.DOTALL)
        if init_data_match:
            print("      ✅ 找到 __INIT_DATA__")
            try:
                init_data = json.loads(init_data_match.group(1))
                # 尝试从中提取价格
                if 'price' in str(init_data)[:1000]:
                    print(f"      包含价格数据")
            except:
                pass
        
        # 尝试其他模式
        price_match = re.search(r'"jdPrice"\s*:\s*"?([\d.]+)"?', m_html)
        if price_match:
            print(f"      ✅ jdPrice: {price_match.group(1)}")
        
        # 查看页面中的 JSON 数据
        json_blocks = re.findall(r'<script[^>]*>\s*window\.(\w+)\s*=\s*(\{[^<]+\})\s*;?\s*</script>', m_html, re.DOTALL)
        for name, content in json_blocks[:3]:
            print(f"      找到: window.{name} (长度: {len(content)})")
            
    except Exception as e:
        print(f"      ❌ 失败: {e}")
    
    # 方法 D: 使用 api.m.jd.com
    print("\n   📌 方法D: api.m.jd.com 商品接口")
    try:
        api_url = "https://api.m.jd.com/client.action"
        api_params = {
            "functionId": "wareBusiness",
            "body": json.dumps({
                "skuId": TEST_SKU,
                "area": "1_72_4137_0",
                "from": "pc-item",
            }),
        }
        r4 = httpx.get(api_url, params=api_params, headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
            "Referer": "https://item.m.jd.com/",
        }, timeout=15)
        print(f"      状态码: {r4.status_code}")
        if r4.status_code == 200:
            try:
                data = r4.json()
                if data.get('code') == '0':
                    print(f"      ✅ 成功获取数据")
                    print(f"      {json.dumps(data, ensure_ascii=False)[:300]}")
                else:
                    print(f"      响应: {r4.text[:200]}")
            except:
                print(f"      响应: {r4.text[:200]}")
    except Exception as e:
        print(f"      ❌ 失败: {e}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        TEST_SKU = sys.argv[1]
    test()
