"""
한자 훈음(뜻과 소리) 라이브러리 연결 및 사용자 정의 사전 모듈 (캐싱 최적화 버전)
"""
import hanjadict
import unicodedata
import json
import os
import streamlit as st

@st.cache_data
def get_custom_dict():
    """custom_meanings.json 파일을 로드하고 캐싱합니다."""
    path = 'custom_meanings.json'
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_custom_meaning(char: str, meaning: str):
    """
    사용자 정의 사전에 새로운 훈음을 추가/수정하고 파일에 저장합니다.
    """
    if not char or not meaning:
        return

    path = 'custom_meanings.json'
    current_dict = {}
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                current_dict = json.load(f)
        except: pass
    
    current_dict[char] = meaning

    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(current_dict, f, ensure_ascii=False, indent=4)
        # 저장 후 캐시 초기화
        st.cache_data.clear()
    except Exception as e:
        print(f"사전 저장 실패: {e}")

@st.cache_resource
def _get_hanjadict_instance():
    """hanjadict 라이브러리 로드를 캐싱합니다."""
    return hanjadict

def get_hanja_meaning(char: str, preferred_sound: str = None) -> str:
    """
    한자의 훈음(뜻과 소리)을 반환합니다.
    """
    if not char or len(char) != 1:
        return ""
    
    # 1. 사용자 정의 사전 확인
    custom_dict = get_custom_dict()
    if char in custom_dict:
        return custom_dict[char]
    
    # 호환 한자 대응 (정규화)
    normalized_char = unicodedata.normalize('NFKC', char)
    if normalized_char in custom_dict:
        return custom_dict[normalized_char]
    
    # 2. hanjadict 조회
    hdict = _get_hanjadict_instance()
    result = hdict.lookup(normalized_char)
    
    if not result:
        result = hdict.lookup(char)
        
    if not result:
        return ""
        
    candidates = [c.strip() for c in result.split(',')]
    
    # 3. 선호하는 음(소리)이 있는 경우 매칭 시도
    if preferred_sound:
        for cand in candidates:
            parts = cand.split()
            if not parts: continue
            actual_sound = parts[-1]
            if actual_sound == preferred_sound: return cand
            if {actual_sound, preferred_sound} <= {"불", "부"}: return cand
            if {actual_sound, preferred_sound} <= {"락", "낙", "악", "요"}: return cand
            if {actual_sound, preferred_sound} <= {"륙", "육"}: return cand
            if {actual_sound, preferred_sound} <= {"례", "예"}: return cand
    
    return candidates[0]