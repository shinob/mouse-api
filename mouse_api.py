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

# OpenCV（画像マッチング機能で必要）
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    print("警告: OpenCV機能が利用できません")
    print("画像マッチング機能は無効化されます")
    print("ヒント: pip install opencv-python")
    OPENCV_AVAILABLE = False

# OCR機能の初期化（APIクライアントを優先）
try:
    from ocr_api_client import EasyOCRClient
    # OCR APIサーバーの可用性をチェック
    ocr_api_client = EasyOCRClient()
    if ocr_api_client.is_server_available():
        OCR_AVAILABLE = True
        OCR_METHOD = "API"
        print("OCR機能: EasyOCR APIを使用します")
    else:
        # APIが利用できない場合はTesseractにフォールバック
        try:
            import pytesseract
            OCR_AVAILABLE = True
            OCR_METHOD = "TESSERACT"
            print("OCR機能: Tesseractを使用します（APIサーバーが利用できません）")
        except ImportError:
            print("警告: OCR機能が利用できません（API・Tesseractともに利用不可）")
            OCR_AVAILABLE = False
            OCR_METHOD = None
except ImportError as e:
    try:
        # OCR APIクライアントが利用できない場合はTesseractを試行
        import pytesseract
        OCR_AVAILABLE = True
        OCR_METHOD = "TESSERACT"
        print("OCR機能: Tesseractを使用します")
    except ImportError as e2:
        print(f"警告: OCR機能が利用できません: {e}, {e2}")
        print("文字検索機能は無効化されます")
        print("ヒント: OCR APIサーバーを起動するか、Tesseractをインストールしてください")
        print("       sudo apt-get install tesseract-ocr tesseract-ocr-jpn")
        print("       pip install pytesseract opencv-python")
        OCR_AVAILABLE = False
        OCR_METHOD = None


app = Flask(__name__)

if GUI_AVAILABLE:
    pyautogui.FAILSAFE = False

# クリップボード機能（pyperclip）の初期化
try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except Exception as e:
    print(f"警告: クリップボード機能が利用できません: {e}")
    print("貼り付け入力モードは無効化されます。必要なら 'pip install pyperclip' を実行し、Linuxでは xclip/xsel の導入が必要です。")
    CLIPBOARD_AVAILABLE = False

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
        
        # フィルタリング: 重複する結果を除去（改良版）
        filtered_results = []
        for result in best_results:
            # 既存の結果と重複していないかチェック
            is_duplicate = False
            for existing in filtered_results:
                # バウンディングボックスの重なりをチェック
                curr_bbox = result['bbox']
                exist_bbox = existing['bbox']
                
                # Y軸中心の計算
                curr_y_center = curr_bbox['y'] + curr_bbox['height'] // 2
                exist_y_center = exist_bbox['y'] + exist_bbox['height'] // 2
                
                # 重なりの計算
                x_overlap = max(0, min(curr_bbox['x'] + curr_bbox['width'], exist_bbox['x'] + exist_bbox['width']) - 
                              max(curr_bbox['x'], exist_bbox['x']))
                y_overlap = max(0, min(curr_bbox['y'] + curr_bbox['height'], exist_bbox['y'] + exist_bbox['height']) - 
                              max(curr_bbox['y'], exist_bbox['y']))
                
                # 重なり率を計算
                curr_area = curr_bbox['width'] * curr_bbox['height']
                exist_area = exist_bbox['width'] * exist_bbox['height']
                overlap_area = x_overlap * y_overlap
                
                # 重複判定条件
                is_significant_overlap = overlap_area > 0.5 * min(curr_area, exist_area)
                is_same_y_center = abs(curr_y_center - exist_y_center) <= 5
                is_similar_text = (result['text'].lower() in existing['text'].lower() or 
                                 existing['text'].lower() in result['text'].lower())
                
                # 重複とみなす条件
                if (is_significant_overlap and is_same_y_center) or \
                   (is_similar_text and abs(result['x'] - existing['x']) < 30 and abs(result['y'] - existing['y']) < 15):
                    # より信頼度の高い方を保持
                    if result['confidence'] > existing['confidence']:
                        filtered_results.remove(existing)
                        filtered_results.append(result)
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                filtered_results.append(result)
        
        return filtered_results
        
    except Exception as e:
        print(f"Tesseract処理エラー: {e}")
        return []

def group_nearby_text(ocr_results, y_tolerance=10, x_tolerance=50):
    """近接する文字をグルーピングして結合（重なりとY軸中心も考慮）"""
    if not ocr_results:
        return ocr_results
    
    # Y座標でソート
    sorted_results = sorted(ocr_results, key=lambda x: (x['bbox']['y'], x['bbox']['x']))
    
    grouped_results = []
    current_group = []
    
    for result in sorted_results:
        if not current_group:
            current_group = [result]
        else:
            # 現在のグループの最後の要素と比較
            last_result = current_group[-1]
            
            # バウンディングボックスの情報
            curr_bbox = result['bbox']
            last_bbox = last_result['bbox']
            
            # Y軸の中心を計算
            curr_y_center = curr_bbox['y'] + curr_bbox['height'] // 2
            last_y_center = last_bbox['y'] + last_bbox['height'] // 2
            
            # Y軸の差とX軸の位置関係
            y_diff = abs(curr_bbox['y'] - last_bbox['y'])
            y_center_diff = abs(curr_y_center - last_y_center)
            
            # X軸の重なりまたは近接性をチェック
            last_right = last_bbox['x'] + last_bbox['width']
            curr_left = curr_bbox['x']
            curr_right = curr_bbox['x'] + curr_bbox['width']
            last_left = last_bbox['x']
            
            # 重なりのチェック
            x_overlap = max(0, min(curr_right, last_right) - max(curr_left, last_left))
            has_x_overlap = x_overlap > 0
            
            # X軸の距離
            x_gap = curr_left - last_right if curr_left > last_right else 0
            
            # グルーピング条件：
            # 1. Y軸の中心が同じ（許容範囲内）で重なりがある場合
            # 2. 従来の近接条件（Y軸の差が小さく、X軸が近接）
            should_group = False
            
            if y_center_diff <= y_tolerance // 2 and has_x_overlap:
                # Y軸中心が同じで重なりがある場合
                should_group = True
            elif y_diff <= y_tolerance and 0 <= x_gap <= x_tolerance:
                # 従来の近接条件
                should_group = True
            elif y_center_diff <= y_tolerance and x_gap <= x_tolerance * 1.5:
                # Y軸中心が近く、X軸の隙間も許容範囲内
                should_group = True
            
            if should_group:
                current_group.append(result)
            else:
                # グループを完成させて新しいグループを開始
                if len(current_group) > 1:
                    grouped_results.append(merge_text_group(current_group))
                else:
                    grouped_results.extend(current_group)
                current_group = [result]
    
    # 最後のグループを処理
    if current_group:
        if len(current_group) > 1:
            grouped_results.append(merge_text_group(current_group))
        else:
            grouped_results.extend(current_group)
    
    return grouped_results

def merge_text_group(text_group):
    """テキストグループを一つの結果にマージ（改良版）"""
    if not text_group:
        return None
    
    if len(text_group) == 1:
        return text_group[0]
    
    # X座標でソートしてテキストを正しい順序で結合
    sorted_group = sorted(text_group, key=lambda x: x['bbox']['x'])
    
    # テキストを結合（重なりがある場合は適切に処理）
    combined_texts = []
    prev_bbox = None
    
    for result in sorted_group:
        current_text = result['text'].strip()
        current_bbox = result['bbox']
        
        # 前のバウンディングボックスと重なりがある場合の処理
        if prev_bbox is not None:
            # X軸の重なりをチェック
            prev_right = prev_bbox['x'] + prev_bbox['width']
            curr_left = current_bbox['x']
            
            # 重なりがある場合はスペースを追加しない
            if curr_left <= prev_right + 5:  # 5ピクセル以内の隙間は重なりとみなす
                # 完全に重なっている場合は前のテキストを更新
                if curr_left <= prev_bbox['x'] + 10:
                    if len(current_text) > len(combined_texts[-1]):
                        combined_texts[-1] = current_text
                else:
                    combined_texts.append(current_text)
            else:
                # 隙間がある場合はスペースを追加
                combined_texts.append(current_text)
        else:
            combined_texts.append(current_text)
        
        prev_bbox = current_bbox
    
    # 重複を除去して結合
    final_text = ' '.join(filter(None, combined_texts))
    
    # バウンディングボックスを統合
    min_x = min(result['bbox']['x'] for result in text_group)
    min_y = min(result['bbox']['y'] for result in text_group)
    max_x = max(result['bbox']['x'] + result['bbox']['width'] for result in text_group)
    max_y = max(result['bbox']['y'] + result['bbox']['height'] for result in text_group)
    
    # 中心座標を計算（加重平均）
    total_weight = sum(result['confidence'] * result['bbox']['width'] for result in text_group)
    if total_weight > 0:
        center_x = int(sum(result['x'] * result['confidence'] * result['bbox']['width'] 
                          for result in text_group) / total_weight)
        center_y = int(sum(result['y'] * result['confidence'] * result['bbox']['height'] 
                          for result in text_group) / sum(result['confidence'] * result['bbox']['height'] 
                          for result in text_group))
    else:
        center_x = (min_x + max_x) // 2
        center_y = (min_y + max_y) // 2
    
    # 信頼度の加重平均を計算
    total_area = sum(result['bbox']['width'] * result['bbox']['height'] for result in text_group)
    if total_area > 0:
        avg_confidence = sum(result['confidence'] * result['bbox']['width'] * result['bbox']['height'] 
                           for result in text_group) / total_area
    else:
        avg_confidence = sum(result['confidence'] for result in text_group) / len(text_group)
    
    return {
        'text': final_text,
        'x': center_x,
        'y': center_y,
        'bbox': {
            'x': min_x,
            'y': min_y,
            'width': max_x - min_x,
            'height': max_y - min_y
        },
        'confidence': avg_confidence,
        'grouped_count': len(text_group)  # グループ化された文字数
    }

def find_text_positions(image, target_text, case_sensitive=False):
    """APIまたはTesseractを使用してテキストの位置を取得"""
    if not OCR_AVAILABLE:
        return []
    
    if OCR_METHOD == "API":
        try:
            # OCR APIを使用
            return ocr_api_client.find_text_positions_api(image, target_text, case_sensitive)
        except Exception as e:
            print(f"OCR API エラー: {e}")
            print("Tesseractにフォールバックします")
            # APIが失敗した場合はTesseractにフォールバック
            return find_text_positions_tesseract(image, target_text, case_sensitive)
    else:
        # Tesseractを使用
        return find_text_positions_tesseract(image, target_text, case_sensitive)

def find_text_positions_tesseract(image, target_text, case_sensitive=False):
    """Tesseractを使用してテキストの位置を取得（グルーピング機能付き）"""
    # Tesseractで全てのテキストと位置情報を取得
    all_results = process_image_with_tesseract(image)
    if not all_results:
        return []
    
    # 近接する文字をグルーピング
    grouped_results = group_nearby_text(all_results)
    
    # 大文字小文字の処理
    search_text = target_text if case_sensitive else target_text.lower()
    
    # マッチするテキストを検索
    matches = []
    
    # 1. まず元の結果で完全一致・部分一致を検索
    for result in grouped_results:
        found_text = result['text'] if case_sensitive else result['text'].lower()
        
        # 部分マッチまたは完全マッチをチェック
        if search_text in found_text:
            match_result = result.copy()
            match_result['matched_text'] = target_text
            match_result['match_type'] = 'direct'
            matches.append(match_result)
    
    # 2. 直接マッチしなかった場合、部分一致からグルーピングを試行
    if not matches:
        partial_matches = []
        for result in grouped_results:
            found_text = result['text'] if case_sensitive else result['text'].lower()
            
            # 部分一致をチェック
            if any(char in found_text for char in search_text) or any(char in search_text for char in found_text):
                partial_matches.append(result)
        
        # 部分一致した結果を再グルーピングして検索
        if partial_matches:
            # より緩い条件でグルーピング
            regrouped = group_nearby_text(partial_matches, y_tolerance=15, x_tolerance=80)
            
            for result in regrouped:
                found_text = result['text'] if case_sensitive else result['text'].lower()
                
                # 再グルーピング後の一致チェック
                if search_text in found_text:
                    match_result = result.copy()
                    match_result['matched_text'] = target_text
                    match_result['match_type'] = 'grouped'
                    matches.append(match_result)
    
    # 3. より高度なファジーマッチング（文字の順序が保たれている場合）
    if not matches:
        for result in grouped_results:
            found_text = result['text'] if case_sensitive else result['text'].lower()
            
            # 文字の順序を保った部分マッチング
            if is_subsequence(search_text, found_text):
                match_result = result.copy()
                match_result['matched_text'] = target_text
                match_result['match_type'] = 'subsequence'
                matches.append(match_result)
    
    return matches

def is_subsequence(target, text):
    """ターゲット文字列がテキスト内で順序を保って含まれているかチェック"""
    target_idx = 0
    for char in text:
        if target_idx < len(target) and char == target[target_idx]:
            target_idx += 1
    return target_idx == len(target)

def find_image_in_screen(template_image, screenshot, threshold=0.8, method=cv2.TM_CCOEFF_NORMED):
    """画面キャプチャ内でテンプレート画像を検索"""
    if not OPENCV_AVAILABLE:
        return []
    
    try:
        # PIL ImageをOpenCV形式に変換
        template_cv = cv2.cvtColor(np.array(template_image), cv2.COLOR_RGB2BGR)
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        
        # グレースケール変換
        template_gray = cv2.cvtColor(template_cv, cv2.COLOR_BGR2GRAY)
        screenshot_gray = cv2.cvtColor(screenshot_cv, cv2.COLOR_BGR2GRAY)
        
        # テンプレートマッチング
        result = cv2.matchTemplate(screenshot_gray, template_gray, method)
        
        # 閾値以上の一致箇所を検索
        locations = np.where(result >= threshold)
        matches = []
        
        # テンプレートのサイズ取得
        template_h, template_w = template_gray.shape
        
        # マッチした場所の情報を収集
        for pt_y, pt_x in zip(locations[0], locations[1]):
            confidence = result[pt_y, pt_x]
            center_x = pt_x + template_w // 2
            center_y = pt_y + template_h // 2
            
            matches.append({
                'center_x': int(center_x),
                'center_y': int(center_y),
                'top_left_x': int(pt_x),
                'top_left_y': int(pt_y),
                'width': int(template_w),
                'height': int(template_h),
                'confidence': float(confidence),
                'method': 'template_matching'
            })
        
        # 信頼度でソート（降順）
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        
        # 重複する検出結果を除去
        filtered_matches = []
        for match in matches:
            is_duplicate = False
            for existing in filtered_matches:
                # 中心点の距離を計算
                distance = ((match['center_x'] - existing['center_x'])**2 + 
                           (match['center_y'] - existing['center_y'])**2)**0.5
                
                # 距離が小さい場合は重複とみなす
                if distance < min(template_w, template_h) * 0.5:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                filtered_matches.append(match)
        
        return filtered_matches
        
    except Exception as e:
        print(f"画像マッチングエラー: {e}")
        return []

def find_image_multi_scale(template_image, screenshot, threshold=0.8, scale_range=(0.5, 2.0), scale_steps=10):
    """マルチスケール画像マッチング（異なるサイズでの検索）"""
    if not OPENCV_AVAILABLE:
        return []
    
    try:
        # PIL ImageをOpenCV形式に変換
        template_cv = cv2.cvtColor(np.array(template_image), cv2.COLOR_RGB2BGR)
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        
        # グレースケール変換
        template_gray = cv2.cvtColor(template_cv, cv2.COLOR_BGR2GRAY)
        screenshot_gray = cv2.cvtColor(screenshot_cv, cv2.COLOR_BGR2GRAY)
        
        all_matches = []
        
        # 複数のスケールで検索
        for scale in np.linspace(scale_range[0], scale_range[1], scale_steps):
            # テンプレートをリサイズ
            template_h, template_w = template_gray.shape
            new_w = int(template_w * scale)
            new_h = int(template_h * scale)
            
            if new_w < 10 or new_h < 10:  # 小さすぎる場合はスキップ
                continue
                
            resized_template = cv2.resize(template_gray, (new_w, new_h))
            
            # テンプレートマッチング
            result = cv2.matchTemplate(screenshot_gray, resized_template, cv2.TM_CCOEFF_NORMED)
            
            # 閾値以上の一致箇所を検索
            locations = np.where(result >= threshold)
            
            # マッチした場所の情報を収集
            for pt_y, pt_x in zip(locations[0], locations[1]):
                confidence = result[pt_y, pt_x]
                center_x = pt_x + new_w // 2
                center_y = pt_y + new_h // 2
                
                all_matches.append({
                    'center_x': int(center_x),
                    'center_y': int(center_y),
                    'top_left_x': int(pt_x),
                    'top_left_y': int(pt_y),
                    'width': int(new_w),
                    'height': int(new_h),
                    'confidence': float(confidence),
                    'scale': float(scale),
                    'method': 'multi_scale_template_matching'
                })
        
        # 信頼度でソート（降順）
        all_matches.sort(key=lambda x: x['confidence'], reverse=True)
        
        # 重複する検出結果を除去
        filtered_matches = []
        for match in all_matches:
            is_duplicate = False
            for existing in filtered_matches:
                # 中心点の距離を計算
                distance = ((match['center_x'] - existing['center_x'])**2 + 
                           (match['center_y'] - existing['center_y'])**2)**0.5
                
                # 距離が小さい場合は重複とみなす
                overlap_threshold = min(match['width'], match['height'], 
                                      existing['width'], existing['height']) * 0.3
                if distance < overlap_threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                filtered_matches.append(match)
        
        return filtered_matches[:10]  # 上位10件まで返す
        
    except Exception as e:
        print(f"マルチスケール画像マッチングエラー: {e}")
        return []

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
            '/usr/share/fonts/truetype/noto/NotoSansJP-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc',
            
            # 追加の日本語フォント検索パス
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/TTF/DejaVuSans.ttf',
            
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
        
        # ダイナミックフォント検索も追加
        import glob
        font_dirs = ['/usr/share/fonts/**/*.ttf', '/usr/share/fonts/**/*.ttc', '/usr/share/fonts/**/*.otf']
        for pattern in font_dirs:
            for font_file in glob.glob(pattern, recursive=True):
                if any(keyword in font_file.lower() for keyword in ['noto', 'cjk', 'jp', 'japan', 'gothic', 'sans']):
                    if font_file not in japanese_font_paths:
                        japanese_font_paths.append(font_file)
        
        for font_path in japanese_font_paths:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, 16)  # フォントサイズを少し大きく
                    print(f"フォント使用: {font_path}")
                    return font, font_path
                except Exception as e:
                    continue
        
        # フォントが見つからない場合の対策
        try:
            font = ImageFont.load_default()
            print("デフォルトフォントを使用（日本語表示に制限があります）")
            return font, "default"
        except:
            print("フォント読み込みエラー")
            return None, None
    
    font, font_path = find_japanese_font()
    
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
        
        # 信頼度とテキストのラベルを作成（グルーピング情報を含む）
        label = f"{text} ({confidence:.1f}%)"
        if 'grouped_count' in result and result['grouped_count'] > 1:
            label += f" [G{result['grouped_count']}]"
        
        # フォントが利用可能な場合のみラベルを描画
        if font:
            # 日本語テキストの表示を試行
            display_label = label
            text_rendered = False
            
            # 日本語テキストの描画を試行
            try:
                # まず日本語テキストでのサイズ計算を試行
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
                        label_width = len(label) * 10
                        label_height = 18
                
                label_x = x
                label_y = max(0, y - label_height - 2)
                
                # ラベル背景を描画
                draw.rectangle([label_x, label_y, label_x + label_width, label_y + label_height], 
                              fill=box_color)
                
                # 日本語テキストの描画を試行
                draw.text((label_x, label_y), display_label, fill=text_color, font=font)
                text_rendered = True
                
            except Exception as e:
                print(f"日本語テキスト描画エラー: {e}, フォント: {font_path}")
                
                # フォールバック: 簡略化したラベル
                try:
                    # 日本語文字を含む場合は、信頼度のみ表示
                    has_japanese = any(ord(char) > 127 for char in text)
                    if has_japanese:
                        fallback_label = f"[日本語] ({confidence:.1f}%)"
                        if 'grouped_count' in result and result['grouped_count'] > 1:
                            fallback_label += f" [G{result['grouped_count']}]"
                    else:
                        # ASCII文字のみの場合はそのまま表示
                        fallback_label = f"{text} ({confidence:.1f}%)"
                        if 'grouped_count' in result and result['grouped_count'] > 1:
                            fallback_label += f" [G{result['grouped_count']}]"
                    
                    # フォールバックラベルのサイズ計算
                    try:
                        bbox_text = draw.textbbox((0, 0), fallback_label, font=font)
                        label_width = bbox_text[2] - bbox_text[0]
                        label_height = bbox_text[3] - bbox_text[1]
                    except:
                        label_width = len(fallback_label) * 8
                        label_height = 16
                    
                    label_x = x
                    label_y = max(0, y - label_height - 2)
                    
                    # ラベル背景を描画
                    draw.rectangle([label_x, label_y, label_x + label_width, label_y + label_height], 
                                  fill=box_color)
                    
                    # フォールバックテキストを描画
                    draw.text((label_x, label_y), fallback_label, fill=text_color, font=font)
                    text_rendered = True
                    
                except Exception as e2:
                    print(f"フォールバック描画エラー: {e2}")
                    text_rendered = False
        
        if not text_rendered:
            # フォントが利用できない場合は座標のみ表示
            coord_label = f"({x},{y})"
            try:
                draw.text((x, max(0, y - 15)), coord_label, fill=text_color)
            except:
                pass  # 描画エラーの場合は無視
        
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

@app.route('/mouse/scroll', methods=['POST'])
def scroll_mouse():
    """マウスホイールスクロール"""
    if not GUI_AVAILABLE:
        return jsonify({'error': 'GUI functionality not available', 'status': 'error'}), 503
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required', 'status': 'error'}), 400
        
        # パラメータ取得
        clicks = data.get('clicks', 1)  # スクロール量（正数で上/右、負数で下/左）
        x = data.get('x')  # スクロール位置のX座標（オプション）
        y = data.get('y')  # スクロール位置のY座標（オプション）
        direction = data.get('direction', 'vertical')  # スクロール方向
        
        # パラメータ検証
        if direction not in ['vertical', 'horizontal']:
            return jsonify({'error': 'Invalid direction. Use vertical or horizontal', 'status': 'error'}), 400
        
        try:
            clicks = int(clicks)
        except (ValueError, TypeError):
            return jsonify({'error': 'clicks must be an integer', 'status': 'error'}), 400
        
        # 指定座標にマウスを移動（オプション）
        if x is not None and y is not None:
            try:
                x = int(x)
                y = int(y)
                pyautogui.moveTo(x, y)
            except (ValueError, TypeError):
                return jsonify({'error': 'x and y coordinates must be integers', 'status': 'error'}), 400
        
        # スクロール実行
        if direction == 'vertical':
            pyautogui.scroll(clicks)
            action = f"垂直スクロール: {'上' if clicks > 0 else '下'}方向に{abs(clicks)}クリック"
        else:
            # 水平スクロール（pyautoguiでは hscroll を使用）
            pyautogui.hscroll(clicks)
            action = f"水平スクロール: {'右' if clicks > 0 else '左'}方向に{abs(clicks)}クリック"
        
        response_data = {
            'status': 'success',
            'action': action,
            'clicks': clicks,
            'direction': direction
        }
        
        if x is not None and y is not None:
            response_data['position'] = {'x': x, 'y': y}
            
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/mouse/drag', methods=['POST'])
def drag_mouse():
    """マウスドラッグ操作"""
    if not GUI_AVAILABLE:
        return jsonify({'error': 'GUI functionality not available', 'status': 'error'}), 503
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required', 'status': 'error'}), 400
        
        # 必須パラメータ
        if 'to_x' not in data or 'to_y' not in data:
            return jsonify({'error': 'to_x and to_y coordinates required', 'status': 'error'}), 400
        
        # パラメータ取得
        from_x = data.get('from_x')  # ドラッグ開始X座標（オプション、現在位置から）
        from_y = data.get('from_y')  # ドラッグ開始Y座標（オプション、現在位置から）
        to_x = int(data['to_x'])     # ドラッグ終了X座標（必須）
        to_y = int(data['to_y'])     # ドラッグ終了Y座標（必須）
        duration = float(data.get('duration', 1.0))  # ドラッグにかける時間（秒）
        button = data.get('button', 'left')  # ドラッグボタン
        
        # パラメータ検証
        if button not in ['left', 'right', 'middle']:
            return jsonify({'error': 'Invalid button. Use left, right, or middle', 'status': 'error'}), 400
        
        # ドラッグ実行
        if from_x is not None and from_y is not None:
            # 指定座標からドラッグ
            from_x = int(from_x)
            from_y = int(from_y)
            pyautogui.drag(to_x - from_x, to_y - from_y, duration=duration, button=button)
            action = f"{button}ボタンで ({from_x}, {from_y}) から ({to_x}, {to_y}) にドラッグ"
        else:
            # 現在位置からドラッグ
            current_x, current_y = pyautogui.position()
            pyautogui.drag(to_x - current_x, to_y - current_y, duration=duration, button=button)
            action = f"{button}ボタンで ({current_x}, {current_y}) から ({to_x}, {to_y}) にドラッグ"
        
        return jsonify({
            'status': 'success',
            'action': action,
            'from_position': {'x': from_x or current_x, 'y': from_y or current_y},
            'to_position': {'x': to_x, 'y': to_y},
            'duration': duration,
            'button': button
        })
        
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

@app.route('/screen/capture_at_cursor', methods=['GET'])
def capture_screen_at_cursor():
    """現在のマウスカーソルを中心に指定サイズで画面をキャプチャ"""
    if not GUI_AVAILABLE:
        return jsonify({'error': 'GUI functionality not available', 'status': 'error'}), 503
    try:
        # クエリパラメータから幅・高さを取得
        if 'width' not in request.args or 'height' not in request.args:
            return jsonify({'error': 'width and height query parameters required', 'status': 'error'}), 400

        try:
            req_width = int(float(request.args.get('width')))
            req_height = int(float(request.args.get('height')))
        except ValueError:
            return jsonify({'error': 'width and height must be numbers', 'status': 'error'}), 400

        if req_width <= 0 or req_height <= 0:
            return jsonify({'error': 'width and height must be positive', 'status': 'error'}), 400

        # カーソル位置を取得
        cursor_x, cursor_y = pyautogui.position()

        # まずフルスクリーンを取得して境界を把握（マルチモニタでも安全）
        full_img = ImageGrab.grab()
        screen_w, screen_h = full_img.size

        # 要求サイズから左上座標を計算（カーソル中心）
        half_w = req_width // 2
        half_h = req_height // 2
        left = cursor_x - half_w
        top = cursor_y - half_h
        right = left + req_width
        bottom = top + req_height

        # 画面内に収まるようクリッピング
        left = max(0, left)
        top = max(0, top)
        right = min(screen_w, right)
        bottom = min(screen_h, bottom)

        # クリッピング後の実サイズ（端にかかった場合に小さくなる）
        cap_width = max(0, right - left)
        cap_height = max(0, bottom - top)

        if cap_width == 0 or cap_height == 0:
            return jsonify({'error': 'Capture region is out of screen bounds', 'status': 'error'}), 400

        # 切り出し
        cropped = full_img.crop((left, top, right, bottom))

        # Base64にエンコード
        img_buffer = io.BytesIO()
        cropped.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')

        return jsonify({
            'status': 'success',
            'image': img_base64,
            'format': 'PNG',
            'size': {'width': cap_width, 'height': cap_height},
            'cursor': {'x': cursor_x, 'y': cursor_y},
            'region': {
                'left': int(left),
                'top': int(top),
                'right': int(right),
                'bottom': int(bottom),
                'width': int(cap_width),
                'height': int(cap_height)
            },
            'requested': {'width': req_width, 'height': req_height}
        })
    
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500

def get_region_coordinates(screenshot, region):
    """指定された範囲の座標を返す"""
    width, height = screenshot.size
    
    region_map = {
        'top_half': (0, 0, width, height // 2),
        'bottom_half': (0, height // 2, width, height),
        'left': (0, 0, width // 2, height),
        'right': (width // 2, 0, width, height),
        'top_left': (0, 0, width // 2, height // 2),
        'top_right': (width // 2, 0, width, height // 2),
        'bottom_left': (0, height // 2, width // 2, height),
        'bottom_right': (width // 2, height // 2, width, height)
    }
    
    return region_map.get(region)

def adjust_coordinates_for_region(matches, region_coords):
    """範囲指定された座標を全画面座標に調整"""
    if not region_coords:
        return matches
    
    x_offset, y_offset = region_coords[0], region_coords[1]
    
    adjusted_matches = []
    for match in matches:
        adjusted_match = match.copy()
        adjusted_match['x'] += x_offset
        adjusted_match['y'] += y_offset
        
        # バウンディングボックスも調整
        if 'bbox' in adjusted_match:
            bbox = adjusted_match['bbox'].copy()
            bbox['x'] += x_offset
            bbox['y'] += y_offset
            adjusted_match['bbox'] = bbox
        
        adjusted_matches.append(adjusted_match)
    
    return adjusted_matches

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
        min_confidence = float(data.get('min_confidence', 10.0))
        region = data.get('region')  # 新しいパラメータ
        
        # スクリーンキャプチャ
        screenshot = ImageGrab.grab()
        
        # 範囲指定がある場合は画像を切り取り
        region_coords = None
        search_screenshot = screenshot
        
        if region:
            # サポートされている範囲の確認
            supported_regions = ['top_half', 'bottom_half', 'left', 'right', 
                               'top_left', 'top_right', 'bottom_left', 'bottom_right']
            
            if region not in supported_regions:
                return jsonify({
                    'error': f'Unsupported region: {region}. Supported regions: {supported_regions}',
                    'status': 'error'
                }), 400
            
            region_coords = get_region_coordinates(screenshot, region)
            if region_coords:
                search_screenshot = screenshot.crop(region_coords)
        
        # OCR（API or Tesseract）でテキストの位置情報を取得
        matches = find_text_positions(search_screenshot, target_text, case_sensitive)
        
        # 範囲指定された場合は座標を全画面座標に調整
        if region_coords:
            matches = adjust_coordinates_for_region(matches, region_coords)
        
        # 信頼度でフィルタリング
        matches = [match for match in matches if match['confidence'] >= min_confidence/100.0]
        
        response_data = {
            'status': 'success',
            'matches': matches,
            'total_found': len(matches)
        }
        
        # 範囲指定の情報も含める
        if region:
            response_data['search_region'] = {
                'region': region,
                'coordinates': region_coords,
                'size': {
                    'width': region_coords[2] - region_coords[0],
                    'height': region_coords[3] - region_coords[1]
                }
            }
        
        return jsonify(response_data)
        
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
        mode = data.get('mode', 'type')  # 'type' or 'paste'
        paste_delay = float(data.get('paste_delay', 0.1))
        preserve_clipboard = bool(data.get('preserve_clipboard', True))
        press_enter = bool(data.get('press_enter', False))
        enter_count = int(data.get('enter_count', 1))
        enter_interval = float(data.get('enter_interval', 0.05))
        
        # 指定座標がある場合はクリック
        if x is not None and y is not None:
            pyautogui.click(x, y)
        
        # 入力モード切り替え
        result = {'status': 'success', 'text': text}
        mode_used = mode
        if mode == 'paste':
            if not CLIPBOARD_AVAILABLE:
                return jsonify({'error': 'Clipboard functionality not available', 'status': 'error'}), 503

            original_clip = None
            original_ok = False
            try:
                if preserve_clipboard:
                    try:
                        original_clip = pyperclip.paste()
                        original_ok = True
                    except Exception:
                        original_ok = False

                # クリップボードへコピー
                try:
                    pyperclip.copy(text)
                except Exception as ce:
                    return jsonify({
                        'error': 'Clipboard copy failed',
                        'details': str(ce),
                        'status': 'error',
                        'hint': 'Linuxでは xclip または xsel の導入が必要です'
                    }), 503

                # 少し待機してから貼り付け（アプリ側の反映待ち）
                time.sleep(paste_delay)

                # OSごとのショートカットで貼り付け
                import platform
                if platform.system() == 'Darwin':
                    pyautogui.hotkey('command', 'v')
                else:
                    pyautogui.hotkey('ctrl', 'v')
            finally:
                if preserve_clipboard and original_ok:
                    try:
                        pyperclip.copy(original_clip if original_clip is not None else '')
                    except Exception:
                        pass
            result['mode'] = 'paste'
        else:
            # 直接タイプ入力
            pyautogui.typewrite(text, interval=interval)
            result['mode'] = 'type'

        # オプション: 入力後にEnterを押下
        if press_enter:
            # 少し間を置いてからEnterを押す
            time.sleep(max(0.0, enter_interval))
            for _ in range(max(1, enter_count)):
                pyautogui.press('enter')
                if enter_interval > 0:
                    time.sleep(enter_interval)
            result['pressed_enter'] = True
            result['enter_count'] = max(1, enter_count)
        else:
            result['pressed_enter'] = False
            result['enter_count'] = 0

        return jsonify(result)
        
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
        min_confidence = float(data.get('min_confidence', 10.0))
        button = data.get('button', 'left')
        click_all = data.get('click_all', False)
        
        if button not in ['left', 'right', 'middle']:
            return jsonify({'error': 'Invalid button. Use left, right, or middle', 'status': 'error'}), 400
        
        # スクリーンキャプチャ
        screenshot = ImageGrab.grab()
        
        # OCR（API or Tesseract）でテキストの位置情報を取得
        matches = find_text_positions(screenshot, target_text, case_sensitive)
        
        # 信頼度でフィルタリング
        matches = [match for match in matches if match['confidence'] >= min_confidence/100.0]
        
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
        
        # OCR（API or Tesseract）でテキストを検出
        if OCR_METHOD == "API":
            try:
                ocr_results = ocr_api_client.process_image_ocr(screenshot)
            except Exception as e:
                print(f"OCR API エラー: {e}")
                print("Tesseractにフォールバックします")
                ocr_results = process_image_with_tesseract(screenshot)
        else:
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

@app.route('/text/ocr', methods=['POST'])
def extract_text_only():
    """スクリーンキャプチャしてOCRテキストのみを返す（画像は含まない）"""
    if not GUI_AVAILABLE:
        return jsonify({'error': 'GUI functionality not available', 'status': 'error'}), 503
    if not OCR_AVAILABLE:
        return jsonify({'error': 'OCR functionality not available', 'status': 'error'}), 503
    
    try:
        data = request.get_json() or {}
        min_confidence = float(data.get('min_confidence', 30.0))  # 最小信頼度
        debug = data.get('debug', False)  # デバッグ情報を含めるか
        
        # スクリーンキャプチャ
        screenshot = ImageGrab.grab()
        
        # デバッグ情報
        debug_info = {}
        if debug:
            debug_info['screenshot_size'] = {'width': screenshot.width, 'height': screenshot.height}
            debug_info['ocr_method'] = OCR_METHOD
            debug_info['ocr_api_available'] = OCR_AVAILABLE
        
        # OCR（API or Tesseract）でテキストを検出
        ocr_results = []
        ocr_error = None
        
        if OCR_METHOD == "API":
            try:
                # OCR APIサーバーが利用可能かチェック
                if hasattr(ocr_api_client, 'is_server_available') and not ocr_api_client.is_server_available():
                    raise Exception("OCR APIサーバーが利用できません")
                
                ocr_results = ocr_api_client.process_image_ocr(screenshot)
                if debug:
                    debug_info['ocr_method_used'] = 'API'
            except Exception as e:
                ocr_error = str(e)
                print(f"OCR API エラー: {e}")
                print("Tesseractにフォールバックします")
                try:
                    ocr_results = process_image_with_tesseract(screenshot)
                    if debug:
                        debug_info['ocr_method_used'] = 'Tesseract (fallback)'
                        debug_info['api_error'] = ocr_error
                except Exception as tesseract_error:
                    if debug:
                        debug_info['tesseract_error'] = str(tesseract_error)
                    raise Exception(f"OCR API失敗: {ocr_error}, Tesseract失敗: {tesseract_error}")
        else:
            ocr_results = process_image_with_tesseract(screenshot)
            if debug:
                debug_info['ocr_method_used'] = 'Tesseract'
        
        if debug:
            debug_info['raw_ocr_count'] = len(ocr_results)
            debug_info['raw_ocr_sample'] = ocr_results[:3] if ocr_results else []
        
        # 信頼度でフィルタリング
        #print(ocr_results)
        filtered_results = [result for result in ocr_results if result['confidence'] >= min_confidence/100.0]
        #print(filtered_results)
        
        response_data = {
            'status': 'success',
            'ocr_results': filtered_results,
            'total_detected': len(filtered_results),
            'parameters': {
                'min_confidence': min_confidence
            }
        }
        
        if debug:
            response_data['debug'] = debug_info
            
        print(response_data)
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/image/search', methods=['POST'])
def search_image():
    """画面キャプチャ内で指定された画像を検索"""
    if not GUI_AVAILABLE:
        return jsonify({'error': 'GUI functionality not available', 'status': 'error'}), 503
    if not OPENCV_AVAILABLE:
        return jsonify({'error': 'OpenCV functionality not available', 'status': 'error'}), 503
    
    try:
        # リクエストからパラメータを取得
        threshold = float(request.form.get('threshold', 0.8))
        multi_scale = request.form.get('multi_scale', 'false').lower() == 'true'
        scale_range_min = float(request.form.get('scale_range_min', 0.5))
        scale_range_max = float(request.form.get('scale_range_max', 2.0))
        scale_steps = int(request.form.get('scale_steps', 10))
        
        # アップロードされた画像ファイルを取得
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided', 'status': 'error'}), 400
        
        image_file = request.files['image']
        if image_file.filename == '':
            return jsonify({'error': 'No image file selected', 'status': 'error'}), 400
        
        # 画像ファイルを読み込み
        try:
            template_image = Image.open(image_file.stream)
            # RGBAをRGBに変換（必要に応じて）
            if template_image.mode == 'RGBA':
                template_image = template_image.convert('RGB')
        except Exception as e:
            return jsonify({'error': f'Invalid image file: {str(e)}', 'status': 'error'}), 400
        
        # スクリーンキャプチャ
        screenshot = ImageGrab.grab()
        
        # 画像マッチングを実行
        if multi_scale:
            matches = find_image_multi_scale(
                template_image, 
                screenshot, 
                threshold=threshold,
                scale_range=(scale_range_min, scale_range_max),
                scale_steps=scale_steps
            )
        else:
            matches = find_image_in_screen(template_image, screenshot, threshold=threshold)
        
        return jsonify({
            'status': 'success',
            'matches': matches,
            'total_found': len(matches),
            'parameters': {
                'threshold': threshold,
                'multi_scale': multi_scale,
                'scale_range': [scale_range_min, scale_range_max] if multi_scale else None,
                'scale_steps': scale_steps if multi_scale else None
            },
            'template_info': {
                'width': template_image.width,
                'height': template_image.height,
                'mode': template_image.mode
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/image/find_and_click', methods=['POST'])
def find_and_click_image():
    """画面キャプチャ内で指定された画像を検索してクリック"""
    if not GUI_AVAILABLE:
        return jsonify({'error': 'GUI functionality not available', 'status': 'error'}), 503
    if not OPENCV_AVAILABLE:
        return jsonify({'error': 'OpenCV functionality not available', 'status': 'error'}), 503
    
    try:
        # リクエストからパラメータを取得
        threshold = float(request.form.get('threshold', 0.8))
        multi_scale = request.form.get('multi_scale', 'false').lower() == 'true'
        scale_range_min = float(request.form.get('scale_range_min', 0.5))
        scale_range_max = float(request.form.get('scale_range_max', 2.0))
        scale_steps = int(request.form.get('scale_steps', 10))
        button = request.form.get('button', 'left')
        click_all = request.form.get('click_all', 'false').lower() == 'true'
        # クリック位置補正（中心からのオフセット）
        try:
            offset_x = int(float(request.form.get('offset_x', 0)))
            offset_y = int(float(request.form.get('offset_y', 0)))
        except ValueError:
            return jsonify({'error': 'offset_x and offset_y must be numbers', 'status': 'error'}), 400
        
        if button not in ['left', 'right', 'middle']:
            return jsonify({'error': 'Invalid button. Use left, right, or middle', 'status': 'error'}), 400
        
        # アップロードされた画像ファイルを取得
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided', 'status': 'error'}), 400
        
        image_file = request.files['image']
        if image_file.filename == '':
            return jsonify({'error': 'No image file selected', 'status': 'error'}), 400
        
        # 画像ファイルを読み込み
        try:
            template_image = Image.open(image_file.stream)
            if template_image.mode == 'RGBA':
                template_image = template_image.convert('RGB')
        except Exception as e:
            return jsonify({'error': f'Invalid image file: {str(e)}', 'status': 'error'}), 400
        
        # スクリーンキャプチャ
        screenshot = ImageGrab.grab()
        
        # 画像マッチングを実行
        if multi_scale:
            matches = find_image_multi_scale(
                template_image, 
                screenshot, 
                threshold=threshold,
                scale_range=(scale_range_min, scale_range_max),
                scale_steps=scale_steps
            )
        else:
            matches = find_image_in_screen(template_image, screenshot, threshold=threshold)
        
        if not matches:
            return jsonify({
                'status': 'not_found',
                'message': 'Image not found in screen capture',
                'matches': []
            })
        
        # Y軸の数値が低い順（画面上部から下部へ）にソート
        matches.sort(key=lambda x: x['center_y'])
        
        # クリック実行
        clicked_positions = []
        targets = matches if click_all else matches[:1]
        
        for match in targets:
            click_x = int(match['center_x']) + offset_x
            click_y = int(match['center_y']) + offset_y
            pyautogui.click(click_x, click_y, button=button)
            clicked_info = match.copy()
            clicked_info.update({
                'click_x': click_x,
                'click_y': click_y,
                'offset_x': offset_x,
                'offset_y': offset_y
            })
            clicked_positions.append(clicked_info)
        
        return jsonify({
            'status': 'success',
            'clicked': clicked_positions,
            'matches': matches,  # 全検索結果も含める
            'total_clicked': len(clicked_positions),
            'total_found': len(matches),
            'parameters': {
                'threshold': threshold,
                'multi_scale': multi_scale,
                'scale_range': [scale_range_min, scale_range_max] if multi_scale else None,
                'scale_steps': scale_steps if multi_scale else None,
                'button': button,
                'click_all': click_all,
                'offset_x': offset_x,
                'offset_y': offset_y
            },
            'template_info': {
                'width': template_image.width,
                'height': template_image.height,
                'mode': template_image.mode
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
        'ocr_available': OCR_AVAILABLE,
        'ocr_method': OCR_METHOD if OCR_AVAILABLE else None,
        'opencv_available': OPENCV_AVAILABLE,
        'clipboard_available': 'CLIPBOARD_AVAILABLE' in globals() and CLIPBOARD_AVAILABLE
    })

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Mouse API Server')
    parser.add_argument('--port', '-p', type=int, default=5000, help='Port to run the server on (default: 5000)')
    parser.add_argument('--host', type=str, default='::', help='Host to bind to (default: :: for IPv4/IPv6)')
    
    args = parser.parse_args()
    
    print(f"Starting Mouse API server on {args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
