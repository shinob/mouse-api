# Mouse API Python クライアント活用ガイド

PC 上で動作する Mouse API を Python から安全・簡単に呼び出し、マウス/キーボード操作・画面キャプチャ・OCR・画像検索を実行するための実用ガイドです。

- 想定対象: Mouse API サーバーを起動できる端末を外部/同一端末から Python で操作したい方
- 対応範囲: 認証、基本操作、OCR/画像検索、エラーハンドリング、IPv6、実用サンプル

---

## 前提条件

- サーバー起動: `mouse_api.py` もしくは `./run.sh` でサーバーを起動
  - 例: `python mouse_api.py --host :: --port 5000`
- 認証: サーバー側で API キーが必須（`X-API-Key` ヘッダー）
  - `.env` の `API_KEY` または `config.json` の `security.api_keys` に設定
  - 未設定時は起動時に「デモ用APIキー」が標準出力に表示されます（その起動中のみ有効）
- 動作要件: GUI 操作・キャプチャが可能な環境（Linux は X11/Wayland、macOS はアクセシビリティ権限）
- 依存ライブラリ（クライアント側）
  ```bash
  pip install requests pillow
  ```

> 注意: サーバーのエンドポイント仕様は `mouse_api.py` に準拠しています。本ガイドの例は同ファイルの実装と一致するように記述しています。

---

## クイックスタート（最小クライアント）

```python
import base64
from typing import Any, Dict, List, Optional

import requests
from PIL import Image
from io import BytesIO


class MouseApiClient:
    def __init__(self, base_url: str = "http://localhost:5000", api_key: Optional[str] = None, timeout: float = 15.0):
        # IPv6 ループバックは "http://[::1]:5000" のようにブラケットで囲む
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"X-API-Key": api_key})

    # --- マウス ---
    def get_mouse_position(self) -> Dict[str, Any]:
        r = self.session.get(f"{self.base_url}/mouse/position", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def move(self, x: int, y: int, duration: float = 0.0) -> Dict[str, Any]:
        r = self.session.post(f"{self.base_url}/mouse/move", json={"x": x, "y": y, "duration": duration}, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def click(self, button: str = "left", x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        payload = {"button": button}
        if x is not None and y is not None:
            payload.update({"x": x, "y": y})
        r = self.session.post(f"{self.base_url}/mouse/click", json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # API 仕様: direction は vertical/horizontal、clicks の符号で方向を表現
    def scroll_vertical(self, clicks: int, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        payload = {"direction": "vertical", "clicks": int(clicks)}
        if x is not None and y is not None:
            payload.update({"x": int(x), "y": int(y)})
        r = self.session.post(f"{self.base_url}/mouse/scroll", json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def scroll_horizontal(self, clicks: int, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        payload = {"direction": "horizontal", "clicks": int(clicks)}
        if x is not None and y is not None:
            payload.update({"x": int(x), "y": int(y)})
        r = self.session.post(f"{self.base_url}/mouse/scroll", json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # ユーティリティ（直感的スクロール）
    def scroll_up(self, clicks: int = 3, **kw):
        return self.scroll_vertical(abs(clicks), **kw)

    def scroll_down(self, clicks: int = 3, **kw):
        return self.scroll_vertical(-abs(clicks), **kw)

    def scroll_right(self, clicks: int = 3, **kw):
        return self.scroll_horizontal(abs(clicks), **kw)

    def scroll_left(self, clicks: int = 3, **kw):
        return self.scroll_horizontal(-abs(clicks), **kw)

    def drag(self, to_x: int, to_y: int, *, from_x: Optional[int] = None, from_y: Optional[int] = None, duration: float = 1.0, button: str = "left") -> Dict[str, Any]:
        payload = {"to_x": int(to_x), "to_y": int(to_y), "duration": float(duration), "button": button}
        if from_x is not None and from_y is not None:
            payload.update({"from_x": int(from_x), "from_y": int(from_y)})
        r = self.session.post(f"{self.base_url}/mouse/drag", json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # --- 画面キャプチャ ---
    def capture(self) -> Image.Image:
        r = self.session.get(f"{self.base_url}/screen/capture", timeout=self.timeout)
        r.raise_for_status()
        b64 = r.json()["image"]
        return Image.open(BytesIO(base64.b64decode(b64)))

    def capture_at_cursor(self, width: int, height: int) -> Image.Image:
        r = self.session.get(f"{self.base_url}/screen/capture_at_cursor", params={"width": width, "height": height}, timeout=self.timeout)
        r.raise_for_status()
        b64 = r.json()["image"]
        return Image.open(BytesIO(base64.b64decode(b64)))

    # --- OCR/テキスト ---
    # min_confidence は 0-100 (%) を推奨
    def text_search(self, text: str, *, case_sensitive: bool = False, min_confidence: float = 50.0, region: Optional[str] = None) -> Dict[str, Any]:
        payload = {"text": text, "case_sensitive": case_sensitive, "min_confidence": float(min_confidence)}
        if region:
            payload["region"] = region
        r = self.session.post(f"{self.base_url}/text/search", json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def text_find_and_click(self, text: str, *, button: str = "left", case_sensitive: bool = False, min_confidence: float = 50.0, click_all: bool = False) -> Dict[str, Any]:
        r = self.session.post(f"{self.base_url}/text/find_and_click", json={
            "text": text, "button": button, "case_sensitive": case_sensitive, "min_confidence": float(min_confidence), "click_all": bool(click_all)
        }, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def text_type(self, text: str, *, x: Optional[int] = None, y: Optional[int] = None, interval: float = 0.1, mode: str = "type", paste_delay: float = 0.1, preserve_clipboard: bool = True, press_enter: bool = False, enter_count: int = 1, enter_interval: float = 0.05) -> Dict[str, Any]:
        payload = {
            "text": text,
            "interval": float(interval),
            "mode": mode,
            "paste_delay": float(paste_delay),
            "preserve_clipboard": bool(preserve_clipboard),
            "press_enter": bool(press_enter),
            "enter_count": int(enter_count),
            "enter_interval": float(enter_interval),
        }
        if x is not None and y is not None:
            payload.update({"x": int(x), "y": int(y)})
        r = self.session.post(f"{self.base_url}/text/type", json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # --- 画像検索 ---
    def image_search(self, image_path: str, *, threshold: float = 0.8, multi_scale: bool = False, scale_range_min: float = 0.5, scale_range_max: float = 2.0, scale_steps: int = 10) -> Dict[str, Any]:
        files = {"image": open(image_path, "rb")}
        data = {
            "threshold": str(threshold),
            "multi_scale": str(multi_scale).lower(),
            "scale_range_min": str(scale_range_min),
            "scale_range_max": str(scale_range_max),
            "scale_steps": str(scale_steps),
        }
        r = self.session.post(f"{self.base_url}/image/search", files=files, data=data, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def image_find_and_click(self, image_path: str, *, threshold: float = 0.8, multi_scale: bool = False, button: str = "left", click_all: bool = False, offset_x: int = 0, offset_y: int = 0) -> Dict[str, Any]:
        files = {"image": open(image_path, "rb")}
        data = {
            "threshold": str(threshold),
            "multi_scale": str(multi_scale).lower(),
            "button": button,
            "click_all": str(click_all).lower(),
            "offset_x": str(int(offset_x)),
            "offset_y": str(int(offset_y)),
        }
        r = self.session.post(f"{self.base_url}/image/find_and_click", files=files, data=data, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # --- キーボード ---
    def hotkey(self, keys: str | list[str]) -> Dict[str, Any]:
        # 例: "ctrl+a" あるいは ["ctrl", "a"]
        payload = {"keys": keys}
        r = self.session.post(f"{self.base_url}/keyboard/hotkey", json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def key_press(self, key: str, *, repeat: int = 1, interval: float = 0.1) -> Dict[str, Any]:
        payload = {"key": key, "repeat": int(repeat), "interval": float(interval)}
        r = self.session.post(f"{self.base_url}/keyboard/press", json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # --- システム ---
    def health(self) -> Dict[str, Any]:
        r = self.session.get(f"{self.base_url}/health", timeout=self.timeout)
        r.raise_for_status()
        return r.json()
```

---

## 使い方サンプル

```python
from pathlib import Path

client = MouseApiClient(base_url="http://localhost:5000", api_key="<YOUR_API_KEY>")

# 現在座標
print(client.get_mouse_position())

# マウス移動 → 左クリック
client.move(500, 300, duration=0.4)
client.click("left")

# スクロール（上へ3、下へ5、右へ2、左へ2）
client.scroll_up(3)
client.scroll_down(5)
client.scroll_right(2)
client.scroll_left(2)

# ドラッグ（現在位置から 800,600 へ）
client.drag(to_x=800, to_y=600, duration=0.8)

# 画面キャプチャを保存
img = client.capture()
Path("capture.png").write_bytes(img.tobytes())  # PILの保存推奨
img.save("capture.png")

# カーソル中心の部分キャプチャ
clip = client.capture_at_cursor(640, 480)
clip.save("clip.png")

# テキスト検索（50%以上の信頼度）
res = client.text_search("OK", min_confidence=50.0)
print(res)

# テキストを探してクリック（最初の一致のみ）
client.text_find_and_click("キャンセル", button="left", min_confidence=60.0)

# テキスト入力（座標クリック→貼り付け、Enterも押下）
client.text_type("こんにちは", x=400, y=500, mode="paste", press_enter=True)

# 画像検索
res = client.image_search("button.png", threshold=0.8)
print(res.get("total_found"))

# 画像検索＆クリック（全一致、中心から右に+10pxズラす）
client.image_find_and_click("button.png", click_all=True, offset_x=10)

# ホットキー・単一キー
client.hotkey("ctrl+a")
client.key_press("enter", repeat=2, interval=0.05)

# ヘルスチェック
print(client.health())
```

---

## パラメータと仕様の要点

- 認証: すべての保護エンドポイントは `X-API-Key` が必要
- スクロール: `direction` は `vertical`/`horizontal`、正の `clicks` が上/右、負が下/左
- ドラッグ: API は `to_x`/`to_y` 必須、`from_x`/`from_y` は省略可能（省略時は現在位置から）
- OCR 検索: `min_confidence` は 0-100 の百分率を推奨（実装上、内部変換が関数により異なるため 30〜70 付近を目安に調整してください）
- 画像検索: `multipart/form-data` で画像をアップロード。マルチスケールは見た目サイズが変わる UI に有効
- IPv6: `http://[::1]:5000` のように角かっこで囲む

---

## 例外・エラーハンドリング

- HTTP レベルエラー: `requests` は `raise_for_status()` で例外。`try/except requests.RequestException` で補足
- アプリケーションエラー: JSON に `{"status":"error", "error": ...}` が返ることがあるため `status` を確認
- タイムアウト: デフォルト `timeout=15.0`。環境に応じて増減
- リトライ: 必要に応じ `requests.adapters.HTTPAdapter` を使ってセッションにリトライ戦略を設定可能

```python
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

retry = Retry(total=3, backoff_factor=0.3, status_forcelist=(500, 502, 503, 504))
client.session.mount("http://", HTTPAdapter(max_retries=retry))
client.session.mount("https://", HTTPAdapter(max_retries=retry))
```

---

## セキュリティの基本

- API キーは長く推測困難な値を使用し、ネットワーク公開時は信頼できるセグメント/トンネル経由に限定
- ログ: `mouse_api.log` にアクセス情報が記録されます。不要な公開を避け、収集方針を組織ポリシーに合わせて調整
- 詳細は `API_SECURITY_GUIDE.md` を参照

---

## よくあるトラブル

- GUI が無効: サーバー起動時に GUI 利用不可の警告が出た場合、仮想環境/権限/ディスプレイ設定を確認（Linux は `DISPLAY=:0` 等）
- クリップボード不可: Linux は `xclip`/`xsel` が必要。`pip install pyperclip` も確認
- OCR 不可: EasyOCR API が落ちている場合は Tesseract を導入（`tesseract-ocr`/`tesseract-ocr-jpn`）
- OpenCV 不可: `pip install opencv-python` を導入

---

## 補足

- サンプルや curl の例は `README.md` も参照
- OCR API 連携の詳細は `OCR_API_USAGE_GUIDE.md` を参照

以上で、Python からの Mouse API 操作に必要な基本は網羅しています。用途に応じて上記クラスをプロジェクト内のユーティリティとして流用・拡張してください。
