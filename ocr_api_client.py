#!/usr/bin/env python3
"""
EasyOCR API クライアント
OCR_API_USAGE_GUIDE.mdで定義されたAPIを使用してOCR処理を行う
"""

import requests
import time
import tempfile
import os
from typing import List, Dict, Optional, Tuple
from PIL import Image


class EasyOCRClient:
    """EasyOCR APIのクライアントクラス"""
    
    def __init__(self, base_url: str = "http://localhost:3000"):
        """
        クライアントを初期化
        
        Args:
            base_url: OCR APIサーバーのベースURL
        """
        self.base_url = base_url.rstrip('/')
        
    def upload_file(self, file_path: str, email: Optional[str] = None) -> Dict:
        """
        ファイルをアップロード
        
        Args:
            file_path: アップロードするファイルのパス
            email: 通知用メールアドレス（オプション）
            
        Returns:
            アップロード結果のレスポンス
        """
        url = f"{self.base_url}/upload"
        files = {"file": open(file_path, "rb")}
        data = {"email": email} if email else {}
        
        try:
            response = requests.post(url, files=files, data=data)
            response.raise_for_status()
            return response.json()
        finally:
            files["file"].close()
    
    def upload_image(self, image: Image.Image, email: Optional[str] = None) -> Dict:
        """
        PIL Imageオブジェクトをアップロード
        
        Args:
            image: PIL Imageオブジェクト
            email: 通知用メールアドレス（オプション）
            
        Returns:
            アップロード結果のレスポンス
        """
        # 一時ファイルに保存してアップロード
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            image.save(temp_file.name, 'PNG')
            temp_path = temp_file.name
        
        try:
            return self.upload_file(temp_path, email)
        finally:
            os.unlink(temp_path)
    
    def upload_base64_image(self, base64_data: str, email: Optional[str] = None) -> Dict:
        """
        Base64エンコードされた画像データをアップロード
        
        Args:
            base64_data: Base64エンコードされた画像データ
            email: 通知用メールアドレス（オプション）
            
        Returns:
            アップロード結果のレスポンス
        """
        import base64
        import io
        
        # Base64データを画像に変換
        image_data = base64.b64decode(base64_data)
        image = Image.open(io.BytesIO(image_data))
        
        # PIL Imageとして処理
        return self.upload_image(image, email)
    
    def check_status(self, filename: str) -> Dict:
        """
        処理状況を確認
        
        Args:
            filename: アップロード時に返されたunique_filename
            
        Returns:
            処理状況のレスポンス
        """
        url = f"{self.base_url}/status/{filename}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    
    def wait_for_completion(self, filename: str, max_wait: int = 300, check_interval: int = 5) -> bool:
        """
        処理完了まで待機
        
        Args:
            filename: アップロード時に返されたunique_filename
            max_wait: 最大待機時間（秒）
            check_interval: 状況確認間隔（秒）
            
        Returns:
            処理が完了した場合True、タイムアウトした場合False
            
        Raises:
            Exception: ファイルが見つからない場合
        """
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status = self.check_status(filename)
            
            if status['status'] == 'completed':
                return True
            elif status['status'] == 'not_found':
                raise Exception("ファイルが見つかりません")
            
            time.sleep(check_interval)
        
        return False  # タイムアウト
    
    def get_results(self, filename: str, result_type: str = "both") -> Dict:
        """
        結果を取得
        
        Args:
            filename: アップロード時に返されたunique_filename
            result_type: 取得する結果の種類 ("both", "image", "text")
            
        Returns:
            処理結果のレスポンス
        """
        url = f"{self.base_url}/result/{filename}"
        params = {"result_type": result_type}
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def download_image(self, image_filename: str, save_path: str) -> None:
        """
        処理済み画像をダウンロード
        
        Args:
            image_filename: /resultレスポンスのprocessed_image値
            save_path: 保存先パス
        """
        url = f"{self.base_url}/download/image/{image_filename}"
        response = requests.get(url)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
    
    def download_csv(self, csv_filename: str, save_path: str) -> None:
        """
        CSVファイルをダウンロード
        
        Args:
            csv_filename: /resultレスポンスのresult_csv値
            save_path: 保存先パス
        """
        url = f"{self.base_url}/download/csv/{csv_filename}"
        response = requests.get(url)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
    
    def process_image_ocr(self, image: Image.Image, email: Optional[str] = None) -> List[Dict]:
        """
        PIL ImageオブジェクトからOCR結果を取得（完全なワークフロー）
        
        Args:
            image: PIL Imageオブジェクト
            email: 通知用メールアドレス（オプション）
            
        Returns:
            OCR結果のリスト。各要素は以下の形式:
            {
                'text': str,           # 検出されたテキスト
                'confidence': float,   # 信頼度 (0-1)
                'bbox': str,          # バウンディングボックス "x,y,width,height"
                'x': int,             # 中心X座標
                'y': int              # 中心Y座標
            }
        """
        # 1. ファイルアップロード
        upload_result = self.upload_image(image, email)
        filename = upload_result["unique_filename"]
        
        # 2. 処理完了まで待機
        if not self.wait_for_completion(filename):
            raise TimeoutError("処理が時間内に完了しませんでした")
        
        # 3. 結果情報を取得してCSVファイル名を確認
        result_info = self.get_results(filename, "both")
        csv_filename = result_info.get('result_csv')
        if not csv_filename:
            raise Exception("CSVファイル名が取得できませんでした")
        
        # 4. CSVファイルをダウンロードして解析
        url = f"{self.base_url}/download/csv/{csv_filename}"
        #print(url)
        csv_response = requests.get(url)
        csv_response.raise_for_status()
        
        import csv
        import io
        csv_content = csv_response.text
        #print(csv_content)
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        
        # 5. CSV結果をmouse_api.pyの形式に変換
        ocr_results = []
        for row in csv_reader:
            try:
                # CSVから座標を取得
                x1 = float(row.get('x1', 0))
                y1 = float(row.get('y1', 0))
                x2 = float(row.get('x2', 0))
                y2 = float(row.get('y2', 0))
                confidence = float(row.get('confidence', 0))
                text = row.get('text', '').strip()
                
                # 空のテキストはスキップ
                if not text:
                    continue
                
                # 中心座標を計算
                center_x = int((x1 + x2) / 2)
                center_y = int((y1 + y2) / 2)
                
                # 幅と高さを計算
                width = int(x2 - x1)
                height = int(y2 - y1)
                
                ocr_results.append({
                    'text': text,
                    'x': center_x,
                    'y': center_y,
                    'bbox': {
                        'x': int(x1),
                        'y': int(y1),
                        'width': width,
                        'height': height
                    },
                    'confidence': confidence
                })
            except (ValueError, TypeError) as e:
                # 座標変換エラーの場合はスキップ
                continue
        
        #print(ocr_results)
        return ocr_results
    
    def find_text_positions_api(self, image: Image.Image, target_text: str, 
                               case_sensitive: bool = False) -> List[Dict]:
        """
        APIを使用してテキストの位置を検索
        
        Args:
            image: PIL Imageオブジェクト
            target_text: 検索するテキスト
            case_sensitive: 大文字小文字を区別するか
            
        Returns:
            マッチしたテキストの位置情報のリスト
        """
        # OCR結果を取得
        ocr_results = self.process_image_ocr(image)
        
        # 大文字小文字の処理
        search_text = target_text if case_sensitive else target_text.lower()
        
        # マッチするテキストを検索
        matches = []
        for result in ocr_results:
            #print(result)
            found_text = result['text'] if case_sensitive else result['text'].lower()
            #print(f"{search_text} : {found_text}")
            
            # 部分マッチまたは完全マッチをチェック
            if search_text in found_text:
            #if found_text in search_text:
                match_result = result.copy()
                match_result['matched_text'] = target_text
                match_result['match_type'] = 'api_direct'
                matches.append(match_result)
        
        #print(matches)
        return matches
    
    def process_base64_image_ocr(self, base64_data: str, email: Optional[str] = None) -> List[Dict]:
        """
        Base64画像データからOCR結果を取得（完全なワークフロー）
        
        Args:
            base64_data: Base64エンコードされた画像データ
            email: 通知用メールアドレス（オプション）
            
        Returns:
            OCR結果のリスト
        """
        import base64
        import io
        
        # Base64データを画像に変換
        image_data = base64.b64decode(base64_data)
        image = Image.open(io.BytesIO(image_data))
        
        # PIL Imageとして処理
        return self.process_image_ocr(image, email)
    
    def find_text_in_base64_image(self, base64_data: str, target_text: str, 
                                  case_sensitive: bool = False) -> List[Dict]:
        """
        Base64画像データからテキストを検索
        
        Args:
            base64_data: Base64エンコードされた画像データ
            target_text: 検索するテキスト
            case_sensitive: 大文字小文字を区別するか
            
        Returns:
            マッチしたテキストの位置情報のリスト
        """
        import base64
        import io
        
        # Base64データを画像に変換
        image_data = base64.b64decode(base64_data)
        image = Image.open(io.BytesIO(image_data))
        
        # PIL Imageとして処理
        return self.find_text_positions_api(image, target_text, case_sensitive)
    
    def is_server_available(self) -> bool:
        """
        OCR APIサーバーが利用可能かチェック
        
        Returns:
            サーバーが利用可能な場合True
        """
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            return response.status_code == 200
        except:
            return False