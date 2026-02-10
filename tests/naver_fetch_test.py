"""
네이버 링크에서 논어 텍스트 추출 테스트 스크립트
"""
import requests
from bs4 import BeautifulSoup
import re

def fetch_naver_content(url):
    """네이버 메모/블로그 등에서 텍스트를 추출하는 예시 함수"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # 실제 환경에서는 페이지 구조에 따라 BeautifulSoup 파싱이 필요할 수 있습니다.
        # 여기서는 단순 텍스트 추출 예시를 보여줍니다.
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text(separator='
')
        
        print("--- 추출된 텍스트 ---")
        print(text)
        print("--------------------")
        
        return text
    except Exception as e:
        print(f"오류 발생: {e}")
        return None

if __name__ == "__main__":
    test_url = "https://naver.me/xUSIbn8s"
    fetch_naver_content(test_url)
