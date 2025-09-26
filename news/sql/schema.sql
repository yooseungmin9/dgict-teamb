drop table popular_news;
CREATE TABLE POPULAR_NEWS (
                              NEWS_ID        NUMBER(10)      PRIMARY KEY,              -- 뉴스 고유 ID (시퀀스로 관리)
                              RANKING        NUMBER(2)       NOT NULL,                 -- 순위 (1~5)
                              TITLE          VARCHAR2(500)   NOT NULL,                 -- 뉴스 제목
                              SUMMARY        VARCHAR2(2000),                           -- 요약 (RAG 검색용)
                              CONTENT        CLOB            NOT NULL,                 -- 뉴스 전문 (스크래핑한 본문)
                              URL            VARCHAR2(1000)  NOT NULL,                 -- 원본 기사 링크
                              VIEW_COUNT     NUMBER(12),                               -- 조회수 (집계된 값)
                              PUBLISHED_AT   DATE,                                     -- 기사 원문 발행일
                              COLLECTED_AT   DATE          DEFAULT SYSDATE NOT NULL    -- 수집/저장 시각
);
describe popular_news;
CREATE SEQUENCE SEQ_NEWS_ID
    START WITH 1
    INCREMENT BY 1
    NOCACHE
    NOCYCLE;

-- 1위
INSERT INTO POPULAR_NEWS
(NEWS_ID, RANKING, TITLE, SUMMARY, CONTENT, URL, VIEW_COUNT, PUBLISHED_AT)
VALUES
    (SEQ_NEWS_ID.NEXTVAL,
     1,
     '삼성전자 주가 급등, 연중 최고치 기록',
     '삼성전자가 외국인 매수세에 힘입어 장중 5% 이상 급등하며 연중 최고치를 경신했다.',
     '삼성전자가 9월 24일 장중 한때 5% 이상 상승하며 연중 최고치를 기록했다.
     외국인 투자자들이 대거 매수에 나서면서 거래량도 평소보다 2배 이상 급증했다.
     증권가에서는 반도체 업황 회복과 인공지능 서버 수요 증가가 긍정적으로 작용했다고 분석했다.
     전문가들은 단기적인 조정 가능성은 있지만 장기적으로 상승세가 이어질 것이라는 전망을 내놓았다.',
     'https://news.example.com/1',
     123450,
     TO_DATE('2025-09-24','YYYY-MM-DD'));

-- 2위
INSERT INTO POPULAR_NEWS
(NEWS_ID, RANKING, TITLE, SUMMARY, CONTENT, URL, VIEW_COUNT, PUBLISHED_AT)
VALUES
    (SEQ_NEWS_ID.NEXTVAL,
     2,
     '코스피 지수 3,500선 돌파',
     '기관과 외국인 동반 매수세로 코스피 지수가 3,500선을 돌파했다.',
     '코스피 지수가 23일 장 마감 기준 3,510.25를 기록하며 3,500선을 돌파했다.
     이는 지난 2년 3개월 만에 처음 있는 일이다.
     기관과 외국인이 동시에 매수에 나서면서 지수 상승을 견인했다.
     반면 개인 투자자들은 차익 실현 매도세를 보였다.
     증권사들은 글로벌 경기 둔화에도 불구하고 반도체, 2차전지 업종의 호조가 국내 시장을 떠받치고 있다고 평가했다.',
     'https://news.example.com/2',
     110320,
     TO_DATE('2025-09-24','YYYY-MM-DD'));

-- 3위
INSERT INTO POPULAR_NEWS
(NEWS_ID, RANKING, TITLE, SUMMARY, CONTENT, URL, VIEW_COUNT, PUBLISHED_AT)
VALUES
    (SEQ_NEWS_ID.NEXTVAL,
     3,
     '원·달러 환율 1,320원대 하락',
     '달러 약세와 외국인 자금 유입으로 원·달러 환율이 1,320원대로 떨어졌다.',
     '원·달러 환율이 24일 장중 한때 1,327.5원을 기록하며 3개월 만에 최저치를 나타냈다.
     최근 미국 연준의 금리 동결 기조와 달러 약세가 맞물리며 원화 강세 요인으로 작용했다.
     또한 국내 증시에 외국인 투자자금이 유입되면서 환율 하락을 가속화했다.
     전문가들은 단기적으로 1,310원까지 하락할 가능성도 배제할 수 없다고 전망했다.',
     'https://news.example.com/3',
     87450,
     TO_DATE('2025-09-24','YYYY-MM-DD'));

-- 4위
INSERT INTO POPULAR_NEWS
(NEWS_ID, RANKING, TITLE, SUMMARY, CONTENT, URL, VIEW_COUNT, PUBLISHED_AT)
VALUES
    (SEQ_NEWS_ID.NEXTVAL,
     4,
     '정부, 전기차 충전 인프라 확대 계획 발표',
     '정부가 2030년까지 전국에 전기차 충전소 30만 기를 구축하겠다고 밝혔다.',
     '산업통상자원부는 24일 기자회견을 통해 2030년까지 전국에 전기차 충전소 30만 기를 설치하겠다는 계획을 발표했다.
     현재 20만 대 수준인 전기차 보급 대수가 2030년에는 500만 대를 넘어설 것으로 예상되기 때문이다.
     정부는 민간 기업과 협력해 충전기 보급 확대와 함께 충전 속도 개선 기술 개발에도 투자할 계획이라고 전했다.',
     'https://news.example.com/4',
     65200,
     TO_DATE('2025-09-24','YYYY-MM-DD'));

-- 5위
INSERT INTO POPULAR_NEWS
(NEWS_ID, RANKING, TITLE, SUMMARY, CONTENT, URL, VIEW_COUNT, PUBLISHED_AT)
VALUES
    (SEQ_NEWS_ID.NEXTVAL,
     5,
     '국제유가, 공급 불안 우려로 급등',
     '중동 지역 정세 불안으로 국제유가가 배럴당 90달러를 돌파했다.',
     '국제유가가 24일 장중 배럴당 90.2달러를 기록하며 급등세를 보였다.
     최근 중동 지역의 지정학적 리스크가 확대되면서 원유 공급 차질에 대한 우려가 커졌기 때문이다.
     또한 주요 산유국들의 감산 정책이 지속되면서 유가 상승 압력이 더욱 커지고 있다.
     전문가들은 단기적으로 유가가 95달러까지 오를 수 있으며, 이는 글로벌 인플레이션에 영향을 줄 수 있다고 분석했다.',
     'https://news.example.com/5',
     59820,
     TO_DATE('2025-09-24','YYYY-MM-DD'));

select count(*) from POPULAR_NEWS;
select * from popular_news;
commit;