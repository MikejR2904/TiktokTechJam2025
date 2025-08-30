import re, json
import pandas as pd
from textblob import TextBlob
from transformers import pipeline


class PolicyEnforcer:
    def __init__(self, min_length=5, relevance_model=None, rant_model=None, use_zero_shot=False):
        self.min_length = min_length
        self.relevance_model = relevance_model or pipeline("zero-shot-classification", model="facebook/bart-large-mnli")  # ML model for relevance
        self.rant_model = rant_model or pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
        self.use_zero_shot = use_zero_shot            # ML model for speculative rant

        # Rule-based keyword sets
        self.bad_words = {"shit", "fuck", "damn", "bitch", "idiot", "stupid"}
        self.ad_keywords = {"visit", "promo", "discount", "buy now", "sale"}
        self.rant_keywords = {"never been", "didn’t visit", "not visited", "not gone", "haven’t gone"}
    # ---------------- Rule-Based Checks ----------------

    def check_profanity(self, text):
        return any(bad in text.lower() for bad in self.bad_words)

    def check_advertisement(self, text):
        if re.search(r"(http[s]?://|www\.|\.\w{2,})", text.lower()):
            return True
        return any(kw in text.lower() for kw in self.ad_keywords)

    def check_repetition(self, text):
        words = text.lower().split()
        return any(words.count(w) > 5 for w in set(words))

    def check_low_quality(self, text):
        return len(text.split()) < self.min_length

    def check_rating_mismatch(self, text, rating):
        sentiment = TextBlob(text).sentiment.polarity
        return (rating >= 4 and sentiment < -0.2) or (rating <= 2 and sentiment > 0.2)

    def check_duplicates(self, df):
        return df.duplicated(subset=["user_name", "text"], keep=False)

    # ---------------- ML-Based Checks ----------------

    def check_irrelevant_ml(self, text):
        if self.relevance_model:
            if self.use_zero_shot:
                result = self.relevance_model(text, candidate_labels=["relevant", "irrelevant"])
                return result["labels"][0] == "irrelevant"
            else:
                return self.relevance_model.predict([text])[0] == 0  # 0 = irrelevant
        return False

    def check_rant_without_visit(self, text):
        rule_flag = any(kw in text.lower() for kw in self.rant_keywords)
        if self.rant_model:
            if self.use_zero_shot:
                result = self.rant_model(text, candidate_labels=["factual", "speculative"])
                ml_flag = result["labels"][0] == "speculative"
            else:
                ml_flag = self.rant_model.predict([text])[0] == 1  # 1 = speculative
        else:
            ml_flag = False
        return rule_flag or ml_flag


    # ---------------- Enforcement ----------------

    def enforce(self, df):
        df["violation_profanity"] = df["text_en"].apply(self.check_profanity)
        df["violation_advertisement"] = df["text_en"].apply(self.check_advertisement)
        df["violation_repetition"] = df["text_en"].apply(self.check_repetition)
        df["violation_low_quality"] = df["text_en"].apply(self.check_low_quality)
        df["violation_rating_mismatch"] = df.apply(
            lambda row: self.check_rating_mismatch(row["text_en"], row["rating"]), axis=1
        )
        df["violation_duplicate"] = self.check_duplicates(df)
        df["violation_irrelevant"] = df["text_en"].apply(self.check_irrelevant_ml)
        df["violation_rant_without_visit"] = df["text_en"].apply(self.check_rant_without_visit)

        # Final flag
        violation_cols = [c for c in df.columns if c.startswith("violation_")]
        df["has_violation"] = df[violation_cols].any(axis=1)

        return df
    
    # def enforce_with_llm(self, df):
    #     violations_data = []

    #     for _, row in df.iterrows():
    #         text = row["text_en"]
    #         rating = row["rating"]

    #         prompt = f"""
    #             You are a content policy enforcer. 
    #             Given the review text and rating, return a JSON object where each key is a policy and the value is true/false.

    #             Policies:
    #             {json.dumps(self.policies, indent=2)}

    #             Review:
    #             "{text}"
    #             Rating: {rating}

    #             Answer ONLY in JSON, e.g.:
    #             {{"profanity": false, "advertisement": true, ...}}
    #         """

    #         response = self.llm(prompt, max_new_tokens=256, do_sample=False)
    #         try:
    #             parsed = json.loads(response[0]["generated_text"].split("{",1)[1].rsplit("}",1)[0].join(["{","}"]))
    #         except Exception:
    #             parsed = {k: False for k in self.policies}  # fallback: no violations

    #         violations_data.append(parsed)

    #     # Merge back into df
    #     violations_df = pd.DataFrame(violations_data)
    #     df = pd.concat([df.reset_index(drop=True), violations_df], axis=1)
    #     df["has_violation"] = df[list(self.policies.keys())].any(axis=1)
    #     df["policy_violation_type"] = df.apply(
    #         lambda r: [p for p in self.policies if r[p]], axis=1
    #     )

    #     return df
