import streamlit as st
import torch
import time
import os
import requests
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    MBartForConditionalGeneration,
    MBart50TokenizerFast,
)
from transformers import AutoProcessor, AutoModelForCausalLM
from google.cloud import texttospeech
import io
import re  # OSD에서 회전 각도 추출용

# ===================================================================
# 0. 설정 및 인증
# ===================================================================

# Tesseract OCR 경로 (실제 경로에 맞게 수정 필요)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Papago API 인증 정보 (실제 배포 시에는 환경변수 사용 권장)
# -> 깃허브 올릴 때는 꼭 이 값들 지우고 환경변수로 바꿔라.
PAPAGO_CLIENT_ID = "4vhevyvhqf"
PAPAGO_CLIENT_SECRET = "RrVqhvpZyjcIj1dhjRqJ47T7DTBCaniCV0gn0J3M"

# Google Cloud 인증 경로 (실제 경로에 맞게 수정 필요)
GOOGLE_CREDENTIALS_PATH = r"C:\Users\user\PycharmProjects\PythonProject5\tenacious-post-332905-7cd866ce3088.json"
if os.path.exists(GOOGLE_CREDENTIALS_PATH):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_CREDENTIALS_PATH
else:
    st.error("Google API 인증 파일을 찾을 수 없습니다. 경로를 확인하세요.")

# 언어 코드 매핑
PAPAGO_LANG_MAP = {"한국어": "ko", "영어": "en", "일본어": "ja"}
MBART_LANG_MAP = {"한국어": "ko_KR", "영어": "en_XX", "일본어": "ja_XX"}
GOOGLE_TTS_STT_MAP = {
    "한국어": "ko-KR",
    "영어": "en-US",
    "일본어": "ja-JP",
}  # TTS용

# Tesseract용 언어 매핑 (심화 OCR에서 사용)
TESSERACT_LANG_MAP = {
    "한국어": "kor",
    "영어": "eng",
    "일본어": "jpn",
}


# ===================================================================
# 1. 모델 로드 및 캐싱 함수
# ===================================================================


@st.cache_resource
def load_captioning_model():
    """GIT Image Captioning 모델을 로드하고 캐싱합니다."""
    try:
        MODEL_NAME = "microsoft/git-base"
        caption_processor = AutoProcessor.from_pretrained(MODEL_NAME)
        caption_model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)
        st.success("✅ GIT 캡셔닝 모델 로드 완료 (오프라인)")
        return {"processor": caption_processor, "model": caption_model}, None
    except Exception as e:
        st.error(f"❌ GIT 캡셔닝 모델 로드 실패: {e}")
        return None, f"GIT 캡셔닝 모델 로드 실패: {e}"


@st.cache_resource
def load_mbart_model():
    """mBART 로컬 번역 모델을 로드하고 캐싱합니다."""
    try:
        MBART_MODEL_NAME = "facebook/mbart-large-50-many-to-many-mmt"
        tokenizer = MBart50TokenizerFast.from_pretrained(MBART_MODEL_NAME)
        model = MBartForConditionalGeneration.from_pretrained(MBART_MODEL_NAME)
        st.success("✅ mBART 번역 모델 로드 완료 (오프라인)")
        return {"tokenizer": tokenizer, "model": model}, None
    except Exception as e:
        st.error(f"❌ mBART 모델 로드 실패: {e}")
        return None, f"mBART 모델 로드 실패: {e}"


# ===================================================================
# 2. OCR 전처리 및 실행 함수
# ===================================================================


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    """
    심화 OCR용 전처리:
    - 그레이스케일(흑백) 변환
    - 회전(기울기) 보정 (OSD)
    - 작은 이미지 해상도 업샘플링
    - 노이즈 제거 (MedianFilter)
    - 대비 강화 + 이진화
    """
    # 1. 그레이스케일(흑백)
    img = image.convert("L")

    # 2. OSD를 이용한 회전 각도 추정 후 deskew
    try:
        osd = pytesseract.image_to_osd(img)
        angle_search = re.search(r"Rotate: (\d+)", osd)
        if angle_search:
            angle = float(angle_search.group(1))
            if angle != 0:
                # 수평을 맞추도록 반대 방향으로 회전
                img = img.rotate(-angle, expand=True)
    except Exception:
        # OSD 실패 시에는 회전 보정 생략
        pass

    # 3. 해상도 업샘플링 (텍스트가 너무 작을 때)
    w, h = img.size
    max_side = max(w, h)
    if max_side < 1000:
        scale = 1000 / max_side
        new_size = (int(w * scale), int(h * scale))
        img = img.resize(new_size, Image.LANCZOS)

    # 4. 노이즈 제거 (MedianFilter)
    img = img.filter(ImageFilter.MedianFilter(size=3))

    # 5. 대비 강화
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)

    # 6. 이진화 (완전 흑/백)
    threshold = 128
    img = img.point(lambda x: 0 if x < threshold else 255, "1")

    return img


def run_ocr(image: Image.Image, lang_code: str, psm: int = 6) -> str:
    """
    공통 OCR 실행 함수
    - lang_code: 'kor', 'eng', 'jpn', 'kor+eng+jpn' 등
    - psm: page segmentation mode (6: 단락, 11: 한 줄 등)
    """
    custom_config = f"--oem 3 --psm {psm}"
    text = pytesseract.image_to_string(image, lang=lang_code, config=custom_config)
    return text.strip()


def is_valid_ocr_text(text: str) -> bool:
    """
    OCR 결과가 '읽을 만한 문장'인지 간단한 휴리스틱으로 판별.
    너무 짧거나, 특수문자 비율이 너무 높으면 노이즈로 간주.
    """
    if not text:
        return False

    t = text.strip()
    if len(t) < 15:  # 15자 미만이면 없는 걸로
        return False

    t_no_nl = t.replace("\n", " ")
    letters = sum(ch.isalpha() for ch in t_no_nl)
    digits = sum(ch.isdigit() for ch in t_no_nl)
    symbols = sum((not ch.isalnum() and not ch.isspace()) for ch in t_no_nl)
    total = len(t_no_nl)

    if letters + digits < 5:
        return False

    if total > 0 and symbols / total > 0.35:
        return False

    return True


# ===================================================================
# 3. 기능 실행 함수 (캡셔닝 / 번역 / TTS)
# ===================================================================


def generate_image_caption(image, caption_tools):
    """이미지 객체를 입력받아 캡션을 생성합니다 (GIT 모델)."""
    start_time = time.time()
    try:
        if not caption_tools:
            return "캡셔닝 모델 로드 실패", 0

        processor = caption_tools["processor"]
        model = caption_tools["model"]

        image_rgb = image.convert("RGB")

        inputs = processor(images=image_rgb, return_tensors="pt")

        # pixel_values 차원 강제 정규화
        pixel_values = inputs.pixel_values
        if pixel_values.dim() == 3:
            pixel_values = pixel_values.unsqueeze(0)  # [1, 3, H, W]
        elif pixel_values.shape[0] != 1:
            pixel_values = pixel_values[0].unsqueeze(0)  # 첫 번째 이미지만 사용

        generated_ids = model.generate(
            pixel_values=pixel_values, max_length=50, num_beams=5
        )
        caption = processor.batch_decode(
            generated_ids, skip_special_tokens=True
        )[0]

        end_time = time.time()
        return caption, (end_time - start_time) * 1000

    except Exception as e:
        return f"캡션 생성 오류: {type(e).__name__} - {e}", 0


def translate_papago(text, target_lang, source_lang):
    """Papago API를 사용하여 텍스트를 번역합니다 (사용자 지정 원본 언어)."""
    start_time = time.time()
    target_code = PAPAGO_LANG_MAP.get(target_lang, "en")
    source_code = PAPAGO_LANG_MAP.get(source_lang, "en")

    url = "https://papago.apigw.ntruss.com/nmt/v1/translation"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": PAPAGO_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": PAPAGO_CLIENT_SECRET,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"source": source_code, "target": target_code, "text": text}
    translated_text = text

    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        result = response.json()["message"]["result"]
        translated_text = result.get("translatedText", text)
        src_lang_returned = result.get("srcLangType", source_code)

        normalized_text = "".join(text.lower().split())
        normalized_translated = "".join(translated_text.lower().split())

        if normalized_translated == normalized_text and src_lang_returned != target_code:
            st.caption(
                f"⚠️ Papago 번역 결과가 원문과 동일합니다. (원문: {source_lang}, 목표: {target_lang})"
            )

        end_time = time.time()
        return translated_text, (end_time - start_time) * 1000

    except Exception as e:
        return (
            f"Papago 오류: {e} - 응답: {response.text if 'response' in locals() else '없음'}",
            0,
        )


def translate_mbart(text, target_lang, mbart_tools, source_lang):
    """mBART 모델로 텍스트를 번역합니다 (오프라인, 일→한 영어 우회 로직 포함)."""
    start_time = time.time()

    m_tools = mbart_tools
    if not m_tools:
        return "mBART 로드 실패", 0

    tokenizer = m_tools["tokenizer"]
    model = m_tools["model"]

    try:
        if source_lang == target_lang:
            return text, 0.0

        if source_lang == "일본어" and target_lang == "한국어":
            # 1단계: 일본어 -> 영어
            tokenizer.src_lang = MBART_LANG_MAP["일본어"]
            encoded_ja_to_en = tokenizer(text, return_tensors="pt")
            generated_en = model.generate(
                **encoded_ja_to_en,
                forced_bos_token_id=tokenizer.lang_code_to_id[MBART_LANG_MAP["영어"]],
            )
            english_text = tokenizer.decode(
                generated_en[0], skip_special_tokens=True
            )

            # 2단계: 영어 -> 한국어
            tokenizer.src_lang = MBART_LANG_MAP["영어"]
            encoded_en_to_ko = tokenizer(english_text, return_tensors="pt")
            generated_ko = model.generate(
                **encoded_en_to_ko,
                forced_bos_token_id=tokenizer.lang_code_to_id[MBART_LANG_MAP["한국어"]],
            )
            translated_text = tokenizer.decode(
                generated_ko[0], skip_special_tokens=True
            )

        else:
            src_code_mbart = MBART_LANG_MAP[source_lang]
            tgt_code_mbart = MBART_LANG_MAP[target_lang]

            tokenizer.src_lang = src_code_mbart
            encoded = tokenizer(text, return_tensors="pt")

            generated = model.generate(
                **encoded,
                forced_bos_token_id=tokenizer.lang_code_to_id[tgt_code_mbart],
            )
            translated_text = tokenizer.decode(
                generated[0], skip_special_tokens=True
            )

        end_time = time.time()
        return translated_text, (end_time - start_time) * 1000

    except Exception as e:
        return f"mBART 번역 오류: {e}", 0


@st.cache_resource
def get_tts_client():
    """Google TextToSpeechClient 클라이언트를 로드합니다."""
    return texttospeech.TextToSpeechClient()


def synthesize_google_cloud_tts(text, lang_code):
    """Google Cloud TTS API를 사용하여 텍스트를 음성으로 변환합니다."""
    start_time = time.time()
    tts_client = get_tts_client()
    synthesis_input = texttospeech.SynthesisInput(text=text)

    voice_name_map = {
        "ko-KR": "ko-KR-Wavenet-D",
        "en-US": "en-US-Wavenet-D",
        "ja-JP": "ja-JP-Wavenet-D",
    }

    voice = texttospeech.VoiceSelectionParams(
        language_code=lang_code,
        name=voice_name_map.get(lang_code, "en-US-Wavenet-D"),
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    try:
        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )
        end_time = time.time()
        return response.audio_content, (end_time - start_time) * 1000, None
    except Exception as e:
        return None, 0, f"Google Cloud TTS 오류: {e}"


# ===================================================================
# 4. Streamlit UI 메인 구성
# ===================================================================


def multimodal_tts_app():
    st.set_page_config(layout="wide")
    st.title("📸 이미지 캡셔닝 및 다국어 TTS")
    st.subheader("시각 장애인 접근성 개선을 위한 멀티모달 AI 파이프라인 시뮬레이션")

    # 1. 모델 로드
    caption_tools, caption_error = load_captioning_model()
    mbart_tools, mbart_error = load_mbart_model()

    if caption_error or mbart_error:
        st.warning("모델 로드 실패로 일부 기능(캡셔닝/오프라인 번역)이 제한될 수 있습니다.")

    st.markdown("---")

    # 2. UI 요소
    uploaded_image = st.file_uploader(
        "이미지 파일 업로드", type=["png", "jpg", "jpeg"], key="image_multimodal"
    )

    col_mode, col_lang, col_ocr_src = st.columns(3)

    with col_mode:
        translation_mode = st.radio(
            "① OCR 텍스트 번역 엔진 선택",
            ["온라인 (Papago API)", "오프라인 (mBART 모델)"],
            key="trans_mode",
        )

    with col_lang:
        target_tts_lang = st.selectbox(
            "② 최종 TTS 출력 언어",
            ["한국어", "영어", "일본어"],
            key="tts_output_lang",
        )

    with col_ocr_src:
        ocr_source_lang = st.selectbox(
            "③ OCR 텍스트 원본 언어",
            ["영어", "일본어", "한국어"],
            key="ocr_source_lang",
            help="이미지에서 추출된 텍스트의 실제 언어를 선택하세요.",
        )

    st.caption("캡셔닝은 항상 GIT (오프라인)로, TTS는 Google Cloud TTS (온라인)로 실행됩니다.")

    if st.button("④ 이미지 분석 및 TTS 실행", key="run_multimodal_pipeline"):
        if uploaded_image is None:
            st.warning("이미지 파일을 먼저 업로드해주세요.")
            return

        st.markdown("---")
        image = Image.open(uploaded_image)
        st.image(image, caption="원본 이미지", use_column_width=True)

        # 1️⃣ 이미지 캡셔닝 (GIT 모델)
        with st.spinner("1/4: 이미지 내용 묘사 (캡셔닝) 생성 중..."):
            caption_text, cap_time = generate_image_caption(image, caption_tools)
        if "오류" in caption_text:
            st.error(f"❌ 캡셔닝 실패: {caption_text}")
            return
        st.success(
            f"✅ 이미지 묘사 (원문) [오프라인, {cap_time:.2f}ms]: **{caption_text}**"
        )

        # 1-1️⃣ 캡션을 최종 언어로 번역 (GIT 캡션 원문은 영어)
        with st.spinner("1-1/4: 캡션을 최종 언어로 번역 중..."):
            if translation_mode == "온라인 (Papago API)":
                translated_caption, cap_trans_time = translate_papago(
                    caption_text, target_tts_lang, "영어"
                )
            else:
                translated_caption, cap_trans_time = translate_mbart(
                    caption_text, target_tts_lang, mbart_tools, "영어"
                )
        st.success(
            f"✅ 캡션 번역 [{target_tts_lang}, {cap_trans_time:.2f}ms]: **{translated_caption}**"
        )

        # 2️⃣ OCR 텍스트 추출 (1차: 사용자가 고른 언어, 2차: 흑백·심화 전처리)
        with st.spinner("2/4: OCR (이미지 내 텍스트) 추출 중..."):
            try:
                # 사용자가 고른 원본 언어 기준으로 Tesseract 언어 결정
                tess_lang_main = TESSERACT_LANG_MAP.get(ocr_source_lang, None)

                # 1차: 원본 이미지 + 단일 언어
                # 만약 매핑을 못 찾으면 마지막 안전장치로 kor+eng+jpn
                first_pass_lang = (
                    tess_lang_main if tess_lang_main is not None else "kor+eng+jpn"
                )
                text_from_image = run_ocr(image, lang_code=first_pass_lang, psm=6)

                def shorten_text(t: str) -> str:
                    return t if len(t) <= 250 else t[:250] + "..."

                text_from_image = shorten_text(text_from_image)

                if text_from_image:
                    st.info(
                        f"✅ OCR 추출 텍스트 (1차, {ocr_source_lang}): **{text_from_image}**"
                    )
                else:
                    st.warning("⚠️ 1차 OCR에서 텍스트를 인식하지 못했습니다.")

                # 1차 결과가 없거나, 너무 짧으면 → 흑백·심화 전처리로 동일 언어로 재시도
                if (not text_from_image) or (len(text_from_image) < 10):
                    st.caption(
                        "🔍 1차 인식이 약해, 흑백·심화 전처리로 다시 시도합니다..."
                    )
                    bw_img = preprocess_for_ocr(image.copy())

                    # 심화 모드에서도 같은 언어 사용
                    deep_lang = first_pass_lang
                    deep_text = run_ocr(bw_img, lang_code=deep_lang, psm=6)
                    deep_text = shorten_text(deep_text)

                    if deep_text:
                        st.info(
                            f"✅ OCR 추출 텍스트 (2차, 흑백·심화 / {ocr_source_lang}): **{deep_text}**"
                        )

                        # 2차 결과가 더 길거나, 1차가 아예 없으면 2차 결과를 채택
                        if (not text_from_image) or (
                            len(deep_text) > len(text_from_image)
                        ):
                            text_from_image = deep_text
                            st.success(
                                "➡ 최종 OCR 텍스트로 2차(흑백·심화) 결과를 사용합니다."
                            )
                    else:
                        st.warning(
                            "⚠️ 흑백·심화 전처리 후에도 텍스트를 인식하지 못했습니다."
                        )

            except Exception as e:
                st.error(f"❌ OCR 실패: {e}")
                text_from_image = ""

            # --- OCR 노이즈 필터링: 이상한 문자열이면 아예 버린다 ---
            if text_from_image:
                if not is_valid_ocr_text(text_from_image):
                    st.info(
                        "ℹ️ 이미지 내 텍스트가 거의 없거나 노이즈로 판단되어, "
                        "OCR 결과는 TTS에 포함하지 않습니다."
                    )
                    text_from_image = ""

        # 3️⃣ OCR 텍스트 번역
        translated_ocr_text = ""
        source_lang_for_translation = st.session_state.ocr_source_lang

        if text_from_image:
            if source_lang_for_translation == target_tts_lang:
                translated_ocr_text = text_from_image
                st.success(
                    f"✅ 번역 결과 [{target_tts_lang}, 0.00ms]: "
                    f"**원문과 목표 언어가 같아 번역 생략**"
                )
            else:
                st.caption(
                    f"번역 엔진: {translation_mode}, 원본 언어: {source_lang_for_translation}"
                )
                with st.spinner("3/4: OCR 텍스트 번역 중..."):
                    if translation_mode == "온라인 (Papago API)":
                        translated_ocr_text, trans_time = translate_papago(
                            text_from_image, target_tts_lang, source_lang_for_translation
                        )
                    else:
                        translated_ocr_text, trans_time = translate_mbart(
                            text_from_image,
                            target_tts_lang,
                            mbart_tools,
                            source_lang_for_translation,
                        )

                    if "오류" in translated_ocr_text:
                        st.error(f"❌ 번역 실패: {translated_ocr_text}")
                    else:
                        st.success(
                            f"✅ 번역 결과 [{target_tts_lang}, {trans_time:.2f}ms]: "
                            f"**{translated_ocr_text}**"
                        )

        # 4️⃣ 언어별 안내 문장 구성
        announce_texts = {
            "한국어": {
                "caption": "이미지 내용입니다:",
                "ocr": "그리고 이미지에서 다음 텍스트가 번역되었습니다:",
                "no_text": "이미지 내 텍스트는 찾지 못했습니다.",
            },
            "영어": {
                "caption": "The image shows:",
                "ocr": "And the text detected in the image has been translated as follows:",
                "no_text": "No text was found in the image.",
            },
            "일본어": {
                "caption": "画像の内容は次のとおりです：",
                "ocr": "そして画像内のテキストは次のように翻訳されました：",
                "no_text": "画像内のテキストは見つかりませんでした。",
            },
        }

        phrases = announce_texts.get(target_tts_lang, announce_texts["한국어"])

        # 5️⃣ 최종 TTS 문장 구성
        if translated_ocr_text and translated_ocr_text.strip():
            final_text_to_speak = (
                f"{phrases['caption']} {translated_caption}. "
                f"{phrases['ocr']} {translated_ocr_text}"
            )
        else:
            # 텍스트가 없을 때는 안내 문장 없이 캡션만 읽어줌
            final_text_to_speak = f"{phrases['caption']} {translated_caption}"

        st.markdown("### 💬 최종 TTS 텍스트 (번역문 반영)")
        st.success(final_text_to_speak)

        # 6️⃣ Google Cloud TTS 실행
        with st.spinner("4/4: 최종 텍스트를 Google Cloud TTS로 합성 중 (고품질)..."):
            google_tts_lang_code = GOOGLE_TTS_STT_MAP.get(target_tts_lang)
            google_audio, google_time, google_error = synthesize_google_cloud_tts(
                final_text_to_speak, google_tts_lang_code
            )

        st.subheader(f"🗣️ TTS 결과 ({target_tts_lang}, Google Cloud TTS)")
        st.metric("합성 소요 시간 (ms)", f"{google_time:.2f} ms")
        if google_error:
            st.error(f"❌ 합성 실패: {google_error}")
            st.warning(
                "Google Cloud TTS API가 활성화되었는지, 인증 파일 경로가 올바른지 확인하세요."
            )
        else:
            st.audio(google_audio, format="audio/mp3")
            st.success("✨ 다국어 TTS 완료!")


if __name__ == "__main__":
    multimodal_tts_app()
