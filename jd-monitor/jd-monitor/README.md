# 京东商品监控脚本

📦 监控京东商品的价格、库存、上下架状态，并在状态变化时通过 Telegram 发送通知。

## 功能特性

- ✅ 监控商品价格变化（涨价/降价）
- ✅ 监控库存状态（有货/无货/预约）
- ✅ 监控上下架状态
- ✅ 监控预约/抢购信息
- ✅ Cookie 失效自动通知
- ✅ 支持单商品/多商品切换
- ✅ Telegram 实时推送通知
- ✅ 状态持久化（重启后恢复）

## 项目结构

```
jd-monitor/
├── config/
│   ├── config.yaml          # 主配置文件
│   └── cookies.txt          # JD Cookie
├── src/
│   ├── monitor.py           # 主监控逻辑
│   ├── jd_api.py            # JD 商品抓取
│   ├── notifier.py          # Telegram 通知
│   ├── cookie_manager.py    # Cookie 管理
│   └── models.py            # 数据模型
├── data/
│   └── state.json           # 商品状态缓存
├── logs/
│   └── monitor.log          # 运行日志
├── requirements.txt
├── run.py                   # 启动入口
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
cd jd-monitor
pip install -r requirements.txt
```

### 2. 配置 Telegram Bot

1. 在 Telegram 中找到 `@BotFather`
2. 发送 `/newbot` 创建新机器人
3. 记录返回的 Bot Token
4. 获取你的 Chat ID：
   - 方法1：发送消息给 `@userinfobot`
   - 方法2：发送消息给你的 Bot，然后访问 `https://api.telegram.org/bot<TOKEN>/getUpdates`

### 3. 配置京东 Cookie

1. 在浏览器中登录 [jd.com](https://www.jd.com)
2. 按 `F12` 打开开发者工具
3. 切换到 `Network`（网络）标签
4. 刷新页面，点击任意请求
5. 在 `Request Headers` 中找到 `Cookie`
6. 复制完整的 Cookie 值到 `config/cookies.txt`

### 4. 修改配置文件

编辑 `config/config.yaml`：

```yaml
# 监控模式
mode: multi  # single 或 multi

# 商品列表
products:
  - sku_id: "100012043978"
    name: "iPhone 15 Pro Max"
  - sku_id: "100026789012"
    name: "PS5 国行"

# Telegram 配置
telegram:
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"

# 监控间隔（秒）
interval: 60
```

### 5. 启动脚本

```bash
# 验证 Cookie
python run.py --validate

# 测试 Telegram
python run.py --test-tg

# 测试运行（只执行一次）
python run.py --test

# 正式启动
python run.py
```

## 命令行参数

| 参数 | 说明 |
|-----|-----|
| `--test` | 测试模式，只运行一次检查 |
| `--validate` | 只验证 Cookie 是否有效 |
| `--test-tg` | 测试 Telegram 连接并发送测试消息 |
| `--log-level` | 日志级别：DEBUG/INFO/WARNING/ERROR |

## 服务器部署（24小时运行）

### 使用 systemd（推荐）

1. 创建服务文件：

```bash
sudo nano /etc/systemd/system/jd-monitor.service
```

2. 写入以下内容：

```ini
[Unit]
Description=JD Product Monitor
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/jd-monitor
ExecStart=/usr/bin/python3 run.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

3. 启用并启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable jd-monitor
sudo systemctl start jd-monitor
```

4. 查看运行状态：

```bash
sudo systemctl status jd-monitor
journalctl -u jd-monitor -f  # 查看实时日志
```

### 使用 Screen

```bash
screen -S jd-monitor
python run.py
# 按 Ctrl+A, D 分离会话
```

## 通知示例

### 价格变化通知
```
📦 商品状态变化

🏷️ iPhone 15 Pro Max
🔗 https://item.jd.com/100012043978.html

💰 价格: ¥8999 → ¥7999 ⬇️

⏰ 2026-02-01 16:00:00
```

### Cookie 失效通知
```
🚨 Cookie 已失效

京东登录状态已过期，请及时更新 Cookie！

📝 更新步骤：
1. 在浏览器中重新登录 jd.com
2. 按 F12 打开开发者工具
3. 复制 Request Headers 中的 Cookie
4. 更新 config/cookies.txt 文件

⏰ 2026-02-01 16:00:00
```

## 常见问题

### Q: Cookie 多久会失效？
A: 一般 7-30 天不等，建议定期检查。

### Q: 如何获取商品 SKU ID？
A: 打开商品页面，URL 中的数字就是 SKU ID，例如 `https://item.jd.com/100012043978.html` 中的 `100012043978`。

### Q: 监控间隔设置多少合适？
A: 建议 60-120 秒，过于频繁可能触发风控。

### Q: 如何监控多个地区的库存？
A: 修改 `config.yaml` 中的 `area` 参数，格式为 `省_市_区县_街道`。

## 许可证

MIT License
