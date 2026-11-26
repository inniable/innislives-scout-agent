"""
innislives-scout-agent
======================
Standalone automated blog topic scout & research agent for innislives.tech.
Collects fresh 1st-party tech/AI/web/cloud/aerospace/automotive/maritime news,
checks existing blog posts to avoid duplicates, and generates SEO/GEO topic
briefings using Gemini (`gemini-4-hydrogen` via official `google-genai` SDK).
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_args: Any, **_kwargs: Any) -> bool:
        return False

REPO_ROOT = Path(__file__).resolve().parent
IDEAS_DIR = REPO_ROOT / "ideas"
SOURCES_PATH = REPO_ROOT / "sources.json"
DEFAULT_BLOG_DIR = Path(os.environ.get("BLOG_CONTENT_DIR", r"C:\project\innislives-blog\src\content\blog"))
LIVE_BLOG_RSS_URL = os.environ.get("LIVE_BLOG_RSS_URL", "https://innislives.tech/rss.xml")

KST = timezone(timedelta(hours=9))

load_dotenv(REPO_ROOT / ".env")


def strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", text or "")
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def fetch_rss_items(source: dict[str, str], max_items: int = 4) -> list[dict[str, str]]:
    url = source["url"]
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; innislives-scout/1.0)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        },
    )
    items: list[dict[str, str]] = []
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)

        entries = root.findall(".//item")
        is_atom = False
        if not entries:
            entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
            is_atom = True

        for entry in entries[:max_items]:
            if is_atom:
                ns = "{http://www.w3.org/2005/Atom}"
                title = (entry.findtext(f"{ns}title") or "").strip()
                link_el = entry.find(f"{ns}link")
                link = (link_el.attrib.get("href", "") if link_el is not None else "").strip()
                summary = strip_html(
                    entry.findtext(f"{ns}summary") or entry.findtext(f"{ns}content") or ""
                )[:350]
                pub = (
                    entry.findtext(f"{ns}published") or entry.findtext(f"{ns}updated") or ""
                ).strip()
            else:
                title = (entry.findtext("title") or "").strip()
                link = (entry.findtext("link") or "").strip()
                summary = strip_html(entry.findtext("description") or "")[:350]
                pub = (entry.findtext("pubDate") or "").strip()

            if title and link:
                items.append(
                    {
                        "source": source["name"],
                        "category": source["category"],
                        "title": title,
                        "link": link,
                        "published": pub,
                        "summary": summary,
                    }
                )
    except Exception as exc:
        print(f"[WARN] Failed to fetch {source['name']} ({url}): {exc}")

    return items


def load_existing_blog_titles() -> list[str]:
    titles: list[str] = []
    seen: set[str] = set()

    # 1. Fetch live published posts from innislives.tech/rss.xml (works in GitHub Actions cloud)
    try:
        req = urllib.request.Request(
            LIVE_BLOG_RSS_URL,
            headers={"User-Agent": "Mozilla/5.0 (compatible; innislives-scout/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            root = ET.fromstring(resp.read())
        for item in root.findall(".//item"):
            t = (item.findtext("title") or "").strip()
            if t and t not in seen:
                seen.add(t)
                titles.append(t)
        print(f"[INFO] Loaded {len(titles)} published titles from {LIVE_BLOG_RSS_URL}")
    except Exception as exc:
        print(f"[WARN] Could not fetch live RSS titles ({exc}); checking local blog dir.")

    # 2. Also include local markdown files if available
    if DEFAULT_BLOG_DIR.exists():
        for md_file in sorted(DEFAULT_BLOG_DIR.glob("*.md")):
            try:
                text = md_file.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', text, re.MULTILINE)
                t = m.group(1).strip() if m else md_file.stem
                if t and t not in seen:
                    seen.add(t)
                    titles.append(t)
            except Exception:
                continue

    return titles


def load_previously_recommended_urls(today_str: str) -> set[str]:
    """Extracts source URLs already recommended in previous days' ideas/*.md files."""
    seen_urls: set[str] = set()
    if not IDEAS_DIR.exists():
        return seen_urls
    url_re = re.compile(r"https?://[^\s\)\]>\"']+")
    for md_file in sorted(IDEAS_DIR.glob("*-topics.md")):
        if md_file.name.startswith(today_str):
            continue
        try:
            text = md_file.read_text(encoding="utf-8", errors="ignore")
            # Only exclude URLs that appeared in the TOP 5 recommendation section (before extra links section)
            top_section = re.split(r"(?:추가|주요)\s*참고", text, maxsplit=1)[0]
            for u in url_re.findall(top_section):
                seen_urls.add(u.rstrip(".,;:/"))
        except Exception:
            continue
    return seen_urls


def build_fallback_markdown(today_str: str, collected: list[dict[str, str]]) -> str:
    lines = [
        f"# 🗞️ {today_str} 블로그 글감 자동 수집 리포트 (원문 요약)",
        "",
        f"> 총 {len(collected)}개의 최신 공식 소스 항목이 수집되었습니다. (`GEMINI_API_KEY`를 설정하면 AI SEO/GEO 기획안 TOP 5가 자동 생성됩니다.)",
        "",
    ]
    for idx, item in enumerate(collected, 1):
        lines.append(
            f"{idx}. **[{item['category']} · {item['source']}]** [{item['title']}]({item['link']})"
        )
        if item["summary"]:
            lines.append(f"   - {item['summary'][:180]}...")
    return "\n".join(lines) + "\n"


def generate_ai_briefing(
    today_str: str,
    collected: list[dict[str, str]],
    existing_titles: list[str],
    api_key: str,
) -> str:
    from google import genai

    client = genai.Client(api_key=api_key, http_options={"timeout": 30000})

    feed_lines = []
    for idx, item in enumerate(collected, 1):
        feed_lines.append(
            f"{idx}. [{item['category']} | {item['source']}] {item['title']}\n"
            f"   URL: {item['link']}\n"
            f"   Date: {item['published']}\n"
            f"   Summary: {item['summary']}"
        )

    existing_block = "\n".join(f"- {t}" for t in existing_titles) or "- (없음)"

    system_instruction = (
        "당신은 IT·AI 및 첨단 공학 전문 블로그 'innislives.tech'의 수석 콘텐츠 전략가이자 SEO/GEO 에디터입니다. "
        "수집된 1차 공식 출처 뉴스와 기술 블로그 목록을 분석해, 블로그의 4대 카테고리 "
        "('AI & 트렌드', '웹/앱 개발', '클라우드 & 인프라', '테크 리뷰 — 우주항공·자동차·모빌리티·해양·하드웨어 포함')에 "
        "균형 있게 맞춘 최고의 블로그 글감 TOP 5를 선별하고 즉시 글쓰기에 착수할 수 있는 기획안을 작성하세요."
    )

    prompt = f"""오늘 날짜: {today_str}

[이미 블로그에 발행된 기존 글 목록 (중복 주제 제외)]
{existing_block}

[오늘 수집된 최신 공식 소스 목록]
{chr(10).join(feed_lines)}

위 자료를 바탕으로 **오늘의 추천 블로그 글감 TOP 5**를 아래 마크다운 형식으로 작성해 주세요:

# 🗞️ {today_str} innislives 블로그 글감 추천 리포트 (TOP 5)

> 오늘 수집된 {len(collected)}개 공식 소스 중 중복을 제외하고 SEO·GEO 파급력이 가장 높은 5개 주제를 선별했습니다.

각 추천 글감(1번~5번)마다 반드시 아래 항목을 포함하세요:
- **추천 카테고리:** (`AI & 트렌드`, `웹/앱 개발`, `클라우드 & 인프라`, `테크 리뷰` 중 택1)
- **추천 SEO 제목 (클릭을 부르는 한글 제목):**
- **핵심 타깃 키워드 4~5개:** (주의: 키워드 안에 슬래시 `/` 문자 사용 금지 — Astro 태그 URL 오류 방지)
- **왜 지금 써야 하는가 (핵심 팩트 3줄 요약):**
- **추천 H2 목차 구성 (4~5단계):**
- **1차 공식 출처 링크:** (반드시 위 수집 목록에 있는 실제 URL 그대로 표기)

중복 방지 및 콘텐츠 믹스(뉴스 70% + 에버그린 30%) 필수 규칙:
- 위 [이미 블로그에 발행된 기존 글 목록]과 URL이 다르더라도, 최근 며칠 내 이미 다룬 **동일 사건·동일 이슈의 단순 후속 기사**는 TOP 5에서 제외하고 완전히 새로운 주제를 선정하세요.
- TOP 5 중 **1~4번은 최신 1차 공식 뉴스 심층 분석**으로 구성하되, **최소 1개(예: 2번 또는 4번)는 검색 수요가 오래 지속되는 '에버그린 실전 가이드·비교 분석·튜토리얼' 형태**(예: 설치·마이그레이션 가이드, 성능/아키텍처 비교, 오류 해결·실무 체크리스트)로 기획해 장기 자연 검색 유입(SEO)을 확보하세요.

마지막에는 오늘 수집된 나머지 주요 참고 링크 5~8개를 `### 🔗 오늘의 추가 참고 링크` 섹션 아래에 한 줄 목록으로 덧붙여 주세요.
"""

    model_candidates = [
        "gemini-3.5-flash-lite",
        "gemini-4-hydrogen",
        "gemini-3.1-flash-lite",
    ]
    last_exc: Exception | None = None
    for model_name in model_candidates:
        try:
            print(f"[INFO] Calling Gemini model: {model_name} ...")
            interaction = client.interactions.create(
                model=model_name,
                input=prompt,
                system_instruction=system_instruction,
                store=False,
            )
            if interaction.output_text:
                print(f"[INFO] AI Topic Briefing succeeded with {model_name}.")
                return interaction.output_text.strip() + "\n"
        except Exception as exc:
            last_exc = exc
            print(f"[WARN] Model {model_name} failed ({exc}); trying fallback model...")
            continue
    if last_exc:
        raise last_exc
    return build_fallback_markdown(today_str, collected)


def main() -> None:
    now_kst = datetime.now(KST)
    today_str = now_kst.strftime("%Y-%m-%d")

    cfg: dict[str, Any] = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    max_per_source = int(cfg.get("max_items_per_source", 4))
    sources: list[dict[str, str]] = cfg.get("sources", [])

    collected: list[dict[str, str]] = []
    for src in sources:
        items = fetch_rss_items(src, max_items=max_per_source)
        print(f"[INFO] {src['name']}: fetched {len(items)} items")
        collected.extend(items)

    prev_urls = load_previously_recommended_urls(today_str)
    if prev_urls:
        before_cnt = len(collected)
        collected = [
            item for item in collected
            if item["link"].rstrip(".,;:/") not in prev_urls
        ]
        print(f"[INFO] Hard-filtered {before_cnt - len(collected)} previously recommended URLs ({len(collected)} fresh items remain).")

    existing_titles = load_existing_blog_titles()
    api_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()

    if api_key and collected:
        print("[INFO] Generating AI Topic Briefing with gemini-4-hydrogen...")
        try:
            report_md = generate_ai_briefing(today_str, collected, existing_titles, api_key)
        except Exception as exc:
            print(f"[WARN] AI briefing failed ({exc}); using fallback report.")
            report_md = build_fallback_markdown(today_str, collected)
    else:
        print("[INFO] GEMINI_API_KEY not set; generating raw source briefing.")
        report_md = build_fallback_markdown(today_str, collected)

    IDEAS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = IDEAS_DIR / f"{today_str}-topics.md"
    out_file.write_text(report_md, encoding="utf-8")
    print(f"[SUCCESS] Saved topic briefing to: {out_file}")


if __name__ == "__main__":
    main()
