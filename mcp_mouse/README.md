# mouse-mcp (MCP server for mouse-api)

他サーバー上で稼働する `mouse-api` を HTTP 経由で呼び出し、LLM クライアントから操作できる MCP サーバーです。複数のリモートを切り替えて利用できます。

## セットアップ

### 依存関係

Python 3.9+ を想定。以下をインストールしてください。

```
pip install mcp>=1.0.0 httpx pydantic Pillow
```

（ネットワーク制限環境では、ホスト側で上記をインストールしてください）

## 起動

1) 設定ファイルを作成

`mcp_mouse/config.example.json` をコピーして `config.json` を作成し、`mouse-api` のベース URL を記入します。

```
cp mcp_mouse/config.example.json mcp_mouse/config.json
```

例:

```json
{
  "defaultServer": "local",
  "servers": {
    "local": { 
      "baseUrl": "http://localhost:5000",
      "headers": {
        "X-API-Key": "your-api-key-here"
      }
    },
    "desk01": { 
      "baseUrl": "http://desk01.local:5000",
      "headers": {
        "X-API-Key": "your-api-key-here"
      }
    }
  }
}
```

**重要**: Mouse APIサーバーでAPIキー認証が有効な場合は、`headers`に`X-API-Key`を設定してください。

環境変数 `MOUSE_MCP_CONFIG` で設定ファイルパスを上書きできます。

2) MCP サーバーを stdio で起動

```
python -m mcp_mouse.server
```

### Claude Desktop での設定（Windows）

Claude Desktop でMCPサーバーとして登録するには、設定ファイルを編集します。

1. Claude Desktop の設定ファイルを開きます：
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

2. 設定ファイルに以下を追加します：

```json
{
  "mcpServers": {
    "mouse-mcp": {
      "command": "python",
      "args": ["-m", "mcp_mouse.server"],
      "env": {}
    }
  }
}
```

3. `mcp_mouse/config.json` を作成して、mouse-apiサーバーのURLを設定します：

```json
{
  "defaultServer": "local",
  "servers": {
    "local": {
      "baseUrl": "http://localhost:5000",
      "headers": {}
    }
  }
}
```

4. Claude Desktop を再起動します。

### 設定確認

Claude Desktop で「MCP」や「ツール」メニューが表示され、mouse-mcpのツールが利用可能になることを確認してください。

### トラブルシューティング

**設定ファイルが見つからない場合：**
- Windows: エクスプローラーのアドレスバーに `%APPDATA%\Claude` と入力
- ファイルが存在しない場合は新規作成してください

**Pythonパスの問題：**
- `python` コマンドが見つからない場合は、フルパスを指定：
```json
{
  "mcpServers": {
    "mouse-mcp": {
      "command": "C:\\Python39\\python.exe",
      "args": ["-m", "mcp_mouse.server"],
      "env": {}
    }
  }
}
```

**作業ディレクトリの設定：**
- `mcp_mouse` ディレクトリの親ディレクトリを作業ディレクトリとして指定：
```json
{
  "mcpServers": {
    "mouse-mcp": {
      "command": "python",
      "args": ["-m", "mcp_mouse.server"],
      "cwd": "C:\\path\\to\\mouse-api",
      "env": {}
    }
  }
}
```

**依存関係のインストール確認：**
```bash
pip install mcp>=1.0.0 httpx pydantic Pillow
```

## 提供ツール

### システム
- `list_servers(server?)`: 設定済みサーバー一覧/疎通確認
- `health(server?)`: サーバーの健康状態を確認

### マウス操作
- `mouse_position(server?)`: 現在のマウス位置を取得
- `mouse_move(server?, x, y, duration?)`: マウスを指定座標に移動
- `mouse_click(server?, button?, x?, y?)`: マウスクリックを実行
- `mouse_scroll(server?, direction, clicks?, x?, y?)`: マウススクロールを実行
- `mouse_drag(server?, from_x, from_y, to_x, to_y, duration?, button?)`: マウスドラッグ操作を実行

### 画面キャプチャ
- `screen_capture(server?)`: スクリーンショットを撮影
- `screen_capture_at_cursor(server?, width, height)`: カーソル位置を中心にスクリーンショットを撮影
- `screen_capture_with_ocr(server?, text?, show_all?, min_confidence?)`: スクリーンショットを撮影してOCR結果を重ね合わせ

### テキスト操作
- `text_type(server?, text, x?, y?, interval?, mode?, press_enter?)`: 指定された文字列をタイプ入力
- `text_search(server?, text, case_sensitive?, min_confidence?)`: 画面内の指定されたテキストを検索
- `text_find_and_click(server?, text, case_sensitive?, min_confidence?, button?, click_all?)`: 指定されたテキストを検索してクリック
- `text_ocr(server?, min_confidence?, debug?)`: スクリーンショットなしでOCRテキストのみを取得

### 画像操作
- `image_search(server?, image_path, threshold?, multi_scale?, scale_range_min?, scale_range_max?, scale_steps?)`: 画面内の指定された画像を検索
- `image_find_and_click(server?, image_path, threshold?, multi_scale?, button?, click_all?, offset_x?, offset_y?)`: 指定された画像を検索してクリック

`image_*` はローカルファイルパスを受け取り、MCP サーバー側でアップロードして `mouse-api` に転送します。

## 画像の扱い（base64→PNG 変換）

- `screen_*` 系のレスポンスに含まれる `image`（base64）は、MCP 側で自動的に PNG ファイルへ変換し、`mcp_mouse/output/` 配下に保存します。
- ツールの返り値では、`image` フィールドを削除し、代わりに `image_file`（保存先パス）と `image_format: "PNG"` を返します。
- 元画像が JPEG 等でも PNG に変換して保存します。
- 保存先ディレクトリ: `mcp_mouse/output`（存在しない場合は自動作成）。

## 注意

- 返却される画像は Base64 文字列です。クライアントによっては出力が大きくなるため注意してください。
- 認証が必要な構成の場合は、`config.json` の `headers` にトークン等を設定してください。
