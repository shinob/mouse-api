import asyncio
import json
import logging
from typing import Dict, Any, Optional
from aiohttp import web, WSMsgType
from client import OllamaMCPClient, MCPMessage
from mouse_integration import MouseCapableOllamaClient

def json_dumps(obj):
    """JSON encoder that doesn't escape unicode characters"""
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))

class MCPServer:
    def __init__(self, host: str = "localhost", port: int = 8080, ollama_host: str = "http://localhost:11434", 
                 model: str = "gpt-oss:20b", mouse_api_host: str = "http://localhost:8000", 
                 mouse_api_key: str = None, enable_mouse: bool = True):
        self.host = host
        self.port = port
        self.ollama_host = ollama_host
        self.model = model
        self.mouse_api_host = mouse_api_host
        self.mouse_api_key = mouse_api_key
        self.enable_mouse = enable_mouse
        self.app = web.Application()
        self.setup_routes()
        self.logger = logging.getLogger(__name__)
        
    def setup_routes(self):
        """Setup HTTP and WebSocket routes"""
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_post('/mcp', self.handle_mcp_request)
        self.app.router.add_post('/enhanced', self.handle_enhanced_request)
        self.app.router.add_get('/ws', self.websocket_handler)
        self.app.router.add_get('/models', self.list_models)
        self.app.router.add_post('/pull', self.pull_model)
        # Mouse control endpoints
        if self.enable_mouse:
            self.app.router.add_post('/mouse/move', self.mouse_move)
            self.app.router.add_post('/mouse/click', self.mouse_click)
            self.app.router.add_get('/mouse/position', self.mouse_position)
            self.app.router.add_get('/screen/capture', self.screen_capture)
    
    async def health_check(self, request):
        """Health check endpoint"""
        return web.json_response({"status": "healthy"}, dumps=json_dumps)
    
    async def handle_mcp_request(self, request):
        """Handle MCP requests via HTTP POST"""
        try:
            data = await request.json()
            message = MCPMessage(
                method=data.get('method'),
                params=data.get('params'),
                id=data.get('id')
            )
            
            if self.enable_mouse:
                async with MouseCapableOllamaClient(self.ollama_host, self.model, self.mouse_api_host, self.mouse_api_key) as client:
                    await client.initialize()
                    result = await client.handle_mcp_message(message)
                    return web.json_response(result, dumps=json_dumps)
            else:
                async with OllamaMCPClient(self.ollama_host, self.model) as client:
                    result = await client.handle_mcp_message(message)
                    return web.json_response(result, dumps=json_dumps)
                
        except Exception as e:
            self.logger.error(f"MCP request failed: {e}")
            return web.json_response(
                {"error": str(e)}, 
                status=400,
                dumps=json_dumps
            )
    
    async def handle_enhanced_request(self, request):
        """Handle enhanced MCP requests with mouse capabilities"""
        try:
            data = await request.json()
            prompt = data.get('prompt', '')
            enable_mouse_actions = data.get('enable_mouse_actions', True)
            
            if self.enable_mouse:
                async with MouseCapableOllamaClient(self.ollama_host, self.model, self.mouse_api_host, self.mouse_api_key) as client:
                    await client.initialize()
                    result = await client.send_enhanced_prompt(prompt, enable_mouse_actions)
                    return web.json_response(result, dumps=json_dumps)
            else:
                async with OllamaMCPClient(self.ollama_host, self.model) as client:
                    result = await client.send_prompt(prompt)
                    return web.json_response(result, dumps=json_dumps)
                    
        except Exception as e:
            self.logger.error(f"Enhanced request failed: {e}")
            return web.json_response(
                {"error": str(e)}, 
                status=400,
                dumps=json_dumps
            )
    
    async def websocket_handler(self, request):
        """Handle WebSocket connections for real-time MCP communication"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        self.logger.info("WebSocket connection established")
        
        client_class = MouseCapableOllamaClient if self.enable_mouse else OllamaMCPClient
        args = (self.ollama_host, self.model, self.mouse_api_host) if self.enable_mouse else (self.ollama_host, self.model)
        
        async with client_class(*args) as client:
            try:
                await client.initialize()
                await ws.send_str(json.dumps({
                    "type": "initialized",
                    "model": client.model
                }))
                
                async for msg in ws:
                    if msg.type == WSMsgType.TEXT:
                        try:
                            data = json.loads(msg.data)
                            message = MCPMessage(
                                method=data.get('method'),
                                params=data.get('params'),
                                id=data.get('id')
                            )
                            
                            if hasattr(client, 'handle_enhanced_mcp_message'):
                                result = await client.handle_enhanced_mcp_message(message)
                            else:
                                result = await client.handle_mcp_message(message)
                            
                            # Check if WebSocket is still open before sending
                            if not ws.closed:
                                await ws.send_str(json.dumps(result, default=str))
                            
                        except Exception as e:
                            # Check if WebSocket is still open before sending error
                            if not ws.closed:
                                await ws.send_str(json.dumps({
                                    "error": str(e),
                                    "id": data.get('id') if 'data' in locals() else None
                                }, default=str))
                    elif msg.type == WSMsgType.ERROR:
                        self.logger.error(f'WebSocket error: {ws.exception()}')
                        break
                    elif msg.type == WSMsgType.CLOSE:
                        self.logger.info("WebSocket connection closed by client")
                        break
                        
            except Exception as e:
                self.logger.error(f"WebSocket handler error: {e}")
                # Only send error if WebSocket is still open
                if not ws.closed:
                    try:
                        await ws.send_str(json.dumps({"error": str(e)}, default=str))
                    except Exception:
                        # Connection may have been closed during error handling
                        pass
        
        self.logger.info("WebSocket connection closed")
        return ws
    
    async def list_models(self, request):
        """List available Ollama models"""
        try:
            async with OllamaMCPClient(self.ollama_host, self.model) as client:
                models = await client.list_models()
                return web.json_response({"models": models}, dumps=json_dumps)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500, dumps=json_dumps)
    
    async def pull_model(self, request):
        """Pull a model to Ollama"""
        try:
            data = await request.json()
            model_name = data.get('model')
            
            if not model_name:
                return web.json_response({"error": "Model name required"}, status=400, dumps=json_dumps)
            
            async with OllamaMCPClient(self.ollama_host, self.model) as client:
                result = await client.pull_model(model_name)
                return web.json_response(result)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500, dumps=json_dumps)
    
    # Direct mouse control endpoints
    async def mouse_move(self, request):
        """Move mouse to specified coordinates"""
        try:
            data = await request.json()
            x = data.get('x')
            y = data.get('y')
            duration = data.get('duration')
            
            if x is None or y is None:
                return web.json_response({"error": "x and y coordinates required"}, status=400, dumps=json_dumps)
            
            async with MouseCapableOllamaClient(self.ollama_host, self.model, self.mouse_api_host) as client:
                await client.initialize()
                result = await client.mouse_move(x, y, duration)
                return web.json_response(result)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500, dumps=json_dumps)
    
    async def mouse_click(self, request):
        """Click mouse at current or specified position"""
        try:
            data = await request.json()
            button = data.get('button', 'left')
            x = data.get('x')
            y = data.get('y')
            
            async with MouseCapableOllamaClient(self.ollama_host, self.model, self.mouse_api_host) as client:
                await client.initialize()
                result = await client.mouse_click(button, x, y)
                return web.json_response(result)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500, dumps=json_dumps)
    
    async def mouse_position(self, request):
        """Get current mouse position"""
        try:
            async with MouseCapableOllamaClient(self.ollama_host, self.model, self.mouse_api_host) as client:
                await client.initialize()
                result = await client._execute_single_action("mouse_position", {})
                return web.json_response(result)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500, dumps=json_dumps)
    
    async def screen_capture(self, request):
        """Capture screenshot"""
        try:
            async with MouseCapableOllamaClient(self.ollama_host, self.model, self.mouse_api_host) as client:
                await client.initialize()
                result = await client.screen_capture()
                return web.json_response(result)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500, dumps=json_dumps)
    
    async def start_server(self):
        """Start the MCP server"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        self.logger.info(f"MCP Server started on {self.host}:{self.port}")
        return runner

async def main():
    """Main function to run the server"""
    logging.basicConfig(level=logging.INFO)
    
    # Load configuration
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        ollama_config = config.get('ollama', {})
        mouse_config = config.get('mouse_api', {})
        server_config = config.get('server', {})
        
        server = MCPServer(
            host=server_config.get('host', 'localhost'),
            port=server_config.get('port', 8080),
            ollama_host=ollama_config.get('host', 'http://localhost:11434'),
            model=ollama_config.get('model', 'gpt-oss:20b'),
            mouse_api_host=mouse_config.get('host', 'http://localhost:8000'),
            mouse_api_key=mouse_config.get('api_key'),
            enable_mouse=mouse_config.get('enabled', True)
        )
    except FileNotFoundError:
        print("config.json not found, using default settings")
        server = MCPServer()
    except Exception as e:
        print(f"Error loading config: {e}, using default settings")
        server = MCPServer()
    
    runner = await server.start_server()
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())