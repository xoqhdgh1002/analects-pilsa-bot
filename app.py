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

# 탭 및 모바일 글자 크기 조절을 위한 CSS
st.markdown("""
    <style>
    /* 기본 설정 (PC) */
    .stTabs [data-baseweb="tab"] p {
        font-size: 1.5rem;
        font-weight: bold;
    }
    
    /* 모바일 전용 설정 (너비 768px 이하) */
    @media (max-width: 768px) {
        .stTabs [data-baseweb="tab"] p {
            font-size: 1.0rem !important;
        }
        h1 {
            font-size: 1.8rem !important;
        }
        .stMarkdown h3 {
            font-size: 1.2rem !important;
        }
        .main .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
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
            new_char = st.text_input("한자", max_chars=1, key="sidebar_new_char", placeholder="예: 說")
        with col2:
            new_meaning = st.text_input("훈음 (뜻 소리)", key="sidebar_new_meaning", placeholder="예: 기쁠 열")
            
        if st.button("내 사전에 반영하기", use_container_width=True):
            if new_char and new_meaning:
                save_custom_meaning(new_char, new_meaning)
                st.success(f"성공! '{new_char}' 반영됨")
                st.rerun()
            else:
                st.warning("내용을 입력해주세요.")

    st.markdown("### 서버 저장")
    if st.button("수정한 내용 서버에 최종 저장하기", type="primary", use_container_width=True):
        try:
            with st.spinner("서버에 저장 중..."):
                subprocess.run(["git", "add", "custom_meanings.json"], check=True)
                try:
                    subprocess.run(["git", "commit", "-m", "chore: update custom meanings via app"], check=True, capture_output=True)
                except:
                    pass
                subprocess.run(["git", "push", "origin", "master"], check=True)
                st.success("서버 저장 완료! 🎉")
        except Exception as e:
            st.error(f"오류: {e}")

# ---------------------------------------------------------------------------
# Main: UI Layout
# ---------------------------------------------------------------------------
if 'pdf_data' not in st.session_state:
    st.session_state.pdf_data = None
if 'preview_images' not in st.session_state:
    st.session_state.preview_images = []
if 'total_passages' not in st.session_state:
    st.session_state.total_passages = 0

col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.markdown("### 🖋️ 데이터 입력")
    user_input = st.text_area(
        "필사할 내용을 입력하세요.",
        placeholder="""260210
9.자한편
30.子曰: "知者不惑, 仁者不憂, 勇者不懼."
(자왈: "지자불혹, 인자불우, 용자불구.")

공자께서 말씀하셨다. "지혜로운 사람은 미혹되지 않고, 어진 사람은 근심하지 않고, 용감한 사람은 두려워하지 않는다."

260210
9.자한편
29.子曰: "歲寒, 然後知松栢之後彫也."
(자왈: "세한, 연후지송백지후조야.")

공자께서 말씀하셨다. "날씨가 추워진 뒤에야 소나무와 잣나무가 늦게 시듦을 안다." """,
        height=600,
        label_visibility="collapsed"
    )
    
    if st.button("📄 PDF 생성하기", type="primary", use_container_width=True):
        if not user_input.strip():
            st.warning("내용을 입력해주세요.")
        else:
            try:
                with st.spinner("PDF 제작 중..."):
                    passages = parse_text_input(user_input)
                    if not passages:
                        st.error("구절을 찾을 수 없습니다.")
                    else:
                        font_path = Path("fonts/NotoSerifCJKkr-Regular.otf")
                        with tempfile.TemporaryDirectory() as tmpdir:
                            pdf_path = Path(tmpdir) / "output.pdf"
                            config = Config()
                            generator = AnalectsTracingPDF(config, str(font_path))
                            generator.generate(passages, str(pdf_path))
                            
                            with open(pdf_path, "rb") as f:
                                st.session_state.pdf_data = f.read()
                            st.session_state.preview_images = convert_from_path(str(pdf_path))
                            st.session_state.total_passages = len(passages)
                            st.rerun()
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

with col_right:
    tab_preview, tab_guide = st.tabs(["👀 미리보기 & 다운로드", "📖 사용 가이드"])
    
    with tab_preview:
        if st.session_state.pdf_data:
            st.success(f"🎉 총 {st.session_state.total_passages}개의 구절 준비 완료!")
            st.download_button(
                label="📥 PDF 다운로드 하기",
                data=st.session_state.pdf_data,
                file_name="analects_tracing.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            with st.container(height=600, border=True):
                for i, image in enumerate(st.session_state.preview_images):
                    st.image(image, caption=f"{i+1} 페이지", use_container_width=True)
        else:
            with st.container(height=600, border=True):
                st.info("👈 왼쪽에서 입력 후 'PDF 생성하기'를 눌러주세요.")
            st.button("📥 다운로드 (준비 안됨)", disabled=True, use_container_width=True)

    with tab_guide:
        st.markdown("### 📋 입력 형식")
        st.markdown("""
        **1. 날짜**: 6자리 (선택)
        **2. 편명**: 숫자.이름
        **3. 원문**: 숫자.한자
        **4. 음독**: (한글소리) - *필수*
        **5. 해석**: 한글 뜻풀이
        """)
        st.code("""260210
9.자한편
30.子曰: "知者不惑, 仁者不憂, 勇자不懼."
(자왈: "지자불혹, 인자불우, 용자불구.")

공자께서 말씀하셨다. "지혜로운 사람은 미혹되지 않고..." """, language="text")

st.markdown("---")
st.caption("Analects Tracing Bot v2.0 | Powered by fpdf2 & Streamlit")