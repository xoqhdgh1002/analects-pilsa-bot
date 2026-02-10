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

# CSS (탭, 모바일, 로그인 화면 스타일)
st.markdown("""
    <style>
    .stTabs [data-baseweb="tab"] p {
        font-size: 1.5rem;
        font-weight: bold;
    }
    @media (max-width: 768px) {
        .stTabs [data-baseweb="tab"] p { font-size: 1.0rem !important; }
        h1 { font-size: 1.8rem !important; }
        .stMarkdown h3 { font-size: 1.2rem !important; }
        .main .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    }
    /* 로그인 화면 중앙 정렬 */
    .login-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 5rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session State 초기화
# ---------------------------------------------------------------------------
if 'user_name' not in st.session_state:
    st.session_state.user_name = None
if 'pdf_data' not in st.session_state:
    st.session_state.pdf_data = None
if 'preview_images' not in st.session_state:
    st.session_state.preview_images = []
if 'total_passages' not in st.session_state:
    st.session_state.total_passages = 0

# ---------------------------------------------------------------------------
# 로그인 화면 (Entry Screen)
# ---------------------------------------------------------------------------
if st.session_state.user_name is None:
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.title("📝 논어 필사 챌린지")
    st.subheader("이름을 입력하고 필사를 시작하세요.")
    
    with st.container(border=True):
        input_name = st.text_input("닉네임 또는 이름", placeholder="예: 공자사랑", key="entry_name")
        if st.button("시작하기", type="primary", use_container_width=True):
            if input_name.strip():
                st.session_state.user_name = input_name.strip()
                st.rerun()
            else:
                st.warning("이름을 입력해주세요.")
    
    st.markdown("---")
    st.caption("누적된 필사 기록은 챌린지 명예의 전당에 등록됩니다.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop() # 여기서 실행 중단

# ---------------------------------------------------------------------------
# 메인 어플리케이션 (Main App) - 로그인 후 보여짐
# ---------------------------------------------------------------------------
user_name = st.session_state.user_name

st.title("📝 논어 필사 PDF 생성기")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header(f"🏃 {user_name}님")
    p_count, d_count = get_user_stats(user_name)
    m1, m2 = st.columns(2)
    m1.metric("누적 구절", f"{p_count}개")
    m2.metric("출석 일수", f"{d_count}일")
    
    with st.expander("🏆 명예의 전당 (Top 5)"):
        leaderboard = get_leaderboard()
        if leaderboard:
            df = pd.DataFrame(leaderboard).head(5)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.caption("첫 번째 주인공이 되어보세요!")

    st.markdown("---")
    st.header("📚 한자 사전 관리")
    with st.expander("사전 데이터 확인/수정", expanded=False):
        custom_dict = get_custom_dict()
        if custom_dict:
            st.dataframe([{"한자": k, "뜻": v} for k, v in custom_dict.items()], use_container_width=True, hide_index=True)
        
        st.subheader("한자 뜻 고치기")
        col1, col2 = st.columns([1, 2])
        new_char = col1.text_input("한자", max_chars=1, key="sb_char")
        new_meaning = col2.text_input("훈음", key="sb_meaning")
        if st.button("내 사전에 반영", use_container_width=True):
            if new_char and new_meaning:
                save_custom_meaning(new_char, new_meaning); st.rerun()

    st.caption("데이터 서버 동기화")
    if st.button("최종 저장 (Git Sync)", use_container_width=True):
        try:
            with st.spinner("동기화 중..."):
                subprocess.run(["git", "add", "custom_meanings.json", "challenge_db.json"], check=False)
                try: subprocess.run(["git", "commit", "-m", "chore: sync data"], check=False, capture_output=True)
                except: pass
                subprocess.run(["git", "push", "origin", "master"], check=True)
                st.success("완료!")
        except Exception as e: st.error(f"오류: {e}")

    st.markdown("---")
    if st.button("다른 이름으로 시작하기 (로그아웃)", variant="secondary"):
        st.session_state.user_name = None
        st.rerun()

# ---------------------------------------------------------------------------
# Main Layout
# ---------------------------------------------------------------------------
col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.markdown("### 🖋️ 데이터 입력")
    user_input = st.text_area(
        "필사할 내용을 입력하세요.",
        placeholder="""260210
9.자한편
30.子曰: "知者不惑, 仁者不憂, 勇者不懼."
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
                            
                            # 챌린지 기록 자동 저장
                            add_log(user_name, len(passages))
                            
                            with open(pdf_path, "rb") as f:
                                st.session_state.pdf_data = f.read()
                            st.session_state.preview_images = convert_from_path(str(pdf_path))
                            st.session_state.total_passages = len(passages)
                            st.rerun()
            except Exception as e:
                st.error(f"오류: {e}")

with col_right:
    tab_preview, tab_guide = st.tabs(["👀 미리보기 & 다운로드", "📖 사용 가이드"])
    
    with tab_preview:
        if st.session_state.pdf_data:
            st.success(f"🎉 **{user_name}**님, 챌린지 기록이 저장되었습니다! (총 {st.session_state.total_passages}구절)")
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
        st.markdown("### 📋 입력 형식 가이드")
        st.markdown("""
        **1. 날짜**: 6자리 (선택)
        **2. 편명**: 숫자.이름 (예: 9.자한편)
        **3. 원문**: 숫자.한자 (예: 30.子曰: ...)
        **4. 음독**: (한글소리) - *필수*
        **5. 해석**: 한글 뜻풀이
        """)
        st.code("""260210
9.자한편
30.子曰: "知者不惑, 仁者不憂, 勇者不懼."
(자왈: "지자불혹, 인자불우, 용자불구.")

공자께서 말씀하셨다. "지혜로운 사람은 미혹되지 않고..." """, language="text")

st.markdown("---")
st.caption(f"Analects Tracing Bot v2.0 | Logged in as {user_name}")