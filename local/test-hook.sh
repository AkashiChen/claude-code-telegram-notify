#!/bin/bash
# local/test-hook.sh
# 本地测试 Hook 脚本（使用 Mock Server）

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🧪 Claude Code Telegram Notify - 本地测试"
echo ""

# 检查依赖
check_deps() {
    local missing=()
    command -v python3 &>/dev/null || missing+=("python3")
    command -v jq &>/dev/null || missing+=("jq")
    command -v curl &>/dev/null || missing+=("curl")

    if [ ${#missing[@]} -gt 0 ]; then
        echo "❌ 缺少依赖: ${missing[*]}"
        exit 1
    fi
    echo "✅ 依赖检查通过"
}

# 设置虚拟环境
setup_venv() {
    cd "$PROJECT_DIR/server"

    if [ ! -d ".venv" ]; then
        echo "   创建虚拟环境..."
        python3 -m venv .venv
    fi

    source .venv/bin/activate
    pip install -q -r requirements.txt 2>/dev/null || true
}

# 运行 Python 单元测试
test_python() {
    echo ""
    echo "🐍 运行 Python 单元测试..."

    cd "$PROJECT_DIR/server"
    setup_venv

    PYTHONPATH=src pytest tests/ -v --tb=short

    echo "✅ Python 测试全部通过"
}

# 启动 Mock Server (设置全局 MOCK_PID)
start_mock_server() {
    echo ""
    echo "🚀 启动 Mock Server..."

    cd "$PROJECT_DIR/server"

    # 使用绝对路径启动，避免子 shell 问题
    VENV_PYTHON="$PROJECT_DIR/server/.venv/bin/python3"

    if [ ! -f "$VENV_PYTHON" ]; then
        echo "❌ 虚拟环境未找到: $VENV_PYTHON"
        return 1
    fi

    # 启动服务（后台）
    PYTHONPATH=src "$VENV_PYTHON" -c "
import uvicorn
from claude_notify.api import create_app
from claude_notify.store import SessionStore

store = SessionStore()
app = create_app(store=store, bot=None, api_key='test_api_key')

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=18000, log_level='warning')
" &
    MOCK_PID=$!
    echo "   PID: $MOCK_PID"

    # 等待服务启动
    sleep 3

    # 检查服务是否启动
    if ! curl -s http://127.0.0.1:18000/health > /dev/null 2>&1; then
        echo "❌ Mock Server 启动失败"
        kill $MOCK_PID 2>/dev/null || true
        MOCK_PID=""
        return 1
    fi

    echo "✅ Mock Server 已启动"
}

# 测试 API
test_api() {
    echo ""
    echo "📡 测试 API..."

    # 测试 health
    echo -n "   GET /health: "
    response=$(curl -s http://127.0.0.1:18000/health)
    if [ "$response" = '{"status":"ok"}' ]; then
        echo "✅ PASS"
    else
        echo "❌ FAIL - $response"
        return 1
    fi

    # 测试 notify
    echo -n "   POST /notify: "
    response=$(curl -s -X POST http://127.0.0.1:18000/notify \
        -H "Authorization: Bearer test_api_key" \
        -H "Content-Type: application/json" \
        -d '{"session_id":"test123","status":"completed","summary":"Test","cwd":"/tmp"}')
    ok=$(echo "$response" | jq -r '.ok')
    if [ "$ok" = "true" ]; then
        echo "✅ PASS"
    else
        echo "❌ FAIL - $response"
        return 1
    fi

    # 测试 reply (无回复)
    echo -n "   GET /reply/test123 (no reply): "
    response=$(curl -s http://127.0.0.1:18000/reply/test123 \
        -H "Authorization: Bearer test_api_key")
    has_reply=$(echo "$response" | jq -r '.has_reply')
    if [ "$has_reply" = "false" ]; then
        echo "✅ PASS"
    else
        echo "❌ FAIL - $response"
        return 1
    fi

    # 测试未授权
    echo -n "   POST /notify (unauthorized): "
    http_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:18000/notify \
        -H "Authorization: Bearer wrong_key" \
        -H "Content-Type: application/json" \
        -d '{"session_id":"test","status":"completed","summary":"Test","cwd":"/tmp"}')
    if [ "$http_code" = "401" ]; then
        echo "✅ PASS"
    else
        echo "❌ FAIL - HTTP $http_code"
        return 1
    fi

    echo "✅ API 测试全部通过"
}

# 测试 Hook 脚本语法
test_hook_syntax() {
    echo ""
    echo "🪝 测试 Hook 脚本..."

    # 检查脚本语法
    echo -n "   语法检查: "
    if bash -n "$SCRIPT_DIR/telegram-notify.sh" 2>/dev/null; then
        echo "✅ PASS"
    else
        echo "❌ FAIL"
        return 1
    fi

    # 测试 stop_hook_active=true (应该直接退出)
    echo -n "   stop_hook_active=true: "
    result=$(echo '{"session_id":"test1","stop_hook_active":true,"cwd":"/tmp"}' | \
        bash "$SCRIPT_DIR/telegram-notify.sh" 2>&1) || true
    if [ -z "$result" ]; then
        echo "✅ PASS (exit 0, no output)"
    else
        echo "❌ FAIL - unexpected output: $result"
        return 1
    fi

    # 测试方案 A: 环境变量禁用
    echo -n "   TELEGRAM_NOTIFY_ENABLED=0: "
    result=$(echo '{"session_id":"test2","stop_hook_active":false,"cwd":"/tmp"}' | \
        TELEGRAM_NOTIFY_ENABLED=0 bash "$SCRIPT_DIR/telegram-notify.sh" 2>&1) || true
    if [ -z "$result" ]; then
        echo "✅ PASS (exit 0, no output)"
    else
        echo "❌ FAIL - unexpected output: $result"
        return 1
    fi

    # 测试方案 B: 文件锁禁用
    echo -n "   .no-notify 文件锁: "
    mkdir -p "$HOME/.claude/hooks"
    touch "$HOME/.claude/hooks/.no-notify"
    result=$(echo '{"session_id":"test3","stop_hook_active":false,"cwd":"/tmp"}' | \
        bash "$SCRIPT_DIR/telegram-notify.sh" 2>&1) || true
    rm -f "$HOME/.claude/hooks/.no-notify"
    if [ -z "$result" ]; then
        echo "✅ PASS (exit 0, no output)"
    else
        echo "❌ FAIL - unexpected output: $result"
        return 1
    fi

    echo "✅ Hook 脚本测试完成"
}

# 清理
cleanup() {
    echo ""
    echo "🧹 清理..."
    if [ -n "$MOCK_PID" ] && kill -0 $MOCK_PID 2>/dev/null; then
        kill $MOCK_PID 2>/dev/null || true
        echo "   已停止 Mock Server (PID: $MOCK_PID)"
    fi
}

# 主流程
main() {
    trap cleanup EXIT

    check_deps
    test_python

    # start_mock_server 会设置全局 MOCK_PID
    start_mock_server || exit 1
    test_api
    test_hook_syntax

    echo ""
    echo "🎉 所有本地测试通过!"
}

main "$@"
