"""
한자 훈음(뜻과 소리) 라이브러리 연결 모듈
"""
import hanjadict
import unicodedata

def get_hanja_meaning(char: str, preferred_sound: str = None) -> str:
    """
    한자의 훈음(뜻과 소리)을 반환합니다.
    preferred_sound가 제공되면 해당 소리로 끝나는 훈음을 우선적으로 찾습니다.
    """
    if not char or len(char) != 1:
        return ""
    
    # 1. 한자 정규화 (호환용 한자를 표준 한자로 변환)
    # 예: U+F972 (不) -> U+4E0D (不)
    normalized_char = unicodedata.normalize('NFKC', char)
    
    # 2. hanjadict에서 훈음 조회
    result = hanjadict.lookup(normalized_char)
    
    # 정규화 후에도 없으면 원본으로 시도
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
            
            # 정확히 일치하거나, '불/부' 같은 특수 케이스 처리
            if actual_sound == preferred_sound:
                return cand
            
            # '불/부' 상호 호환 (두음법칙 및 음변화 대응)
            if {actual_sound, preferred_sound} <= {"불", "부"}:
                return cand
            if {actual_sound, preferred_sound} <= {"락", "낙", "악", "요"}:
                return cand
            if {actual_sound, preferred_sound} <= {"륙", "육"}:
                return cand
            if {actual_sound, preferred_sound} <= {"례", "예"}:
                return cand
    
    # 매칭되는 것이 없거나 선호 음이 없으면 첫 번째(대표) 훈음 반환
    return candidates[0]