import os
import pandas as pd
import numpy as np

DATA_DIR = "src/data/processed"

os.makedirs(DATA_DIR, exist_ok=True)


def extract_metadata_features(df: pd.DataFrame):
    # Use existing columns
    if "photo" in df.columns:
        df["has_photo"] = df["photo"].apply(
            lambda x: 0 if pd.isna(x) or str(x).strip() == "" else 1
        )
    else:
        df["has_photo"] = 0 
    df["review_length"] = df["text_en"].apply(lambda x: len(str(x).split()))
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")

    # Category encoding for rating
    if "rating_category" in df.columns:
        df["rating_category_encoded"] = df["rating_category"].astype("category").cat.codes
        
    df["language_encoded"] = df["language"].astype("category").cat.codes

    return df

if __name__ == "__main__":
    df = pd.read_csv(os.path.join(DATA_DIR, "KaggleReviews_processed.csv"))
    metadata_feats = extract_metadata_features(df)
    metadata_feats.to_csv(os.path.join(DATA_DIR, "metadata_features.csv"), index=False)
    print("[✅] Metadata features saved to data/metadata_features.csv")
