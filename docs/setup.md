# Claude Code Telegram 通知系统部署指南

## 前置要求

- Python 3.11+
- Docker & Docker Compose (可选)
- Telegram Bot Token
- VPS 或云服务器

## 1. 创建 Telegram Bot

1. 在 Telegram 中找到 @BotFather
2. 发送 `/newbot` 创建新 Bot
3. 记录 Bot Token
4. 发送 `/setprivacy` 并选择 `Disable` (允许 Bot 读取群组消息)
5. 获取你的 Chat ID:
   - 给 Bot 发送一条消息
   - 访问 `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - 找到 `chat.id` 字段

## 2. 部署 Server

### 方式 A: Docker 部署 (推荐)

```bash
cd server

# 创建配置文件
cp .env.example .env

# 编辑配置
vim .env
```

填入配置:
```
TELEGRAM_BOT_TOKEN=your_bot_token
ALLOWED_CHAT_IDS=your_chat_id
API_KEY=生成一个随机密钥
```

启动服务:
```bash
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 方式 B: 直接运行

```bash
cd server

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
vim .env

# 运行
PYTHONPATH=src python -m claude_notify.main
```

### 验证部署

```bash
# 健康检查
curl http://your-server:8000/health
# 期望: {"status": "ok"}
```

## 3. 安装本地 Hook

```bash
cd local
./install.sh
```

编辑配置:
```bash
vim ~/.claude/hooks/.env
```

填入:
```
CLAUDE_NOTIFY_API_URL=http://your-server:8000
CLAUDE_NOTIFY_API_KEY=你在 server .env 中设置的 API_KEY
```

## 4. 配置 Claude Code

编辑 `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/telegram-notify.sh",
            "timeout": 3600
          }
        ]
      }
    ],
    "Notification": [
      {
        "matcher": "permission_prompt|idle_prompt",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/telegram-notify.sh"
          }
        ]
      }
    ]
  }
}
```

## 5. 测试

### 测试 API

```bash
curl -X POST http://your-server:8000/notify \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test123","status":"completed","summary":"测试通知","cwd":"/tmp"}'
```

### 测试 Hook

```bash
echo '{"session_id":"test456","stop_hook_active":false,"cwd":"/tmp"}' | \
  ~/.claude/hooks/telegram-notify.sh
```

### 端到端测试

```bash
claude "创建一个 hello.txt 文件"
# 等待 Telegram 通知
# 回复继续或 /done
```

## 6. 禁用通知

当你在电脑前主动使用 Claude Code 时，可以临时禁用通知：

### 方式 A: 环境变量 (单次会话)

```bash
# 启动时禁用通知
TELEGRAM_NOTIFY_ENABLED=0 claude "帮我重构这个项目"
```

### 方式 B: 文件锁 (持续禁用)

```bash
# 禁用通知
touch ~/.claude/hooks/.no-notify

# 启用通知
rm ~/.claude/hooks/.no-notify
```

**推荐**: 添加别名到 `~/.bashrc` 或 `~/.zshrc`:

```bash
alias notify-off='touch ~/.claude/hooks/.no-notify && echo "🔕 Telegram 通知已禁用"'
alias notify-on='rm -f ~/.claude/hooks/.no-notify && echo "🔔 Telegram 通知已启用"'
alias notify-status='[ -f ~/.claude/hooks/.no-notify ] && echo "🔕 通知已禁用" || echo "🔔 通知已启用"'
```

使用:
```bash
notify-off    # 禁用
notify-on     # 启用
notify-status # 查看状态
```

## 故障排除

### Hook 不触发

1. 检查 `~/.claude/settings.json` 语法
2. 运行 `claude --debug` 查看 hook 日志
3. 确认脚本有执行权限: `chmod +x ~/.claude/hooks/telegram-notify.sh`

### 通知发送失败

1. 检查 VPS 服务是否运行: `curl http://your-server:8000/health`
2. 检查 API Key 是否正确
3. 查看服务日志: `docker-compose logs -f`

### Telegram 收不到消息

1. 确认 Bot Token 正确
2. 确认 Chat ID 在 ALLOWED_CHAT_IDS 中
3. 确认已给 Bot 发送过消息激活对话
