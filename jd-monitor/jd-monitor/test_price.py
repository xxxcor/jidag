#!/usr/bin/env python3
"""
测试 api.m.jd.com 接口 - 带正确参数
"""

import httpx
import json
import sys

TEST_SKU = "100268293328"

def test():
    print(f"测试商品: {TEST_SKU}")
    print("=" * 50)
    
    # 测试多个 functionId 和参数组合
    tests = [
        # 商品详情接口
        {
            "name": "wareBusiness (带appid)",
            "functionId": "wareBusiness",
            "appid": "item-v3",
            "body": {
                "skuId": TEST_SKU,
                "area": "1_72_4137_0",
                "cat": "652,654,831",
            }
        },
        # 价格接口
        {
            "name": "queryMaterialPrice",
            "functionId": "queryMaterialPrice",
            "appid": "item-v3",
            "body": {
                "skuId": TEST_SKU,
                "area": "1_72_4137_0",
            }
        },
        # 库存接口
        {
            "name": "queryStockSort",
            "functionId": "queryStockSort",
            "appid": "item-v3",
            "body": {
                "skuId": TEST_SKU,
                "area": "1_72_4137_0",
            }
        },
        # 商品基本信息
        {
            "name": "item-v3",
            "functionId": "wareBusiness",
            "appid": "mitem",
            "body": {
                "skuId": TEST_SKU,
                "fromType": "wxapp",
            }
        },
    ]
    
    for test in tests:
        print(f"\n📌 {test['name']}")
        try:
            params = {
                "functionId": test["functionId"],
                "appid": test["appid"],
                "body": json.dumps(test["body"]),
                "client": "wh5",
                "clientVersion": "1.0.0",
            }
            
            r = httpx.get(
                "https://api.m.jd.com/client.action",
                params=params,
                headers={
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
                    "Referer": "https://item.m.jd.com/",
                },
                timeout=15
            )
            
            print(f"   状态码: {r.status_code}")
            
            if r.status_code == 200:
                try:
                    data = r.json()
                    code = data.get("code", data.get("resultCode", ""))
                    
                    if code in ["0", 0, "200"]:
                        print(f"   ✅ 成功!")
                        # 尝试提取价格和库存
                        result = data.get("data", data)
                        
                        # 价格
                        if "price" in str(result):
                            price_info = result.get("price", {})
                            if isinstance(price_info, dict):
                                print(f"   价格: ¥{price_info.get('p', price_info.get('jdPrice', 'N/A'))}")
                            else:
                                print(f"   价格数据: {price_info}")
                        
                        # 库存
                        if "stock" in str(result).lower():
                            stock_info = result.get("stockInfo", result.get("stock", {}))
                            print(f"   库存: {stock_info}")
                        
                        # 显示部分原始数据
                        print(f"   原始数据: {json.dumps(result, ensure_ascii=False)[:400]}")
                    else:
                        print(f"   响应: {r.text[:300]}")
                except Exception as e:
                    print(f"   解析错误: {e}")
                    print(f"   响应: {r.text[:200]}")
        except Exception as e:
            print(f"   ❌ 请求失败: {e}")
    
    # 额外测试：直接用 URL 参数方式
    print("\n" + "=" * 50)
    print("📌 直接 URL 方式测试")
    
    direct_urls = [
        f"https://wq.jd.com/commodity/mbaseinfo/getxixiinfo?skuids={TEST_SKU}&callback=cb",
        f"https://wq.jd.com/commodity/details/getprice?skuid={TEST_SKU}&callback=cb",
    ]
    
    for url in direct_urls:
        print(f"\n   URL: {url[:60]}...")
        try:
            r = httpx.get(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://m.jd.com/",
            }, timeout=10)
            print(f"   状态码: {r.status_code}")
            print(f"   响应: {r.text[:200]}")
        except Exception as e:
            print(f"   ❌ {e}")
    
    print("\n" + "=" * 50)
    print("测试完成!")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        TEST_SKU = sys.argv[1]
    test()
