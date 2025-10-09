import numpy as np
from sklearn.decomposition import PCA
import umap, hdbscan
from sklearn.cluster import KMeans

def cluster_articles(df):
    X = np.vstack(df["sbert_vec"]).astype("float32")
    X_pca = PCA(n_components=100, random_state=42).fit_transform(X)
    X_umap = umap.UMAP(n_components=15, random_state=42, metric="euclidean").fit_transform(X_pca)

    clusterer = hdbscan.HDBSCAN(min_cluster_size=10, min_samples=5, metric="euclidean")
    labels = clusterer.fit_predict(X_umap)
    df["cluster"] = labels

    noise_idx = df["cluster"] == -1
    if noise_idx.mean() > 0.3 and noise_idx.any():
        X_noise = X_umap[noise_idx]
        k = min(15, max(8, X_noise.shape[0] // 30)) or 8
        km = KMeans(n_clusters=k, random_state=42).fit(X_noise)
        df.loc[noise_idx, "cluster"] = km.labels_ + df["cluster"].max() + 1

    return df, X_umap
