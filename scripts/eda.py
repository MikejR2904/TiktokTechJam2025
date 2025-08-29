import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from collections import Counter
import re
from src.data.preprocess_data import clean_text, detect_lang
import nltk as nltk
nltk.download('stopwords')

df = pd.read_csv("src/data/data_sources/KaggleReviews.csv")
df['text'] = df['text'].apply(clean_text)
df['language'] = df['text'].apply(detect_lang)

sns.set(style="whitegrid")
plt.style.use("seaborn-v0_8-whitegrid")

print("--- Data Info ---")
df.info()

print("\n--- Descriptive Statistics for Ratings ---")
print(df['rating'].describe())

df['review_length'] = df['text'].apply(lambda x: len(str(x).split()))

plt.figure(figsize=(10, 6))
sns.histplot(df['review_length'], bins=50, kde=True)
plt.title('Distribution of Review Length (in words)')
plt.xlabel('Number of Words')
plt.ylabel('Frequency')
plt.xlim(0, 200)
plt.show()

# --- Language Distribution --- #
plt.figure(figsize=(10, 6))
sns.countplot(data=df, y='language', order=df['language'].value_counts().index)
plt.title('Distribution of Reviews by Language')
plt.xlabel('Number of Reviews')
plt.ylabel('Language')
plt.show()

# --- Most Common Words --- #
all_words = ' '.join(df['text']).lower()
words = re.findall(r'\b\w+\b', all_words)
stop_words = set(nltk.corpus.stopwords.words('english'))
filtered_words = [word for word in words if word not in stop_words and len(word) > 2]

word_counts = Counter(filtered_words)
most_common_words = word_counts.most_common(20)
common_words_df = pd.DataFrame(most_common_words, columns=['word', 'count'])

plt.figure(figsize=(12, 8))
sns.barplot(x='count', y='word', data=common_words_df, palette='viridis')
plt.title('Top 20 Most Common Words in Reviews')
plt.xlabel('Count')
plt.ylabel('Word')
plt.show()

avg_length_by_rating = df.groupby('rating')['review_length'].mean().reset_index()

plt.figure(figsize=(10, 6))
sns.barplot(x='rating', y='review_length', data=avg_length_by_rating, palette='coolwarm')
plt.title('Average Review Length by Rating')
plt.xlabel('Rating (1-5)')
plt.ylabel('Average Review Length (words)')
plt.show()

# --- Top Words in High vs. Low-Rated Reviews --- #
high_rated_reviews = df[df['rating'] >= 4]['text']
low_rated_reviews = df[df['rating'] <= 2]['text']

stop_words = set(nltk.corpus.stopwords.words('english'))

def get_top_words(texts, n=20):
    all_words = ' '.join(texts).lower()
    words = re.findall(r'\b\w+\b', all_words)
    filtered_words = [word for word in words if word not in stop_words and len(word) > 2]
    word_counts = Counter(filtered_words)
    return word_counts.most_common(n)

top_positive_words = get_top_words(high_rated_reviews)
positive_df = pd.DataFrame(top_positive_words, columns=['word', 'count'])
plt.figure(figsize=(12, 8))
sns.barplot(x='count', y='word', data=positive_df, palette='Greens_d')
plt.title('Top 20 Most Common Words in High-Rated Reviews')
plt.show()

top_negative_words = get_top_words(low_rated_reviews)
negative_df = pd.DataFrame(top_negative_words, columns=['word', 'count'])
plt.figure(figsize=(12, 8))
sns.barplot(x='count', y='word', data=negative_df, palette='Reds_d')
plt.title('Top 20 Most Common Words in Low-Rated Reviews')
plt.show()

# --- Potential Policy Violations --- #
# Rule 1: Flag reviews with URLs
df['has_url'] = df['text'].apply(lambda x: 1 if "http" in x or "www" in x else 0)

# Rule 2: Flag reviews with common promotional keywords
promo_keywords = ['promo', 'discount', 'free trial', 'buy now', 'visit our website', 'coupon', 'deals']
df['has_promo_keyword'] = df['text'].apply(lambda x: 1 if any(word in x for word in promo_keywords) else 0)

# Rule 3: Flag reviews that are extremely short (potential spam) or extremely long (potential rants)
df['is_outlier_length'] = df['review_length'].apply(lambda x: 1 if x < 5 or x > 150 else 0)

df['potential_violation'] = np.where(
    (df['has_url'] == 1) | 
    (df['has_promo_keyword'] == 1) | 
    (df['is_outlier_length'] == 1), 
    1, 
    0
)

print("\n--- Reviews with Potential Policy Violations (Advanced) ---")
print(df[df['potential_violation'] == 1][['text', 'rating', 'potential_violation']])