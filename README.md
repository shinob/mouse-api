# Mouse API

PCのマウス操作とデスクトップキャプチャを行うREST APIサーバー

## 機能

- マウス位置の取得
- マウスの移動
- マウスクリック（左クリック・右クリック・中クリック）
- デスクトップ画面のキャプチャ
- EasyOCRによる画面上の文字検索
- 文字位置の自動クリック
- 指定座標への文字入力
- ポート番号の設定可能

## システム要件

### Linux
```bash
# Pythonライブラリの依存関係
sudo apt-get update
sudo apt-get install python3-tk python3-dev

# または Red Hat系の場合
sudo yum install tkinter python3-devel
```

### macOS
```bash
# Homebrewを使用している場合
brew install python-tk
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
      "confidence": 95.5
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
      "confidence": 95.5
    }
  ],
  "total_clicked": 1
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
```

## 依存関係

- Flask: REST APIサーバー
- pyautogui: マウス操作
- Pillow: 画像処理
- easyocr: OCR（光学文字認識）
- numpy: 数値計算
- requests: HTTP通信

## 注意事項

- このAPIは操作対象のPC上で実行する必要があります
- セキュリティのため、信頼できるネットワーク環境でのみ使用してください
- Linuxの場合、X11またはWaylandが必要です
- macOSの場合、アクセシビリティ権限が必要な場合があります