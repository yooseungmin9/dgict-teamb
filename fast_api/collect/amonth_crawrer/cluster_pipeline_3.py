from cluster.loader import load_articles
from cluster.model import cluster_articles
from cluster.summarize import summarize_clusters
from cluster.label_gpt import label_with_gpt

def main():
    df = load_articles()
    df, X_umap = cluster_articles(df)     # ← X_umap도 함께 반환
    result = summarize_clusters(df, X_umap)
    label_with_gpt(result)

if __name__ == "__main__":
    main()