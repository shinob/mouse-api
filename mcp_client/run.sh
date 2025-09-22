#!/bin/bash

# Navigate to the script directory
cd "$(dirname "$0")"

echo "MCP Server を起動します..."
echo "ポート: 8080"
echo "停止するには Ctrl+C を押してください"
echo ""

# PYTHONPATH設定
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# サーバー起動
../venv/bin/python3 server.py