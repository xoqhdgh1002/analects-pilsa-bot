"""
한자 훈음(뜻과 소리) 라이브러리 연결 모듈
"""
import hanjadict

def get_hanja_meaning(char: str, preferred_sound: str = None) -> str:
    """
    한자의 훈음(뜻과 소리)을 반환합니다.
    preferred_sound가 제공되면 해당 소리로 끝나는 훈음을 우선적으로 찾습니다.
    예: char='樂', preferred_sound='악' -> '노래 악' 반환 (기본값은 '즐거울 락')
    """
    if not char or len(char) != 1:
        return ""
    
    # hanjadict에서 훈음 조회 (예: '즐거울 락, 노래 악, 좋아할 요')
    result = hanjadict.lookup(char)
    
    if not result:
        return ""
        
    candidates = [c.strip() for c in result.split(',')]
    
    # 선호하는 음(소리)이 있는 경우 매칭 시도
    if preferred_sound:
        for cand in candidates:
            # 훈음은 보통 "뜻 소리" 구조 (예: "노래 악")
            # 마지막 글자가 소리인지 확인
            parts = cand.split()
            if parts and parts[-1] == preferred_sound:
                return cand
    
    # 매칭되는 것이 없거나 선호 음이 없으면 첫 번째(대표) 훈음 반환
    return candidates[0]