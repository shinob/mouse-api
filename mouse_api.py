#!/usr/bin/env python3
import os
import io
import base64
import argparse
import numpy as np
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
try:
    import pytesseract
    import cv2
    OCR_AVAILABLE = True
except Exception as e:
    print(f"警告: OCR機能が利用できません: {e}")
    print("文字検索機能は無効化されます")
    OCR_AVAILABLE = False

app = Flask(__name__)

if GUI_AVAILABLE:
    pyautogui.FAILSAFE = False

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
        lang = data.get('lang', 'jpn+eng')
        case_sensitive = data.get('case_sensitive', False)
        min_confidence = float(data.get('min_confidence', 50.0))
        
        # スクリーンキャプチャ
        screenshot = ImageGrab.grab()
        
        # PIL ImageをOpenCV形式に変換
        cv_image = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        
        # OCRでテキストの位置情報を取得
        ocr_data = pytesseract.image_to_data(cv_image, lang=lang, output_type=pytesseract.Output.DICT)
        
        matches = []
        n_boxes = len(ocr_data['level'])
        
        for i in range(n_boxes):
            text = ocr_data['text'][i].strip()
            if not text:
                continue
            
            # 大文字小文字の処理
            search_text = target_text if case_sensitive else target_text.lower()
            found_text = text if case_sensitive else text.lower()
            
            # 完全一致または部分一致をチェック
            if search_text in found_text:
                x, y, w, h = ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i]
                confidence = float(ocr_data['conf'][i])
                
                # 信頼度チェック
                if confidence < min_confidence:
                    continue
                
                # クリック位置（ボックスの中央）を計算
                click_x = x + w // 2
                click_y = y + h // 2
                
                matches.append({
                    'text': text,
                    'x': click_x,
                    'y': click_y,
                    'bbox': {'x': x, 'y': y, 'width': w, 'height': h},
                    'confidence': confidence
                })
        
        # 信頼度でソート
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        
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
        lang = data.get('lang', 'jpn+eng')
        case_sensitive = data.get('case_sensitive', False)
        min_confidence = float(data.get('min_confidence', 50.0))
        button = data.get('button', 'left')
        click_all = data.get('click_all', False)
        
        if button not in ['left', 'right', 'middle']:
            return jsonify({'error': 'Invalid button. Use left, right, or middle', 'status': 'error'}), 400
        
        # スクリーンキャプチャ
        screenshot = ImageGrab.grab()
        
        # PIL ImageをOpenCV形式に変換
        cv_image = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        
        # OCRでテキストの位置情報を取得
        ocr_data = pytesseract.image_to_data(cv_image, lang=lang, output_type=pytesseract.Output.DICT)
        
        matches = []
        n_boxes = len(ocr_data['level'])
        
        for i in range(n_boxes):
            text = ocr_data['text'][i].strip()
            if not text:
                continue
            
            # 大文字小文字の処理
            search_text = target_text if case_sensitive else target_text.lower()
            found_text = text if case_sensitive else text.lower()
            
            # 完全一致または部分一致をチェック
            if search_text in found_text:
                x, y, w, h = ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i]
                confidence = float(ocr_data['conf'][i])
                
                # 信頼度チェック
                if confidence < min_confidence:
                    continue
                
                # クリック位置（ボックスの中央）を計算
                click_x = x + w // 2
                click_y = y + h // 2
                
                matches.append({
                    'text': text,
                    'x': click_x,
                    'y': click_y,
                    'bbox': {'x': x, 'y': y, 'width': w, 'height': h},
                    'confidence': confidence
                })
        
        # 信頼度でソート
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        
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