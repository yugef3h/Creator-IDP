#!/bin/bash
# ChatBI V0.1 一键启动脚本
# 用法：bash start.sh

set -e

echo "📊 ChatBI - B站创作者视频数据中心"
echo "=================================="
echo ""

# 0. 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3.9+"
    exit 1
fi
echo "✅ Python $(python3 --version)"

# 1. 检查 .env
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "⚠️  已创建 .env 文件，请编辑填入 DEEPSEEK_API_KEY"
        echo "   vim .env"
        exit 1
    else
        echo "❌ 未找到 .env.example"
        exit 1
    fi
fi

# 检查 API Key 是否已配置
if grep -q "sk-your-key" .env 2>/dev/null; then
    echo "⚠️  请先编辑 .env 文件，填入你的 DEEPSEEK_API_KEY"
    echo "   vim .env"
    exit 1
fi
echo "✅ .env 已配置"

# 2. 安装依赖
echo ""
echo "📦 安装依赖..."
pip3 install -q --break-system-packages streamlit jieba sqlglot openai python-dotenv pyyaml pandas faker 2>&1 | tail -1
echo "✅ 依赖就绪"

# 3. 生成数据（如果不存在）
if [ ! -f bilibili_demo.db ]; then
    echo ""
    echo "🔨 生成演示数据..."
    python3 generate_data.py
else
    echo "✅ 数据已存在，跳过生成"
fi

# 4. 启动
VERSION=${1:-v0}
if [ "$VERSION" = "v1" ]; then
    echo ""
    echo "🚀 启动 V1.0 (FastAPI + React)..."
    echo "   后端: http://localhost:8000"
    echo "   前端: http://localhost:5173"
    echo ""
    echo "启动后端..."
    python3 -m uvicorn backend.main:app --reload --port 8000 &
    BACKEND_PID=$!
    echo "启动前端..."
    cd frontend && npm install -s && npm run dev &
    FRONTEND_PID=$!
    echo ""
    echo "按 Ctrl+C 停止所有服务"
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
    wait
else
    echo ""
    echo "🚀 启动 V0.1 (Streamlit)..."
    echo "   打开 http://localhost:8501"
    echo ""
    python3 -m streamlit run app.py --server.headless true 2>&1
fi
