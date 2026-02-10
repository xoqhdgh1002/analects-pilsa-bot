"""
한자 훈음(뜻과 소리) 라이브러리 연결 및 사용자 정의 사전 모듈
"""
import hanjadict
import unicodedata
import json
import os

# 사용자 정의 사전 캐시
_CUSTOM_DICT = None

def _load_custom_dict():
    """custom_meanings.json 파일을 로드합니다."""
    global _CUSTOM_DICT
    if _CUSTOM_DICT is not None:
        return _CUSTOM_DICT
        
    path = 'custom_meanings.json'
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                _CUSTOM_DICT = json.load(f)
        except Exception:
            _CUSTOM_DICT = {}
    else:
        _CUSTOM_DICT = {}
    return _CUSTOM_DICT

def get_custom_dict():
    """사용자 정의 사전을 반환합니다."""
    return _load_custom_dict()

def save_custom_meaning(char: str, meaning: str):
    """
    사용자 정의 사전에 새로운 훈음을 추가/수정하고 파일에 저장합니다.
    """
    global _CUSTOM_DICT
    if not char or not meaning:
        return

    # 메모리 업데이트
    current_dict = _load_custom_dict()
    current_dict[char] = meaning
    _CUSTOM_DICT = current_dict

    # 파일 저장
    path = 'custom_meanings.json'
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(current_dict, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"사전 저장 실패: {e}")

def get_hanja_meaning(char: str, preferred_sound: str = None) -> str:

    """

    한자의 훈음(뜻과 소리)을 반환합니다.

    """

    if not char or len(char) != 1:

        return ""

    

    # 1. 사용자 정의 사전(Override) 확인

    custom_dict = _load_custom_dict()

    if char in custom_dict:

        return custom_dict[char]

    

    # 호환 한자 대응 (정규화 후 다시 확인)

    normalized_char = unicodedata.normalize('NFKC', char)

    if normalized_char in custom_dict:

        return custom_dict[normalized_char]

    

    # 2. hanjadict에서 훈음 조회

    result = hanjadict.lookup(normalized_char)

    

    if not result:

        result = hanjadict.lookup(char)

        

    if not result:

        return ""

        

    candidates = [c.strip() for c in result.split(',')]

    

    # 3. 선호하는 음(소리)이 있는 경우 매칭 시도

    if preferred_sound:

        for cand in candidates:

            parts = cand.split()

            if not parts:

                continue

            

            actual_sound = parts[-1]

            

            if actual_sound == preferred_sound:

                return cand

            

            # 음 변화 대응

            if {actual_sound, preferred_sound} <= {"불", "부"}:

                return cand

            if {actual_sound, preferred_sound} <= {"락", "낙", "악", "요"}:

                return cand

            if {actual_sound, preferred_sound} <= {"륙", "육"}:

                return cand

            if {actual_sound, preferred_sound} <= {"례", "예"}:

                return cand

    

    # 매칭되는 것이 없으면 첫 번째 반환

    return candidates[0]


