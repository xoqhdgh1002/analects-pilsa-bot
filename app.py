import streamlit as st
from pathlib import Path
import tempfile
import subprocess
from analects_tracing import Config, AnalectsTracingPDF, parse_text_input
from hanja_dictionary import get_custom_dict, save_custom_meaning
from challenge_manager import add_log, get_user_stats, get_leaderboard
from pdf2image import convert_from_path
import os
import pandas as pd

# 페이지 설정
st.set_page_config(page_title="논어 필사 PDF 생성기", page_icon="📝", layout="wide")

# CSS 스타일
@st.cache_data
def get_css():
    return """
    <style>
    .stTabs [data-baseweb="tab"] p { font-size: 1.5rem; font-weight: bold; }
    @media (max-width: 768px) {
        .stTabs [data-baseweb="tab"] p { font-size: 1.0rem !important; }
        h1 { font-size: 1.8rem !important; }
        .stMarkdown h3 { font-size: 1.2rem !important; }
        .main .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    }
    .login-container { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 5rem 0; }
    </style>
    """

st.markdown(get_css(), unsafe_allow_html=True)

st.title("📝 논어 필사 PDF 생성기")

# ---------------------------------------------------------------------------
# Session State 초기화
# ---------------------------------------------------------------------------
if 'user_name' not in st.session_state:
    st.session_state.user_name = None
if 'pdf_data' not in st.session_state:
    st.session_state.pdf_data = None
if 'preview_images' not in st.session_state:
    st.session_state.preview_images = []

# ---------------------------------------------------------------------------
# 로그인 화면
# ---------------------------------------------------------------------------
if st.session_state.user_name is None:
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.subheader("이름을 입력하고 필사를 시작하세요.")
    with st.container(border=True):
        input_name = st.text_input("닉네임 또는 이름", placeholder="예: 공자사랑", key="entry_name")
        if st.button("시작하기", type="primary", use_container_width=True):
            if input_name.strip():
                st.session_state.user_name = input_name.strip()
                st.rerun()
    st.markdown("---")
    st.caption("누적된 필사 기록은 챌린지 명예의 전당에 등록됩니다.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ---------------------------------------------------------------------------
# 메인 앱
# ---------------------------------------------------------------------------
user_name = st.session_state.user_name

with st.sidebar:
    st.header(f"🏃 {user_name}님")
    d_count = get_user_stats(user_name)
    st.metric("누적 출석", f"{d_count}일")
    
    with st.expander("🏆 명예의 전당 (Top 5)"):
        leaderboard = get_leaderboard()
        if leaderboard:
            st.dataframe(pd.DataFrame(leaderboard).head(5), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.header("📚 한자 사전 관리")
    with st.expander("사전 데이터 확인/수정"):
        custom_dict = get_custom_dict()
        if custom_dict:
            st.dataframe([{"한자": k, "뜻": v} for k, v in custom_dict.items()], use_container_width=True, hide_index=True)
        st.subheader("한자 뜻 고치기")
        c1, c2 = st.columns([1, 2])
        new_char = c1.text_input("한자", max_chars=1, key="sb_char", placeholder="예: 說")
        new_meaning = c2.text_input("훈음", key="sb_meaning", placeholder="예: 기쁠 열")
        if st.button("내 사전에 반영", use_container_width=True):
            if new_char and new_meaning:
                save_custom_meaning(new_char, new_meaning)
                st.rerun()

    st.caption("서버 데이터 보존")
    if st.button("서버 DB에 최종 저장", use_container_width=True, type="primary"):
        try:
            with st.spinner("동기화 중..."):
                subprocess.run(["git", "add", "custom_meanings.json", "challenge_db.json"], timeout=10, check=False)
                try: subprocess.run(["git", "commit", "-m", "chore: sync"], timeout=5, capture_output=True, check=False)
                except: pass
                subprocess.run(["git", "push", "origin", "master"], timeout=30, check=True)
                st.cache_data.clear()
                st.success("완료!")
        except Exception as e: st.error(f"실패: {e}")

    st.markdown("---")
    if st.button("다른 이름으로 시작하기 (로그아웃)"):
        st.session_state.user_name = None
        st.rerun()

# Layout
col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.markdown("### 🖋️ 데이터 입력")
    user_input = st.text_area(
        "필사 내용을 입력하세요.",
        placeholder="260210\n9.자한편\n30.子曰: \"知者不惑...\"",
        height=600, label_visibility="collapsed"
    )
    
    if st.button("📄 PDF 생성하기", type="primary", use_container_width=True):
        if user_input.strip():
            try:
                with st.spinner("PDF 제작 중..."):
                    passages = parse_text_input(user_input)
                    if passages:
                        font_path = Path("fonts/NotoSerifCJKkr-Regular.otf")
                        with tempfile.TemporaryDirectory() as tmpdir:
                            pdf_path = Path(tmpdir) / "output.pdf"
                            generator = AnalectsTracingPDF(Config(), str(font_path))
                            generator.generate(passages, str(pdf_path))
                            
                            # 챌린지 기록 (구절 수 없이 이름만 전달)
                            result = add_log(user_name)
                            
                            with open(pdf_path, "rb") as f:
                                st.session_state.pdf_data = f.read()
                            st.session_state.preview_images = convert_from_path(str(pdf_path))
                            st.rerun()
            except Exception as e: st.error(f"오류: {e}")

with col_right:
    tab_p, tab_g = st.tabs(["👀 미리보기 & 다운로드", "📖 사용 가이드"])
    with tab_p:
        if st.session_state.pdf_data:
            st.success(f"🎉 **{user_name}**님, 필사 노트 생성 완료! (오늘 출석했습니다 ✅)")
            st.download_button("📥 PDF 다운로드", data=st.session_state.pdf_data, file_name="analects_tracing.pdf", mime="application/pdf", use_container_width=True)
            with st.container(height=600, border=True):
                for img in st.session_state.preview_images:
                    st.image(img, use_container_width=True)
        else:
            with st.container(height=600, border=True):
                st.info("👈 왼쪽에서 입력 후 생성 버튼을 눌러주세요.")

    with tab_g:
        st.markdown("### 📋 입력 형식")
        st.code("260210\n9.자한편\n30.子曰: \"知者不惑...\"\n(자왈: \"지자불혹...\")\n해석 내용...", language="text")

st.markdown("---")
st.caption(f"Analects Tracing Bot v2.0 | User: {user_name}")