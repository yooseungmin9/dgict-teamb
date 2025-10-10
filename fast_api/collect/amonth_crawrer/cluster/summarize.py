from sklearn.metrics import silhouette_score
from collections import Counter

def summarize_clusters(df, X_umap):
    valid = df["cluster"] != -1
    score = silhouette_score(X_umap[valid], df.loc[valid, "cluster"]) if valid.any() else None
    noise_ratio = (df["cluster"] == -1).mean()
    print(f"Silhouette={score:.3f}, Noise={noise_ratio:.2%}, Clusters={df['cluster'].nunique()}")

    result = []
    for cid, group in df.groupby("cluster"):
        if cid == -1:
            continue
        top_keywords = Counter(sum(group["tokens"], [])).most_common(10)
        top_titles = group["title"].head(3).tolist()
        diversity = group["press"].nunique()
        first_time = min(group["published_at"])

        result.append({
            "cluster": int(cid),
            "cluster_id": int(cid),
            "keywords": [k for k, _ in top_keywords[:5]],
            "titles": top_titles,
            "count": int(len(group)),
            "press_diversity": int(diversity),
            "first_published": first_time,
            "ref_ids": [str(x) for x in group["_id"].tolist()]
        })

    return result