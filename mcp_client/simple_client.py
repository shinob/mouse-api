#!/usr/bin/env python3
"""
Simple MCP Client - プロンプトを入力してresponseのみを表示
"""

import requests
import json
import sys

def send_prompt(prompt, enable_mouse_actions=True):
    """プロンプトをMCPサーバーに送信してresponseを取得"""
    url = "http://localhost:8080/enhanced"
    
    payload = {
        "prompt": prompt,
        "enable_mouse_actions": enable_mouse_actions
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            return result.get('response', 'No response field found')
        else:
            return f"Error: HTTP {response.status_code} - {response.text}"
            
    except requests.exceptions.ConnectionError:
        return "Error: Could not connect to MCP server at localhost:8080"
    except requests.exceptions.RequestException as e:
        return f"Error: {e}"
    except json.JSONDecodeError:
        return "Error: Invalid JSON response from server"

def main():
    """メイン関数"""
    print("MCP Simple Client")
    print("================")
    print("MCPサーバー (localhost:8080) にプロンプトを送信します")
    print("終了するには 'quit' または 'exit' を入力してください")
    print()
    
    while True:
        try:
            # プロンプトを入力
            prompt = input("プロンプト: ").strip()
            
            # 終了条件
            if prompt.lower() in ['quit', 'exit', 'q']:
                print("終了します。")
                break
                
            # 空の入力をスキップ
            if not prompt:
                continue
                
            # プロンプトを送信
            print("\n処理中...")
            response = send_prompt(prompt)
            
            # responseを表示
            print("\nResponse:")
            print("-" * 50)
            print(response)
            print("-" * 50)
            print()
            
        except KeyboardInterrupt:
            print("\n\n終了します。")
            break
        except EOFError:
            print("\n\n終了します。")
            break

if __name__ == "__main__":
    main()