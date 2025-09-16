#!/bin/bash

# 仮想環境の作成
python3 -m venv venv

# 仮想環境の有効化
source venv/bin/activate

# 依存関係のインストール
pip install -r requirements.txt

echo "セットアップ完了!"
echo "仮想環境を有効化するには: source venv/bin/activate"
echo "サーバー起動するには: python mouse_api.py"