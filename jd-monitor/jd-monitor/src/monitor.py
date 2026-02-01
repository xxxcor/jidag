"""
主监控逻辑模块

负责状态检测、对比和触发通知
"""

import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from .models import ProductState
from .cookie_manager import CookieManager
from .jd_api import JDApi
from .notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class Monitor:
    """商品监控器"""
    
    def __init__(self, config: dict, base_path: Path):
        """
        初始化监控器
        
        Args:
            config: 配置字典
            base_path: 项目根目录路径
        """
        self.config = config
        self.base_path = base_path
        
        # 状态文件路径
        self.state_file = base_path / "data" / "state.json"
        
        # 初始化组件
        cookie_path = base_path / "config" / "cookies.txt"
        self.cookie_manager = CookieManager(str(cookie_path))
        self.jd_api = JDApi(self.cookie_manager, config)
        
        # Telegram 通知器
        tg_config = config.get("telegram", {})
        self.notifier = TelegramNotifier(
            bot_token=tg_config.get("bot_token", ""),
            chat_id=tg_config.get("chat_id", ""),
            config=config
        )
        
        # 通知配置
        self.notify_config = config.get("notify", {})
        
        # 上次状态缓存
        self._last_states: Dict[str, ProductState] = {}
        
        # Cookie 状态
        self._cookie_valid = True
        self._cookie_alert_sent = False
    
    def get_products(self) -> List[dict]:
        """获取要监控的商品列表"""
        mode = self.config.get("mode", "multi")
        
        if mode == "single":
            single_product = self.config.get("single_product", {})
            if single_product:
                return [single_product]
        
        return self.config.get("products", [])
    
    def load_last_state(self) -> Dict[str, ProductState]:
        """从文件加载上次的状态"""
        if not self.state_file.exists():
            logger.info("没有找到历史状态文件，首次运行")
            return {}
        
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            states = {}
            for sku_id, state_dict in data.items():
                states[sku_id] = ProductState.from_dict(state_dict)
            
            logger.info(f"加载了 {len(states)} 个商品的历史状态")
            return states
            
        except Exception as e:
            logger.error(f"加载状态文件失败: {e}")
            return {}
    
    def save_state(self, states: Dict[str, ProductState]):
        """保存当前状态到文件"""
        try:
            # 确保目录存在
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {sku_id: state.to_dict() for sku_id, state in states.items()}
            
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug("状态保存成功")
            
        except Exception as e:
            logger.error(f"保存状态文件失败: {e}")
    
    async def check_cookie(self) -> bool:
        """检查 Cookie 有效性"""
        try:
            is_valid = await self.cookie_manager.validate_cookies()
            
            if not is_valid:
                self._cookie_valid = False
                
                # 发送 Cookie 失效通知（只发送一次）
                if not self._cookie_alert_sent and self.notify_config.get("on_cookie_expired", True):
                    await self.notifier.send_cookie_expired_alert()
                    self._cookie_alert_sent = True
                    logger.warning("已发送 Cookie 失效通知")
                
                return False
            
            # Cookie 有效，重置标记
            self._cookie_valid = True
            self._cookie_alert_sent = False
            return True
            
        except Exception as e:
            logger.error(f"Cookie 检查异常: {e}")
            return False
    
    async def check_product(self, product: dict) -> Optional[ProductState]:
        """
        检查单个商品状态
        
        Args:
            product: 商品配置字典，包含 sku_id 和 name
            
        Returns:
            商品状态对象
        """
        sku_id = product.get("sku_id")
        name = product.get("name", "")
        
        if not sku_id:
            logger.warning("商品配置缺少 sku_id")
            return None
        
        try:
            state = await self.jd_api.get_product_state(sku_id, name)
            logger.info(f"检查商品: {state.name} | 价格: ¥{state.price} | 库存: {state.stock_text}")
            return state
            
        except Exception as e:
            logger.error(f"检查商品 {sku_id} 失败: {e}")
            return None
    
    def should_notify(self, changes: dict) -> bool:
        """判断是否需要发送通知"""
        if changes.get("is_new"):
            # 首次检测，发送通知
            return True
        
        if not changes:
            return False
        
        # 根据配置判断
        if "price" in changes and self.notify_config.get("on_price_change", True):
            return True
        
        if "in_stock" in changes and self.notify_config.get("on_stock_change", True):
            return True
        
        if "is_on_sale" in changes and self.notify_config.get("on_status_change", True):
            return True
        
        if "presale_info" in changes and self.notify_config.get("on_presale_change", True):
            return True
        
        return False
    
    async def run_once(self) -> bool:
        """
        执行一次完整的检查
        
        Returns:
            检查是否成功完成
        """
        logger.info("=" * 50)
        logger.info(f"开始检查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 检查 Cookie
        if not await self.check_cookie():
            logger.error("Cookie 无效，跳过本次检查")
            return False
        
        # 获取商品列表
        products = self.get_products()
        if not products:
            logger.warning("没有配置要监控的商品")
            return False
        
        # 加载上次状态（如果还没加载）
        if not self._last_states:
            self._last_states = self.load_last_state()
        
        # 检查每个商品
        current_states: Dict[str, ProductState] = {}
        
        for product in products:
            new_state = await self.check_product(product)
            
            if new_state is None:
                continue
            
            sku_id = new_state.sku_id
            current_states[sku_id] = new_state
            
            # 对比状态
            old_state = self._last_states.get(sku_id)
            changes = new_state.diff(old_state)
            
            # 判断是否需要通知
            if self.should_notify(changes):
                logger.info(f"检测到变化: {new_state.name}, 变化: {changes}")
                await self.notifier.send_product_alert(new_state, changes)
            else:
                logger.debug(f"无变化: {new_state.name}")
        
        # 更新状态
        if current_states:
            self._last_states.update(current_states)
            self.save_state(self._last_states)
        
        logger.info(f"检查完成，共 {len(current_states)} 个商品")
        return True
    
    async def start(self):
        """启动监控循环"""
        interval = self.config.get("interval", 60)
        
        logger.info("=" * 50)
        logger.info("京东商品监控启动")
        logger.info(f"监控间隔: {interval} 秒")
        logger.info(f"监控模式: {self.config.get('mode', 'multi')}")
        
        products = self.get_products()
        logger.info(f"监控商品数: {len(products)}")
        for p in products:
            logger.info(f"  - {p.get('name', p.get('sku_id'))}")
        
        # 测试 Telegram 连接
        if await self.notifier.test_connection():
            await self.notifier.send_startup_message(products)
        else:
            logger.error("Telegram 连接失败，请检查配置")
        
        # 主循环
        while True:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"监控执行异常: {e}")
                await self.notifier.send_error_alert(f"监控执行异常: {e}")
            
            logger.info(f"等待 {interval} 秒后进行下次检查...")
            await asyncio.sleep(interval)
