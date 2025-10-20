# 🧠 B팀 AI기반 경제 뉴스분석 프로젝트
**쉽고 빠르게 경제 뉴스의 흐름을 이해할 수 있는 AI기반 웹서비스**

---

## 📌 1. 프로젝트 개요
경제 뉴스를 효율적으로 분석하고, 핵심 이슈·감성 흐름을 한눈에 보여주는  
**AI 경제 뉴스 분석 웹서비스**를 개발했습니다.  
AI가 뉴스 요약·감성 분석·핫토픽 추출을 자동화하여  
사용자가 쉽고 빠르게 경제 트렌드를 이해할 수 있도록 돕습니다.

---

## 🎯 2. 목표
1. 팀 단위 협업으로 **AI 기반 경제 뉴스 분석 서비스 완성**  
2. 데이터–AI–웹 3파트 통합 아키텍처 구축  
3. 수집 → 분석 → 시각화 → 서비스화 전 과정 직접 구현  
4. 대시보드에서 경제 뉴스를 직관적으로 시각화  
5. 분석 결과를 **리포트+웹시연** 형태로 발표

---

## 🧾 3. 데이터 소스
| 출처 | 활용 내용 | 주요 컬럼 |
|------|------------|------------|
| NAVER News API | 경제 카테고리별 기사 수집 | 제목, 본문, 언론사, 발행일 |
| YouTube Data API | 경제 관련 영상 댓글·반응 분석 | 댓글, 좋아요 수, 감성 점수 |
| ECOS API, FRED API | 챗봇 실시간 경제 지표 |
| yfinance 라이브러리 | 챗봇 실시간 환율, 주가 |

---

## 📊 4. 분석 계획 및 시각화
| 분석 항목 | 설명 | 시각화 |
|------------|------|--------|
| 핫토픽 데이터랩 | 분야별 언급량 추이 | 시계열 그래프 |
| 키워드 랭킹 | 기간별 키워드 순위 및 급등 단어 | 순위 리스트 |
| 오늘의 핫토픽 | 실시간 인기 키워드 | 리스트 |
| 감성 분석 | 경제 뉴스의 긍·부정 추이 | 게이지 |
| 오피니언 마이닝 | 유튜브 댓글 감성 분석 | 파이차트 + 워드클라우드 |
| 기사 클러스터링 | GPT 기반 주제 라벨링 | 트리맵 |

---

## 💻 5. 웹 구성

### 🌐 대시보드
- 실시간 글로벌 경제 속보  
- 키워드 핫토픽 그래프 / 랭킹  
- 오늘의 감성 요약  
- 긍·부정 추이 그래프  
- 분석된 기사 개수  
- 유사 기사 클러스터  
- 유튜브 분석 요약  

### 📰 뉴스 요약
- 금일 주요 뉴스  
- 전일 브리핑 및 핵심 키워드  

### 🎥 유튜브 분석
- 댓글 감성 분석  
- 워드클라우드 시각화  

### 💬 챗봇
- GPT-5 기반 RAG 챗봇  
- STT/TTS 지원 (CLOVA, Google Cloud)

### 📚 추천/회원기능
- 경제 서적 및 영상 추천  
- 로그인·회원가입  
- 뉴스 검색

---

## 🧱 6. 기술 스택

| 영역 | 기술 |
|------|------|
| Frontend | HTML, CSS, JS, ToastUI Chart |
| Backend (Web) | Spring Boot (Java 17, Gradle 8.x) |
| Backend (AI/Data) | FastAPI, Python 3.10+, pandas, requests, transformers |
| DB | MongoDB Atlas |
| AI | OpenAI GPT-5, KoBART Summarizer, Custom Sentiment Dict |
| Infra | APScheduler, Google TTS, CLOVA STT |

---

## 📁 7. 폴더 구조

```
│
├── ① [수집 계층: Collect]
│     ├─  news_clawler.py        → 네이버 경제 뉴스 수집
│     ├─  youtube_crowler.py     → 유튜브 영상·댓글 수집
│     └─  MongoDB(test123)
│          ├─ shared_articles
│          ├─ youtube_db2
│          └─ youtube_comments
│
├── ② [전처리 계층: Preprocessing]
│     ├─ preprocess_pipeline_1.py
│     │    ├─ 텍스트 정제 / 불용어 제거(stopwords.txt)
│     │    ├─ TF-IDF + SBERT 임베딩
│     │    └─ 차원 축소(SVD) 후 저장
│     └─ 결과 → MongoDB(articles_preprocessed)
│
├── ③ [분석·클러스터링 계층: Analysis & Clustering]
│     ├─ cluster_pipeline_3.py     → UMAP + HDBSCAN 군집화
│     ├─ summarize.py              → 대표 기사·키워드 요약
│     ├─ label_gpt.py              → GPT 기반 이슈명(Label) 생성
│     ├─ attach_clusters_to_articles_2.py → 기사-클러스터 매핑
│     └─ 결과 → MongoDB(clusters)
│
├── ④ [트렌드·통계 계층: Trend & Statistics Layer]
│     ├─ emoa.py            → 감정 평균 변화 추이
│     ├─ headline.py        → 실시간 경제 헤드라인
│     ├─ count.py           → 카테고리별 뉴스 수량
│     ├─ category_trends.py → 네이버 데이터랩 검색 트렌드
│     └─ config.py          → API 키·카테고리 매핑 설정
│
├── ⑤ [추천 계층: Recommendation Layer]
│     ├─ youtube_api.py     → YouTube 영상 추천 (v3 API)
│     ├─ books_api.py       → 알라딘 도서 추천
│     ├─ book_db_save.py    → 추천 결과 DB 저장
│     └─ client.html        → 도서/영상 카드 UI
│
├── ⑥ [대시보드 계층: Visualization Layer]
│     ├─ senti_chart.py     → 감정 분포 그래프용 API
│     ├─ keywords.py        → 일간 키워드 Top-N
│     ├─ main.py            → FastAPI 템플릿 라우터
│     ├─ index.html         → Chart.js + WordCloud2.js UI
│     └─ index.js           → fetch + 렌더링 로직
│
├── ⑦ [AI 챗봇 계층: AI Assistant Layer]
│     ├─ chatbot.py
│     │    ├─ GPT-5 Function Calling
│     │    ├─ get_latest_news / get_indicator / get_market / search_docs
│     │    ├─ FRED, ECOS, yFinance, MongoDB, Vector Store 연동
│     ├─ watcher.py
│     │    └─ docs 폴더 실시간 감시 → RAG 문서 자동 업로드
│     └─ .vector_store_id, .vs_state.json → RAG 인덱스 상태
│     │ 
│     └─ chatbot_rag.py
│
├── ⑧ [Spring Boot BFF 계층: Backend For Frontend Layer]
│     ├─ Controller
│     │    ├─ YoutubeController.java  → FastAPI(8008)/videos 프록시
│     │    └─ AnalysisController.java → FastAPI(8008)/analysis 프록시
│     ├─ DTO
│     │    ├─ VideoDetailDto.java
│     │    ├─ VideoSummaryDto.java
│     │    ├─ AnalysisResponseDto.java
│     │    ├─ CommentItem.java
│     │    └─ WordItem.java
│     ├─ Domain
│     │    ├─ VideoDoc.java
│     │    └─ CommentDoc.java
│     └─ WebClient → FastAPI JSON 직렬화 후 프론트 전달
│
├── ⑨ [프론트엔드 계층: Dashboard & Interaction]
│     ├─ Thymeleaf 템플릿
│     │    └─ pages/youtube_opinion.html, dashboard.html 등
│     ├─ JS 모듈
│     │    ├─ sentiment.js / ticker.js / trands.js / emoa.js
│     │    └─ wordcloud2.js (시각화)
│     └─ Chart.js, Fetch API로 Spring `/api/...` 호출
│
└── ⑩ [데이터 저장소: MongoDB + OpenAI Vector Store]
      ├─ MongoDB Atlas
      │    ├─ shared_articles, youtube_db2, clusters, ...
      └─ OpenAI Vector Store (docs 기반 RAG 검색)
```

---

## 🔐 8. 환경 변수 (.env 예시)
```env
ECOS_API_KEY=VIU3HJ9GYAQ9P9OMDTCV
OPENAI_API_KEY=sk-xxxx
NAVER_CLIENT_ID=xxxx
NAVER_CLIENT_SECRET=xxxx
GOOGLE_APPLICATION_CREDENTIALS=./credentials.json
MONGO_URI=mongodb+srv://Dgict_TeamB:team1234@cluster0.mongodb.net/
```

---

## 👥 9. 팀 역할 분담
| 이름 | 담당 |
|------|------|
| **유승민** | 기획, 운영, 챗봇 |
| **유도현** | 백엔드, 키워드 랭킹, 추천, 로그인 |
| **윤유정** | 글로벌 뉴스, 감성요약, 기사 개수, 클러스터 |
| **장성진** | 웹크롤러, 뉴스요약, 오피니언 마이닝 |
| **정수현** | 프론트엔드 UI/UX 설계 및 구현 |

---

## 🗓️ 10. 일정
| 기간 | 주요 작업 |
|------|------------|
| 9/15–9/18 | 주제 확정, 데이터 소스 테스트 |
| 9/19–10/09 | DB·분석 파이프라인·UI·시각화 구현 |
| 10/10–10/14 | 발표자료 제작 |
| 10/15 | 최종 발표 |

---

## ✅ 11. 결과물
- 실행 가능한 로컬 웹 서비스  
- 발표 슬라이드 및 시연 스크립트

---

## 🪪 12. 라이선스
> 본 프로젝트는 교육 목적의 오픈소스 예시이며,  
> 향후 Apache 2.0 License 적용을 검토합니다.
