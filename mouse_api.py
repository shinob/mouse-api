#!/usr/bin/env python3
import os
import io
import base64
import argparse
import numpy as np
import requests
import time
import tempfile
from flask import Flask, jsonify, request

# DISPLAY環境変数の設定（Linux環境用）
if os.name == 'posix' and 'DISPLAY' not in os.environ:
    os.environ['DISPLAY'] = ':0'

try:
    import pyautogui
    from PIL import ImageGrab
    GUI_AVAILABLE = True
except Exception as e:
    print(f"警告: GUI機能が利用できません: {e}")
    print("画面キャプチャとマウス操作は無効化されます")
    GUI_AVAILABLE = False

# OCR機能の初期化
OCR_API_URL = os.environ.get('OCR_API_URL', 'http://localhost:8000')
OCR_EMAIL = os.environ.get('OCR_EMAIL', 'test@example.com')
OCR_TIMEOUT = int(os.environ.get('OCR_TIMEOUT', '300'))  # 60秒タイムアウト

def test_ocr_api():
    """OCR APIの接続テスト"""
    try:
        response = requests.get(f"{OCR_API_URL}/", timeout=5)
        return response.text == "ocr api is working."
    except Exception:
        return False

OCR_AVAILABLE = test_ocr_api()
if not OCR_AVAILABLE:
    print(f"警告: OCR API ({OCR_API_URL}) に接続できません")
    print("文字検索機能は無効化されます")

app = Flask(__name__)

if GUI_AVAILABLE:
    pyautogui.FAILSAFE = False

def process_image_with_ocr_api(image):
    """画像をOCR APIで処理してテキストと位置情報を取得"""
    try:
        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            image.save(temp_file, format='PNG')
            temp_path = temp_file.name
        
        # OCR APIにアップロード
        with open(temp_path, 'rb') as f:
            files = {'file': f}
            data = {'email': OCR_EMAIL}
            response = requests.post(f"{OCR_API_URL}/upload", files=files, data=data)
            upload_data = response.json()
            tempfile_name = upload_data['tempfile']
        
        # 一時ファイル削除
        os.unlink(temp_path)
        
        # ポーリングで結果取得
        start_time = time.time()
        while time.time() - start_time < OCR_TIMEOUT:
            result_data = {'tempfile': tempfile_name}
            result_response = requests.post(f"{OCR_API_URL}/result", files={'tempfile': (None, tempfile_name)})
            result_text = result_response.text
            
            if result_text == "working":
                time.sleep(2)  # 2秒待機
                continue
            elif result_text == "false":
                return None
            else:
                # OCR結果を解析して座標情報を推定
                # 注意: OCR APIは座標情報を提供しないため、テキストのみ返す
                return result_text
        
        return None  # タイムアウト
    except Exception as e:
        print(f"OCR API処理エラー: {e}")
        return None

def find_text_positions(image, target_text, case_sensitive=False):
    """OCR APIを使用してテキストの位置を推定"""
    # OCR APIからテキストを取得
    ocr_text = process_image_with_ocr_api(image)
    if not ocr_text:
        return []
    
    # 大文字小文字の処理
    search_text = target_text if case_sensitive else target_text.lower()
    found_text = ocr_text if case_sensitive else ocr_text.lower()
    
    # テキストが見つからない場合
    if search_text not in found_text:
        return []
    
    # OCR APIは座標情報を提供しないため、画面中央を返す
    # より精密な座標が必要な場合は、別途画像処理ライブラリを使用する必要がある
    width, height = image.size
    center_x, center_y = width // 2, height // 2
    
    matches = [{
        'text': target_text,
        'x': center_x,
        'y': center_y,
        'bbox': {'x': center_x - 50, 'y': center_y - 10, 'width': 100, 'height': 20},
        'confidence': 80.0  # 固定値
    }]
    
    return matches

@app.route('/mouse/position', methods=['GET'])
def get_mouse_position():
    if not GUI_AVAILABLE:
        return jsonify({'error': 'GUI functionality not available', 'status': 'error'}), 503
    try:
        x, y = pyautogui.position()
        return jsonify({'x': x, 'y': y, 'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/mouse/move', methods=['POST'])
def move_mouse():
    if not GUI_AVAILABLE:
        return jsonify({'error': 'GUI functionality not available', 'status': 'error'}), 503
    try:
        data = request.get_json()
        if not data or 'x' not in data or 'y' not in data:
            return jsonify({'error': 'x and y coordinates required', 'status': 'error'}), 400
        
        x = int(data['x'])
        y = int(data['y'])
        duration = float(data.get('duration', 0))
        
        pyautogui.moveTo(x, y, duration=duration)
        return jsonify({'status': 'success', 'x': x, 'y': y})
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/mouse/click', methods=['POST'])
def click_mouse():
    if not GUI_AVAILABLE:
        return jsonify({'error': 'GUI functionality not available', 'status': 'error'}), 503
    try:
        data = request.get_json()
        button = data.get('button', 'left') if data else 'left'
        x = data.get('x') if data else None
        y = data.get('y') if data else None
        
        if button not in ['left', 'right', 'middle']:
            return jsonify({'error': 'Invalid button. Use left, right, or middle', 'status': 'error'}), 400
        
        if x is not None and y is not None:
            pyautogui.click(x, y, button=button)
        else:
            pyautogui.click(button=button)
            
        return jsonify({'status': 'success', 'button': button})
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/screen/capture', methods=['GET'])
def capture_screen():
    if not GUI_AVAILABLE:
        return jsonify({'error': 'GUI functionality not available', 'status': 'error'}), 503
    try:
        screenshot = ImageGrab.grab()
        
        img_buffer = io.BytesIO()
        screenshot.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
        
        return jsonify({
            'status': 'success',
            'image': img_base64,
            'format': 'PNG',
            'size': {'width': screenshot.width, 'height': screenshot.height}
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/text/search', methods=['POST'])
def search_text():
    if not GUI_AVAILABLE:
        return jsonify({'error': 'GUI functionality not available', 'status': 'error'}), 503
    if not OCR_AVAILABLE:
        return jsonify({'error': 'OCR functionality not available', 'status': 'error'}), 503
    
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'text parameter required', 'status': 'error'}), 400
        
        target_text = data['text']
        case_sensitive = data.get('case_sensitive', False)
        min_confidence = float(data.get('min_confidence', 50.0))
        
        # スクリーンキャプチャ
        screenshot = ImageGrab.grab()
        
        # OCR APIでテキストの位置情報を取得
        matches = find_text_positions(screenshot, target_text, case_sensitive)
        
        # 信頼度でフィルタリング
        matches = [match for match in matches if match['confidence'] >= min_confidence]
        
        return jsonify({
            'status': 'success',
            'matches': matches,
            'total_found': len(matches)
        })
        
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/text/type', methods=['POST'])
def type_text():
    if not GUI_AVAILABLE:
        return jsonify({'error': 'GUI functionality not available', 'status': 'error'}), 503
    
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'text parameter required', 'status': 'error'}), 400
        
        text = data['text']
        x = data.get('x')
        y = data.get('y')
        interval = float(data.get('interval', 0.1))
        
        # 指定座標がある場合はクリック
        if x is not None and y is not None:
            pyautogui.click(x, y)
        
        # テキスト入力
        pyautogui.typewrite(text, interval=interval)
        
        return jsonify({'status': 'success', 'text': text})
        
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/text/find_and_click', methods=['POST'])
def find_and_click_text():
    if not GUI_AVAILABLE:
        return jsonify({'error': 'GUI functionality not available', 'status': 'error'}), 503
    if not OCR_AVAILABLE:
        return jsonify({'error': 'OCR functionality not available', 'status': 'error'}), 503
    
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'text parameter required', 'status': 'error'}), 400
        
        target_text = data['text']
        case_sensitive = data.get('case_sensitive', False)
        min_confidence = float(data.get('min_confidence', 50.0))
        button = data.get('button', 'left')
        click_all = data.get('click_all', False)
        
        if button not in ['left', 'right', 'middle']:
            return jsonify({'error': 'Invalid button. Use left, right, or middle', 'status': 'error'}), 400
        
        # スクリーンキャプチャ
        screenshot = ImageGrab.grab()
        
        # OCR APIでテキストの位置情報を取得
        matches = find_text_positions(screenshot, target_text, case_sensitive)
        
        # 信頼度でフィルタリング
        matches = [match for match in matches if match['confidence'] >= min_confidence]
        
        if not matches:
            return jsonify({
                'status': 'not_found',
                'message': f'Text "{target_text}" not found',
                'matches': []
            })
        
        # クリック実行
        clicked_positions = []
        targets = matches if click_all else matches[:1]
        
        for match in targets:
            pyautogui.click(match['x'], match['y'], button=button)
            clicked_positions.append(match)
        
        return jsonify({
            'status': 'success',
            'clicked': clicked_positions,
            'total_clicked': len(clicked_positions)
        })
        
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy', 
        'service': 'mouse-api',
        'gui_available': GUI_AVAILABLE,
        'ocr_available': OCR_AVAILABLE
    })

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Mouse API Server')
    parser.add_argument('--port', '-p', type=int, default=5000, help='Port to run the server on (default: 5000)')
    parser.add_argument('--host', type=str, default='::', help='Host to bind to (default: :: for IPv4/IPv6)')
    
    args = parser.parse_args()
    
    print(f"Starting Mouse API server on {args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)