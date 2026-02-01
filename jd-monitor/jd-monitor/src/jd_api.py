"""
京东商品信息抓取模块

由于独立的价格/库存 API 不可用，改用纯页面解析方式：
1. 访问商品详情页
2. 从 pageConfig 和 HTML 中提取价格、库存信息
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
    """京东 API 封装 - 纯页面解析版本"""
    
    # 商品详情页
    ITEM_URL = "https://item.jd.com/{sku}.html"
    
    def __init__(self, cookie_manager: CookieManager, config: dict):
        """初始化"""
        self.cookie_manager = cookie_manager
        self.config = config
        self.area = config.get("area", "1_72_4137_0")
        self.timeout = config.get("advanced", {}).get("timeout", 30)
        self.random_delay = config.get("advanced", {}).get("random_delay", True)
        self.delay_range = config.get("advanced", {}).get("random_delay_range", [1, 3])
    
    def _get_headers(self, referer: str = "https://www.jd.com/") -> dict:
        """获取请求头"""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": referer,
            "Cookie": self.cookie_manager.get_cookies(),
        }
    
    async def _request(self, url: str, headers: dict = None, timeout: int = None) -> Optional[httpx.Response]:
        """发送请求"""
        if headers is None:
            headers = self._get_headers()
        if timeout is None:
            timeout = self.timeout
        
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                return response
        except Exception as e:
            logger.warning(f"请求失败 {url}: {type(e).__name__}")
            return None
    
    async def _delay(self):
        """随机延迟"""
        if self.random_delay:
            delay = random.uniform(*self.delay_range)
            await asyncio.sleep(delay)
    
    async def get_product_state(self, sku_id: str, product_name: str = "") -> ProductState:
        """
        获取商品完整状态（纯页面解析）
        """
        await self._delay()
        
        # 默认值
        result = {
            "name": product_name or f"商品_{sku_id}",
            "price": 0.0,
            "original_price": 0.0,
            "in_stock": False,
            "stock_text": "未知",
            "is_on_sale": True,
            "presale_info": ""
        }
        
        # 请求商品页面
        url = self.ITEM_URL.format(sku=sku_id)
        headers = self._get_headers()
        response = await self._request(url, headers)
        
        if response is None:
            logger.warning(f"无法访问商品页面: SKU={sku_id}")
            return self._create_product_state(sku_id, result)
        
        if response.status_code == 404:
            result["is_on_sale"] = False
            result["stock_text"] = "已下架"
            return self._create_product_state(sku_id, result)
        
        if response.status_code != 200:
            logger.warning(f"商品页面状态异常: SKU={sku_id}, 状态码={response.status_code}")
            return self._create_product_state(sku_id, result)
        
        html = response.text
        
        # 解析页面
        result = self._parse_page(html, sku_id, product_name)
        
        logger.info(f"商品: {result['name'][:25]}... | ¥{result['price']} | {result['stock_text']}")
        
        return self._create_product_state(sku_id, result)
    
    def _parse_page(self, html: str, sku_id: str, product_name: str = "") -> dict:
        """
        解析商品页面，提取所有信息
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
        
        # 检查下架
        if "此商品已下柜" in html or "该商品已下柜" in html or "商品不存在" in html:
            result["is_on_sale"] = False
            result["stock_text"] = "已下架"
            return result
        
        # 1. 提取商品名称
        if not product_name:
            title_match = re.search(r'<title>([^<]+)</title>', html)
            if title_match:
                name = title_match.group(1)
                # 清理标题
                name = re.sub(r'【[^】]*】', '', name)
                name = re.sub(r'-京东$', '', name).strip()
                result["name"] = name[:60] if name else f"商品_{sku_id}"
        
        # 2. 从 pageConfig 提取价格
        # 查找 pageConfig 对象
        pageconfig_match = re.search(r'var\s+pageConfig\s*=\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}', html, re.DOTALL)
        if pageconfig_match:
            config_str = pageconfig_match.group(1)
            
            # 提取 price
            price_match = re.search(r"price\s*:\s*['\"]?([\d.]+)['\"]?", config_str)
            if price_match:
                try:
                    result["price"] = float(price_match.group(1))
                except ValueError:
                    pass
        
        # 3. 备用价格提取方法
        if result["price"] == 0:
            # 尝试从其他位置提取
            price_patterns = [
                r'"p"\s*:\s*"?([\d.]+)"?',
                r'"price"\s*:\s*"?([\d.]+)"?',
                r'data-price="([\d.]+)"',
                r'class="p-price"[^>]*>.*?<span[^>]*>([\d.]+)</span>',
            ]
            for pattern in price_patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    try:
                        price = float(match.group(1))
                        if 0.01 < price < 10000000:
                            result["price"] = price
                            break
                    except ValueError:
                        continue
        
        # 4. 提取原价
        op_patterns = [
            r'"op"\s*:\s*"?([\d.]+)"?',
            r'"m"\s*:\s*"?([\d.]+)"?',
            r'class="p-del"[^>]*>.*?[¥￥]([\d.]+)',
        ]
        for pattern in op_patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    result["original_price"] = float(match.group(1))
                    break
                except ValueError:
                    continue
        
        # 5. 解析库存状态（从页面关键词判断）
        if "无货" in html or "缺货" in html or "暂时缺货" in html:
            result["in_stock"] = False
            result["stock_text"] = "无货"
        elif "采购中" in html:
            result["in_stock"] = False
            result["stock_text"] = "采购中"
        elif "预约" in html and "预约抢购" in html:
            result["in_stock"] = False
            result["stock_text"] = "预约"
            result["presale_info"] = "预约中"
        elif "到货通知" in html:
            result["in_stock"] = False
            result["stock_text"] = "无货"
        elif "加入购物车" in html or "有货" in html or "现货" in html:
            result["in_stock"] = True
            result["stock_text"] = "有货"
        elif "抢购" in html:
            result["in_stock"] = False
            result["stock_text"] = "抢购"
            result["presale_info"] = "抢购中"
        
        return result
    
    def _create_product_state(self, sku_id: str, data: dict) -> ProductState:
        """创建 ProductState 对象"""
        return ProductState(
            sku_id=sku_id,
            name=data.get("name", f"商品_{sku_id}"),
            price=data.get("price", 0.0),
            original_price=data.get("original_price", 0.0),
            in_stock=data.get("in_stock", False),
            stock_text=data.get("stock_text", "未知"),
            is_on_sale=data.get("is_on_sale", True),
            presale_info=data.get("presale_info", ""),
            updated_at=datetime.now()
        )
