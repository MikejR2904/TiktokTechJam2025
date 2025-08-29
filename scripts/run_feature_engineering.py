import pandas as pd
from src.features.text_feats import extract_text_features
from src.features.metadata_feats import extract_metadata_features

def create_feature_dataset(input_csv, output_csv):
    df = pd.read_csv(input_csv)

    print("🔎 Columns in loaded CSV:", list(df.columns))

    # Apply feature extraction
    df = extract_text_features(df)
    print("🔎 Columns in loaded CSV:", list(df.columns))
    df = extract_metadata_features(df)

    # Save final dataset with all features
    df.to_csv(output_csv, index=False)
    print(f"✅ Feature dataset saved to {output_csv}")

if __name__ == "__main__":
    create_feature_dataset("src/data/processed/KaggleReviews_processed.csv", "src/data/processed/final_features.csv")
