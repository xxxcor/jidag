#!/usr/bin/env python3
"""
京东商品监控脚本 - 启动入口

用法：
    python run.py              # 正常启动
    python run.py --test       # 测试模式（只运行一次）
    python run.py --validate   # 只验证 Cookie
"""

import sys
import logging
import asyncio
import argparse
from pathlib import Path

import yaml

# 添加项目根目录到 Python 路径
BASE_PATH = Path(__file__).parent.absolute()
sys.path.insert(0, str(BASE_PATH))

from src.monitor import Monitor
from src.cookie_manager import CookieManager
from src.notifier import TelegramNotifier


def setup_logging(log_level: str = "INFO"):
    """配置日志系统"""
    log_dir = BASE_PATH / "logs"
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / "monitor.log"
    
    # 日志格式
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    # 文件处理器
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # 降低 httpx 的日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def load_config() -> dict:
    """加载配置文件"""
    config_path = BASE_PATH / "config" / "config.yaml"
    
    if not config_path.exists():
        print(f"错误：配置文件不存在 - {config_path}")
        sys.exit(1)
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    return config


async def validate_cookie():
    """验证 Cookie 是否有效"""
    print("正在验证 Cookie...")
    
    cookie_path = BASE_PATH / "config" / "cookies.txt"
    cookie_manager = CookieManager(str(cookie_path))
    
    try:
        cookie_manager.load_cookies()
    except Exception as e:
        print(f"❌ Cookie 加载失败: {e}")
        return False
    
    is_valid = await cookie_manager.validate_cookies()
    
    if is_valid:
        print(f"✅ Cookie 有效！用户: {cookie_manager.username}")
        return True
    else:
        print("❌ Cookie 已失效，请重新登录获取")
        return False


async def test_telegram(config: dict):
    """测试 Telegram 连接"""
    print("正在测试 Telegram 连接...")
    
    tg_config = config.get("telegram", {})
    notifier = TelegramNotifier(
        bot_token=tg_config.get("bot_token", ""),
        chat_id=tg_config.get("chat_id", ""),
        config=config
    )
    
    if await notifier.test_connection():
        print("✅ Telegram 连接成功！")
        
        # 发送测试消息
        await notifier.send_message("🧪 *测试消息*\n\n这是一条来自京东商品监控脚本的测试消息。")
        print("✅ 测试消息已发送！")
        return True
    else:
        print("❌ Telegram 连接失败，请检查 bot_token 和 chat_id")
        return False


async def run_test(config: dict):
    """测试模式：只运行一次检查"""
    print("=" * 50)
    print("测试模式启动")
    print("=" * 50)
    
    monitor = Monitor(config, BASE_PATH)
    await monitor.run_once()
    
    print("=" * 50)
    print("测试完成")


async def run_monitor(config: dict):
    """启动监控"""
    monitor = Monitor(config, BASE_PATH)
    await monitor.start()


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="京东商品监控脚本")
    parser.add_argument("--test", action="store_true", help="测试模式，只运行一次")
    parser.add_argument("--validate", action="store_true", help="只验证 Cookie")
    parser.add_argument("--test-tg", action="store_true", help="测试 Telegram 连接")
    parser.add_argument("--log-level", default="INFO", help="日志级别 (DEBUG/INFO/WARNING/ERROR)")
    
    args = parser.parse_args()
    
    # 配置日志
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    # 加载配置
    try:
        config = load_config()
    except Exception as e:
        print(f"加载配置失败: {e}")
        sys.exit(1)
    
    # 根据参数执行不同操作
    if args.validate:
        result = asyncio.run(validate_cookie())
        sys.exit(0 if result else 1)
    
    if args.test_tg:
        result = asyncio.run(test_telegram(config))
        sys.exit(0 if result else 1)
    
    if args.test:
        asyncio.run(run_test(config))
        sys.exit(0)
    
    # 正常启动监控
    try:
        asyncio.run(run_monitor(config))
    except KeyboardInterrupt:
        logger.info("监控已停止")
        sys.exit(0)
    except Exception as e:
        logger.error(f"监控异常退出: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
