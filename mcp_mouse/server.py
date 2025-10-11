from __future__ import annotations

import asyncio
import base64
import io
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import Tool
from PIL import Image


@dataclass
class ServerConfig:
    name: str
    base_url: str
    headers: Dict[str, str]


class Config:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or self._default_path()
        self.default_server: Optional[str] = None
        self.servers: Dict[str, ServerConfig] = {}
        self._load()

    def _default_path(self) -> Path:
        env = os.getenv("MOUSE_MCP_CONFIG")
        if env:
            return Path(env)
        return Path(__file__).with_name("config.json")

    def _load(self) -> None:
        if not self.path.exists():
            # fallback to example if real config missing
            example = Path(__file__).with_name("config.example.json")
            if example.exists():
                with example.open("r", encoding="utf-8") as f:
                    raw = json.load(f)
            else:
                raw = {"servers": {}}
        else:
            with self.path.open("r", encoding="utf-8") as f:
                raw = json.load(f)

        self.default_server = raw.get("defaultServer")
        servers = raw.get("servers", {})
        for name, sc in servers.items():
            self.servers[name] = ServerConfig(
                name=name,
                base_url=sc["baseUrl"].rstrip("/"),
                headers=sc.get("headers", {}),
            )

    def get(self, name: Optional[str]) -> ServerConfig:
        if not name:
            name = self.default_server
        if not name or name not in self.servers:
            raise ValueError(
                f"Unknown server '{name}'. Configure servers in config.json (defaultServer/servers)."
            )
        return self.servers[name]


class MouseApiClient:
    def __init__(self, cfg: ServerConfig):
        self.base_url = cfg.base_url
        self.headers = cfg.headers
        self.client = httpx.AsyncClient(timeout=30)
        self.ocr_client = httpx.AsyncClient(timeout=120)

    async def _get(self, path: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        r = await self.client.get(url, headers=self.headers, params=params)
        r.raise_for_status()
        return r.json()

    async def _post_json(self, path: str, data: Dict[str, Any], use_ocr_timeout: bool = False) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        client = self.ocr_client if use_ocr_timeout else self.client
        r = await client.post(url, headers={"Content-Type": "application/json", **self.headers}, json=data)
        r.raise_for_status()
        return r.json()

    async def _post_file(self, path: str, files: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        r = await self.client.post(url, headers=self.headers, files=files, data=data)
        r.raise_for_status()
        return r.json()

    # --- mouse ---
    async def mouse_position(self) -> Dict[str, Any]:
        return await self._get("/mouse/position")

    async def mouse_move(self, x: int, y: int, duration: Optional[float]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"x": x, "y": y}
        if duration is not None:
            payload["duration"] = duration
        return await self._post_json("/mouse/move", payload)

    async def mouse_click(self, button: Optional[str], x: Optional[int], y: Optional[int]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if button:
            payload["button"] = button
        if x is not None:
            payload["x"] = x
        if y is not None:
            payload["y"] = y
        return await self._post_json("/mouse/click", payload)

    async def mouse_scroll(
        self,
        direction: str,
        clicks: Optional[int],
        x: Optional[int],
        y: Optional[int],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"direction": direction}
        if clicks is not None:
            payload["clicks"] = clicks
        if x is not None:
            payload["x"] = x
        if y is not None:
            payload["y"] = y
        return await self._post_json("/mouse/scroll", payload)

    async def mouse_drag(
        self,
        from_x: int,
        from_y: int,
        to_x: int,
        to_y: int,
        duration: Optional[float],
        button: Optional[str],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "from_x": from_x,
            "from_y": from_y,
            "to_x": to_x,
            "to_y": to_y,
        }
        if duration is not None:
            payload["duration"] = duration
        if button:
            payload["button"] = button
        return await self._post_json("/mouse/drag", payload)

    # --- screen ---
    async def screen_capture(self) -> Dict[str, Any]:
        return await self._get("/screen/capture")

    async def screen_capture_at_cursor(self, width: int, height: int) -> Dict[str, Any]:
        return await self._get("/screen/capture_at_cursor", params={"width": width, "height": height})

    async def screen_capture_with_ocr(self, text: Optional[str] = None, show_all: Optional[bool] = None, min_confidence: Optional[float] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if text is not None:
            payload["text"] = text
        if show_all is not None:
            payload["show_all"] = show_all
        if min_confidence is not None:
            payload["min_confidence"] = min_confidence
        return await self._post_json("/screen/capture_with_ocr", payload, use_ocr_timeout=True)

    # --- text ---
    async def text_type(self, text: str, x: Optional[int] = None, y: Optional[int] = None, interval: Optional[float] = None, mode: Optional[str] = None, press_enter: Optional[bool] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"text": text}
        if x is not None:
            payload["x"] = x
        if y is not None:
            payload["y"] = y
        if interval is not None:
            payload["interval"] = interval
        if mode is not None:
            payload["mode"] = mode
        if press_enter is not None:
            payload["press_enter"] = press_enter
        return await self._post_json("/text/type", payload)

    async def text_search(self, text: str, case_sensitive: Optional[bool], min_confidence: Optional[float], region: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"text": text}
        if case_sensitive is not None:
            payload["case_sensitive"] = case_sensitive
        if min_confidence is not None:
            payload["min_confidence"] = min_confidence
        if region is not None:
            payload["region"] = region
        return await self._post_json("/text/search", payload, use_ocr_timeout=True)

    async def text_find_and_click(
        self,
        text: str,
        case_sensitive: Optional[bool],
        min_confidence: Optional[float],
        button: Optional[str],
        click_all: Optional[bool],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"text": text}
        if case_sensitive is not None:
            payload["case_sensitive"] = case_sensitive
        if min_confidence is not None:
            payload["min_confidence"] = min_confidence
        if button:
            payload["button"] = button
        if click_all is not None:
            payload["click_all"] = click_all
        return await self._post_json("/text/find_and_click", payload, use_ocr_timeout=True)

    async def text_ocr(self, min_confidence: Optional[float] = None, debug: Optional[bool] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if min_confidence is not None:
            payload["min_confidence"] = min_confidence
        if debug is not None:
            payload["debug"] = debug
        return await self._post_json("/text/ocr", payload, use_ocr_timeout=True)

    # --- image ---
    async def image_search(
        self,
        image_path: Path,
        threshold: Optional[float],
        multi_scale: Optional[bool],
        scale_range_min: Optional[float],
        scale_range_max: Optional[float],
        scale_steps: Optional[int],
    ) -> Dict[str, Any]:
        if not image_path.exists():
            raise FileNotFoundError(str(image_path))
        files = {"image": (image_path.name, image_path.open("rb"), "application/octet-stream")}
        data: Dict[str, Any] = {}
        if threshold is not None:
            data["threshold"] = str(threshold)
        if multi_scale is not None:
            data["multi_scale"] = "true" if multi_scale else "false"
        if scale_range_min is not None:
            data["scale_range_min"] = str(scale_range_min)
        if scale_range_max is not None:
            data["scale_range_max"] = str(scale_range_max)
        if scale_steps is not None:
            data["scale_steps"] = str(scale_steps)
        return await self._post_file("/image/search", files=files, data=data)

    async def image_find_in_region(
        self,
        image_path: Path,
        top: int,
        left: int,
        width: int,
        height: int,
        threshold: Optional[float],
        multi_scale: Optional[bool],
        scale_range_min: Optional[float],
        scale_range_max: Optional[float],
        scale_steps: Optional[int],
    ) -> Dict[str, Any]:
        """Search for an image within a specific region on screen."""
        if not image_path.exists():
            raise FileNotFoundError(str(image_path))
        files = {"image": (image_path.name, image_path.open("rb"), "application/octet-stream")}
        data: Dict[str, Any] = {
            "top": str(top),
            "left": str(left),
            "width": str(width),
            "height": str(height),
        }
        if threshold is not None:
            data["threshold"] = str(threshold)
        if multi_scale is not None:
            data["multi_scale"] = "true" if multi_scale else "false"
        if scale_range_min is not None:
            data["scale_range_min"] = str(scale_range_min)
        if scale_range_max is not None:
            data["scale_range_max"] = str(scale_range_max)
        if scale_steps is not None:
            data["scale_steps"] = str(scale_steps)
        return await self._post_file("/image/find_in_region", files=files, data=data)

    async def image_find_and_click(
        self,
        image_path: Path,
        threshold: Optional[float],
        multi_scale: Optional[bool],
        button: Optional[str],
        click_all: Optional[bool],
        offset_x: Optional[int] = None,
        offset_y: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not image_path.exists():
            raise FileNotFoundError(str(image_path))
        files = {"image": (image_path.name, image_path.open("rb"), "application/octet-stream")}
        data: Dict[str, Any] = {}
        if threshold is not None:
            data["threshold"] = str(threshold)
        if multi_scale is not None:
            data["multi_scale"] = "true" if multi_scale else "false"
        if button:
            data["button"] = button
        if click_all is not None:
            data["click_all"] = "true" if click_all else "false"
        if offset_x is not None:
            data["offset_x"] = str(offset_x)
        if offset_y is not None:
            data["offset_y"] = str(offset_y)
        return await self._post_file("/image/find_and_click", files=files, data=data)

    async def image_nested_search(
        self,
        parent_image_path: Path,
        child_image_path: Path,
        parent_threshold: Optional[float],
        child_threshold: Optional[float],
        parent_multi_scale: Optional[bool],
        child_multi_scale: Optional[bool],
        margin_x: Optional[int] = None,
        margin_y: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Nested image search: search for parent image, then search for child image within parent regions."""
        if not parent_image_path.exists():
            raise FileNotFoundError(str(parent_image_path))
        if not child_image_path.exists():
            raise FileNotFoundError(str(child_image_path))
        
        files = {
            "parent_image": (parent_image_path.name, parent_image_path.open("rb"), "application/octet-stream"),
            "child_image": (child_image_path.name, child_image_path.open("rb"), "application/octet-stream")
        }
        data: Dict[str, Any] = {}
        if parent_threshold is not None:
            data["parent_threshold"] = str(parent_threshold)
        if child_threshold is not None:
            data["child_threshold"] = str(child_threshold)
        if parent_multi_scale is not None:
            data["parent_multi_scale"] = "true" if parent_multi_scale else "false"
        if child_multi_scale is not None:
            data["child_multi_scale"] = "true" if child_multi_scale else "false"
        if margin_x is not None:
            data["margin_x"] = str(margin_x)
        if margin_y is not None:
            data["margin_y"] = str(margin_y)
        return await self._post_file("/image/nested_search", files=files, data=data)

    async def image_nested_find_and_click(
        self,
        parent_image_path: Path,
        child_image_path: Path,
        parent_threshold: Optional[float],
        child_threshold: Optional[float],
        parent_multi_scale: Optional[bool],
        child_multi_scale: Optional[bool],
        button: Optional[str],
        click_all: Optional[bool],
        offset_x: Optional[int] = None,
        offset_y: Optional[int] = None,
        margin_x: Optional[int] = None,
        margin_y: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Nested image search and click: search for parent image, then search and click child image within parent regions."""
        if not parent_image_path.exists():
            raise FileNotFoundError(str(parent_image_path))
        if not child_image_path.exists():
            raise FileNotFoundError(str(child_image_path))
        
        files = {
            "parent_image": (parent_image_path.name, parent_image_path.open("rb"), "application/octet-stream"),
            "child_image": (child_image_path.name, child_image_path.open("rb"), "application/octet-stream")
        }
        data: Dict[str, Any] = {}
        if parent_threshold is not None:
            data["parent_threshold"] = str(parent_threshold)
        if child_threshold is not None:
            data["child_threshold"] = str(child_threshold)
        if parent_multi_scale is not None:
            data["parent_multi_scale"] = "true" if parent_multi_scale else "false"
        if child_multi_scale is not None:
            data["child_multi_scale"] = "true" if child_multi_scale else "false"
        if button:
            data["button"] = button
        if click_all is not None:
            data["click_all"] = "true" if click_all else "false"
        if offset_x is not None:
            data["offset_x"] = str(offset_x)
        if offset_y is not None:
            data["offset_y"] = str(offset_y)
        if margin_x is not None:
            data["margin_x"] = str(margin_x)
        if margin_y is not None:
            data["margin_y"] = str(margin_y)
        return await self._post_file("/image/nested_find_and_click", files=files, data=data)

    # --- keyboard ---
    async def keyboard_hotkey(self, keys: str | list[str]) -> Dict[str, Any]:
        """キーバインド（ホットキー）を実行"""
        payload: Dict[str, Any] = {"keys": keys}
        return await self._post_json("/keyboard/hotkey", payload)

    async def keyboard_press(
        self,
        key: str,
        repeat: Optional[int] = None,
        interval: Optional[float] = None,
    ) -> Dict[str, Any]:
        """単一キーを押下"""
        payload: Dict[str, Any] = {"key": key}
        if repeat is not None:
            payload["repeat"] = repeat
        if interval is not None:
            payload["interval"] = interval
        return await self._post_json("/keyboard/press", payload)

    # --- system ---
    async def health(self) -> Dict[str, Any]:
        return await self._get("/health")

    async def aclose(self):
        await self.client.aclose()
        await self.ocr_client.aclose()


mcp = FastMCP("mouse-mcp")
config = Config()

# Directory to save decoded PNG images
OUTPUT_DIR = (Path(__file__).parent / "output").resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Directory containing reference images for pattern matching
IMAGES_DIR = (Path(__file__).parent / "imgs").resolve()


def _save_base64_image_to_png(b64: str, filename_prefix: str) -> str:
    """Decode base64 image bytes (any format) and save as PNG.

    Returns absolute file path to saved PNG.
    """
    # decode
    raw = base64.b64decode(b64)
    # convert to PNG via Pillow
    with io.BytesIO(raw) as bio:
        with Image.open(bio) as im:
            # always save as PNG
            out_path = OUTPUT_DIR / f"{filename_prefix}.png"
            # ensure unique if exists
            i = 1
            final_path = out_path
            while final_path.exists():
                final_path = OUTPUT_DIR / f"{filename_prefix}_{i}.png"
                i += 1
            im.save(final_path, format="PNG")
            return str(final_path)


def _with_saved_image(resp: Dict[str, Any], filename_prefix: str) -> Dict[str, Any]:
    """If response contains 'image' base64, persist to PNG and replace with 'image_file'."""
    if isinstance(resp, dict) and "image" in resp and isinstance(resp["image"], str):
        try:
            path = _save_base64_image_to_png(resp["image"], filename_prefix)
            # replace image b64 with file path
            resp = dict(resp)
            resp.pop("image", None)
            resp["image_file"] = path
            resp["image_format"] = "PNG"
        except Exception as e:  # noqa: BLE001
            # include error but keep original response
            resp = dict(resp)
            resp["image_decode_error"] = str(e)
    return resp


def _resolve_image_path(image_path: str) -> Path:
    """画像パスを解決します。相対パスの場合はimgsディレクトリを基準に解決します。"""
    path = Path(image_path)
    if path.is_absolute():
        return path
    
    # 相対パスの場合、まずimgsディレクトリから探す
    imgs_path = IMAGES_DIR / image_path
    if imgs_path.exists():
        return imgs_path
    
    # imgsディレクトリに見つからない場合は通常の相対パス解決
    return path


def _client_for(server_name: Optional[str]) -> MouseApiClient:
    cfg = config.get(server_name)
    return MouseApiClient(cfg)


@mcp.tool()
async def list_servers(server: Optional[str] = None) -> Dict[str, Any]:
    """設定済みサーバー一覧と疎通結果を返します。server を指定するとその疎通のみを確認。"""
    result: Dict[str, Any] = {
        "default": config.default_server,
        "servers": [],
    }
    names = [server] if server else list(config.servers.keys())
    for name in names:
        try:
            cli = _client_for(name)
            health = await cli.health()
            await cli.aclose()
            result["servers"].append({"name": name, "baseUrl": config.servers[name].base_url, "ok": True, "health": health})
        except Exception as e:  # noqa: BLE001
            result["servers"].append({"name": name, "baseUrl": config.servers.get(name).base_url if name in config.servers else None, "ok": False, "error": str(e)})
    return result


@mcp.tool()
async def mouse_position(server: Optional[str] = None) -> Dict[str, Any]:
    """現在のマウス位置を取得します"""
    cli = _client_for(server)
    try:
        return await cli.mouse_position()
    finally:
        await cli.aclose()


@mcp.tool()
async def mouse_move(server: Optional[str], x: int, y: int, duration: Optional[float] = None) -> Dict[str, Any]:
    """マウスを指定座標に移動します"""
    cli = _client_for(server)
    try:
        return await cli.mouse_move(x, y, duration)
    finally:
        await cli.aclose()


@mcp.tool()
async def mouse_click(
    server: Optional[str],
    button: Optional[str] = None,
    x: Optional[int] = None,
    y: Optional[int] = None,
) -> Dict[str, Any]:
    """マウスクリックを実行します。buttonは'left'、'right'、'middle'"""
    cli = _client_for(server)
    try:
        return await cli.mouse_click(button, x, y)
    finally:
        await cli.aclose()


@mcp.tool()
async def mouse_scroll(
    server: Optional[str],
    direction: str,
    clicks: Optional[int] = None,
    x: Optional[int] = None,
    y: Optional[int] = None,
) -> Dict[str, Any]:
    """マウススクロールを実行します。directionは'vertical'または'horizontal'"""
    cli = _client_for(server)
    try:
        return await cli.mouse_scroll(direction, clicks, x, y)
    finally:
        await cli.aclose()


@mcp.tool()
async def mouse_drag(
    server: Optional[str],
    from_x: int,
    from_y: int,
    to_x: int,
    to_y: int,
    duration: Optional[float] = None,
    button: Optional[str] = None,
) -> Dict[str, Any]:
    """マウスドラッグ操作を実行します"""
    cli = _client_for(server)
    try:
        return await cli.mouse_drag(from_x, from_y, to_x, to_y, duration, button)
    finally:
        await cli.aclose()


@mcp.tool()
async def screen_capture(server: Optional[str] = None) -> Dict[str, Any]:
    """スクリーンショットを撮影します"""
    cli = _client_for(server)
    try:
        resp = await cli.screen_capture()
        return _with_saved_image(resp, "screen_capture")
    finally:
        await cli.aclose()


@mcp.tool()
async def screen_capture_at_cursor(server: Optional[str], width: int, height: int) -> Dict[str, Any]:
    """カーソル位置を中心にスクリーンショットを撮影します"""
    cli = _client_for(server)
    try:
        resp = await cli.screen_capture_at_cursor(width, height)
        return _with_saved_image(resp, f"screen_capture_at_cursor_{width}x{height}")
    finally:
        await cli.aclose()


@mcp.tool()
async def screen_capture_with_ocr(
    server: Optional[str] = None, 
    text: Optional[str] = None, 
    show_all: Optional[bool] = None, 
    min_confidence: Optional[float] = None
) -> Dict[str, Any]:
    """スクリーンショットを撮影してOCR結果を重ね合わせます"""
    cli = _client_for(server)
    try:
        resp = await cli.screen_capture_with_ocr(text, show_all, min_confidence)
        return _with_saved_image(resp, "screen_capture_with_ocr")
    finally:
        await cli.aclose()


@mcp.tool()
async def text_type(
    server: Optional[str],
    text: str,
    x: Optional[int] = None,
    y: Optional[int] = None,
    interval: Optional[float] = None,
    mode: Optional[str] = None,
    press_enter: Optional[bool] = None,
) -> Dict[str, Any]:
    """指定された文字列をタイプ入力します。modeは'type'または'paste'"""
    cli = _client_for(server)
    try:
        return await cli.text_type(text, x, y, interval, mode, press_enter)
    finally:
        await cli.aclose()


@mcp.tool()
async def text_search(
    server: Optional[str],
    text: str,
    case_sensitive: Optional[bool] = None,
    min_confidence: Optional[float] = None,
    region: Optional[str] = None,
) -> Dict[str, Any]:
    """画面内の指定されたテキストを検索します。regionは'top_half', 'bottom_half', 'left', 'right', 'top_left', 'top_right', 'bottom_left', 'bottom_right'のいずれか"""
    cli = _client_for(server)
    try:
        return await cli.text_search(text, case_sensitive, min_confidence, region)
    finally:
        await cli.aclose()


@mcp.tool()
async def text_find_and_click(
    server: Optional[str],
    text: str,
    case_sensitive: Optional[bool] = None,
    min_confidence: Optional[float] = None,
    button: Optional[str] = None,
    click_all: Optional[bool] = None,
) -> Dict[str, Any]:
    """指定されたテキストを検索してクリックします"""
    cli = _client_for(server)
    try:
        return await cli.text_find_and_click(text, case_sensitive, min_confidence, button, click_all)
    finally:
        await cli.aclose()


@mcp.tool()
async def text_ocr(
    server: Optional[str],
    min_confidence: Optional[float] = None,
    debug: Optional[bool] = None,
) -> Dict[str, Any]:
    """スクリーンショットなしでOCRテキストのみを取得します"""
    cli = _client_for(server)
    try:
        return await cli.text_ocr(min_confidence, debug)
    finally:
        await cli.aclose()


@mcp.tool()
async def image_search(
    server: Optional[str],
    image_path: str,
    threshold: Optional[float] = None,
    multi_scale: Optional[bool] = None,
    scale_range_min: Optional[float] = None,
    scale_range_max: Optional[float] = None,
    scale_steps: Optional[int] = None,
) -> Dict[str, Any]:
    """画面内の指定された画像を検索します。相対パスを指定するとimgsディレクトリから自動的に検索します。"""
    cli = _client_for(server)
    try:
        resolved_path = _resolve_image_path(image_path)
        return await cli.image_search(
            resolved_path, threshold, multi_scale, scale_range_min, scale_range_max, scale_steps
        )
    finally:
        await cli.aclose()


@mcp.tool()
async def image_find_and_click(
    server: Optional[str],
    image_path: str,
    threshold: Optional[float] = None,
    multi_scale: Optional[bool] = None,
    button: Optional[str] = None,
    click_all: Optional[bool] = None,
    offset_x: Optional[int] = None,
    offset_y: Optional[int] = None,
) -> Dict[str, Any]:
    """指定された画像を検索してクリックします。相対パスを指定するとimgsディレクトリから自動的に検索します。"""
    cli = _client_for(server)
    try:
        resolved_path = _resolve_image_path(image_path)
        return await cli.image_find_and_click(resolved_path, threshold, multi_scale, button, click_all, offset_x, offset_y)
    finally:
        await cli.aclose()


@mcp.tool()
async def list_images() -> Dict[str, Any]:
    """利用可能なパターンマッチング用画像を一覧表示します"""
    result: Dict[str, Any] = {
        "images_directory": str(IMAGES_DIR),
        "available_images": []
    }
    
    if IMAGES_DIR.exists():
        for img_file in IMAGES_DIR.glob("*"):
            if img_file.is_file() and img_file.suffix.lower() in {'.png', '.jpg', '.jpeg', '.bmp', '.gif'}:
                result["available_images"].append({
                    "filename": img_file.name,
                    "relative_path": img_file.name,
                    "full_path": str(img_file)
                })
    
    return result


@mcp.tool()
async def image_nested_search(
    server: Optional[str],
    parent_image_path: str,
    child_image_path: str,
    parent_threshold: Optional[float] = None,
    child_threshold: Optional[float] = None,
    parent_multi_scale: Optional[bool] = None,
    child_multi_scale: Optional[bool] = None,
    margin_x: Optional[int] = None,
    margin_y: Optional[int] = None,
) -> Dict[str, Any]:
    """ネスト画像検索: 親画像を検索し、その範囲内で子画像を検索します。相対パスを指定するとimgsディレクトリから自動的に検索します。"""
    cli = _client_for(server)
    try:
        resolved_parent_path = _resolve_image_path(parent_image_path)
        resolved_child_path = _resolve_image_path(child_image_path)
        return await cli.image_nested_search(
            resolved_parent_path, resolved_child_path, parent_threshold, child_threshold,
            parent_multi_scale, child_multi_scale, margin_x, margin_y
        )
    finally:
        await cli.aclose()


@mcp.tool()
async def image_nested_find_and_click(
    server: Optional[str],
    parent_image_path: str,
    child_image_path: str,
    parent_threshold: Optional[float] = None,
    child_threshold: Optional[float] = None,
    parent_multi_scale: Optional[bool] = None,
    child_multi_scale: Optional[bool] = None,
    button: Optional[str] = None,
    click_all: Optional[bool] = None,
    offset_x: Optional[int] = None,
    offset_y: Optional[int] = None,
    margin_x: Optional[int] = None,
    margin_y: Optional[int] = None,
) -> Dict[str, Any]:
    """ネスト画像検索してクリック: 親画像を検索し、その範囲内で子画像を検索してクリックします。相対パスを指定するとimgsディレクトリから自動的に検索します。"""
    cli = _client_for(server)
    try:
        resolved_parent_path = _resolve_image_path(parent_image_path)
        resolved_child_path = _resolve_image_path(child_image_path)
        return await cli.image_nested_find_and_click(
            resolved_parent_path, resolved_child_path, parent_threshold, child_threshold,
            parent_multi_scale, child_multi_scale, button, click_all, offset_x, offset_y, margin_x, margin_y
        )
    finally:
        await cli.aclose()


@mcp.tool()
async def keyboard_hotkey(
    server: Optional[str],
    keys: str,
) -> Dict[str, Any]:
    """キーバインド（ホットキー）を実行します。例: "ctrl+a", "ctrl+c", "alt+tab"など"""
    cli = _client_for(server)
    try:
        return await cli.keyboard_hotkey(keys)
    finally:
        await cli.aclose()


@mcp.tool()
async def keyboard_press(
    server: Optional[str],
    key: str,
    repeat: Optional[int] = None,
    interval: Optional[float] = None,
) -> Dict[str, Any]:
    """単一キーを押下します。repeatで繰り返し回数、intervalで間隔（秒）を指定可能"""
    cli = _client_for(server)
    try:
        return await cli.keyboard_press(key, repeat, interval)
    finally:
        await cli.aclose()


@mcp.tool()
async def health(server: Optional[str] = None) -> Dict[str, Any]:
    """サーバーの健康状態を確認します"""
    cli = _client_for(server)
    try:
        return await cli.health()
    finally:
        await cli.aclose()


if __name__ == "__main__":
    # Stdio MCP server
    mcp.run()
