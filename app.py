import streamlit as st
from pathlib import Path
import tempfile
import subprocess
from analects_tracing import Config, AnalectsTracingPDF, parse_text_input
from hanja_dictionary import get_custom_dict, save_custom_meaning
from pdf2image import convert_from_path
import os

# 페이지 설정
st.set_page_config(page_title="논어 필사 PDF 생성기", page_icon="📝", layout="wide")

# 탭 글자 크기 조절을 위한 CSS
st.markdown("""
    <style>
    .stTabs [data-baseweb="tab"] p {
        font-size: 1.5rem;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📝 논어 필사 PDF 생성기")

# ---------------------------------------------------------------------------
# Sidebar: 사용자 정의 사전 편집
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("📚 한자 사전 관리")
    st.caption("특정 한자의 뜻을 내 입맛에 맞게 고칠 수 있습니다.")
    
    with st.expander("현재 등록된 한자 뜻 보기", expanded=False):
        # 현재 사전 표시
        custom_dict = get_custom_dict()
        if custom_dict:
            st.dataframe(
                [{"한자": k, "뜻": v} for k, v in custom_dict.items()],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("직접 수정한 한자 뜻이 아직 없습니다.")

        st.markdown("---")
        st.subheader("한자 뜻 고치기/추가")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            new_char = st.text_input("한자", max_chars=1, placeholder="예: 說")
        with col2:
            new_meaning = st.text_input("훈음 (뜻 소리)", placeholder="예: 기쁠 열")
            
        if st.button("내 사전에 반영하기", use_container_width=True):
            if new_char and new_meaning:
                save_custom_meaning(new_char, new_meaning)
                st.success(f"성공! 이제 '{new_char}'은(는) '{new_meaning}'(으)로 나옵니다.")
                st.rerun() # 화면 갱신
            else:
                st.warning("한자와 뜻을 모두 입력해주세요.")

    st.markdown("### 서버 저장")
    st.caption("수정한 내용을 서버에 저장하여 영구히 보존합니다.")
    if st.button("수정한 내용 서버에 최종 저장하기", type="primary", use_container_width=True):
        try:
            with st.spinner("서버에 저장 중..."):
                # 1. Add
                subprocess.run(["git", "add", "custom_meanings.json"], check=True)
                
                # 2. Commit
                try:
                    subprocess.run(
                        ["git", "commit", "-m", "chore: update custom meanings via streamlit app"], 
                        check=True, 
                        capture_output=True
                    )
                except subprocess.CalledProcessError:
                    st.info("이미 서버와 내용이 같습니다.")
                
                # 3. Push
                result = subprocess.run(
                    ["git", "push", "origin", "master"], 
                    check=True, 
                    capture_output=True,
                    text=True
                )
                st.success("서버 저장 완료! 이제 안전하게 보관됩니다. 🎉")
        except subprocess.CalledProcessError as e:
            st.error(f"Git 업로드 실패: {e.stderr if hasattr(e, 'stderr') else str(e)}")
        except Exception as e:
            st.error(f"오류 발생: {e}")

# ---------------------------------------------------------------------------
# Main: UI Layout
# ---------------------------------------------------------------------------
# Session State 초기화
if 'pdf_data' not in st.session_state:
    st.session_state.pdf_data = None
if 'preview_images' not in st.session_state:
    st.session_state.preview_images = []
if 'total_passages' not in st.session_state:
    st.session_state.total_passages = 0

# 전체 화면 좌우 분할
col_left, col_right = st.columns([1, 1], gap="large")

# [왼쪽 컬럼] 입력 및 생성
with col_left:
    st.markdown("### 🖋️ 데이터 입력")
    user_input = st.text_area(
        "필사할 내용을 아래 형식에 맞춰 입력해주세요.",
        placeholder="""260210
9.자한편
30.子曰: "知者不惑, 仁者不憂, 勇자不懼."
(자왈: "지자불혹, 인자불우, 용자불구.")

공자께서 말씀하셨다. "지혜로운 사람은 미혹되지 않고, 어진 사람은 근심하지 않고, 용감한 사람은 두려워하지 않는다." """,
        height=600,
        label_visibility="collapsed"
    )
    
    if st.button("📄 PDF 생성하기", type="primary", use_container_width=True):
        if not user_input.strip():
            st.warning("내용을 입력해주세요.")
        else:
            try:
                with st.spinner("전문 서예가가 PDF를 제작 중입니다..."):
                    # 1. 파싱
                    passages = parse_text_input(user_input)
                    if not passages:
                        st.error("입력된 텍스트에서 구절을 찾을 수 없습니다.")
                    else:
                        # 2. PDF 생성
                        font_path = Path("fonts/NotoSerifCJKkr-Regular.otf")
                        if not font_path.exists():
                            st.error("⚠️ 폰트 파일을 찾을 수 없습니다.")
                        else:
                            with tempfile.TemporaryDirectory() as tmpdir:
                                pdf_path = Path(tmpdir) / "output.pdf"
                                config = Config()
                                generator = AnalectsTracingPDF(config, str(font_path))
                                generator.generate(passages, str(pdf_path))
                                
                                # 세션 상태에 결과 저장
                                with open(pdf_path, "rb") as f:
                                    st.session_state.pdf_data = f.read()
                                st.session_state.preview_images = convert_from_path(str(pdf_path))
                                st.session_state.total_passages = len(passages)
                                st.rerun() # 화면 갱신
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

# [오른쪽 컬럼] 미리보기 및 가이드 (탭으로 분리)
with col_right:
    tab_preview, tab_guide = st.tabs(["👀 미리보기 & 다운로드", "📖 사용 가이드"])
    
    # 탭 1: 미리보기
    with tab_preview:
        if st.session_state.pdf_data:
            st.success(f"🎉 총 {st.session_state.total_passages}개의 구절이 준비되었습니다!")
            
            # 다운로드 버튼
            st.download_button(
                label="📥 PDF 다운로드 하기",
                data=st.session_state.pdf_data,
                file_name="analects_tracing.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            
            # 미리보기 영역
            with st.container(height=600, border=True):
                if st.session_state.preview_images:
                    for i, image in enumerate(st.session_state.preview_images):
                        st.image(image, caption=f"{i+1} 페이지", use_container_width=True)
        else:
            # 빈 상태 안내
            with st.container(height=600, border=True):
                st.info("""
                **👈 왼쪽에서 텍스트를 입력하고 'PDF 생성하기'를 눌러주세요.**
                
                생성이 완료되면 이곳에 미리보기가 자동으로 나타납니다.
                """)
            st.button("📥 다운로드 (준비 안됨)", disabled=True, use_container_width=True)

    # 탭 2: 사용 가이드
    with tab_guide:
        st.markdown("### 📋 올바른 입력 형식")
        st.info("아래 순서대로 입력하면 가장 예쁜 PDF가 만들어집니다.")
        
        st.markdown("""
        **1. 날짜 (선택)**
        - 6자리 숫자 (예: `260210`)
        
        **2. 편명**
        - `숫자.이름` (예: `9.자한편`)
        
        **3. 구절 원문**
        - `숫자.한자문장` (예: `30.子曰: ...`)
        
        **4. 음독 (필수)**
        - `(한글소리)` (예: `(자왈: ...)`)
        - **중요**: 괄호 안의 글자 수를 기준으로 한자 훈음을 매핑합니다.
        
        **5. 한글 해석**
        - 자유로운 뜻풀이
        """)
        
        st.markdown("---")
        st.subheader("💡 팁")
        st.write("네이버 메모나 블로그에서 복사한 내용을 그대로 붙여넣어도 대부분 자동으로 인식합니다.")
        
        example_text = """260210
9.자한편
30.子曰: "知者不惑, 仁者不憂, 勇者不懼."
(자왈: "지자불혹, 인자불우, 용자불구.")

공자께서 말씀하셨다. "지혜로운 사람은 미혹되지 않고, 어진 사람은 근심하지 않고, 용감한 사람은 두려워하지 않는다." """
        
        st.code(example_text, language="text")

st.markdown("---")
st.caption("Analects Tracing Bot v2.0 | Powered by fpdf2 & Streamlit")
