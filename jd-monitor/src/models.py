"""
数据模型定义

定义商品状态、价格信息等数据结构
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ProductState:
    """商品状态数据类"""
    
    sku_id: str                          # 商品 SKU ID
    name: str                            # 商品名称
    price: float = 0.0                   # 当前价格
    original_price: float = 0.0          # 原价
    in_stock: bool = False               # 是否有货
    stock_text: str = ""                 # 库存描述（"有货"/"无货"/"预约"等）
    is_on_sale: bool = True              # 是否上架
    presale_info: str = ""               # 预约/抢购信息
    product_url: str = ""                # 商品链接
    updated_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.product_url and self.sku_id:
            self.product_url = f"https://item.jd.com/{self.sku_id}.html"
    
    def diff(self, other: Optional['ProductState']) -> dict:
        """
        对比两个状态，返回差异
        
        Args:
            other: 另一个商品状态，如果为 None 表示首次检测
            
        Returns:
            差异字典，包含变化的字段和新旧值
        """
        if other is None:
            return {"is_new": True}
        
        changes = {}
        
        # 价格变化
        if self.price != other.price:
            changes["price"] = {
                "old": other.price,
                "new": self.price,
                "direction": "down" if self.price < other.price else "up"
            }
        
        # 库存变化
        if self.in_stock != other.in_stock:
            changes["in_stock"] = {
                "old": other.in_stock,
                "new": self.in_stock,
                "old_text": other.stock_text,
                "new_text": self.stock_text
            }
        
        # 库存描述变化（即使有货状态相同，描述可能不同）
        if self.stock_text != other.stock_text and "in_stock" not in changes:
            changes["stock_text"] = {
                "old": other.stock_text,
                "new": self.stock_text
            }
        
        # 上下架状态变化
        if self.is_on_sale != other.is_on_sale:
            changes["is_on_sale"] = {
                "old": other.is_on_sale,
                "new": self.is_on_sale
            }
        
        # 预约信息变化
        if self.presale_info != other.presale_info:
            changes["presale_info"] = {
                "old": other.presale_info,
                "new": self.presale_info
            }
        
        return changes
    
    def to_dict(self) -> dict:
        """转换为字典，用于 JSON 序列化"""
        return {
            "sku_id": self.sku_id,
            "name": self.name,
            "price": self.price,
            "original_price": self.original_price,
            "in_stock": self.in_stock,
            "stock_text": self.stock_text,
            "is_on_sale": self.is_on_sale,
            "presale_info": self.presale_info,
            "product_url": self.product_url,
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ProductState':
        """从字典创建实例"""
        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        else:
            updated_at = datetime.now()
        
        return cls(
            sku_id=data.get("sku_id", ""),
            name=data.get("name", ""),
            price=data.get("price", 0.0),
            original_price=data.get("original_price", 0.0),
            in_stock=data.get("in_stock", False),
            stock_text=data.get("stock_text", ""),
            is_on_sale=data.get("is_on_sale", True),
            presale_info=data.get("presale_info", ""),
            product_url=data.get("product_url", ""),
            updated_at=updated_at
        )


@dataclass
class NotifyEvent:
    """通知事件"""
    
    product: ProductState                # 商品状态
    changes: dict                        # 变化内容
    event_type: str                      # 事件类型: price_change, stock_change, status_change, presale_change
    created_at: datetime = field(default_factory=datetime.now)
