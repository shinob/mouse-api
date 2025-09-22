# Ollama MCP Client with Mouse Control Integration

OllamaをベースとしたMCP（Model Context Protocol）クライアントに、mcp_mouseとの統合によるマウス制御機能を追加した実装です。

## 機能

### 基本機能
- **OllamaMCPClient**: Ollamaとの非同期通信を行うメインクライアント
- **MCPServer**: HTTP/WebSocketベースのMCPサーバー
- **ストリーミング対応**: リアルタイムレスポンス
- **チャット機能**: 会話履歴を含むチャット
- **モデル管理**: モデル一覧取得・ダウンロード

### 拡張機能（マウス統合）
- **MouseCapableOllamaClient**: マウス制御機能統合Ollamaクライアント
- **自動マウス操作**: LLMの応答から自動的にマウス操作を検出・実行
- **画面キャプチャ**: スクリーンショット撮影機能
- **テキスト検索**: OCRによる画面内テキスト検索・クリック
- **直接制御**: プログラム的なマウス・画面制御API

## セットアップ

### 1. Ollamaのインストール

```bash
curl https://ollama.ai/install.sh | sh
ollama serve
ollama pull llama2
```

### 2. 依存関係のインストール

```bash
pip install -r requirements.txt
```

## 使用方法

### 基本的な使用例

```python
import asyncio
from client import OllamaMCPClient

async def example():
    async with OllamaMCPClient(model="llama2") as client:
        await client.initialize()
        response = await client.send_prompt("Hello, world!")
        print(response['response'])

asyncio.run(example())
```

### サーバーの起動

```python
from server import MCPServer
import asyncio

async def main():
    server = MCPServer(host="localhost", port=8080)
    runner = await server.start_server()
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await runner.cleanup()

asyncio.run(main())
```

### WebSocket接続

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onopen = function() {
    ws.send(JSON.stringify({
        method: 'completion',
        params: { prompt: 'Hello from WebSocket!' },
        id: '1'
    }));
};

ws.onmessage = function(event) {
    const response = JSON.parse(event.data);
    console.log(response);
};
```

## API エンドポイント

### HTTP エンドポイント

- `GET /health` - ヘルスチェック
- `POST /mcp` - MCP メッセージの送信
- `GET /models` - 利用可能なモデル一覧
- `POST /pull` - モデルのダウンロード
- `GET /ws` - WebSocket接続

### MCP メソッド

- `initialize` - クライアント初期化
- `completion` - テキスト生成
- `chat` - チャット会話

## 設定

```python
client = OllamaMCPClient(
    ollama_host="http://localhost:11434",  # Ollamaサーバーのホスト
    model="llama2"                        # 使用するモデル
)
```

## 例

詳細な使用例は `examples.py` を参照してください。

```bash
python examples.py
```

## マウス統合機能の使用方法

### 基本的な使用例（マウス統合）

```python
import asyncio
from mouse_integration import MouseCapableOllamaClient

async def example():
    async with MouseCapableOllamaClient(
        ollama_host="http://localhost:11434",
        model="llama2", 
        mouse_api_host="http://localhost:5000"
    ) as client:
        await client.initialize()
        
        # LLMにマウス操作を含むタスクを依頼
        response = await client.send_enhanced_prompt(
            "スクリーンショットを撮って、'Submit'ボタンをクリックしてください"
        )
        print(response['response'])
        
        # 実行されたマウス操作の結果を確認
        if 'mouse_actions_executed' in response:
            for action in response['mouse_actions_executed']:
                print(f"実行: {action['action']} - 成功: {action['success']}")

asyncio.run(example())
```

### 拡張HTTPエンドポイントの使用

```bash
# 拡張プロンプト（マウス操作付き）
curl -X POST http://localhost:8080/enhanced \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "画面をキャプチャして、OKボタンを探してクリックしてください",
    "enable_mouse_actions": true
  }'

# 直接マウス制御
curl -X POST http://localhost:8080/mouse/move \
  -H "Content-Type: application/json" \
  -d '{"x": 100, "y": 200}'

curl -X POST http://localhost:8080/mouse/click \
  -H "Content-Type: application/json" \
  -d '{"button": "left"}'

curl -X GET http://localhost:8080/screen/capture
```

### マウス操作指示の記法

LLMの応答中で以下の記法を使用してマウス操作を指示できます：

```
[MOUSE_ACTION: action_name(parameters)]
```

利用可能なアクション：

**マウス制御:**
- `mouse_position()` - 現在のマウス位置を取得
- `mouse_move(x=100, y=200, duration=1.0)` - マウスを座標へ移動
- `mouse_click(button="left", x=100, y=200)` - マウスクリック
- `mouse_scroll(direction="vertical", clicks=3)` - スクロール
- `mouse_drag(from_x=100, from_y=100, to_x=200, to_y=200)` - ドラッグ操作

**画面キャプチャ:**
- `screen_capture()` - スクリーンショット撮影
- `screen_capture_at_cursor(width=400, height=300)` - カーソル周辺キャプチャ
- `screen_capture_with_ocr(show_all=true)` - OCR付きキャプチャ

**テキスト操作:**
- `text_search(text="検索文字")` - 画面内テキスト検索
- `text_find_and_click(text="クリック対象")` - テキストを検索してクリック
- `text_type(text="入力文字", press_enter=true)` - テキスト入力
- `text_ocr(min_confidence=0.8)` - 画面全体のOCRテキスト抽出

**画像操作:**
- `image_search(image_path="/path/to/image.png")` - 画像検索
- `image_find_and_click(image_path="/path/to/image.png")` - 画像検索してクリック

**システム:**
- `health()` - マウスAPIヘルスチェック

例：
```
ユーザーのリクエストを処理します。まず現在のマウス位置を確認します。

[MOUSE_ACTION: mouse_position()]

次に画面の状況を確認しましょう。

[MOUSE_ACTION: screen_capture()]

画面のテキストをすべて抽出してみます。

[MOUSE_ACTION: text_ocr()]

画面でSubmitボタンを探してクリックします。

[MOUSE_ACTION: text_find_and_click(text="Submit")]

最後に「Thank you」とタイピングします。

[MOUSE_ACTION: text_type(text="Thank you", press_enter=true)]
```

### 詳細な使用例

詳細な使用例は `examples_enhanced.py` を参照してください：

```bash
python examples_enhanced.py
```

### 全機能テスト

新規追加された全機能のテストは `test_full_features.py` を実行してください：

```bash
python test_full_features.py
```