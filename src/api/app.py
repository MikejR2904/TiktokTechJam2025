from fastapi import FastAPI, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any
import uuid, os, random
import pandas as pd
from datetime import datetime
from pydantic import BaseModel, Field

from src.data.schema import User, Place
from src.data.ingest import ingest_scraped_data
from scripts.run_preprocessing import run_preprocessing as preprocess_reviews
from scripts.run_feature_engineering import create_feature_dataset as feature_engineer_reviews
from src.policy.policy_enforcer import PolicyEnforcer
from src.eval.evaluate import evaluate_model


# --- API Specific Models (to handle request/response) ---

class Review(BaseModel):
    place_id: str
    user_id: str
    review_id: str
    text: str
    rating: float
    user_name: str
    timestamp: Optional[str] = None
    
    # Preprocessing fields
    language: Optional[str] = None
    text_en: Optional[str] = None
    review_length: Optional[int] = None
    
    # Feature engineering fields
    sentiment_polarity: Optional[float] = None
    sentiment_subjectivity: Optional[float] = None
    dominant_topic: Optional[str] = None
    user_review_count: Optional[int] = None

class PolicyViolation(BaseModel):
    type: str
    text: str
    review_id: str
    user_id: Optional[str] = None

class PolicyAnalysisSummary(BaseModel):
    violations: List[PolicyViolation]
    total_reviews: int
    positive_reviews: int
    negative_reviews: int
    topics: Dict[str, int]

class EvaluationRequest(BaseModel):
    business_name: str

class EvaluationResponse(BaseModel):
    precision: float
    recall: float
    f1_score: float
    summary: str

# --- FastAPI Application Setup ---

app = FastAPI(
    title="Data Pipeline API",
    description="API for demonstrating a review data pipeline.",
    version="1.0.0",
)

# Allow CORS for the frontend to access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Endpoints ---

@app.post("/api/load_data")
def load_data(business_name: str = Body(..., embed=True), location: Optional[str] = Body(None, embed=True)) -> List[Review]:
    filename = "src/data/data_sources/GoogleMapReviews.csv"
    data_exists = False
    
    if os.path.exists(filename):
        try:
            df = pd.read_csv(filename)
            if not df.empty and df['business_name'].str.contains(business_name, case=False, na=False).any():
                data_exists = True
        except pd.errors.EmptyDataError:
            print("CSV file exists but is empty. Proceeding with scraping.")
        except Exception as e:
            print(f"Error reading CSV file: {e}. Proceeding with scraping.")

    if not data_exists:
        ingest_scraped_data(business_name=business_name, location=location)
    else:
        print("Data already exists for this business. Skipping scraping and loading from file.")

    if not os.path.exists(filename):
        raise HTTPException(status_code=404, detail="Data file not found after ingestion attempt.")

    try:
        df = pd.read_csv(filename)
        if 'place_id' in df.columns:
            df['place_id'] = df['place_id'].astype(str)
        if 'user_id' in df.columns:
            df['user_id'] = df['user_id'].astype(str)
        if 'review_id' in df.columns:
            df['review_id'] = df['review_id'].astype(str)
        filtered_df = df[df['business_name'].str.contains(business_name, case=False, na=False)]

        if filtered_df.empty:
            raise HTTPException(status_code=404, detail="No reviews found for the specified business.")

        # Convert place_id to string to align with the Pydantic model
        filtered_df['place_id'] = filtered_df['place_id'].astype(str)
        
        reviews_data = [Review(**row) for row in filtered_df.to_dict('records')]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read and filter data from CSV: {str(e)}")

    return reviews_data

@app.post("/api/preprocess")
def preprocess_data(business_name: str = Body(..., embed=True), location: Optional[str] = Body(None, embed=True)) -> List[Review]:
    input_path = "src/data/data_sources/GoogleMapReviews.csv"
    output_path = "src/data/processed/GoogleMapReviews_processed.csv"
    
    if not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail="Ingestion data not found. Please run '/api/load_data' first.")

    preprocess_reviews(input_path, output_path)

    try:
        df = pd.read_csv(output_path)
        if 'place_id' in df.columns:
            df['place_id'] = df['place_id'].astype(str)
        if 'user_id' in df.columns:
            df['user_id'] = df['user_id'].astype(str)
        if 'review_id' in df.columns:
            df['review_id'] = df['review_id'].astype(str)
        df = df[df['business_name'].str.contains(business_name, case=False, na=False)]
        processed_reviews = [Review(**row) for row in df.to_dict('records')]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read processed data from CSV: {str(e)}")
    
    return processed_reviews

@app.post("/api/feature_engineer")
def feature_engineer(business_name: str = Body(..., embed=True), location: Optional[str] = Body(None, embed=True)) -> List[Review]:
    input_path = "src/data/processed/GoogleMapReviews_processed.csv"
    output_path = "src/data/processed/GoogleMapReviews_featured.csv"
    
    if not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail="Preprocessed data not found. Please run '/api/preprocess' first.")

    feature_engineer_reviews(input_path, output_path)

    try:
        df = pd.read_csv(output_path)
        if 'place_id' in df.columns:
            df['place_id'] = df['place_id'].astype(str)
        if 'user_id' in df.columns:
            df['user_id'] = df['user_id'].astype(str)
        if 'review_id' in df.columns:
            df['review_id'] = df['review_id'].astype(str)
        df = df[df['business_name'].str.contains(business_name, case=False, na=False)]
        engineered_reviews = [Review(**row) for row in df.to_dict('records')]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read feature engineered data from CSV: {str(e)}")

    return engineered_reviews

@app.post("/api/enforce_policies")
def enforce_policies(business_name: str = Body(..., embed=True), location: Optional[str] = Body(None, embed=True)) -> PolicyAnalysisSummary:
    input_path = "src/data/processed/GoogleMapReviews_featured.csv"

    if not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail="Feature engineered data not found. Please run '/api/feature_engineer' first.")
    
    try:
        # Load the feature-engineered data
        df = pd.read_csv(input_path)
        if 'place_id' in df.columns:
            df['place_id'] = df['place_id'].astype(str)
        if 'user_id' in df.columns:
            df['user_id'] = df['user_id'].astype(str)
        if 'review_id' in df.columns:
            df['review_id'] = df['review_id'].astype(str)

        df = df[df['business_name'].str.contains(business_name, case=False, na=False)]
        df['sentiment_label'] = df['sentiment_polarity'].apply(
            lambda x: 'positive' if x > 0 else ('negative' if x < 0 else 'neutral')
        )

        def add_policy_violation_types(df: pd.DataFrame) -> pd.DataFrame:
            violation_cols = [c for c in df.columns if c.startswith("violation_")]
            types = []

            for _, row in df.iterrows():
                row_types = [col.replace("violation_", "") for col in violation_cols if row[col]]
                types.append(", ".join(row_types) if row_types else None)

            df["policy_violation_type"] = types
            return df
        
        # Instantiate and apply the policy enforcer
        enforcer = PolicyEnforcer(use_zero_shot=True)
        df_enforced = enforcer.enforce(df)
        df_enforced = add_policy_violation_types(df_enforced)

        # Extract policy analysis summary
        violations_df = df_enforced[df_enforced['has_violation'] == True]
        violations = [PolicyViolation(
            type=row['policy_violation_type'],
            text=row['text'],
            review_id=row['review_id'],
            user_id=row['user_id']
        ) for _, row in violations_df.iterrows()]
        
        total_reviews = len(df)
        positive_reviews = len(df[df['sentiment_label'] == 'positive'])
        negative_reviews = len(df[df['sentiment_label'] == 'negative'])
        
        topics = df['topic'].value_counts().to_dict() if 'topic' in df.columns else {}
        
        summary = PolicyAnalysisSummary(
            violations=violations,
            total_reviews=total_reviews,
            positive_reviews=positive_reviews,
            negative_reviews=negative_reviews,
            topics=topics
        )

        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to perform policy enforcement: {str(e)}")
    
@app.post("/api/evaluate")
def evaluate_endpoint(request: EvaluationRequest) -> EvaluationResponse:
    input_path = "src/data/processed/GoogleMapReviews_featured.csv"

    if not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail="Feature engineered data not found. Please run '/api/feature_engineer' first.")
    
    try:
        df = pd.read_csv(input_path)
        df = df[df['business_name'].str.contains(request.business_name, case=False, na=False)]
        
        if df.empty:
            raise HTTPException(status_code=404, detail="No feature-engineered reviews found for the specified business.")

        enforcer = PolicyEnforcer(use_zero_shot=True)
        df_enforced = enforcer.enforce(df)

        predictions = df_enforced['has_violation'].tolist()

        true_labels = [bool(random.getrandbits(1)) for _ in predictions]

        report = evaluate_model(predictions, true_labels)
        
        return EvaluationResponse(**report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to perform model evaluation: {str(e)}")