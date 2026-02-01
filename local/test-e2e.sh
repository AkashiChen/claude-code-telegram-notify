#!/bin/bash
# local/test-e2e.sh
# 端到端测试脚本 - 测试与真实 VPS 服务的连接

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🧪 Claude Code Telegram Notify - 端到端测试"
echo ""

# 加载配置
if [ -f "$SCRIPT_DIR/.env" ]; then
    source "$SCRIPT_DIR/.env"
elif [ -f "$HOME/.claude/hooks/.env" ]; then
    source "$HOME/.claude/hooks/.env"
fi

# 检查配置
check_config() {
    local missing=()

    if [ -z "$CLAUDE_NOTIFY_API_URL" ]; then
        missing+=("CLAUDE_NOTIFY_API_URL")
    fi

    if [ -z "$CLAUDE_NOTIFY_API_KEY" ]; then
        missing+=("CLAUDE_NOTIFY_API_KEY")
    fi

    if [ ${#missing[@]} -gt 0 ]; then
        echo "❌ 缺少配置: ${missing[*]}"
        echo ""
        echo "请在以下位置配置环境变量:"
        echo "  - $SCRIPT_DIR/.env"
        echo "  - 或 ~/.claude/hooks/.env"
        echo ""
        echo "示例:"
        echo "  CLAUDE_NOTIFY_API_URL=http://your-vps-ip:8000"
        echo "  CLAUDE_NOTIFY_API_KEY=your_api_key"
        exit 1
    fi

    echo "📋 配置信息:"
    echo "   API URL: $CLAUDE_NOTIFY_API_URL"
    echo "   API Key: ${CLAUDE_NOTIFY_API_KEY:0:8}..."
    echo ""
}

# 测试 1: 健康检查
test_health() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📡 测试 1: 健康检查"
    echo -n "   GET $CLAUDE_NOTIFY_API_URL/health: "

    response=$(curl -s --connect-timeout 10 "$CLAUDE_NOTIFY_API_URL/health" 2>&1) || {
        echo "❌ FAIL - 无法连接到服务"
        echo "   请检查:"
        echo "   1. VPS 服务是否运行: docker-compose ps"
        echo "   2. 防火墙是否开放端口"
        echo "   3. API URL 是否正确"
        return 1
    }

    if [ "$response" = '{"status":"ok"}' ]; then
        echo "✅ PASS"
    else
        echo "❌ FAIL - 响应: $response"
        return 1
    fi
}

# 测试 2: API 认证
test_auth() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔐 测试 2: API 认证"

    # 测试错误的 API Key
    echo -n "   错误 API Key (应返回 401): "
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "$CLAUDE_NOTIFY_API_URL/notify" \
        -H "Authorization: Bearer wrong_key" \
        -H "Content-Type: application/json" \
        -d '{"session_id":"test","status":"completed","summary":"test","cwd":"/tmp"}')

    if [ "$http_code" = "401" ]; then
        echo "✅ PASS"
    else
        echo "❌ FAIL - HTTP $http_code"
        return 1
    fi

    # 测试正确的 API Key
    echo -n "   正确 API Key (应返回 200): "
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "$CLAUDE_NOTIFY_API_URL/notify" \
        -H "Authorization: Bearer $CLAUDE_NOTIFY_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"session_id":"auth_test","status":"completed","summary":"认证测试","cwd":"/tmp"}')

    if [ "$http_code" = "200" ]; then
        echo "✅ PASS"
    else
        echo "❌ FAIL - HTTP $http_code"
        echo "   请检查 API Key 是否与 VPS 上的配置一致"
        return 1
    fi
}

# 测试 3: 发送通知到 Telegram
test_telegram_notify() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📱 测试 3: 发送 Telegram 通知"
    echo -n "   POST /notify: "

    SESSION_ID="e2e_test_$(date +%s)"

    response=$(curl -s -X POST "$CLAUDE_NOTIFY_API_URL/notify" \
        -H "Authorization: Bearer $CLAUDE_NOTIFY_API_KEY" \
        -H "Content-Type: application/json" \
        -d "{
            \"session_id\": \"$SESSION_ID\",
            \"status\": \"completed\",
            \"summary\": \"🧪 端到端测试通知\\n\\n这是一条测试消息，请回复任意内容或点击按钮。\",
            \"cwd\": \"$(pwd)\",
            \"buttons\": [\"继续\", \"结束\"]
        }")

    ok=$(echo "$response" | jq -r '.ok' 2>/dev/null)

    if [ "$ok" = "true" ]; then
        echo "✅ PASS"
        echo ""
        echo "   📱 请检查你的 Telegram 是否收到通知！"
        echo "   Session ID: $SESSION_ID"
    else
        echo "❌ FAIL - $response"
        echo ""
        echo "   可能的原因:"
        echo "   1. Telegram Bot Token 无效"
        echo "   2. Chat ID 不在白名单中"
        echo "   3. Bot 未被激活（需要先给 Bot 发送消息）"
        return 1
    fi
}

# 测试 4: 轮询回复（可选）
test_poll_reply() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "💬 测试 4: 轮询回复 (可选)"
    echo ""

    read -p "   是否测试回复功能？需要你在 Telegram 中回复 (y/N): " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "   ⏭️  跳过回复测试"
        return 0
    fi

    # 发送新通知
    SESSION_ID="reply_test_$(date +%s)"

    echo ""
    echo "   发送测试通知..."
    response=$(curl -s -X POST "$CLAUDE_NOTIFY_API_URL/notify" \
        -H "Authorization: Bearer $CLAUDE_NOTIFY_API_KEY" \
        -H "Content-Type: application/json" \
        -d "{
            \"session_id\": \"$SESSION_ID\",
            \"status\": \"completed\",
            \"summary\": \"💬 回复测试\\n\\n请在 30 秒内回复任意内容...\",
            \"cwd\": \"$(pwd)\"
        }")

    echo "   📱 请在 Telegram 中回复这条消息..."
    echo "   等待回复中 (30秒超时)..."
    echo ""

    # 轮询等待回复
    for i in {1..10}; do
        sleep 3
        echo -n "   轮询 $i/10: "

        response=$(curl -s "$CLAUDE_NOTIFY_API_URL/reply/$SESSION_ID" \
            -H "Authorization: Bearer $CLAUDE_NOTIFY_API_KEY")

        has_reply=$(echo "$response" | jq -r '.has_reply' 2>/dev/null)

        if [ "$has_reply" = "true" ]; then
            reply=$(echo "$response" | jq -r '.reply' 2>/dev/null)
            action=$(echo "$response" | jq -r '.action' 2>/dev/null)
            echo "✅ 收到回复!"
            echo ""
            echo "   回复内容: $reply"
            echo "   动作类型: $action"

            # 确认收到
            curl -s -X POST "$CLAUDE_NOTIFY_API_URL/ack/$SESSION_ID" \
                -H "Authorization: Bearer $CLAUDE_NOTIFY_API_KEY" > /dev/null

            return 0
        else
            echo "等待中..."
        fi
    done

    echo ""
    echo "   ⏱️  超时 - 未收到回复"
    echo "   这不影响基本功能，只是回复测试未完成"
}

# 测试 5: Hook 脚本集成测试
test_hook_script() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🪝 测试 5: Hook 脚本集成"

    HOOK_SCRIPT="$SCRIPT_DIR/telegram-notify.sh"

    if [ ! -f "$HOOK_SCRIPT" ]; then
        HOOK_SCRIPT="$HOME/.claude/hooks/telegram-notify.sh"
    fi

    if [ ! -f "$HOOK_SCRIPT" ]; then
        echo "   ⚠️  未找到 Hook 脚本，跳过此测试"
        return 0
    fi

    echo -n "   stop_hook_active=true (应直接退出): "
    result=$(echo '{"session_id":"hook_test","stop_hook_active":true,"cwd":"/tmp"}' | \
        bash "$HOOK_SCRIPT" 2>&1) || true

    if [ -z "$result" ]; then
        echo "✅ PASS"
    else
        echo "❌ FAIL - $result"
        return 1
    fi

    echo -n "   禁用开关 TELEGRAM_NOTIFY_ENABLED=0: "
    result=$(echo '{"session_id":"hook_test2","stop_hook_active":false,"cwd":"/tmp"}' | \
        TELEGRAM_NOTIFY_ENABLED=0 bash "$HOOK_SCRIPT" 2>&1) || true

    if [ -z "$result" ]; then
        echo "✅ PASS"
    else
        echo "❌ FAIL - $result"
        return 1
    fi
}

# 主流程
main() {
    check_config

    test_health || exit 1
    test_auth || exit 1
    test_telegram_notify || exit 1
    test_hook_script || exit 1
    test_poll_reply

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🎉 端到端测试完成!"
    echo ""
    echo "下一步:"
    echo "  1. 确认 Telegram 收到了测试通知"
    echo "  2. 运行 Claude Code 进行真实测试:"
    echo "     claude \"创建一个 hello.txt 文件\""
    echo ""
}

main "$@"
