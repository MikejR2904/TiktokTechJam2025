from fastapi import FastAPI
from pydantic import BaseModel
from src.data.preprocess_data import clean_text
from src.features.text_feats import sentiment_score

app = FastAPI()

class ReviewRequest(BaseModel):
    text: str

@app.post("/predict")
def predict(request: ReviewRequest):
    cleaned = clean_text(request.text)
    score = sentiment_score(cleaned)
    return {"cleaned": cleaned, "sentiment_score": score}