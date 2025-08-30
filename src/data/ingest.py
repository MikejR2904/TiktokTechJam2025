import pandas as pd
import re, os
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from pydantic import ValidationError
import uuid

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import hashlib

from src.data.schema import Review, User, Place
from src.data.db import reviews_collection, users_collection, places_collection
from src.data.preprocess_data import clean_text, detect_lang
from src.data.scrape_google_reviews import *

def get_chrome_driver():
    options = Options()
    
    # Basic stability options
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-web-security')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--disable-features=VizDisplayCompositor')
    
    # Anti-detection options
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # User agent
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
    
    # Window size and display options
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--start-maximized')
    
    # Disable logging and notifications
    options.add_argument('--disable-logging')
    options.add_argument('--log-level=3')
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-popup-blocking')
    
    # Performance options
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-renderer-backgrounding')
    options.add_argument('--disable-backgrounding-occluded-windows')
    
    try:
        driver = webdriver.Chrome(options=options)
        
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        })
        
        return driver
    except Exception as e:
        print(f"❌ Error creating Chrome driver: {e}")


def insert_review(data: dict):
    try:
        review = Review(**data)
        reviews_collection.update_one(
            {"review_id": review.review_id},
            {"$set": review.dict(by_alias=True)},
            upsert=True,
        )
    except ValidationError as e:
        print(f"❌ Review validation failed: {e}")
        return None

def insert_user(data: dict):
    try:
        user = User(**data)
        users_collection.update_one(
            {"user_id": user.user_id},
            {"$set": user.dict()},
            upsert=True,
        )
    except ValidationError as e:
        print(f"❌ User validation failed: {e}")

def insert_place(data: dict):
    try:
        place_id = data["place_id"]
        new_rating = data.get("avg_rating", 0)
        existing = places_collection.find_one({"place_id": place_id})

        if existing:
            old_num = existing.get("num_reviews", 0)
            old_avg = existing.get("avg_rating", 0.0)

            new_num = old_num + 1
            updated_avg = ((old_avg * old_num) + new_rating) / new_num

            updated_data = {
                "name": data.get("name", existing.get("name")),
                "num_reviews": new_num,
                "avg_rating": round(updated_avg, 2),
            }

            places_collection.update_one(
                {"place_id": place_id},
                {"$set": updated_data},
                upsert=True,
            )
        else:
            new_place = Place(**data)
            places_collection.insert_one(new_place.dict())

    except ValidationError as e:
        print(f"❌ Place validation failed: {e}")


def ingest_reviews_csv(csv_path: str, source: Optional[str] = None):
    df = pd.read_csv(csv_path)

    for _, row in df.iterrows():
        review_id = str(uuid.uuid4())
        place_id = str(hash(row.get("business_name"))) if pd.notna(row.get("business_name")) else None
        
        raw_text = row.get("text", "")
        cleaned_text = clean_text(raw_text)
        detected_language = detect_lang(cleaned_text)
        
        data = {
            "review_id": review_id,
            "place_id": place_id,
            "user_id": str(uuid.uuid4()),
            "user_name": row.get("author_name"),
            "rating": int(row.get("rating", 0)),
            "text": cleaned_text,
            "language": detected_language,
            "timestamp": datetime.utcnow(),
            "source": source
        }

        insert_review(data)

        user_data = {
            "user_id": data["user_id"],
            "name": data["user_name"],
            "reviews": [data["review_id"]],
        }
        place_data = {
            "place_id": data["place_id"],
            "name": data["business_name"],
            "avg_rating": data["rating"],
            "num_reviews": 1,
        }
        insert_user(user_data)
        insert_place(place_data)


def ingest_scraped_data(business_name: str, location: Optional[str] = None, max_locations: int = 10, max_reviews_per_location: int = 10):
    locations_data = bulk_scrape_locations(
        business_name=business_name,
        location=location,
        max_locations=max_locations
    )
    
    if not locations_data:
        return
    
    all_reviews_to_save = []

    for i, place_data in enumerate(locations_data):
        try:
            print(f"Processing location {i + 1}/{len(locations_data)}: {place_data.get('name', 'N/A')}")
            place_id = place_data.get('place_id')
            place_name = place_data.get('name', 'N/A')
            
            if not place_id:
                continue

            # First, ingest the place data
            insert_place({
                "place_id": place_id,
                "name": place_name,
                "address": place_data.get("address"),
                "category": place_data.get("category", "N/A"),
                "avg_rating": place_data.get("overall_rating", 0),
                "num_reviews": place_data.get("review_count", 0)
            })

            # Then, scrape reviews for this specific business
            scraped_reviews = scrape_google_reviews(
                business_name=place_name,
                location=place_data.get('address'),
                max_reviews=max_reviews_per_location
            )
            
            if not scraped_reviews:
                continue

            # Ingest each scraped review
            for r in scraped_reviews:
                review_id = str(uuid.uuid4())
                user_id = str(uuid.uuid4())
                
                raw_text = r.get("text", "")
                cleaned_text = clean_text(raw_text)
                detected_language = detect_lang(cleaned_text)

                review_data = {
                    "review_id": review_id,
                    "place_id": place_id,
                    "business_name": place_name,
                    "user_id": user_id,
                    "user_name": r.get("author_name", "Unknown"),
                    "rating": r.get("rating", 0),
                    "text": cleaned_text,
                    "language": detected_language,
                    "timestamp": datetime.utcnow(),
                    "review_url": r.get("review_url", ""),
                }
                
                # Insert into the database
                insert_review(review_data)
                
                # Insert user data
                insert_user({
                    "user_id": user_id, 
                    "name": r.get("author_name", "Unknown"),
                    "reviews": [review_id]
                })

                all_reviews_to_save.append(review_data)
        
        except Exception as e:
            print(f"❌ Error processing location '{place_name}': {e}")
            continue
        
    save_to_csv(all_reviews_to_save, "src/data/data_sources/GoogleMapReviews.csv")