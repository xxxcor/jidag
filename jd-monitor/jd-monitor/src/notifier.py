"""
Telegram 通知模块

负责向 Telegram 发送商品状态变化通知
"""

import logging
import httpx
from typing import Optional
from datetime import datetime

from .models import ProductState, NotifyEvent

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Telegram 通知器"""
    
    # Telegram Bot API 地址
    API_BASE = "https://api.telegram.org/bot{token}"
    
    def __init__(self, bot_token: str, chat_id: str, config: dict = None):
        """
        初始化 Telegram 通知器
        
        Args:
            bot_token: Telegram Bot Token
            chat_id: 目标 Chat ID（用户或群组）
            config: 配置字典
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.config = config or {}
        self.api_url = self.API_BASE.format(token=bot_token)
        
        # 重试配置
        self.retry_count = self.config.get("advanced", {}).get("retry_count", 3)
        self.retry_delay = self.config.get("advanced", {}).get("retry_delay", 5)
    
    async def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """
        发送消息到 Telegram
        
        Args:
            text: 消息内容
            parse_mode: 解析模式（Markdown 或 HTML）
            
        Returns:
            发送成功返回 True
        """
        url = f"{self.api_url}/sendMessage"
        
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": False
        }
        
        for attempt in range(self.retry_count):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(url, json=payload)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("ok"):
                        logger.info("Telegram 消息发送成功")
                        return True
                    else:
                        logger.error(f"Telegram API 错误: {result.get('description')}")
                else:
                    logger.error(f"Telegram 请求失败: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"发送 Telegram 消息异常 (尝试 {attempt + 1}/{self.retry_count}): {e}")
            
            # 重试前等待
            if attempt < self.retry_count - 1:
                import asyncio
                await asyncio.sleep(self.retry_delay)
        
        return False
    
    def _escape_markdown(self, text: str) -> str:
        """转义 Markdown 特殊字符"""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    async def send_product_alert(self, product: ProductState, changes: dict) -> bool:
        """
        发送商品状态变化通知
        
        Args:
            product: 当前商品状态
            changes: 变化内容字典
            
        Returns:
            发送成功返回 True
        """
        # 构建消息
        lines = [
            "📦 *商品状态变化*",
            "",
            f"🏷️ {product.name}",
            f"🔗 {product.product_url}",
            ""
        ]
        
        # 价格变化
        if "price" in changes:
            price_change = changes["price"]
            old_price = price_change["old"]
            new_price = price_change["new"]
            direction = "⬇️" if price_change["direction"] == "down" else "⬆️"
            lines.append(f"💰 价格: ¥{old_price} → ¥{new_price} {direction}")
        
        # 库存变化
        if "in_stock" in changes:
            stock_change = changes["in_stock"]
            old_text = stock_change.get("old_text", "无货" if not stock_change["old"] else "有货")
            new_text = stock_change.get("new_text", "有货" if stock_change["new"] else "无货")
            icon = "✅" if stock_change["new"] else "❌"
            lines.append(f"📦 库存: {old_text} → {new_text} {icon}")
        
        # 库存描述变化（非有货/无货状态变化）
        if "stock_text" in changes:
            text_change = changes["stock_text"]
            lines.append(f"📦 库存状态: {text_change['old']} → {text_change['new']}")
        
        # 上下架状态变化
        if "is_on_sale" in changes:
            sale_change = changes["is_on_sale"]
            old_status = "上架" if sale_change["old"] else "下架"
            new_status = "上架" if sale_change["new"] else "下架"
            icon = "🟢" if sale_change["new"] else "🔴"
            lines.append(f"🏪 状态: {old_status} → {new_status} {icon}")
        
        # 预约信息变化
        if "presale_info" in changes:
            presale_change = changes["presale_info"]
            old_info = presale_change["old"] or "无"
            new_info = presale_change["new"] or "无"
            lines.append(f"🎫 预约: {old_info} → {new_info}")
        
        # 首次检测
        if changes.get("is_new"):
            lines = [
                "🆕 *开始监控商品*",
                "",
                f"🏷️ {product.name}",
                f"🔗 {product.product_url}",
                "",
                f"💰 当前价格: ¥{product.price}",
                f"📦 库存状态: {product.stock_text}",
                f"🏪 上架状态: {'上架' if product.is_on_sale else '下架'}"
            ]
            if product.presale_info:
                lines.append(f"🎫 预约信息: {product.presale_info}")
        
        # 添加时间戳
        lines.append("")
        lines.append(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        message = "\n".join(lines)
        
        return await self.send_message(message)
    
    async def send_cookie_expired_alert(self) -> bool:
        """发送 Cookie 过期通知"""
        message = """
🚨 *Cookie 已失效*

京东登录状态已过期，请及时更新 Cookie！

📝 更新步骤：
1. 在浏览器中重新登录 jd.com
2. 按 F12 打开开发者工具
3. 复制 Request Headers 中的 Cookie
4. 更新 `config/cookies.txt` 文件

⏰ {time}
""".format(time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        return await self.send_message(message)
    
    async def send_error_alert(self, error_message: str) -> bool:
        """发送错误通知"""
        message = f"""
⚠️ *监控异常*

{error_message}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return await self.send_message(message)
    
    async def send_startup_message(self, products: list) -> bool:
        """发送启动通知"""
        product_list = "\n".join([f"• {p.get('name', p.get('sku_id'))}" for p in products])
        
        message = f"""
🚀 *京东商品监控已启动*

监控商品列表：
{product_list}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return await self.send_message(message)
    
    async def test_connection(self) -> bool:
        """测试 Telegram 连接"""
        try:
            url = f"{self.api_url}/getMe"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    bot_name = result.get("result", {}).get("username", "Unknown")
                    logger.info(f"Telegram 连接成功，Bot: @{bot_name}")
                    return True
            
            logger.error("Telegram 连接失败")
            return False
            
        except Exception as e:
            logger.error(f"Telegram 连接测试异常: {e}")
            return False
