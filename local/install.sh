#!/bin/bash
# local/install.sh
# 安装 Claude Code Telegram 通知 Hook

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOKS_DIR="$HOME/.claude/hooks"

echo "🚀 安装 Claude Code Telegram 通知 Hook"
echo ""

# 创建 hooks 目录
mkdir -p "$HOOKS_DIR"

# 复制脚本
cp "$SCRIPT_DIR/telegram-notify.sh" "$HOOKS_DIR/"
chmod +x "$HOOKS_DIR/telegram-notify.sh"

# 复制配置模板
if [ ! -f "$HOOKS_DIR/.env" ]; then
    cp "$SCRIPT_DIR/.env.example" "$HOOKS_DIR/.env"
    echo "📝 已创建配置文件: $HOOKS_DIR/.env"
    echo "   请编辑此文件填入你的 API 配置"
else
    echo "⚠️  配置文件已存在: $HOOKS_DIR/.env"
fi

# 检查 jq 是否安装
if ! command -v jq &> /dev/null; then
    echo ""
    echo "⚠️  需要安装 jq:"
    echo "   macOS: brew install jq"
    echo "   Ubuntu: sudo apt install jq"
fi

# 生成 settings.json 配置片段
echo ""
echo "📋 请将以下配置添加到 ~/.claude/settings.json:"
echo ""
cat << 'SETTINGS'
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
SETTINGS

echo ""
echo "✅ 安装完成!"
echo ""
echo "下一步:"
echo "1. 编辑 $HOOKS_DIR/.env 填入 API 配置"
echo "2. 将上述 hooks 配置添加到 ~/.claude/settings.json"
echo "3. 重启 Claude Code"
