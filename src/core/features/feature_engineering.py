import pandas as pd
import re
from textblob import TextBlob
from gensim.models import LdaMulticore
from gensim.corpora import Dictionary
from gensim.parsing.preprocessing import STOPWORDS
import numpy as np
import os

def run_feature_engineering(input_path: str, output_path: str):
    """
    Loads preprocessed data, creates new features, and saves the final DataFrame.
    """
    try:
        # Load the preprocessed data from the previous step
        df = pd.read_csv(input_path)
    except FileNotFoundError:
        print("Preprocessed CSV not found. Loading from scratch for demonstration.")
        # Dummy data for demonstration if the file is missing
        data = {
            "business_name": ["Restaurant A", "Restaurant B", "Restaurant C", "Restaurant D", "Restaurant E"],
            "author_name": ["User1", "User2", "User3", "User4", "User5"],
            "text": ["Great place! The pizza was amazing.", "Terrible service, never coming back.", "A hidden gem, love the atmosphere.", "I love my new phone, but this place is too noisy.", "This is a promotional review for www.bestpizza.com."],
            "photo": [None, None, None, None, None],
            "rating": [5, 1, 4, 2, 5],
            "rating_category": ["High", "Low", "High", "Low", "High"]
        }
        df = pd.DataFrame(data)
        # Preprocess the dummy data
        df['text'] = df['text'].apply(lambda x: re.sub(r'[^a-z0-9\s]', '', str(x).lower().strip()))
    
    # Ensure review_length is present before proceeding
    if 'review_length' not in df.columns:
        df['review_length'] = df['text'].apply(lambda x: len(x.split()))
        print("✅ Review length feature added.")

    # --- 1. Sentiment Analysis ---
    df['sentiment_polarity'] = df['text'].apply(lambda x: TextBlob(x).sentiment.polarity)
    df['sentiment_subjectivity'] = df['text'].apply(lambda x: TextBlob(x).sentiment.subjectivity)
    print("✅ Sentiment analysis features added.")

    # --- 2. Topic Modeling (LDA) ---
    # Prepare data for LDA
    processed_docs = df['text'].apply(lambda text: [word for word in text.split() if word not in STOPWORDS])
    dictionary = Dictionary(processed_docs)
    corpus = [dictionary.doc2bow(doc) for doc in processed_docs]

    # Train the LDA model
    num_topics = 3 # Adjust this number based on your domain
    lda_model = LdaMulticore(corpus=corpus, id2word=dictionary, num_topics=num_topics, passes=10, workers=2)

    # Get the topic for each review and its score
    def get_topic(bow):
        topics = lda_model.get_document_topics(bow, minimum_probability=0.0)
        topics.sort(key=lambda x: x[1], reverse=True)
        return topics[0][0]

    df['dominant_topic'] = [get_topic(bow) for bow in corpus]
    print("✅ Topic modeling features added.")

    # --- 3. User and Place-level Aggregates (Proxy for Timestamps) ---
    user_review_counts = df['author_name'].value_counts()
    df['user_review_count'] = df['author_name'].map(user_review_counts)
    print("✅ User review count feature added.")

    # Save the final DataFrame with all features
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"✅ All features added. Final data saved to {output_path}")

if __name__ == "__main__":
    preprocessed_data_path = "src/data/processed/KaggleReviews_processed.csv"
    featured_data_path = "src/data/processed/KaggleReviews_featured.csv"
    run_feature_engineering(preprocessed_data_path, featured_data_path)