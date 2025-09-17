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
from PIL import Image, ImageDraw, ImageFont

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
    print("OCR機能: Tesseractを使用します")
except ImportError as e:
    print(f"警告: OCR機能が利用できません: {e}")
    print("文字検索機能は無効化されます")
    print("ヒント: sudo apt-get install tesseract-ocr tesseract-ocr-jpn")
    print("       pip install pytesseract opencv-python")
    OCR_AVAILABLE = False


app = Flask(__name__)

if GUI_AVAILABLE:
    pyautogui.FAILSAFE = False

def preprocess_image_for_ocr(image):
    """OCR精度向上のための画像前処理"""
    # PIL ImageをNumPy配列に変換
    img_array = np.array(image)
    
    # OpenCVでグレースケール変換
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array
    
    # 1. ノイズ除去（ガウシアンブラー）
    denoised = cv2.GaussianBlur(gray, (1, 1), 0)
    
    # 2. コントラスト強化（CLAHE - 適応ヒストグラム均等化）
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    
    # 3. シャープニング
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(enhanced, -1, kernel)
    
    # 4. 二値化（Otsuの手法）
    _, binary = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # 5. モルフォロジー演算（ノイズ除去と文字の補完）
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    
    return cleaned

def process_image_with_tesseract(image):
    """Tesseractを使用して画像からテキストと位置情報を取得"""
    if not OCR_AVAILABLE:
        return []
    
    try:
        # 画像前処理を実行
        processed_image = preprocess_image_for_ocr(image)
        
        # Tesseractで文字認識と位置情報を取得
        # 複数の設定を試してベストな結果を選択
        configs = [
            r'--oem 3 --psm 6 -l jpn+eng',  # 標準設定
            r'--oem 3 --psm 3 -l jpn+eng',  # 完全に自動的なページセグメンテーション
            r'--oem 3 --psm 7 -l jpn+eng',  # 単一テキスト行として処理
            r'--oem 3 --psm 8 -l jpn+eng',  # 単一単語として処理
        ]
        
        best_results = []
        best_confidence = 0
        
        for config in configs:
            try:
                data = pytesseract.image_to_data(processed_image, config=config, output_type=pytesseract.Output.DICT)
                
                # 結果を標準化されたフォーマットに変換
                current_results = []
                total_confidence = 0
                valid_count = 0
                
                n_boxes = len(data['text'])
                for i in range(n_boxes):
                    if int(data['conf'][i]) > 30:  # 信頼度閾値を30に設定
                        text = data['text'][i].strip()
                        if text and len(text) > 0:  # 空文字でないもののみ
                            x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                            center_x = x + w // 2
                            center_y = y + h // 2
                            
                            current_results.append({
                                'text': text,
                                'x': center_x,
                                'y': center_y,
                                'bbox': {
                                    'x': x,
                                    'y': y,
                                    'width': w,
                                    'height': h
                                },
                                'confidence': float(data['conf'][i])
                            })
                            
                            total_confidence += float(data['conf'][i])
                            valid_count += 1
                
                # 平均信頼度を計算
                avg_confidence = total_confidence / valid_count if valid_count > 0 else 0
                
                # より良い結果の場合は更新
                if avg_confidence > best_confidence:
                    best_confidence = avg_confidence
                    best_results = current_results
                    
            except Exception:
                continue
        
        # フィルタリング: 重複する結果を除去
        filtered_results = []
        for result in best_results:
            # 既存の結果と重複していないかチェック
            is_duplicate = False
            for existing in filtered_results:
                # 座標が近く、テキストが類似している場合は重複とみなす
                distance = abs(result['x'] - existing['x']) + abs(result['y'] - existing['y'])
                if distance < 20 and result['text'].lower() in existing['text'].lower():
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                filtered_results.append(result)
        
        return filtered_results
        
    except Exception as e:
        print(f"Tesseract処理エラー: {e}")
        return []

def find_text_positions(image, target_text, case_sensitive=False):
    """Tesseractを使用してテキストの位置を取得"""
    # Tesseractで全てのテキストと位置情報を取得
    all_results = process_image_with_tesseract(image)
    if not all_results:
        return []
    
    # 大文字小文字の処理
    search_text = target_text if case_sensitive else target_text.lower()
    
    # マッチするテキストを検索
    matches = []
    for result in all_results:
        found_text = result['text'] if case_sensitive else result['text'].lower()
        
        # 部分マッチまたは完全マッチをチェック
        if search_text in found_text:
            # マッチした場合は結果に追加
            match_result = result.copy()
            match_result['matched_text'] = target_text
            matches.append(match_result)
    
    return matches

def draw_ocr_overlay(image, ocr_results, target_text=None, show_all=True):
    """OCR結果を画像に重ね合わせて描画"""
    # 画像をコピー（元画像を変更しないため）
    overlay_image = image.copy()
    draw = ImageDraw.Draw(overlay_image)
    
    # フォントを設定（日本語対応フォントを優先）
    def find_japanese_font():
        # 日本語対応フォントのパスリスト（優先順）
        japanese_font_paths = [
            # Ubuntu/Debian日本語フォント
            '/usr/share/fonts/truetype/fonts-japanese-gothic.ttf',
            '/usr/share/fonts/truetype/takao-gothic/TakaoGothic.ttf',
            '/usr/share/fonts/truetype/vlgothic/VL-Gothic-Regular.ttf',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
            
            # 一般的な日本語フォント
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            
            # macOS
            '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc',
            '/System/Library/Fonts/Arial Unicode MS.ttf',
            '/Library/Fonts/Arial Unicode MS.ttf',
            '/System/Library/Fonts/Arial.ttf',
            
            # Windows (WSL環境)
            '/mnt/c/Windows/Fonts/msgothic.ttc',
            '/mnt/c/Windows/Fonts/meiryo.ttc',
            '/mnt/c/Windows/Fonts/arial.ttf',
        ]
        
        for font_path in japanese_font_paths:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, 14)
                    print(f"フォント使用: {font_path}")
                    return font
                except Exception as e:
                    continue
        
        # フォントが見つからない場合の対策
        try:
            # より大きなデフォルトフォントを試す
            from PIL import ImageFont
            font = ImageFont.load_default()
            print("デフォルトフォントを使用（日本語表示に制限があります）")
            return font
        except:
            print("フォント読み込みエラー")
            return None
    
    font = find_japanese_font()
    
    # OCR結果を描画
    for i, result in enumerate(ocr_results):
        bbox = result['bbox']
        text = result['text']
        confidence = result['confidence']
        
        # バウンディングボックスの座標
        x, y, w, h = bbox['x'], bbox['y'], bbox['width'], bbox['height']
        
        # ターゲットテキストかどうかで色を変更
        is_target = False
        if target_text:
            target_lower = target_text.lower()
            text_lower = text.lower()
            is_target = target_lower in text_lower
        
        # 色の設定
        if is_target:
            box_color = (255, 0, 0)  # 赤色（ターゲットテキスト）
            text_color = (255, 255, 255)  # 白色
            bg_color = (255, 0, 0, 128)  # 半透明赤
        elif show_all:
            if confidence >= 80:
                box_color = (0, 255, 0)  # 緑色（高信頼度）
            elif confidence >= 50:
                box_color = (255, 165, 0)  # オレンジ色（中信頼度）
            else:
                box_color = (128, 128, 128)  # グレー色（低信頼度）
            text_color = (255, 255, 255)
            bg_color = (*box_color, 128)  # 半透明
        else:
            continue  # show_all=Falseでターゲットでない場合はスキップ
        
        # バウンディングボックスを描画
        draw.rectangle([x, y, x + w, y + h], outline=box_color, width=2)
        
        # 信頼度とテキストのラベルを作成
        label = f"{text} ({confidence:.1f}%)"
        
        # フォントが利用可能な場合のみラベルを描画
        if font:
            # ラベルの背景を描画
            try:
                bbox_text = draw.textbbox((0, 0), label, font=font)
                label_width = bbox_text[2] - bbox_text[0]
                label_height = bbox_text[3] - bbox_text[1]
            except:
                # 古いPillowバージョンの場合
                try:
                    label_width, label_height = draw.textsize(label, font=font)
                except:
                    # textsize()も利用できない場合の推定値
                    label_width = len(label) * 8
                    label_height = 16
            
            label_x = x
            label_y = max(0, y - label_height - 2)
            
            # ラベル背景を描画
            draw.rectangle([label_x, label_y, label_x + label_width, label_y + label_height], 
                          fill=box_color)
            
            # テキストを描画（エラーハンドリング付き）
            try:
                draw.text((label_x, label_y), label, fill=text_color, font=font)
            except Exception as e:
                # 日本語フォントでエラーが発生した場合はASCII文字のみで表示
                ascii_label = f"Text ({confidence:.1f}%)"
                draw.text((label_x, label_y), ascii_label, fill=text_color, font=font)
        else:
            # フォントが利用できない場合は座標のみ表示
            coord_label = f"({x},{y})"
            draw.text((x, max(0, y - 15)), coord_label, fill=text_color)
        
        # 中心点を描画
        center_x, center_y = result['x'], result['y']
        draw.ellipse([center_x-3, center_y-3, center_x+3, center_y+3], 
                    fill=box_color, outline=(255, 255, 255))
    
    return overlay_image

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

@app.route('/screen/capture_with_ocr', methods=['POST'])
def capture_screen_with_ocr():
    """スクリーンキャプチャしてOCR結果を重ね合わせた画像を返す"""
    if not GUI_AVAILABLE:
        return jsonify({'error': 'GUI functionality not available', 'status': 'error'}), 503
    if not OCR_AVAILABLE:
        return jsonify({'error': 'OCR functionality not available', 'status': 'error'}), 503
    
    try:
        data = request.get_json() or {}
        target_text = data.get('text', None)  # 特定のテキストをハイライト
        show_all = data.get('show_all', True)  # 全てのテキストを表示するか
        min_confidence = float(data.get('min_confidence', 30.0))  # 最小信頼度
        
        # スクリーンキャプチャ
        screenshot = ImageGrab.grab()
        
        # OCRでテキストを検出
        ocr_results = process_image_with_tesseract(screenshot)
        
        # 信頼度でフィルタリング
        filtered_results = [result for result in ocr_results if result['confidence'] >= min_confidence]
        
        # OCR結果を画像に重ね合わせ
        overlay_image = draw_ocr_overlay(screenshot, filtered_results, target_text, show_all)
        
        # 画像をBase64エンコード
        img_buffer = io.BytesIO()
        overlay_image.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
        
        # ターゲットテキストが指定されている場合、マッチした結果を別途返す
        target_matches = []
        if target_text:
            target_matches = find_text_positions(screenshot, target_text, False)
            target_matches = [match for match in target_matches if match['confidence'] >= min_confidence]
        
        return jsonify({
            'status': 'success',
            'image': img_base64,
            'format': 'PNG',
            'size': {'width': overlay_image.width, 'height': overlay_image.height},
            'ocr_results': filtered_results,
            'total_detected': len(filtered_results),
            'target_matches': target_matches,
            'total_target_matches': len(target_matches),
            'parameters': {
                'target_text': target_text,
                'show_all': show_all,
                'min_confidence': min_confidence
            }
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