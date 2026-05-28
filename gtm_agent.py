import os
import sys
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

# --- 2. 데이터 수집 함수 (본문 및 실제 지라 전체 연동) ---

# [수정] 실제 Jira 데이터 무제한 연동 (하드코딩 제거)
def fetch_jira_data():
    print("📋 [Step 0] 실제 Jira 파이프라인 데이터 전체 연동 중...")
    if not JIRA_URL or not JIRA_EMAIL or not JIRA_API_TOKEN:
        return "Jira API 정보가 없어 파이프라인을 확인할 수 없습니다."
    try:
        jira_options = {'server': JIRA_URL}
        jira = JIRA(options=jira_options, basic_auth=(JIRA_EMAIL, JIRA_API_TOKEN))
        # maxResults=False를 통해 개수 제한 없이 파이프라인 전체 이슈를 다 가져옵니다.
        issues = jira.search_issues('ORDER BY updated DESC', maxResults=False)
        jira_text = f"Jira 파이프라인 전체 티켓 요약 (총 {len(issues)}개):\n"
        for issue in issues:
            jira_text += f"- [{issue.key}] {issue.fields.summary}\n"
        return jira_text
    except Exception as e:
        return f"Jira 연동 실패 (기존 파이프라인 데이터 확인 불가): {e}"

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
    print("🚀 [Step 1] 퓨리오사 공식 문서 실시간 Fetch 중...")
    for url in urls:
        try:
            res = requests.get(url, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            for s in soup(["script", "style"]): s.decompose()
            all_text += f"\n\n[출처: {url}]\n{soup.get_text(separator=' ', strip=True)}"
            time.sleep(0.1)
        except Exception as e:
            print(f"⚠️ {url} 수집 실패: {e}")
            sys.exit(1)
    return all_text

# [유지] 뉴스 기사 본문 전체 크롤링 함수
def fetch_full_article(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        for s in soup(["script", "style"]): s.decompose()
        # 기사 본문 텍스트만 추출해서 최대 3000자 반환
        text = soup.get_text(separator=' ', strip=True)
        return text[:3000]
    except:
        return "본문 크롤링 실패 (요약문으로 대체)"

# --- 3. 메인 자율 구동부 ---
def main():
    if not GEMINI_API_KEY:
        print("❌ 에러: GEMINI_API_KEY 누락")
        sys.exit(1)

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-3.1-flash-lite')

    # 데이터 수집 실행 (지라 무제한 + 퓨리오사 문서)
    jira_context = fetch_jira_data()
    furiosa_context = fetch_furiosa_docs()

    # 2단계: 최적의 검색 키워드 생성
    print("🧠 [Step 2] 검색 키워드 자율 생성 중...")
    query_gen_prompt = f"""
    아래 퓨리오사AI 문서에서 'Decoder-only Models', 'Pooling Models', 'Planned Models'를 분석해라.
    해당 모델명(버전 포함)들과 RNGD, NPUaaS를 도입할 성향이 높은 기업을 찾기 위한 검색 키워드 목록을 생성해.
    [문서]: {furiosa_context[:15000]}
    형식: 키워드1, 키워드2, 키워드3...
    """
    try:
        dynamic_queries = [q.strip() for q in model.generate_content(query_gen_prompt).text.strip().split(',') if q.strip()]
        print(f"✅ 생성된 쿼리: {dynamic_queries}")
    except Exception as e:
        print(f"❌ 검색어 생성 실패: {e}")
        sys.exit(1)

    # 3단계: B
