import streamlit as st
import time
import os
import requests
from PIL import Image
import pytesseract
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, MBartForConditionalGeneration, MBart50TokenizerFast
from google.cloud import translate
from google.cloud import texttospeech
from google.cloud import speech_v1p1beta1 as speech
from gtts import gTTS
import io
from pydub import AudioSegment # pydub 라이브러리
import json # JSON 저장 기능 추가

# --- 0. 데이터 저장소 설정 및 함수 ---
REVIEW_FILE = 'translation_reviews.json'

def load_reviews():
    """JSON 파일에서 평가 데이터를 로드합니다. 파일이 없으면 빈 딕셔너리를 반환합니다."""
    if os.path.exists(REVIEW_FILE):
        with open(REVIEW_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_review(data):
    """평가 데이터를 JSON 파일에 저장합니다."""
    with open(REVIEW_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def handle_save_button(key, text):
    """저장 버튼 클릭 시 리뷰를 업데이트하고 파일에 저장합니다."""
    # reviews는 세션 상태에 로드된 영구 데이터
    st.session_state.reviews[key] = text.strip()
    save_review(st.session_state.reviews)
    st.success(f"평가 '{key}'가 영구 저장되었습니다.")

# Streamlit 세션 상태에 리뷰 데이터를 로드합니다.
if 'reviews' not in st.session_state:
    st.session_state.reviews = load_reviews()


# --- 1. 환경 설정 및 인증 (기존 값 유지) ---
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
PAPAGO_CLIENT_ID = "4vhevyvhqf"
PAPAGO_CLIENT_SECRET = "RrVqhvpZyjcIj1dhjRqJ47T7DTBCaniCV0gn0J3M"

# ⭐⭐ FFmpeg 경로 강제 지정 (이미지에서 확인된 경로 기반) ⭐⭐
try:
    pydub.AudioSegment.converter = r"C:\ffmpeg\bin\ffmpeg.exe"
    pydub.AudioSegment.ffprobe = r"C:\ffmpeg\bin\ffprobe.exe"
except Exception:
    pass

GOOGLE_CREDENTIALS_PATH = r"C:\Users\user\PycharmProjects\PythonProject5\tenacious-post-332905-7cd866ce3088.json"

if os.path.exists(GOOGLE_CREDENTIALS_PATH):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_CREDENTIALS_PATH
else:
    st.error("Google API 인증 파일을 찾을 수 없습니다. 경로를 확인하세요.")
GOOGLE_PROJECT_ID = "tenacious-post-332905"


# --- 2. 언어 코드 매핑 및 모델 로드 함수 (로컬 3종 통합) ---

PAPAGO_LANG_MAP = {"한국어": "ko", "영어": "en", "일본어": "ja"}
GOOGLE_LANG_MAP = {"한국어": "ko", "영어": "en", "일본어": "ja"}

# Google TTS/STT API가 사용하는 언어 코드
GOOGLE_TTS_STT_MAP = {
    "한국어": "ko-KR",
    "영어": "en-US",
    "일본어": "ja-JP"
}
# gTTS가 사용하는 언어 코드 (ISO 639-1)
GTTS_LANG_MAP = {
    "한국어": "ko",
    "영어": "en",
    "일본어": "ja"
}

MBART_LANG_MAP = {
    "한국어": "ko_KR",
    "영어": "en_XX",
    "일본어": "ja_XX"
}

@st.cache_resource
def load_local_models():
    """세 가지 로컬 모델(mBART, MarianMT 2쌍)을 로드하고 캐싱합니다."""
    local_tools = {'mBART': None, 'MarianMT (ko↔en)': None, 'MarianMT (ja↔en)': None}
    st.info("세 가지 로컬 모델 로드 중...")

    # 1. mBART 모델 로드 (고성능/대용량)
    try:
        MBART_MODEL_NAME = "facebook/mbart-large-50-many-to-many-mmt"
        tokenizer = MBart50TokenizerFast.from_pretrained(MBART_MODEL_NAME)
        model = MBartForConditionalGeneration.from_pretrained(MBART_MODEL_NAME)
        local_tools['mBART'] = {'tokenizer': tokenizer, 'model': model}
        st.success("✅ mBART 모델 로드 완료.")
    except Exception as e:
        st.error(f"❌ mBART 모델 로드 실패: {e}")

    # 2. MarianMT 모델 1: 한국어 ↔ 영어 쌍 (경량)
    try:
        MARIAN_MODEL_NAME_KOEN = "Helsinki-NLP/opus-mt-ko-en"
        m_tokenizer = AutoTokenizer.from_pretrained(MARIAN_MODEL_NAME_KOEN)
        m_model = AutoModelForSeq2SeqLM.from_pretrained(MARIAN_MODEL_NAME_KOEN)
        local_tools['MarianMT (ko↔en)'] = {'ko_en': {'tokenizer': m_tokenizer, 'model': m_model}}
        st.success("✅ MarianMT (ko↔en) 모델 로드 완료.")
    except Exception as e:
        st.error(f"❌ MarianMT (ko↔en) 로드 실패: {e}")

    # 3. MarianMT 모델 2: 일본어 ↔ 영어 쌍 (경량)
    try:
        MARIAN_MODEL_NAME_JAEN = "Helsinki-NLP/opus-mt-ja-en"
        j_tokenizer = AutoTokenizer.from_pretrained(MARIAN_MODEL_NAME_JAEN)
        j_model = AutoModelForSeq2SeqLM.from_pretrained(MARIAN_MODEL_NAME_JAEN)
        local_tools['MarianMT (ja↔en)'] = {'ja_en': {'tokenizer': j_tokenizer, 'model': j_model}}
        st.success("✅ MarianMT (ja↔en) 모델 로드 완료.")
    except Exception as e:
        st.error(f"❌ MarianMT (ja↔en) 로드 실패: {e}")

    return local_tools


# --- 3. 번역 실행 함수 (API 및 로컬 통합) ---
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


def translate_local(model_name, text, lang_pair_code, local_tools):
    """선택된 로컬 모델(mBART, MarianMT 2쌍)로 텍스트를 번역합니다."""
    start_time = time.time()

    try:
        src_lang_name, tgt_lang_name = lang_pair_code.split(" → ")

        if model_name == 'mBART':
            m_tools = local_tools['mBART']
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
            marian_tools = local_tools['MarianMT (ko↔en)']
            if not marian_tools: raise Exception("MarianMT (ko↔en) 로드 실패")
            if lang_pair_code not in ["한국어 → 영어", "영어 → 한국어"]:
                return f"선택된 쌍은 MarianMT (ko↔en)에서 지원하지 않습니다.", 0

            m_tokenizer = marian_tools['ko_en']['tokenizer']
            m_model = marian_tools['ko_en']['model']
            encoded = m_tokenizer(text, return_tensors="pt")
            translated_tokens = m_model.generate(**encoded)
            translated_text = m_tokenizer.decode(translated_tokens[0], skip_special_tokens=True)

        elif model_name == 'MarianMT (ja↔en)':
            marian_tools = local_tools['MarianMT (ja↔en)']
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


# --- 새로운 음성 처리 함수 (TTS 비교 포함) ---

@st.cache_resource
def get_speech_client():
    """Google Speech/TTS 클라이언트를 로드합니다."""
    return texttospeech.TextToSpeechClient(), speech.SpeechClient()


def synthesize_google_cloud_tts(text, lang_code):
    """Google Cloud TTS API를 사용하여 텍스트를 음성으로 변환합니다."""
    start_time = time.time()
    tts_client, _ = get_speech_client()
    synthesis_input = texttospeech.SynthesisInput(text=text)

    # 언어 코드에 맞는 목소리 설정 (Wavenet은 고품질 모델)
    voice_name_map = {
        "ko-KR": "ko-KR-Wavenet-D",
        "en-US": "en-US-Wavenet-D",
        "ja-JP": "ja-JP-Wavenet-D"
    }

    voice = texttospeech.VoiceSelectionParams(
        language_code=lang_code,
        name=voice_name_map.get(lang_code, "en-US-Wavenet-D")
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    try:
        response = tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
        end_time = time.time()
        return response.audio_content, (end_time - start_time) * 1000, None
    except Exception as e:
        return None, 0, f"Google Cloud TTS 오류: {e}"


def synthesize_gtts(text, lang_name):
    """gTTS 라이브러리를 사용하여 텍스트를 음성으로 변환합니다 (오픈소스 대안)."""
    start_time = time.time()

    lang_code = GTTS_LANG_MAP.get(lang_name, 'en')

    try:
        tts = gTTS(text=text, lang=lang_code, slow=False)

        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        audio_content = mp3_fp.getvalue()

        end_time = time.time()
        return audio_content, (end_time - start_time) * 1000, None
    except Exception as e:
        return None, 0, f"gTTS 오류: {e}"


def recognize_speech(audio_file_data, lang_code, sample_rate_hertz=16000):
    """Google STT API를 사용하여 음성 데이터를 텍스트로 인식합니다."""
    _, stt_client = get_speech_client()

    audio = speech.RecognitionAudio(content=audio_file_data)

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=sample_rate_hertz,
        language_code=lang_code
    )

    try:
        response = stt_client.recognize(config=config, audio=audio)
        if response.results:
            return response.results[0].alternatives[0].transcript, None
        return "음성 인식 실패", None
    except Exception as e:
        return None, f"STT 오류: {e}"


# ⭐ 새로운 함수: MP3/WAV 파일을 LINEAR16 WAV 데이터로 변환 ⭐
def convert_to_linear16_wav(uploaded_file):
    """업로드된 오디오 파일을 Google STT가 요구하는 LINEAR16 WAV (16kHz)로 변환"""
    try:
        # 파일 유형 감지 및 로드
        file_type = uploaded_file.name.split('.')[-1].lower()
        if file_type == 'wav' and uploaded_file.type == 'audio/wav':
            audio_segment = AudioSegment.from_wav(io.BytesIO(uploaded_file.getvalue()))
        else:
            audio_segment = AudioSegment.from_file(io.BytesIO(uploaded_file.getvalue()), format=file_type)

        # 1. 16kHz로 리샘플링
        audio_segment = audio_segment.set_frame_rate(16000)
        # 2. 16bit 깊이로 설정 (LINEAR16 인코딩)
        audio_segment = audio_segment.set_sample_width(2)
        # 3. 단일 채널(mono)로 변환 ⭐
        audio_segment = audio_segment.set_channels(1)

        # 4. WAV 형식으로 메모리 버퍼에 내보내기
        wav_buffer = io.BytesIO()
        audio_segment.export(wav_buffer, format="wav")
        return wav_buffer.getvalue(), None
    except Exception as e:
        # ffmpeg가 설치되지 않았을 경우, 여기서 에러가 발생합니다.
        return None, f"오디오 변환 실패 (FFmpeg 및 pydub 필요): {e}"


# --- 4. Streamlit UI 메인 구성 ---

def main():
    st.set_page_config(layout="wide")
    st.title("외국어 번역기 성능 비교 분석 과제")
    st.subheader("Google, Papago API vs. 로컬 3종 모델 비교")

    local_tools = load_local_models()

    # ⭐ 새로운 탭 추가 ⭐
    tab1, tab2, tab3 = st.tabs([
        "🌎 API 번역기 성능 비교 (Google vs. Papago)",
        "💻 로컬 3종 모델 성능 비교",
        "🎤 음성 번역 및 TTS 비교"
    ])

    # 공통 설정
    available_langs = ["한국어", "영어", "일본어"]
    source_lang = st.sidebar.selectbox("원문 언어", available_langs, key="sidebar_src")
    target_lang = st.sidebar.selectbox("번역 목표 언어", available_langs, key="sidebar_tgt")

    if source_lang == target_lang:
        st.sidebar.warning("원문과 목표 언어는 다르게 설정해야 합니다.")

    st.sidebar.markdown("---")
    st.sidebar.markdown("**과제 분석 항목**")
    st.sidebar.markdown("- **정확도/자연스러움** (번역 결과 텍스트)")
    st.sidebar.markdown("- **번역 속도** (ms)")
    st.sidebar.markdown("- **접근성** (인터넷 유무)")

    # 탭 1: API 비교 (기존 코드 유지)
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

                    # ⭐ 주관적 평가 영역 통합 (Google) ⭐
                    review_key = f"google_quality_{source_lang}_{target_lang}"
                    current_review = st.session_state.reviews.get(review_key, "")

                    new_review = st.text_area("주관적 품질 평가 (Google)", current_review, key=f"input_{review_key}")

                    # 저장/수정 버튼
                    col_save, col_delete = st.columns(2)
                    with col_save:
                        if st.button("저장/수정 📝", key=f"save_{review_key}"):
                            handle_save_button(review_key, new_review)
                            st.session_state.reviews[review_key] = new_review
                            st.experimental_rerun() # 저장 후 새로고침
                    with col_delete:
                        if st.button("삭제 🗑️", key=f"delete_{review_key}"):
                            if review_key in st.session_state.reviews:
                                del st.session_state.reviews[review_key]
                                save_review(st.session_state.reviews)
                                st.experimental_rerun()


                with col2:
                    st.metric("Papago 번역 소요 시간", f"{papago_time:.2f} ms")
                    st.success(f"**Papago 번역 결과:** {papago_result}")

                    # ⭐ 주관적 평가 영역 통합 (Papago) ⭐
                    review_key = f"papago_quality_{source_lang}_{target_lang}"
                    current_review = st.session_state.reviews.get(review_key, "")

                    new_review = st.text_area("주관적 품질 평가 (Papago)", current_review, key=f"input_{review_key}")

                    # 저장/수정 버튼
                    col_save, col_delete = st.columns(2)
                    with col_save:
                        if st.button("저장/수정 📝", key=f"save_{review_key}"):
                            handle_save_button(review_key, new_review)
                            st.session_state.reviews[review_key] = new_review
                            st.experimental_rerun()
                    with col_delete:
                        if st.button("삭제 🗑️", key=f"delete_{review_key}"):
                            if review_key in st.session_state.reviews:
                                del st.session_state.reviews[review_key]
                                save_review(st.session_state.reviews)
                                st.experimental_rerun()


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

    # 탭 2: 로컬 번역 (3종 동시 비교 UI 적용)
    with tab2:
        st.header("로컬 3종 모델 성능 비교 (동시 실행)")
        st.markdown("인터넷 연결 없이 구동 가능한 **mBART, MarianMT (ko↔en), MarianMT (ja↔en)** 모델의 성능을 측정합니다.")

        # 4-3. 로컬 텍스트 번역 섹션
        st.subheader("로컬 텍스트 번역 (오프라인 시뮬레이션)")

        local_pairs = [
            "한국어 → 영어", "한국어 → 일본어",
            "영어 → 한국어", "영어 → 일본어",
            "일본어 → 한국어", "일본어 → 영어"
        ]

        m_pair = st.selectbox("번역 쌍 선택", local_pairs, key="local_pair_m")

        text_input_local = st.text_area("로컬 모델로 번역할 텍스트",
                                        "이것은 로컬 모델의 성능과 속도를 측정하기 위한 예시 문장입니다.",
                                        key="text_local_m")

        if st.button("로컬 3종 동시 비교 실행", key="local_btn_m"):

            st.markdown("---")
            if not local_tools:
                st.error("로컬 모델 로드 실패. 라이브러리 설치 및 초기 로드 상태를 확인하세요.")
                return

            local_models_to_compare = ['mBART', 'MarianMT (ko↔en)', 'MarianMT (ja↔en)']
            results = []

            with st.spinner("로컬 모델 3종 동시 번역 중..."):
                for model_name in local_models_to_compare:
                    tools = local_tools.get(model_name)

                    is_supported = True
                    if 'ko↔en' in model_name and m_pair not in ["한국어 → 영어", "영어 → 한국어"]:
                        is_supported = False
                    if 'ja↔en' in model_name and m_pair not in ["일본어 → 영어", "영어 → 일본어"]:
                        is_supported = False

                    if is_supported and tools is not None:
                        result, time_ms = translate_local(model_name, text_input_local, m_pair, local_tools)
                        results.append((model_name, result, time_ms))
                    elif not is_supported:
                        results.append((model_name, "미지원 (언어 쌍 불일치)", 0))
                    else:
                        results.append((model_name, "모델 로드 실패", 0))

            # 결과를 3개의 컬럼으로 출력
            cols = st.columns(len(results))
            for i, (name, result, time_ms) in enumerate(results):
                with cols[i]:
                    st.subheader(f"✅ {name}")
                    if time_ms > 0:
                        st.metric("소요 시간", f"{time_ms:.2f} ms")
                        st.success(f"**결과:** {result}")
                    else:
                        st.error(f"**실패/미지원:** {result}")
                        st.caption("MarianMT는 지원 쌍이 제한적입니다.")

                    # ⭐ 로컬 모델 주관적 평가 영역 통합 ⭐
                    review_key = f"local_quality_{name}_{m_pair}"
                    current_review = st.session_state.reviews.get(review_key, "")

                    st.text_area(f"주관적 품질 평가 ({name})", current_review, key=f"input_{review_key}")

                    # 저장/수정 버튼 그룹
                    col_save, col_delete = st.columns(2)
                    with col_save:
                        if st.button("저장/수정 📝", key=f"save_{review_key}"):
                            new_review = st.session_state[f"input_{review_key}"]
                            handle_save_button(review_key, new_review)
                            st.session_state.reviews[review_key] = new_review
                            st.experimental_rerun()
                    with col_delete:
                        if st.button("삭제 🗑️", key=f"delete_{review_key}"):
                            if review_key in st.session_state.reviews:
                                del st.session_state.reviews[review_key]
                                save_review(st.session_state.reviews)
                                st.experimental_rerun()


    # ⭐ 탭 3: 음성 번역 및 TTS 비교 기능 ⭐
    with tab3:
        st.header("🎤 Google Cloud TTS vs. gTTS (오픈소스) 비교")
        st.markdown("음성 파일을 업로드하고 Google Speech-to-Text로 인식한 후, **Google Cloud TTS와 gTTS의 성능**을 비교합니다.")

        # 1. 음성 파일 업로드
        uploaded_audio = st.file_uploader("음성 파일 업로드 (.wav 추천)", type=['wav', 'mp3'], key="audio_uploader")

        st.subheader("설정 및 텍스트 입력")
        col_stt, col_tts = st.columns(2)
        with col_stt:
            stt_lang = st.selectbox("① 원본 음성 언어 (STT)", available_langs, key="stt_src_lang")
        with col_tts:
            tts_lang = st.selectbox("② TTS 출력 언어 (번역 목표)", available_langs, key="tts_tgt_lang")

        if stt_lang == tts_lang:
            st.warning("STT 언어와 TTS 언어는 다르게 설정해야 번역 파이프라인이 유효합니다.")

        if st.button("③ STT 인식 및 TTS 비교 실행", key="run_audio_pipeline"):
            if uploaded_audio is None:
                st.warning("음성 파일을 먼저 업로드해주세요.")
                return

            st.markdown("---")

            # --- 0. 오디오 파일 변환 (MP3 -> WAV) ---
            with st.spinner(f"0/3: 오디오 파일 변환 중 (WAV로 디코딩)..."):
                # ⭐ 업로드된 파일을 LINEAR16 WAV로 변환 ⭐
                wav_audio_data, convert_error = convert_to_linear16_wav(uploaded_audio)

            if convert_error:
                st.error(f"❌ 오디오 변환 실패: {convert_error}")
                st.warning("FFmpeg 설치 및 환경 변수 설정이 필요합니다. 또는 파일을 직접 WAV 형식으로 변환하여 업로드해주세요.")
                return

            # --- 1. STT (음성 인식) - Google API 사용 ---
            with st.spinner(f"1/3: {stt_lang} 음성 인식 중 (Google STT)..."):
                stt_lang_code = GOOGLE_TTS_STT_MAP.get(stt_lang)
                sample_rate = 16000
                # ⭐ 변환된 WAV 데이터 사용 ⭐
                recognized_text, stt_error = recognize_speech(wav_audio_data, stt_lang_code, sample_rate)

            if stt_error:
                st.error(f"❌ 음성 인식 실패: {stt_error}. Google Cloud Speech-to-Text API가 활성화되었는지 확인하세요.")
                return

            if "음성 인식 실패" in recognized_text:
                st.error(f"❌ 인식된 텍스트 ({stt_lang}): **음성 인식 실패**")
                return

            st.success(f"✅ 인식된 텍스트 ({stt_lang}): **{recognized_text}**")

            # --- 2. 텍스트 번역 (Google Translate API 사용) ---
            with st.spinner(f"2/3: 텍스트 번역 중 (Google Translate)..."):
                translated_text, _ = translate_google(recognized_text, stt_lang, tts_lang)

            st.success(f"✅ 번역된 최종 텍스트 ({tts_lang}): **{translated_text}**")
            st.markdown("---")

            # --- 3. TTS 비교 (Google Cloud vs gTTS) ---

            tts_results = []

            # 3-A. Google Cloud TTS 실행
            with st.spinner("3A/3: Google Cloud TTS 합성 중 (고품질)..."):
                google_tts_lang_code = GOOGLE_TTS_STT_MAP.get(tts_lang)
                google_audio, google_time, google_error = synthesize_google_cloud_tts(translated_text,
                                                                                      google_tts_lang_code)
                tts_results.append(("Google Cloud TTS", google_audio, google_time, google_error))

            # 3-B. gTTS (오픈소스) 실행
            with st.spinner("3B/3: gTTS (오픈소스) 합성 중..."):
                gtts_audio, gtts_time, gtts_error = synthesize_gtts(translated_text, tts_lang)
                tts_results.append(("gTTS (오픈소스)", gtts_audio, gtts_time, gtts_error))

            # --- 4. 결과 출력 및 비교 ---
            cols = st.columns(2)

            for i, (name, audio_content, time_ms, error) in enumerate(tts_results):
                with cols[i]:
                    st.subheader(f"🗣️ {name}")
                    st.metric("소요 시간 (ms)", f"{time_ms:.2f} ms")

                    if error:
                        st.error(f"❌ 합성 실패: {error}")
                    else:
                        st.audio(audio_content, format='audio/mp3')

                        # ⭐ TTS 주관적 평가 영역 통합 ⭐
                        review_key = f"tts_quality_{name}_{tts_lang}"
                        current_review = st.session_state.reviews.get(review_key, "")

                        st.text_area(f"주관적 품질 평가 ({name})", current_review, key=f"input_{review_key}")

                        # 저장/수정 버튼 그룹
                        col_save, col_delete = st.columns(2)
                        with col_save:
                            if st.button("저장/수정 📝", key=f"save_{review_key}"):
                                new_review = st.session_state[f"input_{review_key}"]
                                handle_save_button(review_key, new_review)
                                st.session_state.reviews[review_key] = new_review
                                st.experimental_rerun()
                        with col_delete:
                            if st.button("삭제 🗑️", key=f"delete_{review_key}"):
                                if review_key in st.session_state.reviews:
                                    del st.session_state.reviews[review_key]
                                    save_review(st.session_state.reviews)
                                    st.experimental_rerun()

                        st.success("합성 완료!")


if __name__ == "__main__":
    main()
