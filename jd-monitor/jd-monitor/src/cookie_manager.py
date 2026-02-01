"""
Cookie 管理模块

负责 Cookie 的读取、解析和有效性验证
"""

import logging
import httpx
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CookieManager:
    """Cookie 管理器"""
    
    # 验证 Cookie 的接口
    VALIDATE_URL = "https://passport.jd.com/user/petName/getUserInfoForMini498.action"
    
    # 通用请求头
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.jd.com/",
    }
    
    def __init__(self, cookie_path: str):
        """
        初始化 Cookie 管理器
        
        Args:
            cookie_path: Cookie 文件路径
        """
        self.cookie_path = Path(cookie_path)
        self._cookies: Optional[str] = None
        self._is_valid: Optional[bool] = None
        self._username: Optional[str] = None
    
    def load_cookies(self) -> str:
        """
        从文件加载 Cookie
        
        Returns:
            Cookie 字符串
            
        Raises:
            FileNotFoundError: Cookie 文件不存在
            ValueError: Cookie 文件为空或无效
        """
        if not self.cookie_path.exists():
            raise FileNotFoundError(f"Cookie 文件不存在: {self.cookie_path}")
        
        content = self.cookie_path.read_text(encoding="utf-8").strip()
        
        # 过滤注释行
        lines = [line.strip() for line in content.split("\n") 
                 if line.strip() and not line.strip().startswith("#")]
        
        if not lines:
            raise ValueError("Cookie 文件为空，请填入有效的 Cookie")
        
        # 取最后一行非注释内容作为 Cookie
        self._cookies = lines[-1]
        
        if self._cookies == "YOUR_COOKIE_HERE":
            raise ValueError("请将 Cookie 替换为真实的 Cookie 值")
        
        logger.info("Cookie 加载成功")
        return self._cookies
    
    def get_cookies(self) -> str:
        """获取 Cookie，如果未加载则自动加载"""
        if self._cookies is None:
            self.load_cookies()
        return self._cookies
    
    def get_headers(self) -> dict:
        """
        获取带 Cookie 的请求头
        
        Returns:
            完整的请求头字典
        """
        headers = self.DEFAULT_HEADERS.copy()
        headers["Cookie"] = self.get_cookies()
        return headers
    
    async def validate_cookies(self) -> bool:
        """
        异步验证 Cookie 是否有效
        
        Returns:
            True 表示有效，False 表示无效或已过期
        """
        try:
            cookies = self.get_cookies()
            
            # 首先检查 Cookie 中是否包含必要的字段
            if "pt_key" not in cookies or "pt_pin" not in cookies:
                logger.warning("Cookie 中缺少 pt_key 或 pt_pin")
                self._is_valid = False
                return False
            
            # 尝试从 Cookie 中提取用户名
            import re
            pin_match = re.search(r'pt_pin=([^;]+)', cookies)
            if pin_match:
                import urllib.parse
                self._username = urllib.parse.unquote(pin_match.group(1))
            
            headers = self.get_headers()
            
            # 尝试访问用户信息接口
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    self.VALIDATE_URL,
                    headers=headers,
                    follow_redirects=True
                )
            
            # 检查响应
            if response.status_code == 200:
                try:
                    data = response.json()
                    # 如果能获取到用户昵称，说明 Cookie 有效
                    if "nickName" in data or "realName" in data:
                        nick = data.get("nickName") or data.get("realName")
                        if nick:
                            self._username = nick
                        self._is_valid = True
                        logger.info(f"Cookie 验证成功，当前用户: {self._username}")
                        return True
                except Exception:
                    pass
            
            # 尝试备用验证方法
            return await self._validate_fallback()
            
        except Exception as e:
            logger.error(f"Cookie 验证失败: {e}")
            self._is_valid = False
            return False
    
    async def _validate_fallback(self) -> bool:
        """备用验证方法：通过访问订单或收藏接口验证"""
        try:
            headers = self.get_headers()
            
            # 方法1：尝试访问收藏接口
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://api.m.jd.com/api?appid=jd-cphdeveloper-m&functionId=queryShopFavList&body={}",
                    headers=headers,
                    follow_redirects=True
                )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    # 如果返回了有效数据（不是要求登录的错误），说明 Cookie 有效
                    if data.get("code") == "0" or data.get("result") or "data" in data:
                        self._is_valid = True
                        logger.info(f"Cookie 验证成功（备用方法），用户: {self._username or '已登录'}")
                        return True
                except Exception:
                    pass
            
            # 方法2：检查 Cookie 中 pt_key 的有效性（简单检查长度和格式）
            cookies = self.get_cookies()
            import re
            pt_key_match = re.search(r'pt_key=([^;]+)', cookies)
            if pt_key_match:
                pt_key = pt_key_match.group(1)
                # pt_key 通常是较长的字符串
                if len(pt_key) > 20:
                    # 假设格式正确，标记为有效（实际有效性会在第一次请求时验证）
                    self._is_valid = True
                    logger.info(f"Cookie 格式检查通过，用户: {self._username or '未知'}")
                    return True
            
            self._is_valid = False
            return False
            
        except Exception as e:
            logger.error(f"备用验证失败: {e}")
            self._is_valid = False
            return False
    
    def validate_cookies_sync(self) -> bool:
        """
        同步验证 Cookie（用于初始化检查）
        
        Returns:
            True 表示有效
        """
        import asyncio
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.validate_cookies())
    
    @property
    def is_valid(self) -> Optional[bool]:
        """Cookie 是否有效（需要先调用 validate_cookies）"""
        return self._is_valid
    
    @property
    def username(self) -> Optional[str]:
        """当前登录的用户名"""
        return self._username
