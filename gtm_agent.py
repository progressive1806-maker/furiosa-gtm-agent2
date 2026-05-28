import os
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import google.generativeai as genai
from jira import JIRA

# --- 1. 환경 설정 및 API 키 로드 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
NARAJANGTEO_API_KEY = os.getenv("NARAJANGTEO_API_KEY")
JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

# Jira 연동 (사수님 가이드: 백그라운드 매칭용, 리포트 본문 언급 금지)
jira_context = "현재 Jira 파이프라인에 존재하는 주요 접점 업체 리스트: [엘리스, 삼성SDS, SK C&C, 네이버클라우드, KT클라우드]"

# --- 2. 실시간 정보 100% 동적 수집 함수 ---
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
    print("🚀 [Step 1] 퓨리오사 공식 문서 10개 실시간 Fetch 및 분석 시작...")
    for url in urls:
        try:
            res = requests.get(url, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            # 불필요한 스크립트/스타일 제거하여 순수 텍스트만 추출
            for s in soup(["script", "style"]): s.decompose()
            all_text += f"\n\n[공식 문서 출처: {url}]\n{soup.get_text(separator=' ', strip=True)}"
            time.sleep(0.1)
        except Exception as e:
            print(f"⚠️ {url} 수집 실패: {e}")
            continue
    return all_text

# --- 3. 메인 자율 구동부 ---
def main():
    if not GEMINI_API_KEY:
        print("❌ 에러: GEMINI_API_KEY가 환경 변수에 설정되지 않았습니다.")
        return

    # 제미나이 AI 클라이언트 설정
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-pro')

    # 1단계: 실시간 퓨리오사 제품 정보 및 로드맵 크롤링
    furiosa_context = fetch_furiosa_docs()


    # 2단계: [하드코딩 제거] 제미나이가 문서를 읽고 최적의 검색 키워드를 스스로 무제한 생성
    print("🧠 [Step 2] 에이전트 자율 판단: 최신 지원 모델 및 로드맵 기반 시장 검색어 생성 중...")
    query_gen_prompt = f"""
    너는 퓨리오사AI의 기술 영업 및 BD 담당자야. 
    아래 수집된 퓨리오사AI 공식 문서에서 'Decoder-only Models', 'Pooling Models', 'Planned Models'를 전부 분석해라.
    해당 모델명(예: Llama, Qwen, Exaone 등 버전 포함)들과 우리 제품 RNGD, NPUaaS를 도입할 성향이 높은 잠재 고객사(엔터프라이즈, 대기업, 클라우드 이용사, SI 기업)를 뉴스 및 조달청에서 발굴하기 위한 최적의 검색 키워드 목록을 생성해줘.
    
    [실시간 퓨리오사 정보]
    {furiosa_context[:15000]}
    
    형식: 키워드1, 키워드2, 키워드3... (개수 제한 두지 말고 매칭 가능한 키워드를 전부 콤마로 구분하여 출력)
    """
    
    try:
        query_response = model.generate_content(query_gen_prompt).text.strip()
        dynamic_queries = [q.strip() for q in query_response.split(',') if q.strip()]
        print(f"✅ 자율 생성된 검색 쿼리 목록: {dynamic_queries}")
    except Exception as e:
        # 하드코딩된 대체 쿼리를 쓰지 않고, 오류 메시지 출력 후 프로그램을 완전히 종료합니다.
        print(f"❌ 검색어 자율 생성 실패! 제미나이 API 오류로 에이전트 실행을 중단합니다: {e}")
        return

    # 3단계: 자율 생성된 쿼리로 B2B 뉴스 및 시장 데이터 검색
    print(f"📰 [Step 3] 생성된 {len(dynamic_queries)}개 키워드로 네이버 뉴스 시장조사 진행 중...")
    market_raw_data = ""
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
    
    for q in dynamic_queries:
        if not NAVER_CLIENT_ID: break
        try:
            res = requests.get(f"https://openapi.naver.com/v1/search/news.json?query={q}&display=5", headers=headers).json()
            for item in res.get('items', []):
                market_raw_data += f"제목: {item['title']}\n요약: {item['description']}\n\n"
        except: continue

    # 4단계: 나라장터 Open API 연동 수집 (B2G용 데이터)
    b2g_raw_data = ""
    if NARAJANGTEO_API_KEY:
        print("🏢 [Step 4] 나라장터 Open API 실시간 입찰 공고 수집 중...")
        try:
            from_date = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d%H%M')
            to_date = datetime.now().strftime('%Y%m%d%H%M')
            url = "http://apis.data.go.kr/1230000/BidPublicInfoService05/getBidPblancListInfoServcPPSSrch"
            
            # 제미나이가 뽑은 키워드 중 상위 핵심 단어로 조달청 공고 매칭
            search_keyword = dynamic_queries[0] if dynamic_queries else "AI"
            params = {
                'serviceKey': NARAJANGTEO_API_KEY, 
                'numOfRows': '20', 
                'inqryBgnDt': from_date, 
                'inqryEndDt': to_date,
                'bidNtceNm': search_keyword, 
                'type': 'json'
            }
            res = requests.get(url, params=params, timeout=12).json()
            items = res.get('response', {}).get('body', {}).get('items', [])
            for item in items: 
                b2g_raw_data += f"공고명: {item['bidNtceNm']} / 발주처: {item['ntceInsttNm']} / 상세URL: {item['bidNtceDetailUrl']}\n"
        except Exception as e: 
            b2g_raw_data = f"나라장터 실시간 API 연동 제한 또는 호출 오류: {e}"
    else:
        b2g_raw_data = "나라장터 API Key 미설정 상태입니다."

    # --- 5단계: 사수님 요구사항 프롬프트 원문 주입 ---
    SUPERVISOR_PROMPT = r"""
# IMPORTANT: 매 실행 시 이 링크들 모두 직접 들어가서 본문 다 읽기 (Gemini)

 다음 URL들은 퓨리오사AI 제품 정보·SDK 버전·모델 지원이 *실시간으로 변동*되는
 공식 문서입니다.
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

비즈니스(BD·Sales) 팀이 쓸 수 있는 에이전트가 필요하다. 그 중 **GTM(Go To Market) 리서치 에이전트**가 이 작업의 대상이다

배경 문제: 퓨리오사AI는 현재 engage 하고 있는 고객도 있지만, engage 하지 못하고 있는 고객들이 더 많다. 특정 업체·회사·대기업 그룹에서 AI를 도입하는 사례가 기사로 심심치 않게 나오는데, 사람이 이걸 시의적절하게 트래킹하기는 불가능하다. 이를 자동화해서 **"우리가 어떤 회사들과 협업할 수 있을지"**를 알려주는 것이 이 에이전트의 핵심 아웃풋이다.

알파센스 같은 외부 마켓 리서치 회사의 리포트는 우리에게 필요한 수준이 아니다. 그들은 시장·엔터프라이즈 전략·경쟁 현황을 *하이 레벨·제너럴*하게 다룬다. 우리가 지금 당장 필요한 건 그게 아니다. **"우리는 결국 누구랑 이야기를 해야 되고, 어떤 이야기를 해야 되고, 우리 핏에 맞는 고객이 누구인지"**를 알아야 한다. 거시적 이야기가 아니라 **미시적 요소**가 실무에 필요하다.

따라서 우리만의 에이전트를 만들어서 우리 입맛에 맞게 리포트를 계속 만들고, 필요하면 튜닝도 한다.

---

## 2. 작동 방식과 출력 형태

- **자동 보고**: 사용자가 별도의 프롬프트를 입력할 필요 없이, **매주 월요일 정해진 시각에 자동으로 보고**가 되는 형태를 원한다. 그게 최종 목표다.
- 주기: **일주일에 한 번** 정도 체크.
- 보고 형식: 리포트 형태로 정리되어, 이를 보고 BD&Sales 사수님이 컨택을 쉽게 할 수 있어야 한다.
- 그 퀄리티가 우리가 원하는 결과에 맞게 나와 줘야 한다. 그래서 사전에 플랜(= 프롬프트)을 잘 짜는 것이 중요하다. 플랜 자체가 사실은 프롬프트가 된다.

구현 도구는 자유다. Claude Code, Codex, Gemini 등 무엇으로 하든 상관없다.

---

## 3. 후보 평가의 핵심 기준 — 모델 핏

 1. 지원 모델: https://developer.furiosa.ai/latest/en/overview/supported_models.html을 보면 우리가 **현재 지원하고 있는 모델의 로드맵**이 있고, **앞으로 계획 중인 모델 로드맵**이 있다. 이 로드맵 안에서 뭔가를 활용·개발하려고 하는 기업들이 1차 컨택 후보다. 그 기업들을 *실제 기사*나 *시장 자료*를 통해 확인할 수 있으면, 그 업체는 "우리 로드맵을 많이 쓰는 서비스나 제품을 개발하고 있기 때문에 협업을 하기에 굉장히 좋은 상황"이다. 우리 입장에서 쉽게 engage 할 수 있다. 
반대로, **우리 로드맵에 없는 모델**(예: Stable Diffusion 같은)을 가지고 뭔가 개발하는 회사는, 우리와 함께 일할 수 없는 회사다. 리포트에 나오면 안된다. 예를 들어 우리는 현재 exaone 4.0은 지원가능한 모델이고, k-exaone은 미래 플랜에 있는 모델이다. 근데 exaone 5.0은 로드맵에 현재 없다. 그니까 exaone만 보면 안되고 뒤에 버전 숫자도 봐야 한다.

예시: Qwen 3 32B로 뭔가 개발하려는 모델 회사 → 우리와 같이 일할 수 있는 끈덕지가 생긴다.

후속 사수님 Slack 지시 (2026-05-26): supported_models 페이지의 **3개 카테고리**만 매칭 대상으로 사용한다:
- Decoder-only Models (Text Generation)
- Pooling Models
- Planned Models for Future Releases

이 3개 카테고리에 포함되지 않는 모델들의 자료는 찾지 않는다.

**온프레미스 기업, CSP(클라우드 서비스 공급 기업)에서 제공하는 클라우드 서비스를 이용하는 기업들은  1. 지원 모델: https://developer.furiosa.ai/latest/en/overview/supported_models.html 본문에 지원 모델 3개 카테고리 중 하나가 명시되지 않으면 후보에서 제외한다.**

---

## 4. 핏에 맞는 회사 vs 핏에 안 맞는 회사

핏에 맞는 회사인지 안 맞는지 sorting을 정확히 하려면 그들과 미팅을 해봐야 알 수 있다. 그러나 미팅 없이도, 우리 뜻에 맞고 **단기적·중기적으로 협업 가능**할 것으로 추정되는 회사들을 에이전트가 찾아주는 것이 목표다.

---

## 5. 의사결정자 정보 (LinkedIn 포함)

LinkedIn 같은 데서 검색해서, **이 사업을 engage 할 수 있기 위한 담당자의 LinkedIn 계정 주소**를 리포트에 넣으면 좋다.

여기서 말하는 담당자는 **의사결정자**다. 의사결정을 할 수 있는 사람을 만나야 그 사람이 우리 제품을 사게끔 할 수 있다. 우리 입장에서는 의사결정을 하실 수 있는 분이 중요하다. **우리 제품을 도입할 수 있는 의사결정을 할 수 있는 담당자를 찾아야 한다.**

---

## 6. 리포트에서 빼야 할 것 / 표시 방식

- 리포트에서 '제외 기사' 같은 건 빼도 된다. **보는 사람 입장에서 필요한 내용만 들어가면 된다.**
- Jira는 **연동은 시켜놓되, 리포트에는 Jira를 굳이 언급하지 말고** 해당 기업이 실제 우리 고객 파이프라인에 있는지 확인하기 위한 용도로만 활용한다. 예: 해당 기업이 Jira의 DMD 딜을 보니 엘리스와 접점이 있으면, **`기존접점: 엘리스 ✅`** 처럼 간단히 표시해도 된다.

---

## 7. 온프레미스에 국한하지 않는다 (클라우드도 포함)

온프레미스에만 집중할 필요는 없다. 온프레미스도 중요하지만, **클라우드 형태로 NPU를 활용하는 고객들**도 있다. 그리고 우리 RNGD는 곧 **삼성 SDS에서 NPUaaS를 7월에 출시할 계획**이다. 우리 회사 NPU 제품인 RNGD(레니게이드)를 쓴다. 그러면 온프레미스를 원하지 않고 클라우드 환경에서만 NPU를 쓰고 싶은 고객들에게는 NPUaaS 쪽으로 유도할 수 있다. 그렇게 컨택할 기업들을 찾아주는 에이전트가 구현되기를 원한다. **온프레미스에 국한할 필요가 없다.**

가장 좋은 케이스: 고객이 AWS·MS Azure·구글 클라우드를 쓰고 있는 게 아니라 **원래 삼성 SDS의 SCP(Samsung Cloud Platform)를 쓰고 있는 고객**이 있다. GPU든 뭐든 그런 클라우드를 쓰고 있는 고객은, AI 추론 서비스가 필요하면 자연스럽게 삼성 SDS 클라우드 위에서 우리 제품을 돌리면 된다. 그런 케이스의 기업들도 조사해서 포함되게 한다.

---

## 8. CSP 운영사 대상 영업 컨셉

클라우드 플랫폼 기업이 데이터센터에서 GPU를 가지고 있다면, 그 위에 서비스를 만들 수 있다. 그게 추론(Inference) 서비스라면, 클라우드 플랫폼 입장에서는 굳이 GPU가 필요 없고 NPU가 필요할 수도 있으니, 그렇게 유도해야 한다.

원래 GPU는 클라우드 플랫폼사에서 홍보하는 게 맞다. 그런데 NPU는 레퍼런스가 많지 않아서, CSP(클라우드 서비스 제공사) 입장에서는 "과연 NPU를 쓰는 게 맞을까?" 의문이 있다. 그래서 **그들 대신 우리가 고객을 대신 찾아준다**. 찾아서 거기에 꽂아준다. 그러면 그 CSP는 "NPU가 시장성이 별로 없다고 생각했는데 고객들이 나타나기 시작했으니 우리도 NPU 인프라를 확장해야겠다"라고 생각하게 되고, 우리는 그 클라우드 업체한테 **서버를 더 팔 수 있다.**

만약 CSP에 처음 서버를 팔았는데 NPU를 아무도 안 쓰면, 삼성SDS 같은 CSP 입장에서는 당연히 추가로 우리 제품을 안 산다. 서버실이 없는 고객 입장에서는 클라우드 서비스에 들어가 있지 않는 이상 우리 제품을 쓸 수 없다. 우리가 클라우드 서비스에 들어가 있고 그 위에서 활용할 수 있게 만드는 게 핵심.

현재 우리 회사는 삼성 외에 다른 클라우드 서버 파트너는 사실상 아직 더 없다. 엘리스라는 곳이 있긴 한데 정부 사업만 하고 있다.

---

## 9. 경쟁사 동향

주간 리포트에는 우리가 영업하기 좋은 회사들을 찾는 것이 메인이지만, **경쟁사 현황 체크**도 같이 하면 좋다. 경쟁사가 지금 어떤 사업을 수주했는지, 어떤 고객과 engage 하고 있는지, 어떻게 업데이트가 됐는지 등은 기사에서 다 나온다.

**경쟁사 관련 포함/제외 기준:**
- ❌ 경쟁사가 투자를 받았다 같은 내용은 **필요 없다**
- ✅ Go-to-market 관점에서 **경쟁사가 지금 하고 있는 것·성취한 것** 정리

성취의 예: 경쟁사가 KT 클라우드 같은 CSP와 손잡고 NPUaaS를 출시할 거라는 기사가 나오면, 그게 성취다. 이미 이뤘거나, 논의 중이거나, 파트너십을 체결했거나, 어떤 고객에게 납품했거나 — 그들의 GTM 활동 중 우리가 참고할 만한 것들.

---

## 10. 리포트에 들어가야 할 것 — engage 핏 근거 + Win-Win + 매출 시나리오

리포트에는 다음이 있어야 한다:
- 우리 입장에서 어떤 프로젝트·고객사·사업에 engage 핏이 맞는 **이유**
- 우리가 **단기적·중기적·장기적**으로 engage 하면 매출을 창출할 수 있는 이유

예: 국방부를 예로 들면, **왜 단기적·중기적으로 이 프로젝트에 관심을 가져야 하는지**, 어떻게 하면 이 프로젝트가 우리 입장에서 **단기적인 매출 창출 기회**가 되는지를 명시.

**Win-Win 2가지 표시:**
우리는 고객 기업에게 "너네가 우리를 써야지 이익이다"라는 것을 제안해야 한다. 따라서:
- **고객도 win인 이유**
- **우리도 win인 이유**

이 **2가지 윈 이유**가 같이 표시되어야 한다.

---

## 11. 리포트 두 버전 비교

- **버전 1: B2B만** (네이버, RSS)
- **버전 2: B2B + B2G** (네이버, RSS, 나라장터)

두 가지를 만들어서 더 나은 쪽을 사수님이 선택한다. 지금 보고 싶은 건 **B2B에 더 마음이 가지만 일단 둘 다 보고 싶어하신다**.

---

## 12. 나라장터 활용 — 발주처 vs SI 사업자

나라장터에는 입찰 정보·제안서가 다 올라와 있다. 이를 보고 실제로 **SI(System Integrator) 하시는 분**이 붙어서 "우리가 이걸 할 수 있어요" 하면서 수주를 따는 구조다.

예: 가상의 예시를 들어보면 AI CCTV 전환은 울산·경남·한국도로공사에서 전환할 필요가 있다는 수요를 갖고 있고, 그들의 Requirement에 따라 AI 시스템으로 어떻게 전환할지는 SI 사업자가 검토해서 발주처에 솔루션을 갖고 오는 컨셉. 발주처는 "너네가 깔아주면 거기에 대한 돈을 줄게"라고 한다.

즉 조달청에서 올리는 공고는 **국가 사업을 실제로 실행할 수 있는 사업자(SI)를 잡는** 것이고, **그 사업자들이 사업을 실현시키기 위해 working** 한다. **우리가 영업할 대상은 발주처가 아니라 그 SI 사업자**다.

**공고 검색 정밀도:**
NPU로 검색하면 "NPU 센터" 같은 공고가 나오는데, 우리랑 관련이 있어 보이지만 내용을 뜯어보면 무조건 관련이 있는 게 아니라 타당성 조사 및 기본 계획 수립 기획 영역이라면서 우리랑 관련이 없는 경우도 있었다. 우리가 타당성 조사를 하지는 않는다. **타당성 조사를 할 사람을 찾는 공고**는 우리 영역이 아니다.

---

---

## 13. 사수님 어조에서 도출되는 추가 원칙들

- **하드코딩 금지**: "검색 쿼리가 가장 중요한데, 하드코딩하면 안 된다"고 명시. 모델 리스트가 SDK 업데이트마다 변하므로, 매 실행마다 동적으로 가져와야 한다.
- **사람보다 에이전트가 알아서**: "에이전트가 알아서 찾아가지고 그래서 우리한테 그거를 리포트를 주는 거죠."
- **플랜 = 프롬프트**: 플랜이 곧 프롬프트가 되는 구조. 플랜을 잘 짜야 결과가 잘 나온다.

---

## 사용 안내 (이 파일이 LLM에 어떻게 들어가는지)

이 파일 전체는 새 통합 LLM 호출(integrated_evaluator)의 **시스템 컨텍스트**로 들어간다. 매 실행마다 LLM이 이 요구사항을 읽고:
1. 기사 본문에서 우리 핏에 맞는 회사를 직접 판단
2. 경쟁사 락인 케이스 자동 detect → 경쟁사 동향으로 분류
3. SI vs 발주처 구분
4. Win-Win + 단/중/장기 매출 시나리오 작성
5. 의사결정자 정보 탐색

**보안 가드**: 이 파일의 내용은 LLM 사고용. 리포트 본문에 **직접 인용 금지**
"""

    # 6단계: 제미나이를 독립적으로 2번 호출하여 완벽하게 구분된 문서 생성
    print("🎨 [Step 5] 버전별 맞춤형 보고서 작성 및 파일 분리 저장 중...")
    
    # 버전 1: B2B 전용 리포트 요구사항 전달
    prompt_v1 = (
        f"{SUPERVISOR_PROMPT}\n\n"
        f"[실시간 연동 데이터]\n"
        f"- 퓨리오사 기술 컨텍스트: {furiosa_context}\n"
        f"- 시장 뉴스 데이터: {market_raw_data}\n"
        f"- 내부 파이프라인 맥락: {jira_context}\n\n"
        f"**지시사항**: 조달청 및 나라장터(B2G) 공고 데이터는 완벽히 무시하고, "
        f"순수 민간 엔터프라이즈 및 클라우드(B2B) 대상 '버전 1: B2B GTM 리서치 리포트'만 가독성 높은 HTML 양식으로 본문만 출력해라."
    )
    report_v1 = model.generate_content(prompt_v1).text.replace("```html", "").replace("```", "").strip()

    # 버전 2: B2B + B2G 통합 리포트 요구사항 전달
    prompt_v2 = (
        f"{SUPERVISOR_PROMPT}\n\n"
        f"[실시간 연동 데이터]\n"
        f"- 퓨리오사 기술 컨텍스트: {furiosa_context}\n"
        f"- 시장 뉴스 데이터: {market_raw_data}\n"
        f"- 나라장터 공고 데이터: {b2g_raw_data}\n"
        f"- 내부 파이프라인 맥락: {jira_context}\n\n"
        f"**지시사항**: 민간 B2B 세일즈 전략과 더불어 나라장터 공고를 바탕으로 발주처가 아닌 'SI 사업자'를 "
        f"영업 타겟으로 잡는 매출 시나리오를 포함해 '버전 2: B2B+B2G 통합 GTM 리서치 리포트'를 가독성 높은 HTML 양식으로 본문만 출력해라."
    )
    report_v2 = model.generate_content(prompt_v2).text.replace("```html", "").replace("```", "").strip()

    # 7단계: 출력 폴더 및 파일 생성 (메인 대시보드 + 개별 페이지 2개)
    os.makedirs("reports", exist_ok=True)
    
    index_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>FuriosaAI GTM 리서치 에이전트 대시보드</title>
        <style>
            body {{ font-family: 'Malgun Gothic', sans-serif; text-align: center; padding-top: 80px; background-color: #f8f9fa; color: #333; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
            h1 {{ color: #003366; margin-bottom: 10px; }}
            .time {{ color: #666; font-size: 0.9em; margin-bottom: 40px; }}
            .btn {{ display: inline-block; width: 260px; padding: 18px; margin: 15px; text-decoration: none; color: white; font-weight: bold; border-radius: 8px; transition: all 0.2s; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            .btn-b2b {{ background-color: #0056b3; }}
            .btn-b2b:hover {{ background-color: #004085; transform: translateY(-2px); }}
            .btn-integrated {{ background-color: #28a745; }}
            .btn-integrated:hover {{ background-color: #1e7e34; transform: translateY(-2px); }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 FuriosaAI GTM Research Agent</h1>
            <div class="time">최근 자동 리서치 수행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
            <p style="font-size: 1.1em; color: #444; margin-bottom: 30px;">원하시는 리포트 버전을 선택하시면 전용 분석 페이지로 이동합니다.</p>
            <a href="b2b.html" class="btn btn-b2b">버전 1: B2B 전용 리포트 보기</a>
            <a href="b2b_b2g.html" class="btn btn-integrated">버전 2: B2B + B2G 리포트 보기</a>
        </div>
    </body>
    </html>
    """
    
    # 개별 파일 영구 저장
    with open("reports/index.html", "w", encoding="utf-8") as f: f.write(index_html)
    with open("reports/b2b.html", "w", encoding="utf-8") as f: f.write(report_v1)
    with open("reports/b2b_b2g.html", "w", encoding="utf-8") as f: f.write(report_v2)
    
    print("✅ [성공] 독립된 2종의 리포트 및 대시보드(index.html) 빌드가 완료되었습니다.")

if __name__ == "__main__":
    main()
