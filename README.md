# innislives-scout-agent

**innislives.tech** 블로그의 **자동 소재 수집 에이전트** 및 **대화형 리서치 에이전트** 전용 독립 프로젝트입니다.

## 주요 구성
- `scout_agent.py`: 4대 카테고리(AI & 트렌드, 웹/앱 개발, 클라우드 & 인프라, 테크 리뷰[우주항공·자동차·해양·하드웨어]) 13개 1차 공식 RSS에서 최신 글감을 수집하고, `gemini-4-hydrogen` 모델로 SEO/GEO 기획안 TOP 5를 생성해 `ideas/YYYY-MM-DD-topics.md`로 저장합니다.
- `sources.json`: 수집 대상 공식 RSS 소스 목록
- `.github/workflows/daily_scout.yml`: 매일 오전 08:00 KST 자동 수집 및 GitHub Issue 알림 발행 워크플로우
- `.agents/skills/blog-topic-scout/SKILL.md`: Antigravity 대화형 리서치 에이전트 전용 스킬
- `글감_수집_실행.bat`: Windows 원클릭 실행 배치 파일

## 사용 방법
1. `.env.example`을 복사해 `.env`로 만든 뒤 `GEMINI_API_KEY`를 입력합니다.
2. `pip install -r requirements.txt` 실행 후 `python scout_agent.py` (또는 `글감_수집_실행.bat` 더블클릭)로 실행합니다.
3. 별도 GitHub 저장소(`innislives-scout-agent`)에 푸시하고 Actions Secret에 `GEMINI_API_KEY`를 등록하면 매일 아침 8시 자동으로 글감 리포트가 생성됩니다.
