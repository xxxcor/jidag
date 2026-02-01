"""
京东商品信息抓取模块

使用多种方法获取商品价格和库存信息，按优先级尝试：
1. 价格 API（p.3.cn）
2. 移动端页面解析
3. PC 端页面解析
"""

import re
import json
import random
import logging
import asyncio
import httpx
from typing import Optional, Tuple
from datetime import datetime

from .models import ProductState
from .cookie_manager import CookieManager

logger = logging.getLogger(__name__)


class JDApi:
    """京东 API 封装"""
    
    # 价格接口（多个备用）
    PRICE_URLS = [
        "https://p.3.cn/prices/mgets",
        "https://pe.3.cn/prices/mgets",
    ]
    
    # 库存接口
    STOCK_URL = "https://c0.3.cn/stocks"
    
    # 商品详情页
    ITEM_URL = "https://item.jd.com/{sku}.html"
    MOBILE_URL = "https://item.m.jd.com/product/{sku}.html"
    
    def __init__(self, cookie_manager: CookieManager, config: dict):
        """初始化"""
        self.cookie_manager = cookie_manager
        self.config = config
        self.area = config.get("area", "1_72_4137_0")
        self.timeout = config.get("advanced", {}).get("timeout", 15)
        self.random_delay = config.get("advanced", {}).get("random_delay", True)
        self.delay_range = config.get("advanced", {}).get("random_delay_range", [1, 3])
    
    def _get_headers(self, referer: str = "https://www.jd.com/") -> dict:
        """获取请求头"""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": referer,
            "Cookie": self.cookie_manager.get_cookies(),
        }
    
    async def _request_with_retry(self, url: str, params: dict = None, headers: dict = None, 
                                   max_retries: int = 2, timeout: int = None) -> Optional[httpx.Response]:
        """带重试的请求"""
        if timeout is None:
            timeout = self.timeout
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                    response = await client.get(url, params=params, headers=headers)
                    if response.status_code == 200:
                        return response
            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    logger.debug(f"请求超时，重试 {attempt + 2}/{max_retries}: {url}")
                    await asyncio.sleep(1)
                continue
            except Exception as e:
                logger.debug(f"请求异常: {type(e).__name__}")
                break
        return None
    
    async def _delay(self):
        """随机延迟"""
        if self.random_delay:
            delay = random.uniform(*self.delay_range)
            await asyncio.sleep(delay)
    
    async def get_price_from_api(self, sku_id: str) -> Tuple[float, float]:
        """
        从价格 API 获取价格
        
        Returns:
            (当前价格, 原价)
        """
        headers = self._get_headers(f"https://item.jd.com/{sku_id}.html")
        
        params = {
            "skuIds": f"J_{sku_id}",
            "type": "1",
            "area": self.area,
            "pduid": str(random.randint(1000000000, 9999999999)),
            "_": str(int(datetime.now().timestamp() * 1000))
        }
        
        for price_url in self.PRICE_URLS:
            response = await self._request_with_retry(price_url, params, headers, timeout=20)
            
            if response and response.status_code == 200:
                try:
                    data = response.json()
                    if data and len(data) > 0:
                        item = data[0]
                        price = float(item.get("p", 0))
                        original_price = float(item.get("m", item.get("op", price)))
                        if price > 0:
                            logger.debug(f"价格 API 获取成功: ¥{price}")
                            return price, original_price
                except Exception as e:
                    logger.debug(f"解析价格失败: {e}")
        
        return 0.0, 0.0
    
    async def get_stock_from_api(self, sku_id: str) -> Tuple[bool, str]:
        """
        从库存 API 获取库存状态
        
        尝试多个备用接口：
        1. 主库存接口 c0.3.cn（可能不通）
        2. 备用库存接口
        3. 从价格接口获取库存信息
        
        Returns:
            (是否有货, 库存描述)
        """
        headers = self._get_headers(f"https://item.jd.com/{sku_id}.html")
        
        # 备用库存接口列表
        stock_urls = [
            "https://c0.3.cn/stocks",
            "https://cd.jd.com/stocks",  # 备用接口
        ]
        
        params = {
            "skuId": sku_id,
            "area": self.area,
            "venderId": "0",
            "cat": "0,0,0",
            "_": str(int(datetime.now().timestamp() * 1000))
        }
        
        # 尝试库存接口
        for stock_url in stock_urls:
            response = await self._request_with_retry(stock_url, params, headers, timeout=10, max_retries=1)
            
            if response and response.status_code == 200:
                try:
                    data = response.json()
                    stock_state = data.get("StockState", 0)
                    stock_name = data.get("StockStateName", "")
                    
                    if stock_state > 0 or stock_name:
                        in_stock = stock_state in [33, 40, 1]
                        stock_text = stock_name or self._parse_stock_code(stock_state)
                        logger.debug(f"库存 API 获取成功: {stock_text}")
                        return in_stock, stock_text
                except Exception as e:
                    logger.debug(f"解析库存失败: {e}")
        
        # 如果库存接口都失败，尝试从商品页面获取库存状态
        logger.debug("库存 API 不可用，尝试从页面解析")
        return await self._get_stock_from_page(sku_id)
    
    async def _get_stock_from_page(self, sku_id: str) -> Tuple[bool, str]:
        """
        从商品页面解析库存状态
        """
        headers = self._get_headers()
        url = self.ITEM_URL.format(sku=sku_id)
        
        response = await self._request_with_retry(url, headers=headers, timeout=15, max_retries=1)
        
        if response and response.status_code == 200:
            html = response.text
            
            # 从页面判断库存状态
            if "无货" in html or "缺货" in html or "暂时缺货" in html:
                return False, "无货"
            elif "采购中" in html:
                return False, "采购中"
            elif "预约" in html:
                return False, "预约"
            elif "抢购" in html:
                return False, "抢购"
            elif "有货" in html or "现货" in html or "加入购物车" in html:
                return True, "有货"
            elif "到货通知" in html:
                return False, "无货"
        
        return False, "未知"
    
    async def get_info_from_page(self, sku_id: str, product_name: str = "") -> dict:
        """
        从商品页面获取信息（作为备用方法）
        """
        result = {
            "name": product_name or f"商品_{sku_id}",
            "price": 0.0,
            "original_price": 0.0,
            "in_stock": False,
            "stock_text": "未知",
            "is_on_sale": True,
            "presale_info": ""
        }
        
        # 尝试移动端页面
        url = self.MOBILE_URL.format(sku=sku_id)
        headers = self._get_headers()
        headers["User-Agent"] = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"
        
        response = await self._request_with_retry(url, headers=headers)
        
        if response is None:
            # 尝试 PC 端页面
            url = self.ITEM_URL.format(sku=sku_id)
            headers = self._get_headers()
            response = await self._request_with_retry(url, headers=headers)
        
        if response is None:
            return result
        
        if response.status_code == 404:
            result["is_on_sale"] = False
            result["stock_text"] = "已下架"
            return result
        
        html = response.text
        
        # 检查下架
        if "商品已下柜" in html or "商品不存在" in html:
            result["is_on_sale"] = False
            result["stock_text"] = "已下架"
            return result
        
        # 提取商品名
        if not product_name:
            match = re.search(r'<title>([^<]+)</title>', html)
            if match:
                name = match.group(1).strip()
                name = re.sub(r'[-_|【】].*?京东.*$', '', name).strip()
                result["name"] = name[:50] if name else f"商品_{sku_id}"
        
        # 尝试从页面提取库存状态
        if "无货" in html or "缺货" in html:
            result["in_stock"] = False
            result["stock_text"] = "无货"
        elif "有货" in html or "现货" in html:
            result["in_stock"] = True
            result["stock_text"] = "有货"
        
        # 预约检测
        if "预约" in html:
            result["presale_info"] = "预约中"
            result["stock_text"] = "预约"
        elif "抢购" in html:
            result["presale_info"] = "抢购中"
            result["stock_text"] = "抢购"
        
        return result
    
    def _parse_stock_code(self, code: int) -> str:
        """解析库存状态码"""
        state_map = {
            1: "有货", 33: "有货", 34: "无货",
            36: "预约", 40: "可配货", 0: "未知"
        }
        return state_map.get(code, f"状态:{code}")
    
    async def get_product_state(self, sku_id: str, product_name: str = "") -> ProductState:
        """
        获取商品完整状态
        
        综合使用多种方法获取商品信息
        """
        await self._delay()
        
        # 1. 从页面获取基本信息（名称、上架状态）
        page_info = await self.get_info_from_page(sku_id, product_name)
        
        # 如果商品已下架，直接返回
        if not page_info["is_on_sale"]:
            logger.info(f"商品已下架: SKU={sku_id}")
            return ProductState(
                sku_id=sku_id,
                name=product_name or page_info["name"],
                is_on_sale=False,
                stock_text="已下架",
                updated_at=datetime.now()
            )
        
        await self._delay()
        
        # 2. 尝试从 API 获取价格
        price, original_price = await self.get_price_from_api(sku_id)
        
        await self._delay()
        
        # 3. 尝试从 API 获取库存
        in_stock, stock_text = await self.get_stock_from_api(sku_id)
        
        # 如果 API 获取失败，使用页面解析的结果
        if stock_text == "未知" and page_info["stock_text"] != "未知":
            in_stock = page_info["in_stock"]
            stock_text = page_info["stock_text"]
        
        # 构建结果
        name = product_name or page_info["name"]
        presale_info = page_info["presale_info"]
        
        logger.info(f"商品状态: {name[:20]}... | ¥{price} | {stock_text}")
        
        return ProductState(
            sku_id=sku_id,
            name=name,
            price=price,
            original_price=original_price,
            in_stock=in_stock,
            stock_text=stock_text,
            is_on_sale=True,
            presale_info=presale_info,
            updated_at=datetime.now()
        )
