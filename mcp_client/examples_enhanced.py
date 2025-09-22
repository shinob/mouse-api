"""
Enhanced examples demonstrating Ollama MCP Client with mouse control integration
マウス制御統合機能を持つOllama MCPクライアントの拡張使用例
"""

import asyncio
import json
import logging
from mouse_integration import MouseCapableOllamaClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def basic_mouse_integration_example():
    """Basic example of using Ollama with mouse control"""
    print("=== Basic Mouse Integration Example ===")
    
    async with MouseCapableOllamaClient(
        ollama_host="http://localhost:11434",
        model="gpt-oss:20b",
        mouse_api_host="http://localhost:8000"
    ) as client:
        # Initialize both Ollama and mouse API
        init_result = await client.initialize()
        print(f"Initialization: {init_result}")
        
        # Send a prompt that requests mouse actions
        #prompt = "Please take a screenshot and then click on any text that says 'Submit' or 'OK'"
        prompt = "マウスの現在位置を取得してそこから10pxずつXとYをずらして下さい。"
        
        response = await client.send_enhanced_prompt(prompt)
        print(f"Response: {response.get('response', '')}")
        
        if 'mouse_actions_executed' in response:
            print("Mouse actions were executed:")
            for action in response['mouse_actions_executed']:
                print(f"  - {action['action']}: {action.get('success', 'Unknown')}")

async def direct_mouse_control_example():
    """Example of direct mouse control without LLM intervention"""
    print("\n=== Direct Mouse Control Example ===")
    
    async with MouseCapableOllamaClient(
        ollama_host="http://localhost:11434",
        model="gpt-oss:20b",
        mouse_api_host="http://localhost:8000"
    ) as client:
        await client.initialize()
        
        # Take a screenshot first
        print("Taking screenshot...")
        screenshot = await client.screen_capture()
        print(f"Screenshot result: {screenshot.get('status', 'Unknown')}")
        
        # Save screenshot if successful
        if screenshot.get('status') == 'success' and 'image' in screenshot:
            import base64
            image_data = base64.b64decode(screenshot['image'])
            with open('screenshot_example.png', 'wb') as f:
                f.write(image_data)
            print("Screenshot saved as 'screenshot_example.png'")
        
        # Get current mouse position
        position = await client._execute_single_action("mouse_position", {})
        print(f"Current mouse position: {position}")
        
        # Move mouse to specific position
        move_result = await client.mouse_move(100, 200, 1.0)
        print(f"Mouse move result: {move_result}")
        
        # Search for text on screen
        search_result = await client.text_search("Submit", case_sensitive=False)
        print(f"Text search result: {search_result}")
        
        # If text found, click on it
        if search_result.get('found', False):
            locations = search_result.get('locations', [])
            if locations:
                first_location = locations[0]
                x, y = first_location['center']
                print(f"Clicking on 'Submit' at ({x}, {y})")
                await client.mouse_click("left", x, y)

async def conversational_mouse_example():
    """Example of conversational interface with mouse actions"""
    print("\n=== Conversational Mouse Example ===")
    
    async with MouseCapableOllamaClient(
        ollama_host="http://localhost:11434", 
        model="gpt-oss:20b",
        mouse_api_host="http://localhost:8000"
    ) as client:
        await client.initialize()
        
        conversation = [
            "Hello! Can you take a screenshot for me?",
            "Now please move the mouse to coordinates 100, 200",
            "Can you find any text that says 'File' on the screen and click it?",
        ]
        
        for prompt in conversation:
            print(f"\nUser: {prompt}")
            response = await client.send_enhanced_prompt(prompt)
            print(f"Assistant: {response.get('response', '')}")
            
            if 'mouse_actions_executed' in response:
                print("Actions executed:")
                for action in response['mouse_actions_executed']:
                    if action['success']:
                        print(f"  ✓ {action['action']} succeeded")
                    else:
                        print(f"  ✗ {action['action']} failed: {action.get('error', 'Unknown error')}")

async def http_server_example():
    """Example of using the HTTP server interface"""
    print("\n=== HTTP Server Interface Example ===")
    
    import aiohttp
    
    # Test enhanced endpoint
    async with aiohttp.ClientSession() as session:
        # Enhanced request with mouse actions
        payload = {
            "prompt": "Please take a screenshot and tell me what you see",
            "enable_mouse_actions": True
        }
        
        try:
            async with session.post('http://localhost:8080/enhanced', json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    print(f"Enhanced response: {result.get('response', '')}")
                    if 'mouse_actions_executed' in result:
                        print(f"Mouse actions: {len(result['mouse_actions_executed'])} executed")
                else:
                    print(f"Error: {resp.status}")
        except Exception as e:
            print(f"Connection error: {e}")

async def websocket_example():
    """Example of using WebSocket interface"""
    print("\n=== WebSocket Interface Example ===")
    
    import aiohttp
    
    try:
        session = aiohttp.ClientSession()
        async with session.ws_connect('ws://localhost:8080/ws') as ws:
            print("WebSocket connected")
            
            # Send enhanced completion request
            message = {
                "method": "enhanced_completion",
                "params": {
                    "prompt": "Please click on any button you can find on the screen",
                    "enable_mouse_actions": True
                },
                "id": "test-1"
            }
            
            await ws.send_str(json.dumps(message))
            
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    response = json.loads(msg.data)
                    print(f"WebSocket response: {response}")
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    print(f"WebSocket error: {ws.exception()}")
                    break
        
        await session.close()
        
    except Exception as e:
        print(f"WebSocket connection error: {e}")

async def test_error_handling():
    """Test error handling and fallback behavior"""
    print("\n=== Error Handling Test ===")
    
    # Test with invalid mouse API host
    async with MouseCapableOllamaClient(
        ollama_host="http://localhost:11434",
        model="llama2", 
        mouse_api_host="http://localhost:9999"  # Invalid port
    ) as client:
        init_result = await client.initialize()
        print(f"Init with invalid mouse API: {init_result}")
        
        # Should still work for regular Ollama requests
        response = await client.send_prompt("Hello, what is 2+2?")
        print(f"Regular prompt response: {response.get('response', '')}")
        
        # Enhanced prompt should handle mouse API unavailability gracefully
        response = await client.send_enhanced_prompt("Please take a screenshot")
        print(f"Enhanced prompt with unavailable mouse API: {response.get('response', '')}")

async def main():
    """Run all examples"""
    print("Starting Ollama MCP Client with Mouse Integration Examples")
    print("=" * 60)
    
    try:
        await basic_mouse_integration_example()
        await direct_mouse_control_example()
        await conversational_mouse_example()
        await http_server_example()
        await websocket_example()
        await test_error_handling()
        
    except Exception as e:
        logger.error(f"Example failed: {e}")
        print(f"Error running examples: {e}")
    
    print("\n" + "=" * 60)
    print("Examples completed!")

if __name__ == "__main__":
    asyncio.run(main())