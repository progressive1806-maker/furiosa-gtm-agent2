import os
import requests
from bs4 import BeautifulSoup
import time
import datetime
import google.generativeai as genai
from jira import JIRA

# --- 1. 환경 설정 및 API 키 로드 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

# Jira 연동 (사수님 요구사항 반영)
jira = None
try:
    jira_options = {'server': JIRA_URL}
    # 변수명을 위에서 설정한 대로 바꿉니다.
    jira = JIRA(options=jira_options, basic_auth=(JIRA_EMAIL, JIRA_API_TOKEN))
except:
    jira = None

# --- 2. 데이터 수집 함수 ---
def fetch_furiosa_docs():
    urls = [
        "https://developer.furiosa.ai/latest/en/overview/supported_models.html",
        "https://developer.furiosa.ai/docs-dev/PR-3475/en/whatsnew/release-2026.2.html",
        "https://developer.furiosa.ai/latest/en/overview/rngd.html",
        "https://developer.furiosa.ai/latest/en/overview/software_stack.html",
        "https://developer.furiosa.ai/latest/en/overview/roadmap.html",
        "https://developer.furiosa.ai/latest/en/furiosa_llm/intro.html",
        "https://developer.furiosa.ai/latest/en/cloud_native_toolkit/intro.html",
        "https://developer.furiosa.ai/latest/en/device_management/system_management_interface.html",
        "https://huggingface.co/furiosa-ai",
        "https://huggingface.co/furiosa-ai/models"
    ]
    all_text = ""
    print("🚀 [Step 1] 퓨리오사 공식 문서 수집 중...")
    for url in urls:
        try:
            res = requests.get(url, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            for s in soup(["script", "style"]): s.decompose()
            all_text += f"\n\n[출처: {url}]\n{soup.get_text(separator=' ', strip=True)[:2500]}"
            time.sleep(0.3)
        except: continue
    return all_text

def get_market_data():
    print("📰 [Step 2] 네이버 뉴스 및 시장 데이터 수집 중...")
    queries = ["AI 서버 도입", "LLM 서비스 구축", "NPU 도입", "데이터센터 확장"]
    news_text = ""
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
    for q in queries:
        try:
            res = requests.get(f"https://openapi.naver.com/v1/search/news.json?query={q}&display=5", headers=headers).json()
            for item in res.get('items', []):
                news_text += f"제목: {item['title']}\n요약: {item['description']}\n\n"
        except: continue
    return news_text

# --- 3. 메인 실행 ---
def main():
    print("🤖 GTM Research Agent 작동 시작...")
    
    furiosa_info = fetch_furiosa_docs() 
    market_info = get_market_data()
    
    # Jira 파이프라인 정보 (사수님 가이드: 해당 기업이 기존 고객인지 확인용)
    jira_context = "현재 Jira 파이프라인에 존재하는 주요 접점 업체: [엘리스, 삼성SDS, SK C&C, 네이버클라우드, 케이티클라우드]" 

    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY가 설정되지 않았습니다.")
        return
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-pro')

    # 사수님 요구사항 (프롬프트 전문)
    instructions = r"""
# IMPORTANT: 매 실행 시 이 링크들 모두 직접 들어가서 본문 다 읽기 (Gemini)

 다음 URL들은 퓨리오사AI 제품 정보·SDK 버전·모델 지원이 *실시간으로 변동*되는 공식 문서입니다.
 매번 실행마다 *반드시* 모든 페이지를 직접 fetch해서 본문을 다 읽고 판단하세요.

 1. 지원 모델: https://developer.furiosa.ai/latest/en/overview/supported_models.html
 2. 최신 릴리즈: https://developer.furiosa.ai/docs-dev/PR-3475/en/whatsnew/release-2026.2.html
 3. RNGD 사양: https://developer.furiosa.ai/latest/en/overview/rngd.html
 4. 소프트웨어 스택: https://developer.furiosa.ai/latest/en/overview/software_stack.html
 5. 로드맵: https://developer.furiosa.ai/latest/en/overview/roadmap.html
 6. Furiosa LLM: https://developer.furiosa.ai/latest/en/furiosa_llm/intro.html
 7. Cloud Native Toolkit: https://developer.furiosa.ai/latest/en/cloud_native_toolkit/intro.html
 8. SMI: https://developer.furiosa.ai/latest/en/device_management/system_management_interface.html
 9. https://huggingface.co/furiosa-ai
 10. https://huggingface.co/furiosa-ai/models

 위 문서를 다 읽지 않은 상태로 판단하지 마세요.

# GTM Research Agent — 사수님 요구사항 (정제판)

---

## 1. 에이전트의 목적과 배경
비즈니스(BD·Sales) 팀이 쓸 수 있는 에이전트가 필요하다. 그 중 **GTM(Go To Market) 리서치 에이전트**가 이 작업의 대상이다.
퓨리오사AI와 협업 가능한 기업을 발굴하고 미시적인 실무 리포트를 만드는 것이 핵심이다.

## 2. 작동 방식과 출력 형태
- 매주 월요일 자동 보고 (리포트 형식).
- 사전 플랜(=프롬프트)에 충실할 것.

## 3. 후보 평가의 핵심 기준 — 모델 핏
- supported_models 페이지의 3개 카테고리(Decoder-only, Pooling, Planned)와 매칭되는 경우만 컨택 후보로 선정.
- 모델 버전 숫자까지 엄격하게 확인할 것 (예: Exaone 4.0 지원 시 5.0은 제외).
- 3개 카테고리에 명시되지 않은 모델을 사용하는 기업은 제외.

## 4. 핏에 맞는 회사 vs 안 맞는 회사
- 단기적/중기적 협업 가능성을 추정하여 소팅.

## 5. 의사결정자 정보 (LinkedIn 포함)
- 도입 의사결정을 할 수 있는 담당자의 LinkedIn 검색 주소 포함.

## 6. 리포트 표시 방식
- Jira 데이터는 '기존 접점 유무' 확인용으로만 쓰고 리포트에는 `기존접점: ✅` 정도로만 간단히 표시.

## 7. 온프레미스 + 클라우드(NPUaaS) 모두 포함
- 삼성 SDS의 NPUaaS(7월 출시)를 활용할 수 있는 고객(예: SDS SCP 이용 고객) 적극 발굴.

## 8. CSP 운영사 대상 영업 컨셉
- CSP(삼성SDS 등)를 위해 우리가 대신 고객을 찾아 꽂아주는 시나리오 포함.

## 9. 경쟁사 동향
- 경쟁사의 GTM 성취(수주, 파트너십, 납품 등)만 요약. 투자는 제외.

## 10. 리포트 필수 내용
- Engage 핏 근거 + Win-Win(고객측/우리측 각각) + 단/중/장기 매출 창출 시나리오.

## 11. 리포트 버전(하나의 리포트가 아니라 각각 따로 두 개의 리포트)
- 버전 1: B2B만 / 버전 2: B2B + B2G (나라장터 포함).

## 12. 나라장터 활용
- 발주처가 아닌 **SI 사업자**를 타겟팅할 것. 타당성 조사 공고는 제외.

## 13. 추가 원칙
- 하드코딩 금지 (동적 수집).
- 에이전트 자율 판단 중시.
"""

    # 최종 프롬프트 조합
    final_prompt = (
        "당신은 퓨리오사AI의 GTM 리서치 에이전트입니다.\n\n"
        "1. [실시간 퓨리오사 정보]\n" + furiosa_info + "\n\n"
        "2. [시장 데이터]\n" + market_info + "\n\n"
        "3. [Jira 파이프라인 정보]\n" + jira_context + "\n\n"
        "4. [수행 가이드 및 요구사항]\n" + instructions + "\n\n"
        "**위의 모든 데이터를 분석하여 사수님이 만족할 만한 가독성 좋은 HTML 형식의 주간 리포트를 작성하세요.**"
    )

    print("🧠 Gemini 분석 및 리포트 생성 중...")
    try:
        response = model.generate_content(final_prompt)
        content = response.text.replace("```html", "").replace("```", "").strip()

        os.makedirs("reports", exist_ok=True)
        with open("reports/index.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("✅ 리포트 생성 완료: reports/index.html")
    except Exception as e:
        print(f"❌ 실패: {e}")

if __name__ == "__main__":
    main()
