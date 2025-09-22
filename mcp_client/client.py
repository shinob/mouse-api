import json
import asyncio
import logging
from typing import Dict, Any, Optional, List
import aiohttp
from dataclasses import dataclass

@dataclass
class MCPMessage:
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[str] = None

class OllamaMCPClient:
    def __init__(self, ollama_host: str = "http://localhost:11434", model: str = "gpt-oss:20b"):
        self.ollama_host = ollama_host
        self.model = model
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logging.getLogger(__name__)
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def initialize(self) -> Dict[str, Any]:
        """Initialize MCP connection with Ollama"""
        try:
            url = f"{self.ollama_host}/api/tags"
            async with self.session.get(url) as response:
                if response.status == 200:
                    models = await response.json()
                    available_models = [model['name'] for model in models.get('models', [])]
                    
                    if self.model not in available_models:
                        self.logger.warning(f"Model {self.model} not found. Available models: {available_models}")
                        if available_models:
                            self.model = available_models[0]
                            self.logger.info(f"Using {self.model} instead")
                    
                    return {
                        "status": "initialized",
                        "model": self.model,
                        "available_models": available_models
                    }
                else:
                    raise Exception(f"Failed to connect to Ollama: {response.status}")
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            raise
    
    async def send_prompt(self, prompt: str, stream: bool = False) -> Dict[str, Any]:
        """Send a prompt to Ollama and get response"""
        try:
            url = f"{self.ollama_host}/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": stream
            }
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    if stream:
                        result = await self._handle_stream_response(response)
                    else:
                        result = await response.json()
                    
                    # Remove unnecessary context field
                    if 'context' in result:
                        del result['context']
                    
                    return result
                else:
                    error_text = await response.text()
                    raise Exception(f"Ollama request failed: {response.status} - {error_text}")
        except Exception as e:
            self.logger.error(f"Failed to send prompt: {e}")
            raise
    
    async def _handle_stream_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """Handle streaming response from Ollama"""
        full_response = ""
        async for line in response.content:
            if line:
                try:
                    chunk = json.loads(line.decode('utf-8'))
                    if 'response' in chunk:
                        full_response += chunk['response']
                    if chunk.get('done', False):
                        return {
                            "response": full_response,
                            "done": True,
                            "model": chunk.get('model', self.model)
                        }
                except json.JSONDecodeError:
                    continue
        
        return {"response": full_response, "done": True}
    
    async def chat(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Send chat messages to Ollama"""
        try:
            url = f"{self.ollama_host}/api/chat"
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False
            }
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # Remove unnecessary context field
                    if 'context' in result:
                        del result['context']
                    
                    return result
                else:
                    error_text = await response.text()
                    raise Exception(f"Chat request failed: {response.status} - {error_text}")
        except Exception as e:
            self.logger.error(f"Chat failed: {e}")
            raise
    
    async def handle_mcp_message(self, message: MCPMessage) -> Dict[str, Any]:
        """Handle MCP protocol messages"""
        if message.method == "initialize":
            return await self.initialize()
        elif message.method == "completion":
            prompt = message.params.get("prompt", "") if message.params else ""
            return await self.send_prompt(prompt)
        elif message.method == "chat":
            messages = message.params.get("messages", []) if message.params else []
            return await self.chat(messages)
        else:
            raise Exception(f"Unknown MCP method: {message.method}")
    
    async def pull_model(self, model_name: str) -> Dict[str, Any]:
        """Pull a model from Ollama"""
        try:
            url = f"{self.ollama_host}/api/pull"
            payload = {"name": model_name}
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    return {"status": "success", "message": f"Model {model_name} pulled successfully"}
                else:
                    error_text = await response.text()
                    raise Exception(f"Failed to pull model: {response.status} - {error_text}")
        except Exception as e:
            self.logger.error(f"Failed to pull model {model_name}: {e}")
            raise
    
    async def list_models(self) -> List[str]:
        """List available models in Ollama"""
        try:
            url = f"{self.ollama_host}/api/tags"
            async with self.session.get(url) as response:
                if response.status == 200:
                    models_data = await response.json()
                    return [model['name'] for model in models_data.get('models', [])]
                else:
                    raise Exception(f"Failed to list models: {response.status}")
        except Exception as e:
            self.logger.error(f"Failed to list models: {e}")
            raise