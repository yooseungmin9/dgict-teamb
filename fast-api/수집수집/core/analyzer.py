from __future__ import annotations
import os, re
from typing import List, Tuple
from collections import Counter
from sklearn.feature_extraction.text import CountVectorizer
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from database import find_text_since

STOP = {
    # 최소 불용어
    "경제","대한","관련","기자","사진","영상","뉴스","오늘","것","수","등","중","및","위해","이번","통해",
    "네이버","블로그","일보","머니투데이","한국경제","매일경제","서울경제","파이낸셜뉴스"
}

TOKEN_PATTERN = r"(?u)[가-힣A-Za-z]{2,}"

def _tokenize_corpus(texts: List[str]) -> Counter:
    vec = CountVectorizer(token_pattern=TOKEN_PATTERN, lowercase=False)
    X = vec.fit_transform(texts)
    vocab = vec.get_feature_names_out()
    counts = X.sum(axis=0).A1
    pairs = [(vocab[i], int(counts[i])) for i in range(len(vocab))]
    pairs = [(w, c) for w, c in pairs if w not in STOP and not re.match(r"^\d+$", w)]
    return Counter(dict(pairs))

def top_keywords(days: int = 7, topk: int = 50) -> List[Tuple[str, int]]:
    texts = find_text_since("articles", days) + find_text_since("blogs", days)
    if not texts:
        return []
    cnt = _tokenize_corpus(texts)
    return cnt.most_common(topk)

def make_wordcloud(save_path: str, days: int = 7, topk: int = 200) -> int:
    texts = find_text_since("articles", days) + find_text_since("blogs", days)
    if not texts:
        return 0
    cnt = _tokenize_corpus(texts)
    wc = WordCloud(font_path="C:/Windows/Fonts/malgun.ttf" if os.name=="nt" else "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                   width=1200, height=600, background_color="white")
    wc.generate_from_frequencies(dict(cnt.most_common(topk)))
    plt.figure(figsize=(12,6))
    plt.imshow(wc, interpolation="bilinear")
    plt.axis("off")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, bbox_inches="tight")
    plt.close()
    return 1
