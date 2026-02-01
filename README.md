# Claude Code Telegram Notify

Claude Code 任务通知系统 - 通过 Telegram 接收任务完成通知并远程回复继续执行。

## 功能

- 📬 任务完成时发送 Telegram 通知
- 🤖 智能摘要（可选）
- 💬 支持远程回复继续执行
- 🧵 同一 Session 在同一 Thread 中交互
- 🔘 按钮快捷操作 + 文本回复

## 快速开始

### 1. 部署 Server

```bash
cd server
cp .env.example .env
# 编辑 .env 填入配置
docker-compose up -d
```

### 2. 安装本地 Hook

```bash
cd local
./install.sh
```

### 3. 配置环境变量

编辑 `~/.claude/hooks/.env`

## 文档

- [部署指南](docs/setup.md)
