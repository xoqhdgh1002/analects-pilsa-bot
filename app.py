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
# Main: PDF 생성
# ---------------------------------------------------------------------------
st.markdown("""
텍스트를 입력하면 **추적(Tracing)용 필사 PDF**를 만들어 드립니다.  
형식 예시: `29.子曰: "歲寒, 然後知松栢之後彫也."`
""")

# 설정 및 경로
FONT_PATH = Path("fonts/NotoSerifCJKkr-Regular.otf")

# 폰트 확인
if not FONT_PATH.exists():
    st.error("⚠️ 폰트 파일이 `fonts/` 디렉토리에 없습니다. 폰트를 먼저 업로드해주세요.")
    st.stop()

# 입력 섹션
user_input = st.text_area(
    "필사할 내용을 입력하세요 (여러 구절을 동시에 입력할 수 있습니다):",
    placeholder="""[입력 예시 - 아래 형식을 복사해서 사용하세요]

260209
9.자한편
30.子曰: "知者不惑, 仁者不憂, 勇者不懼."
(자왈: "지자불혹, 인자불우, 용자불구.")

공자께서 말씀하셨다. "지혜로운 사람은 미혹되지 않고, 어진 사람은 근심하지 않고, 용감한 사람은 두려워하지 않는다."

https://naver.me/xUSIbn8s

260209
9.자한편
29.子曰: "歲寒, 然後知松栢之後彫也."
(자왈: "세한, 연후지송백지후조야.")

공자께서 말씀하셨다. "날씨가 추워진 뒤에야 소나무와 잣나무가 늦게 시듦을 안다."

https://naver.me/xUSIbn8s """,
    height=400
)

if st.button("PDF 생성하기"):
    if not user_input.strip():
        st.warning("내용을 입력해주세요.")
    else:
        try:
            with st.spinner("PDF를 생성 중입니다..."):
                # 1. 파싱
                passages = parse_text_input(user_input)
                if not passages:
                    st.error("입력된 텍스트에서 구절을 찾을 수 없습니다. 형식을 확인해주세요.")
                else:
                    # 2. 임시 파일 생성
                    with tempfile.TemporaryDirectory() as tmpdir:
                        pdf_path = Path(tmpdir) / "output.pdf"
                        
                        config = Config()
                        generator = AnalectsTracingPDF(config, str(FONT_PATH))
                        generator.generate(passages, str(pdf_path))
                        
                        # 3. 미리보기 이미지 생성 (모든 페이지)
                        images = convert_from_path(str(pdf_path))
                        if images:
                            st.subheader("미리보기 (전체 페이지)")
                            for i, image in enumerate(images):
                                st.image(image, caption=f"{i+1} 페이지", use_container_width=True)
                        
                        # 4. 다운로드 버튼
                        with open(pdf_path, "rb") as f:
                            st.download_button(
                                label="📄 PDF 다운로드",
                                data=f,
                                file_name="analects_tracing.pdf",
                                mime="application/pdf"
                            )
        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")

st.markdown("---")
st.caption("Powered by fpdf2 & Streamlit")
