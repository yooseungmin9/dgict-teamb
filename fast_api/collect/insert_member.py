from pymongo import MongoClient
from pymongo.errors import BulkWriteError
import random, re
from datetime import datetime, timezone

MONGO_URI = "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/"
DB_NAME   = "test123"
COL_NAME  = "members"

TOTAL_USERS = 2000
BATCH = 500
PASSWORD = "test123"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
col = db[COL_NAME]

# 분포/가중치 (한글 키)
PARENT_WEIGHT = {
    "글로벌": 0.25,
    "금융": 0.18,
    "부동산": 0.22,
    "산업": 0.20,
    "주식": 0.12,
    "일반": 0.03,
}

SUB_WEIGHT = {
    "산업": {
        "반도체": 0.45,
        "전기차": 0.25,
        "로봇": 0.15,
        "AI인프라": 0.15,
    },
    "금융": {
        "금리": 0.40,
        "환율원자재": 0.25,
        "예금": 0.20,
        "대출": 0.10,
        "보험": 0.05,
    },
    "주식": {
        "기초": 0.40,
        "ETF": 0.25,
        "거래량": 0.20,
        "공모주": 0.10,
        "리츠": 0.05,
    },
    "글로벌": {
        "환율원자재": 0.35,
        "지정학공급망": 0.25,
        "미국": 0.20,
        "중국": 0.15,
        "국제기구": 0.05,
    },
    "부동산": {
        "가격": 0.30,
        "아파트": 0.25,
        "전세": 0.20,
        "청약": 0.15,
        "재건축": 0.05,
        "정책세금": 0.05,
    },
    "일반": {
        "거시기초": 0.35,
        "노동": 0.25,
        "소비": 0.20,
        "경기순환": 0.15,
        "가계부채": 0.05,
    },
}

# 설문 분포
MAIN_SOURCES_DIST = {"portal":0.42,"sns":0.28,"youtube":0.22,"ott":0.04,"pressSite":0.04}
PORTALS_DIST = {"Naver":0.72,"Daum":0.18,"Google":0.10}
SNS_DIST = {"Instagram":0.55,"X":0.30,"TikTok":0.15}
VIDEO_DIST = {"YouTube":0.85,"TikTok":0.15}
OTT_DIST = {"Netflix":0.75,"Tving":0.25}

REGION_DIST = {
    "서울":0.18,"부산":0.06,"대구":0.05,"인천":0.07,"광주":0.04,"대전":0.04,"울산":0.03,
    "경기":0.24,"강원":0.03,"충북":0.03,"충남":0.04,"전북":0.03,"전남":0.03,"경북":0.04,"경남":0.04,"제주":0.02
}
GENDER_DIST = {"남":0.49,"여":0.51}
AGE_DIST = {"1960-1969":0.13,"1970-1979":0.18,"1980-1989":0.24,"1990-1999":0.28,"2000-2005":0.17}

# 유틸
surnames = ["김","이","박","최","정","강","조","윤","장","임","오","한","신","서","권","황","안","송","류","홍"]
first_names = ["민","수","지","영","준","호","현","아","진","우","선","재","태","성","보","은","하","채","동","혁"]

# 램덤 이름 조합
def random_korean_name():
    return random.choice(surnames) + random.choice(first_names) + random.choice(first_names)

# 가중치를 부여한 값을 추출
def sample_from_dist(dist: dict, k=1, unique=True):
    labels, weights = zip(*dist.items())
    total = float(sum(weights)) or 1.0
    probs = [w/total for w in weights]
    if k == 1:
        return [random.choices(labels, probs, k=1)[0]]
    if unique:
        k = min(k, len(labels))
        scored = [(lbl, random.random()*(1.0/(probs[i]+1e-9))) for i,lbl in enumerate(labels)]
        scored.sort(key=lambda x:x[1])
        return [lbl for (lbl,_) in scored[:k]]
    return random.choices(labels, probs, k=k)

# 랜덤 출생년도
def sample_age_birth_year():
    bucket = sample_from_dist(AGE_DIST,1)[0]
    s,e = bucket.split("-")
    return random.randint(int(s), int(e))

# 램덤 연락처
def random_phone():
    return f"010-{random.randint(1000,9999)}-{random.randint(1000,9999)}"

# 관심사: interests / preferences
PARENTS = ["글로벌","금융","부동산","산업","주식","일반"]
SUBS = {
    "글로벌":["미국","중국","환율원자재","지정학공급망","국제기구"],
    "금융":["금리","대출","예금","보험","환율원자재"],
    "부동산":["가격","아파트","전세","청약","재건축","정책세금"],
    "산업":["반도체","전기차","로봇","AI인프라"],
    "주식":["기초","ETF","거래량","공모주","리츠"],
    "일반":["거시기초","소비","노동","경기순환","가계부채"]
}

# 내부 확률 0~1 정규화
def norm_weights(d: dict):
    tot = float(sum(v for v in d.values() if v>0))
    if tot<=0: return {k:1.0/len(d) for k in d}
    return {k:(max(0.0,v)/tot) for k,v in d.items()}

PARENT_WEIGHT_N = norm_weights(PARENT_WEIGHT)
SUB_WEIGHT_N = {p: norm_weights(SUB_WEIGHT.get(p,{s:1.0 for s in SUBS[p]})) for p in PARENTS}

# 관심사 필드 저장
def build_preferences_and_interests():
    explicit = {}
    interests_sum = {p:0 for p in PARENTS}

    for p in PARENTS:
        base = PARENT_WEIGHT_N[p]*12.0
        total_clicks = max(0, int(round(base + random.uniform(-2,3))))
        if total_clicks==0: continue
        submap = {}
        subs=list(SUB_WEIGHT_N[p].keys())
        weights=[SUB_WEIGHT_N[p][s] for s in subs]
        remain=total_clicks
        while remain>0:
            s=random.choices(subs,weights,k=1)[0]
            cur=submap.get(s,0)
            if cur<4:
                submap[s]=cur+1
                remain-=1
            elif all(submap.get(x,0)>=4 for x in subs):
                break
        if submap:
            explicit[p]=submap
            interests_sum[p]=sum(submap.values())

    implicit={}
    main_k=1 if random.random()<0.7 else 2
    mainSources=sample_from_dist(MAIN_SOURCES_DIST,k=main_k,unique=True)
    portals=[]
    if "portal" in mainSources:
        portal_k=1 if random.random()<0.8 else 2
        portals=sample_from_dist(PORTALS_DIST,k=portal_k,unique=True)
    sns_k=0 if random.random()<0.35 else (1 if random.random()<0.7 else 2)
    video_k=0 if random.random()<0.25 else 1
    ott_k=0 if random.random()<0.7 else 1
    sns=sample_from_dist(SNS_DIST,k=sns_k,unique=True) if sns_k>0 else []
    video=sample_from_dist(VIDEO_DIST,k=video_k,unique=True) if video_k>0 else []
    ott=sample_from_dist(OTT_DIST,k=ott_k,unique=True) if ott_k>0 else []
    mainSource_single=mainSources[0] if mainSources else None
    portal_single=portals[0] if portals else None

    preferences={
        "explicit":explicit,
        "implicit":implicit,
        "lastUpdated":datetime.now(timezone.utc),
        "mainSources":mainSources,
        "portals":portals,
        "mainSource":mainSource_single,
        "platforms":{
            "portal":portal_single,
            "sns":sns,
            "video":video,
            "ott":ott
        }
    }

    # 한글 parent → 영문 interests 필드명 변환
    PARENT_TO_EN = {
        "글로벌":"global","금융":"finance","부동산":"estate",
        "산업":"industry","주식":"stock","일반":"general"
    }
    interests={ PARENT_TO_EN[p]: interests_sum.get(p,0) for p in PARENTS }

    return preferences, interests

# 유저번호
def find_next_user_index():
    max_idx=0
    cursor=col.find({"_id":{"$regex":r"^user\d{3,5}$"}},{"_id":1})
    for doc in cursor:
        m=re.match(r"^user(\d{3,5})$",doc["_id"])
        if m:
            n=int(m.group(1))
            if n>max_idx: max_idx=n
    return max_idx+1

# 데이터 저장
def main():
    start_idx=find_next_user_index()
    end_idx=start_idx+TOTAL_USERS-1
    print(f"[INFO] Generating users: user{start_idx:04d} ~ user{end_idx:04d}")
    def weighted_pick(dist):
        labs,ws=zip(*dist.items())
        s=float(sum(ws)) or 1.0
        ps=[w/s for w in ws]
        return random.choices(labs,ps,k=1)[0]
    docs=[]
    now=datetime.now(timezone.utc)
    for i in range(start_idx,end_idx+1):
        _id=f"user{i:04d}"
        name=random_korean_name()
        birth_year=sample_age_birth_year()
        phone=random_phone()
        region=weighted_pick(REGION_DIST)
        gender=weighted_pick(GENDER_DIST)
        preferences,interests=build_preferences_and_interests()
        doc={
            "_id":_id,
            "password":PASSWORD,
            "name":name,
            "birth_year":birth_year,
            "phone":phone,
            "region":region,
            "gender":gender,
            "interests":interests,
            "admin":0,
            "createdAt":now,
            "updatedAt":now,
            "preferences":preferences
        }
        docs.append(doc)
        if len(docs)>=BATCH:
            try:
                col.insert_many(docs,ordered=False)
                print(f"[OK] Inserted {len(docs)} docs (up to {_id})")
            except BulkWriteError as e:
                nins=e.details.get("nInserted",0)
                print(f"[WARN] BulkWriteError; inserted={nins}, err={len(e.details.get('writeErrors',[]))}")
            docs=[]
    if docs:
        try:
            col.insert_many(docs,ordered=False)
            print(f"[OK] Inserted tail {len(docs)} docs (last={docs[-1]['_id']})")
        except BulkWriteError as e:
            nins=e.details.get("nInserted",0)
            print(f"[WARN] BulkWriteError on tail; inserted={nins}, err={len(e.details.get('writeErrors',[]))}")
    print("[DONE] Generation complete.")

if __name__=="__main__":
    main()
