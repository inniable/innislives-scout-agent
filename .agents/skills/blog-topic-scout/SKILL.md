---
name: blog-topic-scout
description: innislives.tech 블로그를 위한 최신 AI·웹개발·클라우드·포괄적 테크 리뷰(우주항공·자동차·해양·하드웨어) 글감을 1차 공식 출처에서 수집하고 SEO/GEO 최적화 기획안과 마크다운(.md) 초안을 생성하는 리서치 에이전트 스킬입니다.
---

# innislives 블로그 소재 수집 & 기획 에이전트 (Blog Topic Scout)

사용자가 "블로그 글감 찾아줘", "오늘 쓸 주제 추천해줘", "최신 트렌드 수집해줘"라고 요청하면 다음 절차를 따르세요.

## 1. 기존 글 중복 확인
- `C:\project\innislives-blog\src\content\blog\` 폴더의 기존 `.md` 파일 목록과 제목을 확인하여 중복 주제를 제외합니다.

## 2. 4대 카테고리별 1차 공식 출처 우선 수집 (저작권 안전)
- **AI & 트렌드:** Google AI Blog, OpenAI, Anthropic
- **웹/앱 개발:** Astro Blog, GitHub Blog, 프론트엔드/모바일 프레임워크 공식 릴리즈
- **클라우드 & 인프라:** Cloudflare Blog, Vercel, 서버리스/엣지 인프라
- **테크 리뷰 (포괄적 첨단 테크):** NVIDIA Newsroom, MIT Tech Review, **우주항공**(NASA, SpaceNews), **자동차·모빌리티**(Electrek, EV·자율주행), **해양·조선·해양공학**(gCaptain, MarineLink)

## 3. 출력 규격 (글감 추천 브리핑)
4대 카테고리에 균형 있게 맞춘 **TOP 5 글감**을 아래 형식으로 제안합니다:
1. 추천 카테고리 & SEO 제목
2. 핵심 타깃 검색 키워드
3. 핵심 팩트 3줄 요약 (1차 공식 출처 URL 필수)
4. H2/H3 목차 초안
5. 사용자가 번호를 선택하면 즉시 `innislives-blog` 스키마(`title`, `description`, `pubDate`, `category`, `tags`, `tldr`, `faq`)에 맞춘 완성 `.md` 포스트를 작성합니다.
