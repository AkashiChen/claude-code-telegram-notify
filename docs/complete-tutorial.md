# Claude Code Telegram 通知系统 - 完整部署教程

本教程将指导你从零开始部署整个系统，包括获取 Telegram Bot Token、部署 VPS 服务、配置本地 Hook。

---

## 📋 目录

1. [创建 Telegram Bot 并获取 Token](#1-创建-telegram-bot-并获取-token)
2. [获取你的 Chat ID](#2-获取你的-chat-id)
3. [VPS 部署服务](#3-vps-部署服务)
4. [本地配置 Hook](#4-本地配置-hook)
5. [端到端测试](#5-端到端测试)

---

## 1. 创建 Telegram Bot 并获取 Token

### Step 1.1: 找到 BotFather

在 Telegram 中搜索 `@BotFather`，这是 Telegram 官方的 Bot 管理机器人。

![BotFather](https://core.telegram.org/file/811140327/1/zlN4goPTupk/9ff2f2f01c4bd1b013)

### Step 1.2: 创建新 Bot

1. 向 BotFather 发送 `/newbot`
2. 输入 Bot 的**显示名称**（例如：`Claude Code Notify`）
3. 输入 Bot 的**用户名**（必须以 `bot` 结尾，例如：`my_claude_notify_bot`）

### Step 1.3: 获取 Bot Token

创建成功后，BotFather 会返回类似这样的消息：

```
Done! Congratulations on your new bot. You will find it at t.me/my_claude_notify_bot.

Use this token to access the HTTP API:
7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

Keep your token secure and store it safely.
```

**⚠️ 重要**: 复制并保存这个 Token（格式：`数字:字母数字字符串`），这是你的 `TELEGRAM_BOT_TOKEN`。

### Step 1.4: 配置 Bot 隐私设置（可选）

如果你打算在群组中使用 Bot：

1. 向 BotFather 发送 `/setprivacy`
2. 选择你的 Bot
3. 选择 `Disable`

这允许 Bot 读取群组中的所有消息。

---

## 2. 获取你的 Chat ID

Chat ID 是你与 Bot 对话的唯一标识，用于限制谁可以接收通知。

### Step 2.1: 激活 Bot

在 Telegram 中找到你刚创建的 Bot（搜索 `@你的bot用户名`），点击 `Start` 或发送任意消息。

### Step 2.2: 获取 Chat ID

在浏览器中访问以下 URL（替换 `<YOUR_BOT_TOKEN>`）：

```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
```

例如：
```
https://api.telegram.org/bot7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/getUpdates
```

### Step 2.3: 找到 Chat ID

返回的 JSON 中找到 `chat.id` 字段：

```json
{
  "ok": true,
  "result": [
    {
      "update_id": 123456789,
      "message": {
        "message_id": 1,
        "from": {
          "id": 987654321,
          "first_name": "Your Name"
        },
        "chat": {
          "id": 987654321,    <-- 这就是你的 Chat ID
          "first_name": "Your Name",
          "type": "private"
        },
        "text": "Hello"
      }
    }
  ]
}
```

**记录这个 Chat ID**（例如：`987654321`），这是你的 `ALLOWED_CHAT_IDS`。

> 💡 **提示**: 如果 `result` 为空数组 `[]`，说明你还没有给 Bot 发送消息，请先发送一条消息再刷新页面。

---

## 3. VPS 部署服务

### 选择 VPS 提供商

推荐的 VPS 提供商（按价格排序）：

| 提供商 | 最低价格 | 特点 |
|--------|---------|------|
| [Vultr](https://www.vultr.com/) | $3.5/月 | 全球节点，按小时计费 |
| [DigitalOcean](https://www.digitalocean.com/) | $4/月 | 简单易用，文档丰富 |
| [Linode](https://www.linode.com/) | $5/月 | 稳定可靠 |
| [AWS Lightsail](https://aws.amazon.com/lightsail/) | $3.5/月 | AWS 生态 |
| [阿里云](https://www.aliyun.com/) | ¥24/月 | 国内访问快 |
| [腾讯云](https://cloud.tencent.com/) | ¥29/月 | 国内访问快 |

> 💡 **最低配置**: 1 CPU, 512MB RAM 即可运行本服务

### Step 3.1: 创建 VPS 实例

以 Vultr 为例：

1. 注册账号并登录
2. 点击 "Deploy New Server"
3. 选择：
   - **Server Type**: Cloud Compute (Shared CPU)
   - **Location**: 选择离你近的节点（如 Tokyo, Singapore）
   - **OS**: Ubuntu 22.04 LTS
   - **Plan**: 最便宜的即可（$3.5/月）
4. 点击 "Deploy Now"

### Step 3.2: 连接到 VPS

```bash
# 使用 SSH 连接（替换为你的 VPS IP）
ssh root@your-vps-ip

# 首次连接会提示确认指纹，输入 yes
```

### Step 3.3: 安装 Docker

```bash
# 更新系统
apt update && apt upgrade -y

# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 安装 Docker Compose
apt install docker-compose -y

# 验证安装
docker --version
docker-compose --version
```

### Step 3.4: 部署服务

```bash
# 克隆项目（或上传代码）
git clone https://github.com/your-username/claude-code-telegram-notify.git
cd claude-code-telegram-notify/server

# 创建配置文件
cp .env.example .env

# 编辑配置
nano .env
```

填入以下内容（替换为你的实际值）：

```bash
# Telegram 配置
TELEGRAM_BOT_TOKEN=7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ALLOWED_CHAT_IDS=987654321

# API 配置（生成一个随机密钥）
API_KEY=your_random_api_key_here_make_it_long_and_secure

# 服务配置
HOST=0.0.0.0
PORT=8000
```

> 💡 **生成随机 API Key**:
> ```bash
> openssl rand -hex 32
> ```

启动服务：

```bash
# 启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 检查状态
docker-compose ps
```

### Step 3.5: 配置防火墙（可选但推荐）

```bash
# 允许 SSH 和服务端口
ufw allow 22
ufw allow 8000
ufw enable
```

### Step 3.6: 验证部署

```bash
# 在 VPS 上测试
curl http://localhost:8000/health
# 期望: {"status":"ok"}

# 从本地测试（替换为你的 VPS IP）
curl http://your-vps-ip:8000/health
# 期望: {"status":"ok"}
```

### Step 3.7: 配置域名和 HTTPS（可选）

如果你有域名，可以配置 Nginx 反向代理 + Let's Encrypt SSL：

```bash
# 安装 Nginx 和 Certbot
apt install nginx certbot python3-certbot-nginx -y

# 创建 Nginx 配置
cat > /etc/nginx/sites-available/claude-notify << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

# 启用配置
ln -s /etc/nginx/sites-available/claude-notify /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# 获取 SSL 证书
certbot --nginx -d your-domain.com
```

---

## 4. 本地配置 Hook

### Step 4.1: 安装 Hook 脚本

在你的本地电脑上：

```bash
cd claude-code-telegram-notify/local
./install.sh
```

这会：
- 复制 `telegram-notify.sh` 到 `~/.claude/hooks/`
- 创建 `.env.example` 配置模板

### Step 4.2: 配置环境变量

```bash
# 编辑配置
vim ~/.claude/hooks/.env
```

填入：

```bash
# VPS 服务地址（替换为你的 VPS IP 或域名）
CLAUDE_NOTIFY_API_URL=http://your-vps-ip:8000

# API 密钥（与 VPS 上 .env 中的 API_KEY 相同）
CLAUDE_NOTIFY_API_KEY=your_random_api_key_here_make_it_long_and_secure

# 轮询配置（可选）
POLL_INTERVAL=3
POLL_TIMEOUT=3600
```

### Step 4.3: 配置 Claude Code

编辑 `~/.claude/settings.json`：

```bash
vim ~/.claude/settings.json
```

添加 hooks 配置：

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
    ]
  }
}
```

> ⚠️ **注意**: 如果文件已有内容，需要合并 JSON，确保语法正确。

### Step 4.4: 验证配置

```bash
# 检查脚本权限
ls -la ~/.claude/hooks/telegram-notify.sh
# 应该有 x 权限: -rwxr-xr-x

# 检查配置文件
cat ~/.claude/hooks/.env

# 测试连接 VPS
curl http://your-vps-ip:8000/health
```

---

## 5. 端到端测试

### Step 5.1: 测试 API 通知

```bash
# 发送测试通知
curl -X POST http://your-vps-ip:8000/notify \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test123","status":"completed","summary":"🎉 测试通知成功！","cwd":"/tmp"}'
```

**期望结果**: 你的 Telegram 收到一条通知消息。

### Step 5.2: 测试 Hook 脚本

```bash
# 模拟 Claude Code 调用 Hook
echo '{"session_id":"test456","stop_hook_active":false,"cwd":"/tmp"}' | \
  ~/.claude/hooks/telegram-notify.sh
```

**期望结果**:
1. Telegram 收到通知
2. 脚本等待你的回复（轮询中）
3. 在 Telegram 中回复 `/done`
4. 脚本退出

### Step 5.3: 完整端到端测试

```bash
# 启动 Claude Code 执行任务
claude "创建一个 hello.txt 文件，内容是 Hello World"
```

**期望流程**:
1. Claude 完成任务
2. 📱 Telegram 收到通知（包含任务摘要）
3. 你可以：
   - 回复文字继续任务（如："再创建一个 goodbye.txt"）
   - 点击按钮或回复 `/done` 结束
4. Claude 根据你的回复继续或停止

---

## 🎉 完成！

恭喜你完成了整个系统的部署！现在你可以：

- 启动长任务后离开电脑
- 通过 Telegram 接收任务完成通知
- 远程回复继续执行新任务
- 使用 `notify-off` / `notify-on` 控制通知开关

---

## 📚 附录

### 常用命令

```bash
# VPS 上
docker-compose logs -f      # 查看日志
docker-compose restart      # 重启服务
docker-compose down         # 停止服务
docker-compose up -d        # 启动服务

# 本地
notify-off                  # 禁用通知
notify-on                   # 启用通知
notify-status               # 查看状态
```

### 配置汇总

| 配置项 | 位置 | 说明 |
|--------|------|------|
| `TELEGRAM_BOT_TOKEN` | VPS `.env` | 从 BotFather 获取 |
| `ALLOWED_CHAT_IDS` | VPS `.env` | 从 getUpdates API 获取 |
| `API_KEY` | VPS `.env` + 本地 `.env` | 自己生成，两边一致 |
| `CLAUDE_NOTIFY_API_URL` | 本地 `.env` | VPS 地址 |

### 故障排除

详见 [setup.md](./setup.md#故障排除)
