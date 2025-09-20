#!/bin/bash

echo "Mouse API セットアップを開始します..."

# システム要件のチェック
echo "システム要件をチェックしています..."

# Tesseract OCRのチェック
if ! command -v tesseract &> /dev/null; then
    echo "警告: Tesseract OCRがインストールされていません"
    echo "OCR機能を使用するには以下のコマンドを実行してください:"
    echo "  Ubuntu/Debian: sudo apt-get install tesseract-ocr tesseract-ocr-jpn"
    echo "  Red Hat系: sudo yum install tesseract tesseract-langpack-jpn"
    echo "  macOS: brew install tesseract tesseract-lang"
    echo ""
else
    echo "✅ Tesseract OCRが利用可能です"
fi

# python3-tkのチェック (Linuxのみ)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if ! python3 -c "import tkinter" &> /dev/null; then
        echo "警告: python3-tkがインストールされていません"
        echo "GUI機能を使用するには以下のコマンドを実行してください:"
        echo "  Ubuntu/Debian: sudo apt-get install python3-tk python3-dev"
        echo "  Red Hat系: sudo yum install tkinter python3-devel"
        echo ""
    fi
fi

# 仮想環境の作成
echo "仮想環境を作成しています..."
python3 -m venv venv

# 仮想環境の有効化
echo "仮想環境を有効化しています..."
source venv/bin/activate

# pipのアップグレード
echo "pipをアップグレードしています..."
pip install --upgrade pip

# 依存関係のインストール
echo "依存関係をインストールしています..."
pip install -r requirements.txt

echo ""
echo "✅ セットアップ完了!"
echo ""
echo "📋 次のステップ:"
echo "  1. 仮想環境を有効化: source venv/bin/activate"
echo "  2. サーバー起動: ./run.sh"
echo "  3. または手動起動: python mouse_api.py"
echo ""
echo "🔧 利用可能な機能:"
echo "  - マウス操作 (位置取得、移動、クリック)"
echo "  - スクリーンキャプチャ"
echo "  - OCR文字検索 (Tesseract使用)"
echo "  - 文字入力"
echo "  - 文字検索＆自動クリック"
echo ""
echo "📖 詳細はREADME.mdを参照してください"