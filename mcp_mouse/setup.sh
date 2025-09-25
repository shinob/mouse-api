#!/bin/bash

# MCP Mouse Setup Script
set -e

echo "=== MCP Mouse セットアップスクリプト ==="
echo ""

# Current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Python version check
echo "1. Python環境の確認..."
if ! command -v python3 &> /dev/null; then
    echo "エラー: Python 3 が見つかりません"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "Python バージョン: $PYTHON_VERSION"

# Install dependencies
echo ""
echo "2. 依存関係のインストール..."
if command -v pip3 &> /dev/null; then
    pip3 install -r requirements.txt
elif command -v pip &> /dev/null; then
    pip install -r requirements.txt
else
    echo "エラー: pip が見つかりません"
    exit 1
fi

# Create config from example if not exists
echo ""
echo "3. 設定ファイルの確認..."
if [ ! -f "config.json" ]; then
    echo "config.json が存在しないため、config.example.json からコピーします..."
    cp config.example.json config.json
    echo "config.json を作成しました"
else
    echo "config.json は既に存在します"
fi

# Create output directory
echo ""
echo "4. 出力ディレクトリの作成..."
mkdir -p output
echo "output ディレクトリを作成しました"

# Create imgs directory if not exists
echo ""
echo "5. imgsディレクトリの確認..."
IMGS_DIR="../imgs"
if [ ! -d "$IMGS_DIR" ]; then
    mkdir -p "$IMGS_DIR"
    echo "imgs ディレクトリを作成しました: $IMGS_DIR"
else
    echo "imgs ディレクトリは既に存在します: $IMGS_DIR"
fi

# Configuration guidance
echo ""
echo "=== セットアップ完了 ==="
echo ""
echo "次のステップ:"
echo "1. config.json を編集してサーバー設定を調整してください"
echo "   - defaultServer: 使用するデフォルトサーバー名"
echo "   - servers: サーバー設定（URL、APIキー等）"
echo ""
echo "2. Claude Desktop の設定に以下のMCP設定を追加してください:"
echo ""
echo '  "mcpServers": {'
echo '    "mouse-mcp": {'
echo '      "command": "python3",'
echo "      \"args\": [\"$SCRIPT_DIR/server.py\"]"
echo '    }'
echo '  }'
echo ""
echo "3. パターンマッチング用の画像を imgs/ ディレクトリに配置してください"
echo "   現在の imgs ディレクトリ: $IMGS_DIR"
echo ""
echo "4. テスト実行:"
echo "   python3 server.py"
echo ""