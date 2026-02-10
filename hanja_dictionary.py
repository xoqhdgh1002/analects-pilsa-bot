"""
한자 훈음(뜻과 소리) 라이브러리 연결 모듈
"""
import hanjadict

def get_hanja_meaning(char: str) -> str:
    """
    한자의 훈음(뜻과 소리)을 반환합니다.
    hanjadict 라이브러리를 사용하여 5만 자 이상의 한자 데이터를 지원합니다.
    """
    if not char or len(char) != 1:
        return ""
    
    # hanjadict에서 훈음 조회 (예: '배울 학')
    result = hanjadict.lookup(char)
    
    if result:
        return result
    
    return ""