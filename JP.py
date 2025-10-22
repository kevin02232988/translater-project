import streamlit as st
import time
import os
import requests
from PIL import Image
import pytesseract
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, MBartForConditionalGeneration, MBart50TokenizerFast
from google.cloud import translate

# EasyNMT는 빌드 오류로 제외, MarianMT 2쌍으로 대체합니다.

# --- 1. 환경 설정 및 인증 (기존 값 유지) ---
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
PAPAGO_CLIENT_ID = "CLIENT_ID"
PAPAGO_CLIENT_SECRET = "CLIENT_SECRET"
GOOGLE_CREDENTIALS_PATH = r"CREDENTIALS_PATH"

if os.path.exists(GOOGLE_CREDENTIALS_PATH):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_CREDENTIALS_PATH
else:
    st.error("Google API 인증 파일을 찾을 수 없습니다. 경로를 확인하세요.")
GOOGLE_PROJECT_ID = "GOOGLE_PROJECT_ID"

# --- 2. 언어 코드 매핑 및 모델 로드 함수 (로컬 3종 통합) ---

PAPAGO_LANG_MAP = {"한국어": "ko", "영어": "en", "일본어": "ja"}
GOOGLE_LANG_MAP = {"한국어": "ko", "영어": "en", "일본어": "ja"}

# mBART 언어 코드 매핑
MBART_LANG_MAP = {
    "한국어": "ko_KR",
    "영어": "en_XX",
    "일본어": "ja_XX"
}


@st.cache_resource
def load_local_models():
    """세 가지 로컬 모델(mBART, MarianMT_koen, MarianMT_jaen)을 로드하고 캐싱합니다."""
    # ⭐ 오류 해결: 키 이름을 UI 선택 박스와 일치하도록 변경 ⭐
    local_tools = {'mbart': None, 'marianmt_koen': None, 'marianmt_jaen': None}
    st.info("세 가지 로컬 모델 로드 중... (첫 실행 시 파일 다운로드 필요)")

    # 1. mBART 모델 로드 (고성능/대용량)
    try:
        MBART_MODEL_NAME = "facebook/mbart-large-50-many-to-many-mmt"
        tokenizer = MBart50TokenizerFast.from_pretrained(MBART_MODEL_NAME)
        model = MBartForConditionalGeneration.from_pretrained(MBART_MODEL_NAME)
        local_tools['mbart'] = {'tokenizer': tokenizer, 'model': model}
        st.success("✅ mBART 모델 로드 완료.")
    except Exception as e:
        st.error(f"❌ mBART 모델 로드 실패: {e}")

    # 2. MarianMT 모델 1: 한국어 ↔ 영어 쌍 (경량)
    try:
        MARIAN_MODEL_NAME_KOEN = "Helsinki-NLP/opus-mt-ko-en"
        m_tokenizer = AutoTokenizer.from_pretrained(MARIAN_MODEL_NAME_KOEN)
        m_model = AutoModelForSeq2SeqLM.from_pretrained(MARIAN_MODEL_NAME_KOEN)
        local_tools['marianmt_koen'] = {'ko_en': {'tokenizer': m_tokenizer, 'model': m_model}}  # 키 이름 수정됨
        st.success("✅ MarianMT (ko↔en) 모델 로드 완료.")
    except Exception as e:
        st.error(f"❌ MarianMT (ko↔en) 로드 실패: {e}")

    # 3. MarianMT 모델 2: 일본어 ↔ 영어 쌍 (경량)
    try:
        MARIAN_MODEL_NAME_JAEN = "Helsinki-NLP/opus-mt-ja-en"
        j_tokenizer = AutoTokenizer.from_pretrained(MARIAN_MODEL_NAME_JAEN)
        j_model = AutoModelForSeq2SeqLM.from_pretrained(MARIAN_MODEL_NAME_JAEN)
        local_tools['marianmt_jaen'] = {'ja_en': {'tokenizer': j_tokenizer, 'model': j_model}}  # 키 이름 수정됨
        st.success("✅ MarianMT (ja↔en) 모델 로드 완료.")
    except Exception as e:
        st.error(f"❌ MarianMT (ja↔en) 로드 실패: {e}")

    return local_tools


# --- 3. 번역 실행 함수 (로컬 통합) ---

def translate_papago(text, source_lang, target_lang):
    """NCP Papago Translation API를 사용하여 텍스트를 번역하고 시간을 측정합니다."""
    start_time = time.time()
    url = "https://papago.apigw.ntruss.com/nmt/v1/translation"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": PAPAGO_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": PAPAGO_CLIENT_SECRET,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "source": PAPAGO_LANG_MAP.get(source_lang, "en"),
        "target": PAPAGO_LANG_MAP.get(target_lang, "en"),
        "text": text
    }

    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        translated_text = response.json()['message']['result']['translatedText']
        end_time = time.time()
        return translated_text, (end_time - start_time) * 1000
    except Exception as e:
        return f"Papago 오류: {e} - 응답: {response.text if 'response' in locals() else '없음'}", 0


def translate_google(text, source_lang, target_lang):
    """Google Cloud Translation API 호출 함수."""
    start_time = time.time()
    try:
        client = translate.TranslationServiceClient()
        parent = f"projects/{GOOGLE_PROJECT_ID}"
        response = client.translate_text(
            parent=parent,
            contents=[text],
            target_language_code=GOOGLE_LANG_MAP.get(target_lang, "ko"),
            source_language_code=GOOGLE_LANG_MAP.get(source_lang, "en"),
        )
        translated_text = response.translations[0].translated_text
        end_time = time.time()
        return translated_text, (end_time - start_time) * 1000
    except Exception as e:
        return f"Google 오류: {e}", 0


# ⭐ 3개 로컬 모델을 모두 처리하는 통합 번역 함수 ⭐
def translate_local(model_name, text, lang_pair_code, local_tools):
    """선택된 로컬 모델(mBART, MarianMT_koen, MarianMT_jaen)로 텍스트를 번역합니다."""
    start_time = time.time()

    try:
        src_lang_name, tgt_lang_name = lang_pair_code.split(" → ")

        if model_name == 'mBART':
            # mBART 로직
            m_tools = local_tools['mbart']
            if not m_tools: raise Exception("mBART 로드 실패")
            src_code_mbart = MBART_LANG_MAP[src_lang_name]
            tgt_code_mbart = MBART_LANG_MAP[tgt_lang_name]
            tokenizer = m_tools['tokenizer']
            model = m_tools['model']
            tokenizer.src_lang = src_code_mbart
            encoded = tokenizer(text, return_tensors="pt")
            generated = model.generate(**encoded, forced_bos_token_id=tokenizer.lang_code_to_id[tgt_code_mbart])
            translated_text = tokenizer.decode(generated[0], skip_special_tokens=True)

        elif model_name == 'MarianMT (ko↔en)':
            # MarianMT ko↔en 로직
            marian_tools = local_tools['marianmt_koen']  # ⭐ 수정된 키 이름 사용
            if not marian_tools: raise Exception("MarianMT (ko↔en) 로드 실패")
            if lang_pair_code not in ["한국어 → 영어", "영어 → 한국어"]:
                return f"선택된 쌍은 MarianMT (ko↔en)에서 지원하지 않습니다.", 0

            m_tokenizer = marian_tools['ko_en']['tokenizer']
            m_model = marian_tools['ko_en']['model']
            encoded = m_tokenizer(text, return_tensors="pt")
            translated_tokens = m_model.generate(**encoded)
            translated_text = m_tokenizer.decode(translated_tokens[0], skip_special_tokens=True)

        elif model_name == 'MarianMT (ja↔en)':
            # MarianMT ja↔en 로직
            marian_tools = local_tools['marianmt_jaen']  # ⭐ 수정된 키 이름 사용
            if not marian_tools: raise Exception("MarianMT (ja↔en) 로드 실패")
            if lang_pair_code not in ["일본어 → 영어", "영어 → 일본어"]:
                return f"선택된 쌍은 MarianMT (ja↔en)에서 지원하지 않습니다.", 0

            m_tokenizer = marian_tools['ja_en']['tokenizer']
            m_model = marian_tools['ja_en']['model']
            encoded = m_tokenizer(text, return_tensors="pt")
            translated_tokens = m_model.generate(**encoded)
            translated_text = m_tokenizer.decode(translated_tokens[0], skip_special_tokens=True)

        else:
            translated_text = "유효하지 않은 모델 선택"

        end_time = time.time()
        return translated_text, (end_time - start_time) * 1000

    except Exception as e:
        return f"{model_name} 번역 오류: {e}", 0


# --- 4. Streamlit UI 메인 구성 ---

def main():
    st.set_page_config(layout="wide")
    st.title("외국어 번역기 성능 비교 분석 과제")
    st.subheader("Google, Papago API vs. 로컬 3종 모델 비교")

    local_tools = load_local_models()

    # 탭 나누기
    tab1, tab2 = st.tabs(["🌎 API 번역기 성능 비교 (Google vs. Papago)", "💻 로컬 3종 모델 성능 비교"])

    # 공통 설정
    available_langs = ["한국어", "영어", "일본어"]
    source_lang = st.sidebar.selectbox("원문 언어", available_langs)
    target_lang = st.sidebar.selectbox("번역 목표 언어", available_langs)

    if source_lang == target_lang:
        st.sidebar.warning("원문과 목표 언어는 다르게 설정해야 합니다.")

    st.sidebar.markdown("---")
    st.sidebar.markdown("**과제 분석 항목**")
    st.sidebar.markdown("- **정확도/자연스러움** (번역 결과 텍스트)")
    st.sidebar.markdown("- **번역 속도** (ms)")
    st.sidebar.markdown("- **접근성** (인터넷 유무)")

    # 탭 1: API 비교 (코드 변경 없음)
    with tab1:
        st.header("API 번역 성능 비교")
        st.subheader("1. 텍스트 번역")
        text_input = st.text_area("번역할 텍스트를 입력하세요.",
                                  "안녕하세요. 이 문장은 인공지능 번역기의 성능을 테스트하기 위한 샘플입니다.",
                                  key="text_api")

        if st.button("텍스트 번역 실행 (API)", key="text_api_btn"):
            if source_lang == target_lang:
                st.warning("원문 언어와 목표 언어가 동일합니다. 다른 언어를 선택해주세요.")
            else:
                st.markdown("---")
                with st.spinner("API 번역 실행 중..."):
                    google_result, google_time = translate_google(text_input, source_lang, target_lang)
                    papago_result, papago_time = translate_papago(text_input, source_lang, target_lang)

                col1, col2 = st.columns(2)

                with col1:
                    st.metric("Google 번역 소요 시간", f"{google_time:.2f} ms")
                    st.success(f"**Google 번역 결과:** {google_result}")
                    st.text_area("주관적 품질 평가 (Google)", "", key="google_quality")

                with col2:
                    st.metric("Papago 번역 소요 시간", f"{papago_time:.2f} ms")
                    st.success(f"**Papago 번역 결과:** {papago_result}")
                    st.text_area("주관적 품질 평가 (Papago)", "", key="papago_quality")

        st.subheader("2. 이미지 번역 (OCR + 번역)")
        uploaded_file = st.file_uploader("이미지 파일을 업로드하세요", type=["png", "jpg", "jpeg"], key="image_api")

        if uploaded_file and st.button("이미지 번역 실행 (API)", key="image_api_btn"):
            if source_lang == target_lang:
                st.warning("원문 언어와 목표 언어가 동일합니다. 다른 언어를 선택해주세요.")
            else:
                st.markdown("---")
                with st.spinner("이미지 처리 및 API 번역 중..."):
                    image = Image.open(uploaded_file)
                    st.image(image, caption="원본 이미지", use_column_width=True)

                    try:
                        text_from_image = pytesseract.image_to_string(image, lang='kor+eng+jpn').strip()
                        st.info(f"✅ OCR 추출 텍스트: **{text_from_image}**")

                        if text_from_image:
                            google_img_result, google_img_time = translate_google(text_from_image, source_lang,
                                                                                  target_lang)
                            papago_img_result, papago_img_time = translate_papago(text_from_image, source_lang,
                                                                                  target_lang)

                            col1_img, col2_img = st.columns(2)
                            with col1_img:
                                st.metric("Google 이미지 번역 (총 소요 시간)", f"{(google_img_time):.2f} ms")
                                st.success(f"**Google 최종 결과:** {google_img_result}")
                            with col2_img:
                                st.metric("Papago 이미지 번역 (총 소요 시간)", f"{(papago_img_time):.2f} ms")
                                st.success(f"**Papago 최종 결과:** {papago_img_result}")
                        else:
                            st.warning("이미지에서 텍스트를 추출하지 못했습니다. 더 선명한 이미지를 사용해 보세요.")

                    except Exception as e:
                        st.error(f"이미지 번역 실행 중 오류 발생: {e}")

    # 탭 2: 로컬 번역
    with tab2:
        st.header("로컬 3종 모델 성능 비교")
        st.markdown("인터넷 연결 없이 구동 가능한 **mBART, MarianMT (ko↔en), MarianMT (ja↔en)** 모델의 성능을 측정합니다.")

        # 4-3. 로컬 텍스트 번역 섹션
        st.subheader("로컬 텍스트 번역 (오프라인 시뮬레이션)")

        # ⭐⭐ 로컬 모델 선택 드롭다운 (3종) ⭐⭐
        local_model_select = st.selectbox("비교할 로컬 모델 선택", ['mBART', 'MarianMT (ko↔en)', 'MarianMT (ja↔en)'])

        # MarianMT는 특정 쌍만 지원한다는 경고 표시
        if 'MarianMT' in local_model_select:
            st.warning(f"{local_model_select}는 경량 모델로, 해당 쌍(ko↔en 또는 ja↔en)만 지원합니다.")

        # mBART가 지원하는 모든 양방향 쌍을 정의
        local_pairs = [
            "한국어 → 영어", "한국어 → 일본어",
            "영어 → 한국어", "영어 → 일본어",
            "일본어 → 한국어", "일본어 → 영어"
        ]

        m_pair = st.selectbox("번역 쌍 선택", local_pairs, key="local_pair")

        text_input_local = st.text_area("로컬 모델로 번역할 텍스트",
                                        "이것은 로컬 모델의 성능과 속도를 측정하기 위한 예시 문장입니다.",
                                        key="text_local")

        if st.button("로컬 번역 실행", key="local_btn"):
            # 로컬 모델의 내부 키 이름(mbart, marianmt_koen, marianmt_jaen)을 선택된 이름에 맞춰 변환
            # ⭐⭐ 이 부분이 이제 올바른 키 이름을 참조합니다. ⭐⭐
            model_key = local_model_select.lower().replace(" ", "").replace("(", "").replace(")", "").replace("↔", "")

            if local_tools[model_key] is None:
                st.error(f"선택한 {local_model_select} 모델이 로드되지 않았습니다. 모델 로드 상태를 확인하세요.")
            else:
                st.markdown("---")
                with st.spinner(f"로컬 모델 ({local_model_select}) 번역 중..."):
                    local_result, local_time = translate_local(local_model_select, text_input_local, m_pair,
                                                               local_tools)

                st.metric(f"{local_model_select} 번역 소요 시간", f"{local_time:.2f} ms")
                st.success(f"**{local_model_select} 번역 결과:** {local_result}")
                st.caption("주의: 모델마다 용량이 다르며, 성능 차이가 클 수 있습니다.")
                st.text_area(f"주관적 품질 평가 ({local_model_select})", "", key=f"{local_model_select}_quality")


if __name__ == "__main__":
    main()
