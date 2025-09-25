import json
import asyncio
import logging
from typing import Dict, Any, Optional, List
import re
from pathlib import Path
from client import OllamaMCPClient, MCPMessage
import httpx

class MouseCapableOllamaClient(OllamaMCPClient):
    """
    Ollama MCP Client with integrated mouse control capabilities
    マウス制御機能を統合したOllama MCPクライアント
    """
    
    def __init__(self, ollama_host: str = "http://localhost:11434", model: str = "gpt-oss:20b", 
                 mouse_api_host: str = "http://localhost:8000", mouse_api_key: str = None):
        super().__init__(ollama_host, model)
        self.mouse_api_host = mouse_api_host
        self.mouse_api_key = mouse_api_key
        self.mouse_tools_enabled = True
        self.mouse_headers = {"X-API-Key": mouse_api_key} if mouse_api_key else {}
        
    async def initialize(self) -> Dict[str, Any]:
        """Initialize both Ollama and mouse API connections"""
        # Initialize Ollama
        result = await super().initialize()
        
        # Check mouse API availability
        try:
            url = f"{self.mouse_api_host}/health"
            async with self.session.get(url, headers=self.mouse_headers) as response:
                if response.status == 200:
                    result["mouse_api_available"] = True
                    self.logger.info("Mouse API connection established")
                else:
                    result["mouse_api_available"] = False
                    self.mouse_tools_enabled = False
                    self.logger.warning(f"Mouse API not available: {response.status}")
        except Exception as e:
            result["mouse_api_available"] = False
            self.mouse_tools_enabled = False
            self.logger.warning(f"Failed to connect to mouse API: {e}")
            
        return result
    
    async def send_enhanced_prompt(self, prompt: str, enable_mouse_actions: bool = True) -> Dict[str, Any]:
        """
        Send prompt to Ollama with mouse action detection and execution
        マウスアクション検出・実行機能付きプロンプト送信
        """
        # Add mouse capability context to prompt if enabled
        if enable_mouse_actions and self.mouse_tools_enabled:
            enhanced_prompt = self._add_mouse_context(prompt)
        else:
            enhanced_prompt = prompt
            
        # Get response from Ollama
        response = await self.send_prompt(enhanced_prompt)
        
        # Parse and execute mouse actions if any
        if enable_mouse_actions and self.mouse_tools_enabled:
            actions = self._parse_mouse_actions(response.get('response', ''))
            if actions:
                action_results = await self._execute_mouse_actions(actions)
                response['mouse_actions_executed'] = action_results
                
        return response
    
    def _add_mouse_context(self, prompt: str) -> str:
        """Add mouse control context to the prompt"""
        context = """
あなたはマウスと画面制御機能を利用できます。回答する際は、以下の形式でマウス操作を含めることができます：

[MOUSE_ACTION: action_name(parameters)]

利用可能なアクション：

マウス制御:
- mouse_position() - 現在のマウス位置を取得
- mouse_move(x, y, duration=optional) - マウスを指定座標に移動
- mouse_click(button="left"|"right"|"middle", x=optional, y=optional) - マウスクリック
- mouse_scroll(direction="vertical"|"horizontal", clicks=3, x=optional, y=optional) - スクロール
- mouse_drag(from_x, from_y, to_x, to_y, duration=optional, button="left") - ドラッグ操作

画面キャプチャ:
- screen_capture() - 全画面スクリーンショット
- screen_capture_at_cursor(width, height) - カーソル周辺のスクリーンショット
- screen_capture_with_ocr(text=optional, show_all=true, min_confidence=0.8) - OCR付きスクリーンショット

テキスト操作:
- text_search(text="検索文字", case_sensitive=false, min_confidence=0.8, region="top_half") - 画面内テキスト検索
- text_find_and_click(text="クリック対象", case_sensitive=false, button="left") - テキストを検索してクリック
- text_type(text="入力文字", x=optional, y=optional, mode="type", press_enter=false, paste_delay=0.1) - テキスト入力
- text_ocr(min_confidence=0.8, debug=false) - 画面全体のテキスト抽出

画像操作:
- image_search(image_path="/path/to/image.png", threshold=0.8, multi_scale=true) - 画像検索
- image_find_and_click(image_path="/path/to/image.png", threshold=0.8, button="left", offset_x=0, offset_y=0) - 画像検索してクリック

システム:
- health() - マウスAPIヘルスチェック

回答例：
ユーザーのリクエストを処理します。まず現在のマウス位置を確認します。

[MOUSE_ACTION: mouse_position()]

現在のマウス位置が確認できました。次に画面の状況を確認しましょう。

[MOUSE_ACTION: screen_capture()]

画面のテキストをすべて抽出してみます。

[MOUSE_ACTION: text_ocr()]

IMPORTANT: 日本語で自然な会話形式で回答してください。マウス操作の実行結果は別途提供されるので、操作の説明と合わせて親しみやすく応答してください。

ユーザーの質問: """ + prompt
        
        return context
    
    def _parse_mouse_actions(self, response: str) -> List[Dict[str, Any]]:
        """Parse mouse actions from Ollama response"""
        actions = []
        pattern = r'\[MOUSE_ACTION:\s*([^]]+)\]'
        matches = re.findall(pattern, response)
        
        for match in matches:
            try:
                # Simple parsing for action(params) format
                if '(' in match and match.endswith(')'):
                    action_name = match.split('(')[0].strip()
                    params_str = match[match.index('(')+1:-1]
                    
                    # Parse parameters
                    params = {}
                    if params_str.strip():
                        # Handle both positional and named parameters
                        param_parts = []
                        current_part = ""
                        paren_count = 0
                        
                        for char in params_str:
                            if char == ',' and paren_count == 0:
                                param_parts.append(current_part.strip())
                                current_part = ""
                            else:
                                if char == '(':
                                    paren_count += 1
                                elif char == ')':
                                    paren_count -= 1
                                current_part += char
                        
                        if current_part.strip():
                            param_parts.append(current_part.strip())
                        
                        # Parse each parameter
                        for i, param in enumerate(param_parts):
                            if '=' in param:
                                # Named parameter
                                key, value = param.split('=', 1)
                                key = key.strip()
                                value = value.strip().strip('"\'')
                            else:
                                # Positional parameter - map to common parameter names
                                value = param.strip().strip('"\'')
                                if action_name == 'mouse_move':
                                    if i == 0:
                                        key = 'x'
                                    elif i == 1:
                                        key = 'y'
                                    elif i == 2:
                                        key = 'duration'
                                    else:
                                        continue
                                elif action_name == 'mouse_click':
                                    if i == 0:
                                        key = 'button'
                                    elif i == 1:
                                        key = 'x'
                                    elif i == 2:
                                        key = 'y'
                                    else:
                                        continue
                                else:
                                    key = f'param_{i}'
                            
                            # Convert to appropriate type
                            if value.isdigit():
                                params[key] = int(value)
                            elif value.replace('.', '').isdigit():
                                params[key] = float(value)
                            elif value.lower() in ['true', 'false']:
                                params[key] = value.lower() == 'true'
                            else:
                                params[key] = value
                    
                    actions.append({
                        'action': action_name,
                        'params': params
                    })
            except Exception as e:
                self.logger.error(f"Failed to parse mouse action '{match}': {e}")
                
        return actions
    
    async def _execute_mouse_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute parsed mouse actions"""
        results = []
        
        for action in actions:
            try:
                result = await self._execute_single_action(action['action'], action['params'])
                results.append({
                    'action': action['action'],
                    'params': action['params'],
                    'result': result,
                    'success': True
                })
            except Exception as e:
                results.append({
                    'action': action['action'],
                    'params': action['params'],
                    'error': str(e),
                    'success': False
                })
                self.logger.error(f"Failed to execute action {action['action']}: {e}")
        
        return results
    
    async def _execute_single_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single mouse action via HTTP API"""
        url_map = {
            'mouse_move': '/mouse/move',
            'mouse_click': '/mouse/click',
            'mouse_scroll': '/mouse/scroll',
            'mouse_drag': '/mouse/drag',
            'screen_capture': '/screen/capture',
            'screen_capture_at_cursor': '/screen/capture_at_cursor',
            'screen_capture_with_ocr': '/screen/capture_with_ocr',
            'text_search': '/text/search',
            'text_type': '/text/type',
            'text_find_and_click': '/text/find_and_click',
            'text_ocr': '/text/ocr',
            'image_search': '/image/search',
            'image_find_and_click': '/image/find_and_click',
            'mouse_position': '/mouse/position',
            'health': '/health'
        }
        
        if action not in url_map:
            raise ValueError(f"Unknown action: {action}")
        
        url = f"{self.mouse_api_host}{url_map[action]}"
        
        # GET requests for certain actions
        if action in ['screen_capture', 'mouse_position', 'health']:
            async with self.session.get(url, params=params, headers=self.mouse_headers) as response:
                response.raise_for_status()
                return await response.json()
        elif action == 'screen_capture_at_cursor':
            # Special handling for cursor capture with query params
            async with self.session.get(url, params=params, headers=self.mouse_headers) as response:
                response.raise_for_status()
                return await response.json()
        elif action in ['image_search', 'image_find_and_click']:
            # Special handling for file uploads
            return await self._handle_image_upload_action(action, params)
        else:
            # POST requests for actions with parameters
            async with self.session.post(url, json=params, headers={**self.mouse_headers, "Content-Type": "application/json"}) as response:
                response.raise_for_status()
                return await response.json()
    
    async def handle_enhanced_mcp_message(self, message: MCPMessage) -> Dict[str, Any]:
        """Handle MCP messages with mouse enhancement"""
        if message.method == "enhanced_completion":
            prompt = message.params.get("prompt", "") if message.params else ""
            enable_mouse = message.params.get("enable_mouse_actions", True) if message.params else True
            return await self.send_enhanced_prompt(prompt, enable_mouse)
        else:
            # Fall back to standard MCP handling
            return await self.handle_mcp_message(message)
    
    # Direct mouse control methods for programmatic use
    async def mouse_move(self, x: int, y: int, duration: Optional[float] = None) -> Dict[str, Any]:
        """Move mouse to specified coordinates"""
        params = {"x": x, "y": y}
        if duration is not None:
            params["duration"] = duration
        return await self._execute_single_action("mouse_move", params)
    
    async def mouse_click(self, button: Optional[str] = None, x: Optional[int] = None, 
                          y: Optional[int] = None) -> Dict[str, Any]:
        """Click mouse at current or specified position"""
        params = {}
        if button:
            params["button"] = button
        if x is not None:
            params["x"] = x
        if y is not None:
            params["y"] = y
        return await self._execute_single_action("mouse_click", params)
    
    async def screen_capture(self) -> Dict[str, Any]:
        """Capture screenshot"""
        return await self._execute_single_action("screen_capture", {})
    
    async def text_search(self, text: str, case_sensitive: bool = False, 
                          min_confidence: float = 0.8, region: Optional[str] = None) -> Dict[str, Any]:
        """Search for text on screen with optional region specification"""
        params = {
            "text": text,
            "case_sensitive": case_sensitive,
            "min_confidence": min_confidence
        }
        if region is not None:
            params["region"] = region
        return await self._execute_single_action("text_search", params)
    
    async def text_find_and_click(self, text: str, button: str = "left", 
                                  case_sensitive: bool = False) -> Dict[str, Any]:
        """Find text on screen and click it"""
        params = {
            "text": text,
            "button": button,
            "case_sensitive": case_sensitive
        }
        return await self._execute_single_action("text_find_and_click", params)
    
    async def _handle_image_upload_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle image upload actions that require file uploads"""
        image_path = params.get('image_path')
        if not image_path:
            raise ValueError(f"image_path required for {action}")
        
        # Check if file exists
        file_path = Path(image_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        url_map = {
            'image_search': '/image/search',
            'image_find_and_click': '/image/find_and_click'
        }
        
        url = f"{self.mouse_api_host}{url_map[action]}"
        
        # Prepare files for upload
        files = {"image": (file_path.name, file_path.open("rb"), "application/octet-stream")}
        
        # Convert non-string parameters to form data
        data = {}
        for key, value in params.items():
            if key != 'image_path':  # Skip the image_path parameter
                if isinstance(value, bool):
                    data[key] = "true" if value else "false"
                else:
                    data[key] = str(value)
        
        async with self.session.post(url, files=files, data=data, headers=self.mouse_headers) as response:
            response.raise_for_status()
            return await response.json()
    
    # Additional convenience methods for new functionality
    async def mouse_drag(self, from_x: int, from_y: int, to_x: int, to_y: int, 
                         duration: Optional[float] = None, button: str = "left") -> Dict[str, Any]:
        """Drag mouse from one position to another"""
        params = {
            "from_x": from_x,
            "from_y": from_y,
            "to_x": to_x,
            "to_y": to_y,
            "button": button
        }
        if duration is not None:
            params["duration"] = duration
        return await self._execute_single_action("mouse_drag", params)
    
    async def mouse_scroll(self, direction: str = "vertical", clicks: int = 3, 
                           x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        """Scroll mouse wheel"""
        params = {
            "direction": direction,
            "clicks": clicks
        }
        if x is not None:
            params["x"] = x
        if y is not None:
            params["y"] = y
        return await self._execute_single_action("mouse_scroll", params)
    
    async def screen_capture_at_cursor(self, width: int, height: int) -> Dict[str, Any]:
        """Capture screenshot around cursor position"""
        params = {"width": width, "height": height}
        return await self._execute_single_action("screen_capture_at_cursor", params)
    
    async def screen_capture_with_ocr(self, text: Optional[str] = None, 
                                      show_all: bool = True, min_confidence: float = 0.8) -> Dict[str, Any]:
        """Capture screenshot with OCR overlay"""
        params = {
            "show_all": show_all,
            "min_confidence": min_confidence
        }
        if text is not None:
            params["text"] = text
        return await self._execute_single_action("screen_capture_with_ocr", params)
    
    async def text_type(self, text: str, x: Optional[int] = None, y: Optional[int] = None,
                        interval: float = 0.05, mode: str = "type", press_enter: bool = False,
                        paste_delay: float = 0.1, preserve_clipboard: bool = True,
                        enter_count: int = 1, enter_interval: float = 0.05) -> Dict[str, Any]:
        """Type text at current or specified position with advanced options"""
        params = {
            "text": text,
            "interval": interval,
            "mode": mode,
            "press_enter": press_enter,
            "paste_delay": paste_delay,
            "preserve_clipboard": preserve_clipboard,
            "enter_count": enter_count,
            "enter_interval": enter_interval
        }
        if x is not None:
            params["x"] = x
        if y is not None:
            params["y"] = y
        return await self._execute_single_action("text_type", params)
    
    async def text_ocr(self, min_confidence: float = 0.8, debug: bool = False) -> Dict[str, Any]:
        """Extract text from screen using OCR"""
        params = {
            "min_confidence": min_confidence,
            "debug": debug
        }
        return await self._execute_single_action("text_ocr", params)
    
    async def image_search(self, image_path: str, threshold: float = 0.8, 
                           multi_scale: bool = True) -> Dict[str, Any]:
        """Search for image on screen"""
        params = {
            "image_path": image_path,
            "threshold": threshold,
            "multi_scale": multi_scale
        }
        return await self._execute_single_action("image_search", params)
    
    async def image_find_and_click(self, image_path: str, threshold: float = 0.8,
                                   multi_scale: bool = True, button: str = "left",
                                   click_all: bool = False, offset_x: int = 0, 
                                   offset_y: int = 0) -> Dict[str, Any]:
        """Find image on screen and click it with optional offset"""
        params = {
            "image_path": image_path,
            "threshold": threshold,
            "multi_scale": multi_scale,
            "button": button,
            "click_all": click_all,
            "offset_x": offset_x,
            "offset_y": offset_y
        }
        return await self._execute_single_action("image_find_and_click", params)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check mouse API health status"""
        return await self._execute_single_action("health", {})