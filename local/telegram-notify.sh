#!/bin/bash
# local/telegram-notify.sh
# Claude Code Stop/Notification Hook - Telegram 通知脚本

set -e

# 加载配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
    source "$SCRIPT_DIR/.env"
elif [ -f "$HOME/.claude/hooks/.env" ]; then
    source "$HOME/.claude/hooks/.env"
fi

# 默认配置
CLAUDE_NOTIFY_API_URL="${CLAUDE_NOTIFY_API_URL:-http://localhost:8000}"
CLAUDE_NOTIFY_API_KEY="${CLAUDE_NOTIFY_API_KEY:-}"
POLL_INTERVAL="${POLL_INTERVAL:-3}"
POLL_TIMEOUT="${POLL_TIMEOUT:-3600}"

# 读取 stdin JSON 输入
INPUT=$(cat)

# 解析输入
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')
HOOK_EVENT_NAME=$(echo "$INPUT" | jq -r '.hook_event_name // "Stop"')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty')

# 如果是 Notification 事件，获取额外字段
NOTIFICATION_TYPE=$(echo "$INPUT" | jq -r '.notification_type // empty')
MESSAGE=$(echo "$INPUT" | jq -r '.message // empty')

# 检查是否是 stop hook 触发的继续（避免无限循环）
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
    exit 0
fi

# 检查必要配置
if [ -z "$CLAUDE_NOTIFY_API_KEY" ]; then
    echo "Error: CLAUDE_NOTIFY_API_KEY not set" >&2
    exit 0  # 不阻塞 Claude
fi

if [ -z "$SESSION_ID" ]; then
    echo "Error: session_id not found in input" >&2
    exit 0
fi

# 确定状态类型
STATUS="completed"
if [ "$HOOK_EVENT_NAME" = "Notification" ]; then
    case "$NOTIFICATION_TYPE" in
        permission_prompt) STATUS="permission" ;;
        idle_prompt) STATUS="idle" ;;
        *) STATUS="completed" ;;
    esac
fi

# 生成摘要
generate_summary() {
    local summary=""

    # 如果有 Notification 消息，使用它
    if [ -n "$MESSAGE" ]; then
        summary="$MESSAGE"
    elif [ -f "$TRANSCRIPT_PATH" ]; then
        # 从 transcript 提取最近的 assistant 消息
        summary=$(tail -50 "$TRANSCRIPT_PATH" 2>/dev/null | \
            jq -r 'select(.type == "assistant") | .message.content[]? | select(.type == "text") | .text' 2>/dev/null | \
            tail -c 500 || echo "任务已完成")
    else
        summary="任务已完成，等待您的指示。"
    fi

    # 截断过长的摘要
    if [ ${#summary} -gt 500 ]; then
        summary="${summary:0:497}..."
    fi

    echo "$summary"
}

SUMMARY=$(generate_summary)

# 发送通知
send_notify() {
    local response
    response=$(curl -s -w "\n%{http_code}" -X POST \
        "${CLAUDE_NOTIFY_API_URL}/notify" \
        -H "Authorization: Bearer ${CLAUDE_NOTIFY_API_KEY}" \
        -H "Content-Type: application/json" \
        -d "{
            \"session_id\": \"${SESSION_ID}\",
            \"status\": \"${STATUS}\",
            \"summary\": $(echo "$SUMMARY" | jq -Rs .),
            \"cwd\": \"${CWD}\"
        }" 2>/dev/null)

    local http_code=$(echo "$response" | tail -1)
    local body=$(echo "$response" | sed '$d')

    if [ "$http_code" != "200" ]; then
        echo "Error: Failed to send notification (HTTP $http_code)" >&2
        return 1
    fi

    local ok=$(echo "$body" | jq -r '.ok')
    if [ "$ok" != "true" ]; then
        echo "Error: Notification failed: $(echo "$body" | jq -r '.error')" >&2
        return 1
    fi

    return 0
}

# 轮询等待回复
poll_reply() {
    local elapsed=0

    while [ $elapsed -lt $POLL_TIMEOUT ]; do
        local response
        response=$(curl -s -w "\n%{http_code}" -X GET \
            "${CLAUDE_NOTIFY_API_URL}/reply/${SESSION_ID}" \
            -H "Authorization: Bearer ${CLAUDE_NOTIFY_API_KEY}" 2>/dev/null)

        local http_code=$(echo "$response" | tail -1)
        local body=$(echo "$response" | sed '$d')

        if [ "$http_code" = "200" ]; then
            local has_reply=$(echo "$body" | jq -r '.has_reply')

            if [ "$has_reply" = "true" ]; then
                local reply=$(echo "$body" | jq -r '.reply')
                local action=$(echo "$body" | jq -r '.action')

                # 确认收到
                curl -s -X POST \
                    "${CLAUDE_NOTIFY_API_URL}/ack/${SESSION_ID}" \
                    -H "Authorization: Bearer ${CLAUDE_NOTIFY_API_KEY}" >/dev/null 2>&1

                # 根据 action 决定行为
                case "$action" in
                    done|cancel)
                        # 允许 Claude 停止
                        exit 0
                        ;;
                    continue|*)
                        # 阻止停止，注入用户回复作为新指令
                        echo "{\"decision\": \"block\", \"reason\": \"$reply\"}"
                        exit 0
                        ;;
                esac
            fi
        fi

        sleep $POLL_INTERVAL
        elapsed=$((elapsed + POLL_INTERVAL))
    done

    # 超时，允许停止
    echo "Timeout waiting for reply" >&2
    exit 0
}

# 主流程
main() {
    # 发送通知（重试 3 次）
    local retry=0
    while [ $retry -lt 3 ]; do
        if send_notify; then
            break
        fi
        retry=$((retry + 1))
        sleep 2
    done

    if [ $retry -eq 3 ]; then
        echo "Failed to send notification after 3 retries" >&2
        exit 0  # 不阻塞 Claude
    fi

    # 轮询等待回复
    poll_reply
}

main
