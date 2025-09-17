# Mouse API

PCのマウス操作、デスクトップキャプチャ、OCR、画像マッチングを行う高機能REST APIサーバー

## 機能

### 🖱️ マウス操作
- マウス位置の取得
- マウスの移動
- マウスクリック（左クリック・右クリック・中クリック）
- マウスホイールスクロール（上下左右対応）
- マウスドラッグ操作

### 📸 画面キャプチャ
- デスクトップ画面のキャプチャ
- 複数形式での保存（PNG, JPEG, BMP）
- OCR結果の可視化画像生成

### 🔍 高度なOCR機能（Tesseract）
- 高精度な日本語・英語文字認識
- 画像前処理による精度向上
- テキストグルーピング（重なり・Y軸中心統合）
- 信頼度による重複除去
- 文字位置の自動クリック
- 複数マッチング戦略（直接・グループ・サブシーケンス）

### 🖼️ 画像マッチング
- テンプレート画像による画面内検索
- マルチスケール対応（サイズ変化に対応）
- 画像検索＆自動クリック
- 高精度OpenCVマッチング

### ⌨️ テキスト入力
- 指定座標への文字入力
- 文字間隔の調整

### 🔧 その他
- IPv4/IPv6対応
- ポート番号の設定可能
- リアルタイムヘルスチェック

## システム要件

### Linux
```bash
# Pythonライブラリの依存関係
sudo apt-get update
sudo apt-get install python3-tk python3-dev

# Tesseract OCRのインストール
sudo apt-get install tesseract-ocr tesseract-ocr-jpn

# または Red Hat系の場合
sudo yum install tkinter python3-devel
sudo yum install tesseract tesseract-langpack-jpn
```

### macOS
```bash
# Homebrewを使用している場合
brew install python-tk

# Tesseract OCRのインストール
brew install tesseract tesseract-lang
```

## インストール

### 仮想環境を使用（推奨）

```bash
# セットアップスクリプトを実行
chmod +x setup.sh
./setup.sh

# または手動でセットアップ
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### システム全体にインストール（非推奨）

```bash
pip install -r requirements.txt --break-system-packages
```

## 使用方法

### サーバー起動

#### 起動スクリプトを使用（推奨）

```bash
# 実行権限を付与
chmod +x run.sh

# デフォルトポート（5000）で起動（IPv4/IPv6両対応）
./run.sh

# ポート番号を指定して起動
./run.sh 8080

# IPv4のみで起動
./run.sh 8080 127.0.0.1

# IPv6のみで起動
./run.sh 8080 ::1

# IPv6の全インターフェースで起動
./run.sh 8080 "::"
```

#### 手動起動

```bash
# 仮想環境を有効化
source venv/bin/activate

# デフォルトポート（5000）で起動
python mouse_api.py

# ポート番号を指定して起動
python mouse_api.py --port 8080

# IPv4で起動
python mouse_api.py --host 127.0.0.1 --port 3000

# IPv6で起動
python mouse_api.py --host ::1 --port 3000

# IPv6の全インターフェースで起動
python mouse_api.py --host "::" --port 3000
```

### API エンドポイント

#### マウス位置取得

```bash
GET /mouse/position
```

**レスポンス例:**
```json
{
  "x": 100,
  "y": 200,
  "status": "success"
}
```

#### マウス移動

```bash
POST /mouse/move
Content-Type: application/json

{
  "x": 300,
  "y": 400,
  "duration": 1.0
}
```

**パラメータ:**
- `x` (必須): X座標
- `y` (必須): Y座標  
- `duration` (オプション): 移動にかける時間（秒）、デフォルト: 0

**レスポンス例:**
```json
{
  "status": "success",
  "x": 300,
  "y": 400
}
```

#### マウスクリック

```bash
POST /mouse/click
Content-Type: application/json

{
  "button": "left",
  "x": 100,
  "y": 200
}
```

**パラメータ:**
- `button` (オプション): クリックボタン（`left`, `right`, `middle`）、デフォルト: `left`
- `x` (オプション): X座標（指定しない場合は現在位置）
- `y` (オプション): Y座標（指定しない場合は現在位置）

**レスポンス例:**
```json
{
  "status": "success",
  "button": "left"
}
```

#### マウススクロール

```bash
POST /mouse/scroll
Content-Type: application/json

{
  "x": 500,
  "y": 300,
  "direction": "up",
  "clicks": 3
}
```

**パラメータ:**
- `direction` (必須): スクロール方向（`up`, `down`, `left`, `right`）
- `clicks` (オプション): スクロールクリック数、デフォルト: 3
- `x` (オプション): スクロール前に移動するX座標
- `y` (オプション): スクロール前に移動するY座標

**レスポンス例:**
```json
{
  "status": "success",
  "action": "スクロール (上方向) を3回実行",
  "direction": "up",
  "clicks": 3,
  "position": {
    "x": 500,
    "y": 300
  }
}
```

#### マウスドラッグ

```bash
POST /mouse/drag
Content-Type: application/json

{
  "start_x": 100,
  "start_y": 100,
  "end_x": 300,
  "end_y": 200,
  "duration": 1.0,
  "button": "left"
}
```

**パラメータ:**
- `start_x` (必須): ドラッグ開始X座標
- `start_y` (必須): ドラッグ開始Y座標
- `end_x` (必須): ドラッグ終了X座標
- `end_y` (必須): ドラッグ終了Y座標
- `duration` (オプション): ドラッグ時間（秒）、デフォルト: 1.0
- `button` (オプション): ドラッグボタン（`left`, `right`, `middle`）、デフォルト: `left`

**レスポンス例:**
```json
{
  "status": "success",
  "action": "ドラッグ操作を実行 (100, 100) → (300, 200)",
  "start_position": {
    "x": 100,
    "y": 100
  },
  "end_position": {
    "x": 300,
    "y": 200
  },
  "duration": 1.0,
  "button": "left"
}
```

#### デスクトップキャプチャ

```bash
GET /screen/capture
```

**レスポンス例:**
```json
{
  "status": "success",
  "image": "iVBORw0KGgoAAAANSUhEUgAA...",
  "format": "PNG",
  "size": {
    "width": 1920,
    "height": 1080
  }
}
```

- `image`: Base64エンコードされた画像データ

#### OCR結果付きキャプチャ

```bash
POST /screen/capture_with_ocr
Content-Type: application/json

{
  "text": "ハイライトするテキスト",
  "show_all": true,
  "min_confidence": 30.0
}
```

**パラメータ:**
- `text` (オプション): ハイライト表示するターゲットテキスト
- `show_all` (オプション): 全てのテキストを表示、デフォルト: `true`
- `min_confidence` (オプション): 最小信頼度（0-100）、デフォルト: 30.0

**レスポンス例:**
```json
{
  "status": "success",
  "image": "iVBORw0KGgoAAAANSUhEUgAA...",
  "format": "PNG",
  "size": {
    "width": 1920,
    "height": 1080
  },
  "ocr_results": [
    {
      "text": "検出されたテキスト",
      "x": 150,
      "y": 200,
      "bbox": {"x": 100, "y": 180, "width": 100, "height": 40},
      "confidence": 95.5,
      "grouped_count": 2
    }
  ],
  "total_detected": 15,
  "target_matches": [
    {
      "text": "ハイライトするテキスト",
      "x": 300,
      "y": 400,
      "confidence": 98.2,
      "match_type": "direct"
    }
  ],
  "total_target_matches": 1
}
```

#### 文字検索

```bash
POST /text/search
Content-Type: application/json

{
  "text": "検索したい文字列",
  "case_sensitive": false,
  "min_confidence": 50.0
}
```

**パラメータ:**
- `text` (必須): 検索する文字列
- `case_sensitive` (オプション): 大文字小文字を区別、デフォルト: `false`
- `min_confidence` (オプション): 最小信頼度（0-100）、デフォルト: 50.0

**レスポンス例:**
```json
{
  "status": "success",
  "matches": [
    {
      "text": "検索したい文字列",
      "x": 150,
      "y": 200,
      "bbox": {"x": 100, "y": 180, "width": 100, "height": 40},
      "confidence": 95.5,
      "grouped_count": 1,
      "match_type": "direct"
    }
  ],
  "total_found": 1
}
```

#### 文字入力

```bash
POST /text/type
Content-Type: application/json

{
  "text": "入力したい文字列",
  "x": 300,
  "y": 400,
  "interval": 0.1
}
```

**パラメータ:**
- `text` (必須): 入力する文字列
- `x` (オプション): クリック後に入力する場合のX座標
- `y` (オプション): クリック後に入力する場合のY座標
- `interval` (オプション): 文字間の入力間隔（秒）、デフォルト: 0.1

**レスポンス例:**
```json
{
  "status": "success",
  "text": "入力したい文字列"
}
```

#### 文字検索＆クリック

```bash
POST /text/find_and_click
Content-Type: application/json

{
  "text": "クリックしたい文字列",
  "case_sensitive": false,
  "min_confidence": 50.0,
  "button": "left",
  "click_all": false
}
```

**パラメータ:**
- `text` (必須): 検索してクリックする文字列
- `case_sensitive` (オプション): 大文字小文字を区別、デフォルト: `false`
- `min_confidence` (オプション): 最小信頼度（0-100）、デフォルト: 50.0
- `button` (オプション): クリックボタン（`left`, `right`, `middle`）、デフォルト: `left`
- `click_all` (オプション): すべての一致をクリック、デフォルト: `false`

**レスポンス例:**
```json
{
  "status": "success",
  "clicked": [
    {
      "text": "クリックしたい文字列",
      "x": 150,
      "y": 200,
      "bbox": {"x": 100, "y": 180, "width": 100, "height": 40},
      "confidence": 95.5,
      "grouped_count": 1,
      "match_type": "direct"
    }
  ],
  "total_clicked": 1
}
```

#### 画像検索

```bash
POST /image/search
Content-Type: multipart/form-data

Form Data:
- image: <画像ファイル>
- threshold: 0.8
- multi_scale: false
- scale_range_min: 0.5
- scale_range_max: 2.0
- scale_steps: 10
```

**パラメータ:**
- `image` (必須): 検索するテンプレート画像ファイル
- `threshold` (オプション): マッチング閾値（0.0-1.0）、デフォルト: 0.8
- `multi_scale` (オプション): マルチスケール検索、デフォルト: false
- `scale_range_min` (オプション): 最小スケール、デフォルト: 0.5
- `scale_range_max` (オプション): 最大スケール、デフォルト: 2.0
- `scale_steps` (オプション): スケールステップ数、デフォルト: 10

**レスポンス例:**
```json
{
  "status": "success",
  "matches": [
    {
      "center_x": 400,
      "center_y": 300,
      "top_left_x": 350,
      "top_left_y": 250,
      "width": 100,
      "height": 100,
      "confidence": 0.95,
      "scale": 1.0,
      "method": "template_matching"
    }
  ],
  "total_found": 1,
  "template_info": {
    "width": 100,
    "height": 100,
    "mode": "RGB"
  }
}
```

#### 画像検索＆クリック

```bash
POST /image/find_and_click
Content-Type: multipart/form-data

Form Data:
- image: <画像ファイル>
- threshold: 0.8
- multi_scale: false
- button: left
- click_all: false
```

**パラメータ:**
- `image` (必須): 検索するテンプレート画像ファイル
- `threshold` (オプション): マッチング閾値（0.0-1.0）、デフォルト: 0.8
- `multi_scale` (オプション): マルチスケール検索、デフォルト: false
- `button` (オプション): クリックボタン（`left`, `right`, `middle`）、デフォルト: `left`
- `click_all` (オプション): 全マッチ箇所をクリック、デフォルト: false

**レスポンス例:**
```json
{
  "status": "success",
  "clicked": [
    {
      "center_x": 400,
      "center_y": 300,
      "top_left_x": 350,
      "top_left_y": 250,
      "width": 100,
      "height": 100,
      "confidence": 0.95,
      "method": "template_matching"
    }
  ],
  "total_clicked": 1,
  "total_found": 1
}
```

#### ヘルスチェック

```bash
GET /health
```

**レスポンス例:**
```json
{
  "status": "healthy",
  "service": "mouse-api",
  "gui_available": true,
  "ocr_available": true
}
```

## 使用例

### curl を使用した例

```bash
# IPv4でのアクセス
curl http://localhost:5000/mouse/position

# IPv6でのアクセス
curl http://[::1]:5000/mouse/position

# マウス移動
curl -X POST http://localhost:5000/mouse/move \
  -H "Content-Type: application/json" \
  -d '{"x": 500, "y": 300, "duration": 0.5}'

# 左クリック
curl -X POST http://localhost:5000/mouse/click \
  -H "Content-Type: application/json" \
  -d '{"button": "left", "x": 100, "y": 100}'

# マウススクロール（上方向）
curl -X POST http://localhost:5000/mouse/scroll \
  -H "Content-Type: application/json" \
  -d '{"direction": "up", "clicks": 3, "x": 500, "y": 300}'

# マウスドラッグ
curl -X POST http://localhost:5000/mouse/drag \
  -H "Content-Type: application/json" \
  -d '{"start_x": 100, "start_y": 100, "end_x": 300, "end_y": 200, "duration": 1.0}'

# デスクトップキャプチャ
curl http://localhost:5000/screen/capture

# 文字検索
curl -X POST http://localhost:5000/text/search \
  -H "Content-Type: application/json" \
  -d '{"text": "OK", "min_confidence": 70.0}'

# 文字入力
curl -X POST http://localhost:5000/text/type \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello World", "x": 300, "y": 400}'

# 文字検索してクリック
curl -X POST http://localhost:5000/text/find_and_click \
  -H "Content-Type: application/json" \
  -d '{"text": "ボタン", "button": "left"}'

# OCR結果付きキャプチャ
curl -X POST http://localhost:5000/screen/capture_with_ocr \
  -H "Content-Type: application/json" \
  -d '{"text": "OK", "show_all": true, "min_confidence": 30.0}'

# 画像検索
curl -X POST http://localhost:5000/image/search \
  -F "image=@button.png" \
  -F "threshold=0.8"

# マルチスケール画像検索
curl -X POST http://localhost:5000/image/search \
  -F "image=@icon.png" \
  -F "threshold=0.7" \
  -F "multi_scale=true" \
  -F "scale_range_min=0.5" \
  -F "scale_range_max=2.0"

# 画像検索してクリック
curl -X POST http://localhost:5000/image/find_and_click \
  -F "image=@button.png" \
  -F "threshold=0.8" \
  -F "button=left"
```

### Python を使用した例

```python
import requests
import base64
from PIL import Image
import io

# APIサーバーのURL
API_URL = "http://localhost:5000"

# マウス位置取得
response = requests.get(f"{API_URL}/mouse/position")
position = response.json()
print(f"マウス位置: ({position['x']}, {position['y']})")

# マウス移動
requests.post(f"{API_URL}/mouse/move", json={
    "x": 400,
    "y": 300,
    "duration": 1.0
})

# 左クリック
requests.post(f"{API_URL}/mouse/click", json={
    "button": "left",
    "x": 400,
    "y": 300
})

# マウススクロール
requests.post(f"{API_URL}/mouse/scroll", json={
    "direction": "up",
    "clicks": 3,
    "x": 500,
    "y": 300
})

# マウスドラッグ
requests.post(f"{API_URL}/mouse/drag", json={
    "start_x": 100,
    "start_y": 100,
    "end_x": 300,
    "end_y": 200,
    "duration": 1.0
})

# デスクトップキャプチャ
response = requests.get(f"{API_URL}/screen/capture")
data = response.json()

# Base64画像をデコードして保存
image_data = base64.b64decode(data['image'])
image = Image.open(io.BytesIO(image_data))
image.save("screenshot.png")

# 文字検索
search_response = requests.post(f"{API_URL}/text/search", json={
    "text": "OK",
    "min_confidence": 70.0
})
search_data = search_response.json()
print(f"見つかった文字: {len(search_data['matches'])}個")

# 文字入力
requests.post(f"{API_URL}/text/type", json={
    "text": "Hello World",
    "x": 300,
    "y": 400
})

# 文字検索してクリック
click_response = requests.post(f"{API_URL}/text/find_and_click", json={
    "text": "ボタン",
    "button": "left"
})
click_data = click_response.json()
if click_data['status'] == 'success':
    print(f"クリックしました: {click_data['total_clicked']}個")

# OCR結果付きキャプチャ
ocr_response = requests.post(f"{API_URL}/screen/capture_with_ocr", json={
    "text": "OK",
    "show_all": True,
    "min_confidence": 30.0
})
ocr_data = ocr_response.json()
if ocr_data['status'] == 'success':
    print(f"検出されたテキスト: {ocr_data['total_detected']}個")
    print(f"ターゲットマッチ: {ocr_data['total_target_matches']}個")
    
    # OCR可視化画像を保存
    overlay_image_data = base64.b64decode(ocr_data['image'])
    overlay_image = Image.open(io.BytesIO(overlay_image_data))
    overlay_image.save("ocr_overlay.png")

# 画像検索
with open("button.png", "rb") as f:
    files = {"image": f}
    data = {"threshold": 0.8}
    image_search_response = requests.post(f"{API_URL}/image/search", 
                                        files=files, data=data)

image_search_data = image_search_response.json()
if image_search_data['status'] == 'success':
    print(f"画像マッチ: {image_search_data['total_found']}個")
    for match in image_search_data['matches']:
        print(f"  中心座標: ({match['center_x']}, {match['center_y']})")
        print(f"  信頼度: {match['confidence']:.3f}")

# 画像検索＆クリック
with open("button.png", "rb") as f:
    files = {"image": f}
    data = {"threshold": 0.8, "button": "left"}
    image_click_response = requests.post(f"{API_URL}/image/find_and_click", 
                                       files=files, data=data)

image_click_data = image_click_response.json()
if image_click_data['status'] == 'success':
    print(f"画像クリック: {image_click_data['total_clicked']}個")
```

## 依存関係

- **Flask**: REST APIサーバー
- **pyautogui**: マウス操作・画面キャプチャ
- **Pillow (PIL)**: 画像処理・変換
- **pytesseract**: Tesseract OCRのPythonバインディング
- **opencv-python (cv2)**: 画像処理・テンプレートマッチング
- **numpy**: 数値計算・画像配列操作
- **requests**: HTTP通信（サンプルスクリプト用）

### システム依存関係
- **Tesseract OCR**: 光学文字認識エンジン
- **日本語言語パック**: 日本語文字認識用

## サンプルスクリプト

### 📸 画面キャプチャ
```bash
# 基本キャプチャ
./sample_screen_capture.py

# JPEG形式で高品質保存
./sample_screen_capture.py --format JPEG --quality 95

# 連続キャプチャ（5回、2秒間隔）
./sample_screen_capture.py --count 5 --interval 2

# デモ実行
./sample_screen_capture.py --demo-formats
```

### 🔍 OCR・テキスト検索
```bash
# 基本のファイル検索
./sample_find_file.py

# OCR可視化テスト
./sample_find_file.py --test-ocr

# 全検索方法のデモ
./sample_find_file.py --demo
```

### 🎨 OCR結果可視化
```bash
# 基本の可視化
./sample_ocr_visualization.py

# 特定テキストをハイライト
./sample_ocr_visualization.py --target "ファイル"

# 高信頼度のみ表示
./sample_ocr_visualization.py --confidence 80 --hide-all
```

### 🖼️ 画像マッチング
```bash
# 基本の画像検索
./sample_image_search.py button.png

# マルチスケール検索
./sample_image_search.py icon.png --multi-scale --threshold 0.7

# 検索してクリック
./sample_image_search.py button.png --click --threshold 0.8

# 全マッチ箇所をクリック
./sample_image_search.py icon.png --click-all --multi-scale
```

### 🖱️ マウス操作
```bash
# 基本操作デモ
./sample_mouse_operations.py

# 現在位置表示
./sample_mouse_operations.py --position

# マウス移動
./sample_mouse_operations.py --move 500 300

# クリック（座標指定）
./sample_mouse_operations.py --click 100 100 left

# スクロール
./sample_mouse_operations.py --scroll up 5 400 300

# インタラクティブデモ
./sample_mouse_operations.py --demo

# スクロールパターンデモ
./sample_mouse_operations.py --demo-scroll

# ドラッグパターンデモ
./sample_mouse_operations.py --demo-drag
```

## 注意事項

- このAPIは操作対象のPC上で実行する必要があります
- セキュリティのため、信頼できるネットワーク環境でのみ使用してください
- Linuxの場合、X11またはWaylandが必要です
- macOSの場合、アクセシビリティ権限が必要な場合があります
- OCR機能を使用するにはTesseractのインストールが必要です
- 画像マッチング機能を使用するにはOpenCVが必要です（requirements.txtに含まれています）

## 機能一覧

| 機能カテゴリ | エンドポイント | 説明 |
|--------------|----------------|------|
| **マウス操作** | `/mouse/position` | マウス座標取得 |
| | `/mouse/move` | マウス移動 |
| | `/mouse/click` | マウスクリック |
| | `/mouse/scroll` | マウススクロール |
| | `/mouse/drag` | マウスドラッグ |
| **画面キャプチャ** | `/screen/capture` | 基本キャプチャ |
| | `/screen/capture_with_ocr` | OCR結果付きキャプチャ |
| **テキスト検索** | `/text/search` | OCRテキスト検索 |
| | `/text/find_and_click` | テキスト検索＆クリック |
| | `/text/type` | テキスト入力 |
| **画像マッチング** | `/image/search` | 画像検索 |
| | `/image/find_and_click` | 画像検索＆クリック |
| **システム** | `/health` | ヘルスチェック |

## 高度な機能

### 🔧 OCR前処理
- ノイズ除去（ガウシアンブラー）
- コントラスト強化（CLAHE）
- シャープニング
- 二値化（Otsuの手法）
- モルフォロジー演算

### 🧩 テキストグルーピング
- Y軸中心による自動統合
- 重なるバウンディングボックスの結合
- 信頼度による重複除去
- 3段階マッチング戦略

### 📐 画像マッチング
- OpenCVテンプレートマッチング
- マルチスケール対応
- 重複検出の自動除去
- 高精度信頼度計算