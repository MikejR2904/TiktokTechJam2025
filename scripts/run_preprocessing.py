import pandas as pd
import os
from src.data.preprocess_data import clean_text, detect_lang, translate_to_english

def run_preprocessing(input_path: str, output_path: str):
    try:
        df = pd.read_csv(input_path)
    except FileNotFoundError:
        print(f"❌ Error: The file {input_path} was not found.")
        return

    print("🚀 Starting data preprocessing...")

    df['text'] = df['text'].apply(clean_text)
    df['language'] = df['text'].apply(detect_lang)
    df['text_en'] = df.apply(lambda row: translate_to_english(row['text'], row['language']), axis=1)
    df['review_length'] = df['text_en'].apply(lambda x: len(str(x).split()))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    df.to_csv(output_path, index=False)

if __name__ == "__main__":
    raw_data_path = "src/data/data_sources/KaggleReviews.csv"
    processed_data_path = "src/data/processed/KaggleReviews_processed.csv"
    run_preprocessing(raw_data_path, processed_data_path)