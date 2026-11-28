"""
Google Search Console (GSC) API 기반 주간 키워드 성과 자동 분석 및 모니터링 스크립트
- 최근 7일간의 검색 키워드(Query), 페이지별 노출수, 클릭수, 평균 순위 수집
- 11위~20위(2페이지 상단)의 1페이지 진입 유망 Quick-Win 키워드 자동 분류
- 주간 성과 보고서 Markdown 생성 및 GitHub Issue 자동 등록
"""

import os
import json
import sys
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
import requests

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "inniable/innislives-scout-agent")
CREDENTIALS_JSON = os.environ.get("GSC_CREDENTIALS_JSON")
EXPLICIT_SITE_URL = os.environ.get("GSC_SITE_URL")


def get_gsc_service():
    """GCP 서비스 계정 인증 및 Search Console API 클라이언트 빌드"""
    if not CREDENTIALS_JSON:
        print("[ERROR] 환경변수 GSC_CREDENTIALS_JSON이 설정되지 않았습니다.")
        sys.exit(1)

    try:
        cred_dict = json.loads(CREDENTIALS_JSON)
    except Exception as e:
        print(f"[ERROR] GSC_CREDENTIALS_JSON 파싱 실패: {e}")
        sys.exit(1)

    credentials = service_account.Credentials.from_service_account_info(
        cred_dict,
        scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
    )
    return build("searchconsole", "v1", credentials=credentials)


def determine_target_site(service):
    """서비스 계정이 접근 가능한 사이트 목록 조회 및 자동 매핑"""
    if EXPLICIT_SITE_URL:
        print(f"[INFO] 지정된 사이트 URL 사용: {EXPLICIT_SITE_URL}")
        return EXPLICIT_SITE_URL

    try:
        sites_res = service.sites().list().execute()
        site_entries = sites_res.get("siteEntry", [])
        print(f"[INFO] 접근 가능한 사이트 목록: {[s.get('siteUrl') for s in site_entries]}")

        # innislives 관련 사이트 우선 탐색
        for s in site_entries:
            url = s.get("siteUrl", "")
            if "innislives" in url:
                print(f"[INFO] 타겟 사이트 자동 감지: {url}")
                return url

        if site_entries:
            chosen = site_entries[0].get("siteUrl")
            print(f"[INFO] 첫 번째 사이트 선택: {chosen}")
            return chosen
    except Exception as e:
        print(f"[WARN] 사이트 목록 자동 조회 실패 ({e}), 기본 URL로 진행합니다.")

    # 기본값 (도메인 속성 또는 URL 접두사)
    return "sc-domain:innislives.tech"


def fetch_search_analytics(service, site_url):
    """최근 7일 검색 실적 데이터 조회 (GSC API 기준 3일 전 ~ 10일 전)"""
    end_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")

    print(f"[INFO] 데이터 조회 기간: {start_date} ~ {end_date} (Site: {site_url})")

    request_body = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": ["query", "page"],
        "rowLimit": 2000,
        "dataState": "final"
    }

    try:
        res = service.searchanalytics().query(siteUrl=site_url, body=request_body).execute()
        return res.get("rows", []), start_date, end_date
    except Exception as e:
        print(f"[ERROR] Search Analytics 쿼리 실패: {e}")
        # 혹시 도메인 속성(sc-domain:) 또는 URL(https://) 형식 차이일 경우 대비
        alt_url = "https://innislives.tech/" if "sc-domain" in site_url else "sc-domain:innislives.tech"
        print(f"[INFO] 대체 URL ({alt_url})로 재시도합니다...")
        try:
            res = service.searchanalytics().query(siteUrl=alt_url, body=request_body).execute()
            return res.get("rows", []), start_date, end_date
        except Exception as e2:
            print(f"[ERROR] 대체 URL 쿼리도 실패: {e2}")
            return [], start_date, end_date


def analyze_keywords(rows):
    """키워드 성과 분류: Top 10, Quick-Win(11~20위), CTR 개선 대상"""
    top_performers = []
    quick_wins = []
    low_ctr_targets = []
    total_clicks = 0
    total_impressions = 0

    for r in rows:
        query = r["keys"][0]
        full_page = r["keys"][1]
        page_slug = full_page.replace("https://innislives.tech/blog/", "").replace("https://innislives.com/blog/", "").rstrip("/")
        
        clicks = int(r.get("clicks", 0))
        impressions = int(r.get("impressions", 0))
        ctr = round(float(r.get("ctr", 0)) * 100, 2)
        position = round(float(r.get("position", 0)), 1)

        total_clicks += clicks
        total_impressions += impressions

        item = {
            "query": query,
            "page": page_slug,
            "clicks": clicks,
            "impressions": impressions,
            "ctr": ctr,
            "position": position
        }

        # 1. Top 클릭 유입 키워드 (1위 ~ 10위권 내)
        if position <= 10.5 and clicks > 0:
            top_performers.append(item)

        # 2. Quick-Win 키워드 (11위 ~ 20위 사이, 노출 1회 이상)
        elif 10.5 < position <= 20.0:
            quick_wins.append(item)

        # 3. 노출은 높은데 클릭률이 2% 미만인 키워드
        if impressions >= 10 and ctr < 2.0:
            low_ctr_targets.append(item)

    # 정렬
    top_performers.sort(key=lambda x: (x["clicks"], x["impressions"]), reverse=True)
    quick_wins.sort(key=lambda x: (x["impressions"], -x["position"]), reverse=True)
    low_ctr_targets.sort(key=lambda x: x["impressions"], reverse=True)

    summary = {
        "total_queries": len(rows),
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "avg_ctr": round((total_clicks / total_impressions * 100), 2) if total_impressions > 0 else 0
    }

    return top_performers[:15], quick_wins[:15], low_ctr_targets[:10], summary


def build_markdown_report(top_10, quick_wins, low_ctr, summary, start_date, end_date):
    """GitHub Issue 및 아카이빙용 마크다운 보고서 구성"""
    md = [
        f"# 📊 주간 SEO & GEO 검색 키워드 성과 보고서 ({start_date} ~ {end_date})",
        "",
        "> Google Search Console API로부터 수집된 최근 7일간의 실제 유입 쿼리 분석 데이터입니다.",
        "",
        "### 📈 주간 종합 지표 요약",
        f"- **총 유입 쿼리 수**: `{summary['total_queries']:,}개`",
        f"- **총 검색 노출수(Impressions)**: `{summary['total_impressions']:,}회`",
        f"- **총 검색 클릭수(Clicks)**: `{summary['total_clicks']:,}회`",
        f"- **평균 클릭률(CTR)**: `{summary['avg_ctr']}%`",
        "",
        "---",
        "",
        "## 🎯 1. 1페이지 진입 유망주 (Quick-Win 키워드: 11위 ~ 20위)",
        "구글 검색 2페이지 상단에 걸쳐 있는 키워드입니다. 해당 포스트의 본문 내용과 소제목에 해당 키워드를 1~2회 추가 배치하면 1페이지(Top 10) 진입으로 클릭수가 급증할 수 있습니다.",
        ""
    ]

    if quick_wins:
        md.append("| 검색 쿼리 (Query) | 관련 포스트 | 평균 순위 | 노출수 | 클릭수 | CTR |")
        md.append("| :--- | :--- | :---: | :---: | :---: | :---: |")
        for q in quick_wins:
            md.append(f"| **`{q['query']}`** | `{q['page']}` | **{q['position']}위** | {q['impressions']}회 | {q['clicks']}회 | {q['ctr']}% |")
    else:
        md.append("_현재 11~20위권에 진입한 대기 키워드가 없습니다. 꾸준한 신규 포스팅으로 노출 범위를 넓혀가세요._")

    md.extend([
        "",
        "---",
        "",
        "## 🏆 2. Top 클릭 견인 핵심 키워드 (Top 10 진입군)",
        ""
    ])

    if top_10:
        md.append("| 검색 쿼리 (Query) | 관련 포스트 | 평균 순위 | 클릭수 | 노출수 | CTR |")
        md.append("| :--- | :--- | :---: | :---: | :---: | :---: |")
        for q in top_10:
            md.append(f"| **`{q['query']}`** | `{q['page']}` | {q['position']}위 | **{q['clicks']}회** | {q['impressions']}회 | {q['ctr']}% |")
    else:
        md.append("_현재 Top 10 순위 내에서 유의미한 클릭이 발생한 키워드가 아직 없습니다._")

    md.extend([
        "",
        "---",
        "",
        "## 💡 3. 제목 & 메타 설명 개선 추천 (노출多, 클릭률 < 2%)",
        "구글 검색 결과창에는 자주 노출되지만 사용자가 클릭하지 않는 글입니다. 제목(Title)에 궁금증을 유발하는 문구나 숫자를 추가하는 것을 추천합니다.",
        ""
    ])

    if low_ctr:
        md.append("| 검색 쿼리 (Query) | 관련 포스트 | 노출수 | CTR | 평균 순위 | 최적화 팁 |")
        md.append("| :--- | :--- | :---: | :---: | :---: | :--- |")
        for q in low_ctr:
            md.append(f"| `{q['query']}` | `{q['page']}` | {q['impressions']}회 | {q['ctr']}% | {q['position']}위 | 제목에 매력적인 헤드라인 또는 핵심 숫자 반영 |")
    else:
        md.append("_클릭률 개선이 시급한 저효율 키워드가 없습니다._")

    return "\n".join(md)


def create_github_issue(title, body):
    """GitHub Issue 자동 생성"""
    if not GITHUB_TOKEN:
        print("[INFO] GITHUB_TOKEN 없음 - 로컬 테스트 모드로 Issue 발행을 건너뜁니다.")
        return

    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "title": title,
        "body": body,
        "labels": ["seo-report", "analytics"]
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code == 201:
            print(f"[SUCCESS] 주간 SEO 보고서 GitHub Issue 발행 성공: {res.json().get('html_url')}")
        else:
            print(f"[WARN] GitHub Issue 등록 응답 코드: {res.status_code} ({res.text})")
    except Exception as e:
        print(f"[ERROR] GitHub Issue 등록 실패: {e}")


def main():
    print("[1/4] Google Search Console API 서비스 초기화 중...")
    service = get_gsc_service()

    print("[2/4] 대상 블로그 사이트 확인 중...")
    site_url = determine_target_site(service)

    print("[3/4] 최근 7일간 검색 실적 쿼리 수집 중...")
    rows, start_date, end_date = fetch_search_analytics(service, site_url)
    print(f"[INFO] 수집된 검색어 행 수: {len(rows)}개")

    print("[4/4] 키워드 성과 분석 및 리포트 작성 중...")
    top_10, quick_wins, low_ctr, summary = analyze_keywords(rows)
    report_md = build_markdown_report(top_10, quick_wins, low_ctr, summary, start_date, end_date)

    # 리포트 파일 아카이빙
    os.makedirs("reports", exist_ok=True)
    report_file = f"reports/{end_date}-weekly-seo.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"[SUCCESS] 보고서 파일 저장 완료: {report_file}")

    # GitHub Issue 등록
    issue_title = f"📊 [주간 SEO/GEO 리포트] 구글 검색 키워드 성과 분석 ({start_date} ~ {end_date})"
    create_github_issue(issue_title, report_md)


if __name__ == "__main__":
    main()
