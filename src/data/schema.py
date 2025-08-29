from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class Review(BaseModel):
    review_id: str = Field(..., description="Unique review identifier")
    place_id: str = Field(..., description="Google place/business ID")
    user_id: Optional[str] = Field(None, description="Reviewer unique identifier")
    user_name: Optional[str] = None
    rating: int = Field(..., ge=1, le=5, description="Star rating (1-5)")
    text: str = Field(..., description="Original review text")
    language: Optional[str] = Field("en", description="Language code, e.g. 'en', 'fr'")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Preprocessing
    tokens: Optional[List[str]] = None
    sentiment: Optional[float] = Field(
        None, description="Predicted sentiment score, e.g. -1 to +1"
    )
    embeddings: Optional[List[float]] = None
    # GPS info
    lat: Optional[float] = None
    lng: Optional[float] = None

class Place(BaseModel):
    place_id: str = Field(..., description="Google Maps place ID")
    name: str
    category: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    avg_rating: Optional[float] = None
    num_reviews: Optional[int] = 0

class User(BaseModel):
    user_id: str = Field(..., description="User unique identifier")
    name: Optional[str] = None
    reviews: Optional[List[str]] = None
    # Track user locations
    lat: Optional[float] = None
    lng: Optional[float] = None
