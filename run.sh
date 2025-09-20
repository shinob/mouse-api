#!/bin/bash

# デフォルト値
DEFAULT_PORT=5000
DEFAULT_HOST="::"  # IPv4とIPv6の両方をバインド

# 引数の解析
PORT=${1:-$DEFAULT_PORT}
HOST=${2:-$DEFAULT_HOST}

echo "Mouse API サーバーを起動します..."
echo "ホスト: $HOST"
echo "ポート: $PORT"
echo ""

# 仮想環境が存在するかチェック
if [ ! -d "venv" ]; then
    echo "仮想環境が見つかりません。先にsetup.shを実行してください。"
    echo "実行方法: ./setup.sh"
    exit 1
fi

# 仮想環境の有効化
source venv/bin/activate

# 依存関係がインストールされているかチェック
if ! python3 -c "import flask" 2>/dev/null; then
    echo "依存関係が不足しています。requirements.txtからインストールします..."
    pip install -r requirements.txt
fi

# DISPLAY環境変数の設定（Linux GUI環境用）
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
    echo "DISPLAY環境変数を :0 に設定しました"
fi

# サーバー起動
echo "サーバーを起動中..."
echo "停止するには Ctrl+C を押してください"
echo ""

python3 mouse_api.py --host "$HOST" --port "$PORT"