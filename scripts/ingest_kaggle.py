from src.data.ingest import ingest_reviews_csv

if __name__ == "__main__":
    ingest_reviews_csv("src/data/data_sources/KaggleReviews.csv", source="kaggle")