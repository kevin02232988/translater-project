# **외국어 번역기 성능 비교 분석 프로젝트 최종 보고서 2021143013 김준성**

# **외국어 번역기 성능 비교 분석 프로젝트 최종 보고서**

**프로젝트명:** 외국어 번역기 성능 비교 분석 시스템 구축 **과목명:** 인공지능 개발 프로젝트 **학번 / 이름:** 2021143013 김준성 **제출일:** 2025년 10월 중간고사사

## **1. 프로젝트 개요**

### **1.1 프로젝트 목표 및 동기**

본 프로젝트는 인공지능 기반의 기계 번역(Machine Translation) 시스템을 **실제 서비스 환경(API)**과 **비용/접근성이 없는 로컬 환경**으로 구분하여 그 성능을 비교 분석하는 것을 목표로 한다.

특히, 번역기의 핵심 성능인 **번역 품질(정확도 및 자연스러움)**과 **번역 속도(Latency)**를 측정하고, 오프라인 환경에서도 고품질 번역을 수행할 수 있는 **로컬 모델의 실효성**을 검증하는 데 중점을 두었다.

- **비교 대상 언어:** 한국어, 영어, 일본어 (모든 양방향 쌍)
- **비교 항목:** API(Google vs Papago) 와 인터넷이 필요없는 로컬 모델 3종(mBART, MarianMT 2쌍)
- **특징 기능:** 텍스트 번역 및 OCR을 활용한 이미지 텍스트 번역 통합 지원

### **1.2 개발 환경 및 도구**

| **항목** | **내용** | **비고** |
| --- | --- | --- |
| **언어** | Python 3.10+ |  |
| **프레임워크** | Streamlit | 비교 분석을 위한 웹 UI 구축 |
| **API** | Google Cloud Translation API | 범용 고성능 API |
|  | Naver Cloud Papago API | 한국어 특화 API |
| **로컬 모델** | mBART-Large-50 | 대용량/고품질 다국어 모델 |
|  | MarianMT (ko↔en, ja↔en) | 경량/빠른 속도 특화 모델 |
| **이미지 처리** | pytesseract (OCR) | 이미지 텍스트 추출 기능 |
| **개발 환경** | PyCharm |  |

## **2. 시스템 구조**

프로젝트 시스템은 크게 두 가지 섹션으로 구성되며, 모든 기능은 Streamlit 웹 인터페이스를 통해 통합 관리된다.

| **섹션** | **기능** | **비교 항목** |
| --- | --- | --- |
| **API 번역 성능 비교** | Google / Papago API를 활용한 텍스트 및 OCR 이미지 번역 | 정확도, 속도, 비용 효율성 |
| **로컬 3종 모델 성능 비교** | mBART, MarianMT (ko↔en), MarianMT (ja↔en) 동시 실행 | 품질, 속도, 모델 용량, 오프라인 접근성 |

## **3. 모델 선정 및 로컬 모델 구조 (심층 분석)**

### **3.1 API 모델 선정**

- **Google Cloud Translation:** 전 세계에서 가장 널리 사용되는 범용 신경망 번역(NMT) 모델로, 번역 품질의 **기준점(Baseline)** 및 **다국어 처리 능력**을 측정하기 위해 선정.
- **Naver Cloud Papago:** 한국어-외국어 번역에 특화되어 있어, **한국어 구어체 및 관용 표현** 처리 능력을 Google과 대조 비교하기 위해 선정.

### **3.2 로컬 모델 구성 및 선정 논리**

당초 로컬 모델 2종(mBART, MarianMT)을 목표로 했으나, 교수님의 피드백에 따라 **총 3종의 모델**로 확장하여 성능을 다각도로 비교했다.

| **No.** | **모델 이름** | **유형** | **주요 비교 목표** | **용량 (추정)** |
| --- | --- | --- | --- | --- |
| 1 | **mBART-Large-50** | 다국어/대형 | **최고 품질** (고성능 모델의 한계 속도 측정) | 약 2.5GB |
| 2 | **MarianMT (ko↔en)** | 경량/단일 쌍 | **최고 속도** (mBART 대비 속도/품질 트레이드오프 분석) | 약 300MB |
| 3 | **MarianMT (ja↔en)** | 경량/단일 쌍 | **언어 특화 비교** (일본어 처리 시 mBART 대비 성능 측정) | 약 300MB |

## **4. 모델 학습 및 성능 (테스트 결과 요약)**

*(이 섹션은 데이터를 수집한 후 작성해야 합니다. 아래는 예시 데이터입니다.)*

### **4.1 평균 번역 속도 비교 (한↔영 쌍 기준)**

| **모델** | **유형** | **평균 속도 (ms)** |
| --- | --- | --- |
| **Papago API** | API | **350.5** |
| **Google API** | API | 415.8 |
| **MarianMT (ko↔en)** | 로컬(경량) | 550.2~1200.5 |
| **mBART** | 로컬(대형) | 3,210.7 |

### **4.2 품질 분석 결과 (주관적 F1-점수 평균)**

| **모델** | **일반 문장 (5점 만점)** | **구어체/관용구 (5점 만점)** | **전문 용어 (5점 만점)** |
| --- | --- | --- | --- |
| **Google** | 4.3 | 3.0 | 4.1 |
| **Papago** | 4.8 | **4.5** | 4.9 |
| **mBART** | 4.2 | 2.9 | **4.1** |

## **5. 문제점 및 해결 과정**

프로젝트의 난이도는 단순 API 호출이 아닌 **로컬 환경에서의 복잡한 모델 관리**에 있었으며, 다음과 같은 핵심적인 문제들을 극복했다.

### **5.1 API 키 인증 및 URL 불일치 문제 해결**

| **문제** | **발생 원인** | **해결 과정** |
| --- | --- | --- |
| **Google API 오류** | 서비스 계정 키(JSON)와 프로젝트 ID의 연동 방식에 대한 이해 부족. | 환경 변수(GOOGLE_APPLICATION_CREDENTIALS) 설정 및 클라이언트 라이브러리 사용을 통해 **API 키 대신 서비스 계정 인증** 방식으로 전환 완료. |
| **Papago 404/401 오류** | 네이버 클라우드 플랫폼(NCP)의 **공식 API URL**과 **요청 헤더 필드명** 불일치. | https://openapi.naver.com/v1/papago/n2mt URL을 https://papago.apigw.ntruss.com/nmt/v1/translation으로 수정하고, 헤더 필드명을 NCP 표준인 X-NCP-APIGW-API-KEY로 변경하여 해결. |

### **5.2 로컬 모델 통합 및 환경 설정 문제 해결**

| **문제** | **발생 원인** | **해결 과정** |
| --- | --- | --- |
| **Tesseract OCR 오류** | kor, eng, jpn 언어 팩(.traineddata 파일)의 시스템 누락. | GitHub에서 누락된 언어 팩을 수동 다운로드하여 Tesseract 설치 폴더의 tessdata 경로에 복사하여 문제 해결. |
| **MarianMT 키 오류** | UI에서 생성된 모델 이름과 코드 내부의 저장된 키(local_tools 딕셔너리)가 불일치. | load_local_models 함수와 UI 로직의 키 문자열(MarianMT (ko↔en))을 **완벽히 통일**하여 KeyError 발생 원인 제거. |
| **ko↔ja 복합 모델 로드 실패** | MarianMT (ko↔en) + MarianMT (en↔ja) 두 모델을 연결하는 복합 로직 구현 시, opus-mt-en-ja 모델 다운로드/로드 과정에서 지속적인 네트워크 및 캐시 오류 발생. | 프로젝트 안정성을 위해 복합 모델 구현을 제외. 최종적으로 안정적인 3가지 로컬 모델(mBART, MarianMT ko↔en, ja↔en)을 비교 대상으로 확정하여 분석의 초점을 명확히 함. |

실행 사진

사진 1: 

![IM1.png]

사진 2:

![IM2.png]



사진 3:

![IM3.png]

소스코드:

import streamlit as st

import time

import os

import requests

from PIL import Image

import pytesseract

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, MBartForConditionalGeneration, MBart50TokenizerFast

from google.cloud import translate

# --- 1. 환경 설정 및 인증---

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

PAPAGO_CLIENT_ID = "_CLIENT_ID"

PAPAGO_CLIENT_SECRET = "CLIENT_SECRET"

GOOGLE_CREDENTIALS_PATH = "GOOGLE_CREDENTIALS_PATH"

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

# 오류 해결: 키 이름을 UI 선택 박스와 일치하도록 정의

local_tools = {'mBART': None, 'MarianMT (ko↔en)': None, 'MarianMT (ja↔en)': None}

st.info("세 가지 로컬 모델 로드 중... (첫 실행 시 파일 다운로드 필요)")

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

"""선택된 로컬 모델(mBART, MarianMT_koen, MarianMT_jaen)로 텍스트를 번역합니다."""

start_time = time.time()

try:

src_lang_name, tgt_lang_name = lang_pair_code.split(" → ")

if model_name == 'mBART':

# mBART 로직

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

# MarianMT ko↔en 로직

marian_tools = local_tools['MarianMT (ko↔en)']

if not marian_tools: raise Exception("MarianMT (ko↔en) 로드 실패")

if lang_pair_code not in ["한국어 → 영어", "영어 → 한국어"]:

return f"선택된 쌍은 MarianMT (ko↔en)에서 지원하지 않습니다. (ko↔en만 지원)", 0

m_tokenizer = marian_tools['ko_en']['tokenizer']

m_model = marian_tools['ko_en']['model']

encoded = m_tokenizer(text, return_tensors="pt")

translated_tokens = m_model.generate(**encoded)

translated_text = m_tokenizer.decode(translated_tokens[0], skip_special_tokens=True)

elif model_name == 'MarianMT (ja↔en)':

# MarianMT ja↔en 로직

marian_tools = local_tools['MarianMT (ja↔en)']

if not marian_tools: raise Exception("MarianMT (ja↔en) 로드 실패")

if lang_pair_code not in ["일본어 → 영어", "영어 → 일본어"]:

return f"선택된 쌍은 MarianMT (ja↔en)에서 지원하지 않습니다. (ja↔en만 지원)", 0

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

# 탭 2: 로컬 번역 (3종 동시 비교 UI 적용)

with tab2:

st.header("로컬 3종 모델 성능 비교 (동시 실행)")

st.markdown(

"인터넷 연결 없이 구동 가능한 **mBART, MarianMT (ko↔en), MarianMT (ja↔en)** 모델의 성능을 비교합니다. (EasyNMT는 설치 문제로 제외)")

# 4-3. 로컬 텍스트 번역 섹션

st.subheader("로컬 텍스트 번역 (오프라인 시뮬레이션)")

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

# 버튼 클릭 시 3개 모델을 동시에 실행하고 3개 컬럼에 출력

if st.button("로컬 3종 동시 비교 실행", key="local_btn"):

st.markdown("---")

if not local_tools:

st.error("로컬 모델 로드 실패. 라이브러리 설치 및 초기 로드 상태를 확인하세요.")

return

# 비교할 세 모델의 키를 직접 사용

local_models_to_compare = ['mBART', 'MarianMT (ko↔en)', 'MarianMT (ja↔en)']

results = []

with st.spinner("로컬 모델 3종 동시 번역 중..."):

for model_name in local_models_to_compare:

tools = local_tools.get(model_name)

if tools is not None:

result, time_ms = translate_local(model_name, text_input_local, m_pair, local_tools)

results.append((model_name, result, time_ms))

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

st.text_area(f"주관적 품질 평가 ({name})", "", key=f"{name}_quality_{i}")

if __name__ == "__main__":

main()
