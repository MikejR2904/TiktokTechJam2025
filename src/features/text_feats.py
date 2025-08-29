import os
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from textblob import TextBlob

DATA_DIR = "src/data"

os.makedirs(DATA_DIR, exist_ok=True)

def extract_text_features(df, text_col="text_en"):
    # Keep original columns
    output = df.copy()

    # --- Text-based features ---
    output["word_count"] = df[text_col].apply(lambda x: len(str(x).split()))
    output["char_count"] = df[text_col].apply(lambda x: len(str(x)))
    output["avg_word_length"] = df[text_col].apply(
        lambda x: np.mean([len(w) for w in str(x).split()]) if len(str(x).split()) > 0 else 0
    )

    # Sentiment
    output["sentiment_polarity"] = df[text_col].apply(lambda x: TextBlob(str(x)).sentiment.polarity)
    output["sentiment_subjectivity"] = df[text_col].apply(lambda x: TextBlob(str(x)).sentiment.subjectivity)

    # TF-IDF (top 50 keywords)
    tfidf = TfidfVectorizer(max_features=50, stop_words="english")
    tfidf_matrix = tfidf.fit_transform(df[text_col].astype(str))
    tfidf_df = pd.DataFrame(tfidf_matrix.toarray(), 
                            columns=[f"tfidf_{t}" for t in tfidf.get_feature_names_out()],
                            index=df.index)

    # Merge everything (original + engineered features)
    output = pd.concat([output, tfidf_df], axis=1)
    return output


if __name__ == "__main__":
    df = pd.read_csv(os.path.join(DATA_DIR, "KaggleReviews_processed.csv"))
    text_feats = extract_text_features(df, text_col="text_en")
    text_feats.to_csv(os.path.join(DATA_DIR, "text_features.csv"), index=False)
    print("[✅] Text features saved to data/text_features.csv")
