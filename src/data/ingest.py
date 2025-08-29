import pandas as pd
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

def get_chrome_driver():
    """Initialize Chrome driver with appropriate options"""
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
    
    # Set realistic user agent
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
        
        # Execute stealth scripts
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
            {"$set": review.dict()},
            upsert=True,
        )
    except ValidationError as e:
        print(f"❌ Review validation failed: {e}")

def get_stable_chrome_driver():
    """Get a stable Chrome driver"""
    options = Options()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--log-level=3')
    options.add_argument('--silent')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    return webdriver.Chrome(options=options)

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


def ingest_reviews_csv(csv_path: str, source: Optional[str] = None):
    df = pd.read_csv(csv_path)

    for _, row in df.iterrows():
        review_id = str(uuid.uuid4())
        place_id = str(hash(row.get("business_name"))) if pd.notna(row.get("business_name")) else None
        
        # You'll need to run a separate function to ingest Places
        # For now, we'll just insert the review with the place_id
        raw_text = row.get("text", "")
        cleaned_text = clean_text(raw_text)
        detected_language = detect_lang(cleaned_text)
        
        data = {
            "review_id": review_id,
            "place_id": place_id,
            "user_id": str(uuid.uuid4()), # Generate a unique user_id
            "user_name": row.get("author_name"), # ⬅️ Correct mapping
            "rating": int(row.get("rating", 0)),
            "text": cleaned_text,
            "language": detected_language, # You can also run a language detection function here
            "timestamp": datetime.utcnow(), # ⬅️ Use the `date` field from your schema
            "source": source # Use the source argument
        }
        
        try:
            review = Review(**data)
            reviews_collection.update_one(
                {"review_id": review.review_id},
                {"$set": review.dict(by_alias=True)}, # Use by_alias to handle Pydantic model's field names
                upsert=True,
            )
        except ValidationError as e:
            print(f"❌ Review validation failed for row with rating {row.get('rating')}: {e}")
        
        user_data = {
            "user_id": data["user_id"],
            "name": data["user_name"],
            # You can add logic to count reviews later
        }
        insert_user(user_data)


def ingest_users_csv(csv_path: str):
    df = pd.read_csv(csv_path)

    for _, row in df.iterrows():
        data = {
            "user_id": str(row.get("user_id") or row.get("id")),
            "name": row.get("name", None),
            "reviews": row.get("reviews").split(",") if pd.notna(row.get("reviews")) else [],
        }
        insert_user(data)

def resolve_place_id(business_name: str, location: Optional[str] = None, use_scraper: bool = True) -> Optional[str]:
    """Resolve place ID and scrape basic place information"""
    query = f"{business_name}, {location}" if location else business_name
    place_id = str(int(hashlib.md5(query.encode()).hexdigest()[:12], 16))
    
    # Check if place already exists in database
    existing = places_collection.find_one({"place_id": place_id})
    if existing:
        return place_id

    if use_scraper:
        driver = None
        try:
            driver = get_chrome_driver()
            search_url = f"https://www.google.com/maps/search/{query.replace(' ', '%20')}"
            driver.get(search_url)
            
            # Wait for search results to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-value='Search results']"))
            )
            
            # Click on the first search result
            try:
                # Updated selector for clickable business results
                first_result = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "div[role='article'] a"))
                )
                first_result.click()
                time.sleep(3)
            except:
                print("Could not click on first result")

            # Extract business name
            try:
                name_elem = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))
                )
                name = name_elem.text
            except:
                name = business_name

            # Extract address
            try:
                # Look for address button or text
                address_selectors = [
                    "button[data-item-id='address']",
                    "button[data-value='Address']",
                    "[data-item-id='address']",
                    "div[data-value='Address'] div[class*='fontBodyMedium']"
                ]
                address = None
                for selector in address_selectors:
                    try:
                        addr_elem = driver.find_element(By.CSS_SELECTOR, selector)
                        address = addr_elem.text
                        break
                    except:
                        continue
            except:
                address = None

            # Extract coordinates from URL if available
            lat, lng = None, None
            try:
                current_url = driver.current_url
                # Look for coordinates in URL pattern: @lat,lng,zoom
                coord_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', current_url)
                if coord_match:
                    lat = float(coord_match.group(1))
                    lng = float(coord_match.group(2))
            except:
                pass

            # Save place to database
            place = Place(
                place_id=place_id,
                name=name,
                address=address,
                lat=lat,
                lng=lng
            )
            places_collection.update_one(
                {"place_id": place.place_id},
                {"$set": place.dict()},
                upsert=True
            )
            print(f"✅ Saved place: {name}")
            
        except Exception as e:
            print(f"❌ Error resolving place: {e}")
        finally:
            if driver:
                driver.quit()

    return place_id

# def scrape_google_reviews(business_name: str, location: Optional[str] = None, max_reviews: int = 10) -> List[Dict]:
#     """Scrape Google Maps reviews with updated selectors and better error handling"""
#     query = f"{business_name}, {location}" if location else business_name
#     reviews = []
#     driver = None
    
#     try:
#         print(f"🔍 Searching for: {query}")
#         driver = get_chrome_driver()
        
#         # Navigate to Google Maps
#         base_url = "https://www.google.com/maps"
#         driver.get(base_url)
#         time.sleep(3)
        
#         # Search for the business
#         try:
#             search_box = WebDriverWait(driver, 10).until(
#                 EC.element_to_be_clickable((By.ID, "searchboxinput"))
#             )
#             search_box.clear()
#             search_box.send_keys(query)
#             time.sleep(1)
            
#             # Click search button or press enter
#             search_button = driver.find_element(By.ID, "searchbox-searchbutton")
#             search_button.click()
#             time.sleep(5)
#             print("✅ Search completed")
            
#         except Exception as e:
#             print(f"❌ Error with search: {e}")
#             # Try alternative URL method
#             search_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
#             driver.get(search_url)
#             time.sleep(5)
        
#         # Wait for results and click on first business
#         try:
#             # Wait for the search results panel to appear
#             WebDriverWait(driver, 15).until(
#                 EC.presence_of_element_located((By.CSS_SELECTOR, "[role='main']"))
#             )
            
#             # Look for business results with multiple selector strategies
#             business_selectors = [
#                 "a[data-value='Directions']",  # Directions link
#                 "div[role='article'] h3 a",   # Business title link
#                 "a.hfpxzc",                    # Classic selector
#                 "[data-value='Directions'] a", # Alternative directions
#                 ".Nv2PK a"                     # Another possible selector
#             ]
            
#             clicked = False
#             for selector in business_selectors:
#                 try:
#                     business_link = WebDriverWait(driver, 5).until(
#                         EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
#                     )
#                     driver.execute_script("arguments[0].click();", business_link)
#                     print(f"✅ Clicked business using selector: {selector}")
#                     clicked = True
#                     break
#                 except:
#                     continue
            
#             if not clicked:
#                 print("❌ Could not click on any business result")
#                 return []
                
#             time.sleep(5)
            
#         except Exception as e:
#             print(f"❌ Error clicking business: {e}")
#             return []
        
#         # Wait for business details to load
#         try:
#             WebDriverWait(driver, 10).until(
#                 EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))
#             )
#             print("✅ Business details loaded")
#         except:
#             print("❌ Business details did not load")
#             return []
        
#         # Try to navigate to reviews section
#         try:
#             # Look for reviews tab or section
#             reviews_selectors = [
#                 "button[data-value='Sort reviews']",
#                 "div[data-value='Reviews'] button",
#                 ".F7nice button[data-tab-index='1']",
#                 "button[aria-label*='reviews']",
#                 "button[jsaction*='review']"
#             ]
            
#             for selector in reviews_selectors:
#                 try:
#                     reviews_tab = driver.find_element(By.CSS_SELECTOR, selector)
#                     driver.execute_script("arguments[0].click();", reviews_tab)
#                     print(f"✅ Clicked reviews tab: {selector}")
#                     time.sleep(3)
#                     break
#                 except:
#                     continue
                    
#         except Exception as e:
#             print(f"⚠️ Could not find reviews tab: {e}")
        
#         # Scroll to load reviews
#         try:
#             # Find scrollable container and scroll down
#             for _ in range(3):
#                 driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
#                 time.sleep(2)
#         except:
#             pass
        
#         # Extract reviews with multiple strategies
#         print("🔍 Looking for review elements...")
        
#         review_containers = []
        
#         # Strategy 1: Look for review containers
#         container_selectors = [
#             ".jftiEf",
#             "[data-review-id]",
#             "div[jsaction*='review']",
#             ".WMbnJf",
#             ".gws-localreviews__google-review"
#         ]
        
#         for selector in container_selectors:
#             try:
#                 containers = driver.find_elements(By.CSS_SELECTOR, selector)
#                 if containers:
#                     print(f"✅ Found {len(containers)} review containers with: {selector}")
#                     review_containers = containers[:max_reviews]
#                     break
#             except:
#                 continue
        
#         if not review_containers:
#             print("❌ No review containers found, trying alternative approach...")
            
#             # Alternative: look for any elements that might contain reviews
#             alt_selectors = [
#                 "div[role='article']",
#                 ".review",
#                 "[class*='review']",
#                 "div[class*='Review']"
#             ]
            
#             for selector in alt_selectors:
#                 try:
#                     containers = driver.find_elements(By.CSS_SELECTOR, selector)
#                     if len(containers) > 1:  # Likely reviews if multiple found
#                         print(f"✅ Found {len(containers)} potential reviews with: {selector}")
#                         review_containers = containers[:max_reviews]
#                         break
#                 except:
#                     continue
        
#         if not review_containers:
#             print("❌ No review elements found at all")
#             return []
        
#         # Extract data from review containers
#         for i, container in enumerate(review_containers):
#             try:
#                 review_data = {}
                
#                 # Extract author name
#                 author_found = False
#                 author_selectors = [
#                     ".d4r55",
#                     "[data-value*='contributor']",
#                     ".TSUbDb a",
#                     "span[class*='TSUbDb']",
#                     ".reviewer-name",
#                     "a[data-href*='contrib']"
#                 ]
                
#                 for selector in author_selectors:
#                     try:
#                         author_elem = container.find_element(By.CSS_SELECTOR, selector)
#                         review_data['author_name'] = author_elem.text.strip()
#                         if review_data['author_name']:
#                             author_found = True
#                             break
#                     except:
#                         continue
                
#                 if not author_found:
#                     review_data['author_name'] = "Unknown"
                
#                 # Extract rating
#                 rating_found = False
#                 rating_selectors = [
#                     "span[aria-label*='star']",
#                     ".kvMYJc",
#                     "[class*='star']",
#                     "span[role='img']"
#                 ]
                
#                 for selector in rating_selectors:
#                     try:
#                         rating_elem = container.find_element(By.CSS_SELECTOR, selector)
#                         aria_label = rating_elem.get_attribute("aria-label") or ""
#                         title = rating_elem.get_attribute("title") or ""
                        
#                         # Try to extract rating number
#                         for text in [aria_label, title]:
#                             if text:
#                                 rating_match = re.search(r'(\d+)', text)
#                                 if rating_match:
#                                     review_data['rating'] = int(rating_match.group(1))
#                                     rating_found = True
#                                     break
                        
#                         if rating_found:
#                             break
                            
#                     except:
#                         continue
                
#                 if not rating_found:
#                     review_data['rating'] = 0
                
#                 # Extract review text
#                 text_found = False
#                 text_selectors = [
#                     ".wiI7pd",
#                     "[data-expandable-section]",
#                     ".review-text",
#                     "span[jsaction*='review']",
#                     ".MyEned span"
#                 ]
                
#                 for selector in text_selectors:
#                     try:
#                         text_elem = container.find_element(By.CSS_SELECTOR, selector)
#                         review_text = text_elem.text.strip()
#                         if len(review_text) > 10:  # Ensure it's actual review text
#                             review_data['text'] = review_text
#                             text_found = True
#                             break
#                     except:
#                         continue
                
#                 if not text_found:
#                     review_data['text'] = ""
                
#                 # Extract time
#                 try:
#                     time_selectors = [
#                         ".rsqaWe",
#                         "[class*='time']",
#                         ".review-time"
#                     ]
                    
#                     for selector in time_selectors:
#                         try:
#                             time_elem = container.find_element(By.CSS_SELECTOR, selector)
#                             review_data['relative_time'] = time_elem.text.strip()
#                             break
#                         except:
#                             continue
#                     else:
#                         review_data['relative_time'] = ""
                        
#                 except:
#                     review_data['relative_time'] = ""
                
#                 # Only add review if we found at least author or rating
#                 if review_data['author_name'] != "Unknown" or review_data['rating'] > 0:
#                     reviews.append(review_data)
#                     print(f"✅ Review {i+1}: {review_data['author_name']} - {review_data['rating']}⭐")
#                 else:
#                     print(f"⚠️ Skipped review {i+1}: insufficient data")
                
#             except Exception as e:
#                 print(f"❌ Error processing review {i+1}: {e}")
#                 continue
        
#     except Exception as e:
#         print(f"❌ Main error in scraping: {e}")
#         import traceback
#         traceback.print_exc()
        
#     finally:
#         if driver:
#             try:
#                 driver.quit()
#                 print("✅ Browser closed")
#             except:
#                 pass
    
#     print(f"🎉 Successfully scraped {len(reviews)} reviews")
#     return reviews

# def ingest_scraped_reviews(business_name: str, location: Optional[str] = None, max_reviews: int = 10):
#     """Main function to scrape and ingest reviews"""
#     print(f"🚀 Starting review ingestion for: {business_name}")
    
#     # Resolve place ID
#     place_id = resolve_place_id(business_name, location)
#     if not place_id:
#         print("❌ Could not resolve place ID")
#         return
    
#     # Scrape reviews
#     scraped_reviews = scrape_google_reviews(business_name, location, max_reviews)
    
#     if not scraped_reviews:
#         print("❌ No reviews scraped")
#         return
    
#     # Insert reviews into database
#     for r in scraped_reviews:
#         try:
#             review_id = str(uuid.uuid4())
#             user_id = str(uuid.uuid4())
#             text = clean_text(r.get("text", ""))
#             lang = detect_lang(text) if text else "en"
            
#             insert_review({
#                 "review_id": review_id,
#                 "place_id": place_id,
#                 "user_id": user_id,
#                 "user_name": r.get("author_name", "Unknown"),
#                 "rating": r.get("rating", 0),
#                 "text": text,
#                 "language": lang,
#                 "timestamp": datetime.utcnow(),
#                 "relative_time": r.get("relative_time", "")
#             })
            
#             insert_user({
#                 "user_id": user_id, 
#                 "name": r.get("author_name", "Unknown")
#             })
            
#         except Exception as e:
#             print(f"❌ Error inserting review: {e}")
    
#     print(f"✅ Successfully ingested {len(scraped_reviews)} reviews for {business_name}")

def bulk_scrape_all_locations(business_name: str, location: Optional[str] = None, max_locations: int = 20) -> List[Dict]:
    """
    Scrape basic data from ALL locations in search results WITHOUT clicking
    Perfect for RAG system - gets overview data quickly
    """
    query = f"{business_name}, {location}" if location else business_name
    driver = None
    all_locations_data = []
    
    try:
        print(f"🔍 Bulk scraping: {query}")
        driver = get_stable_chrome_driver()
        
        # Navigate and search
        driver.get("https://www.google.com/maps")
        time.sleep(3)
        
        search_box = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "searchboxinput"))
        )
        search_box.clear()
        search_box.send_keys(query)
        
        search_button = driver.find_element(By.ID, "searchbox-searchbutton")
        search_button.click()
        time.sleep(5)
        
        # Scroll to load more results
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        
        print("✅ Search completed, extracting ALL location data...")
        
        # Find all business cards in search results
        business_cards = driver.find_elements(By.CSS_SELECTOR, "div[role='article']")[:max_locations]
        
        print(f"📍 Found {len(business_cards)} business locations")
        
        for i, card in enumerate(business_cards):
            try:
                location_data = {}
                
                # Extract business name
                name_selectors = [".qBF1Pd", ".fontHeadlineSmall", "h3"]
                for selector in name_selectors:
                    try:
                        name_elem = card.find_element(By.CSS_SELECTOR, selector)
                        location_data['name'] = name_elem.text.strip()
                        break
                    except:
                        continue
                else:
                    location_data['name'] = f"{business_name} Location {i+1}"
                
                # Extract address
                address_selectors = [
                    ".W4Efsd:last-child .W4Efsd", 
                    ".W4Efsd[style*='color']",
                    ".W4Efsd",
                    "[data-value='Address']"
                ]
                for selector in address_selectors:
                    try:
                        addr_elems = card.find_elements(By.CSS_SELECTOR, selector)
                        for addr_elem in addr_elems:
                            addr_text = addr_elem.text.strip()
                            # Check if it looks like an address
                            if (len(addr_text) > 5 and 
                                any(keyword in addr_text.lower() for keyword in ['street', 'road', 'ave', 'blvd', 'drive', 'singapore', 'block']) or 
                                re.search(r'\d', addr_text)):
                                location_data['address'] = addr_text
                                break
                        if 'address' in location_data:
                            break
                    except:
                        continue
                else:
                    location_data['address'] = "Address not found"
                
                # Extract overall rating
                try:
                    rating_elem = card.find_element(By.CSS_SELECTOR, "span[aria-label*='star']")
                    aria_label = rating_elem.get_attribute('aria-label') or ''
                    rating_match = re.search(r'(\d+\.?\d*)', aria_label)
                    if rating_match:
                        location_data['overall_rating'] = float(rating_match.group(1))
                    else:
                        location_data['overall_rating'] = 0
                except:
                    location_data['overall_rating'] = 0
                
                # Extract review count
                try:
                    review_count_selectors = [
                        "span[aria-label*='review']",
                        ".UY7F9",
                        "button[aria-label*='review']"
                    ]
                    for selector in review_count_selectors:
                        try:
                            count_elem = card.find_element(By.CSS_SELECTOR, selector)
                            count_text = count_elem.get_attribute('aria-label') or count_elem.text
                            count_match = re.search(r'(\d+)', count_text)
                            if count_match:
                                location_data['review_count'] = int(count_match.group(1))
                                break
                        except:
                            continue
                    else:
                        location_data['review_count'] = 0
                except:
                    location_data['review_count'] = 0
                
                # Extract business type/category
                try:
                    # Look for business category
                    category_selectors = [".W4Efsd:first-child", ".fontBodyMedium"]
                    for selector in category_selectors:
                        try:
                            cat_elem = card.find_element(By.CSS_SELECTOR, selector)
                            cat_text = cat_elem.text.strip()
                            # Skip if it looks like address or rating
                            if (not re.search(r'\d+\.?\d*\s*star', cat_text.lower()) and 
                                not re.search(r'\d+.*(?:street|road|ave)', cat_text.lower()) and
                                len(cat_text) < 50):
                                location_data['category'] = cat_text
                                break
                        except:
                            continue
                    else:
                        location_data['category'] = "Restaurant"
                except:
                    location_data['category'] = "Restaurant"
                
                # Extract price level ($ symbols)
                try:
                    price_elem = card.find_element(By.CSS_SELECTOR, "[aria-label*='Price']")
                    price_text = price_elem.get_attribute('aria-label') or ''
                    location_data['price_level'] = price_text
                except:
                    location_data['price_level'] = "Price not available"
                
                # Extract hours status
                try:
                    hours_selectors = [
                        "[data-value='Open']",
                        "[data-value='Closed']", 
                        "[class*='open']",
                        "[class*='closed']"
                    ]
                    for selector in hours_selectors:
                        try:
                            hours_elem = card.find_element(By.CSS_SELECTOR, selector)
                            location_data['hours_status'] = hours_elem.text.strip()
                            break
                        except:
                            continue
                    else:
                        location_data['hours_status'] = "Hours not available"
                except:
                    location_data['hours_status'] = "Hours not available"
                
                # Try to extract a few visible reviews without clicking
                location_data['sample_reviews'] = extract_visible_reviews_from_card(card)
                
                # Generate place_id for consistency
                place_query = f"{location_data['name']}, {location_data['address']}"
                location_data['place_id'] = str(int(hashlib.md5(place_query.encode()).hexdigest()[:12], 16))
                
                # Add extraction metadata
                location_data['extraction_type'] = 'bulk_search_results'
                location_data['extracted_at'] = datetime.utcnow()
                location_data['business_query'] = query
                
                all_locations_data.append(location_data)
                
                print(f"✅ Location {i+1}: {location_data['name']} - {location_data['overall_rating']}⭐ ({location_data['review_count']} reviews)")
                
            except Exception as e:
                print(f"❌ Error extracting location {i+1}: {e}")
                continue
        
        print(f"🎉 Bulk extraction complete: {len(all_locations_data)} locations")
        
    except Exception as e:
        print(f"❌ Error in bulk scraping: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    return all_locations_data

def extract_visible_reviews_from_card(card_element) -> List[Dict]:
    """Extract any visible review snippets from the business card"""
    sample_reviews = []
    
    try:
        # Look for review snippets that might be visible in the card
        review_selectors = [
            ".jftiEf",
            "[data-review-id]", 
            ".review",
            "[class*='review']"
        ]
        
        for selector in review_selectors:
            try:
                review_elements = card_element.find_elements(By.CSS_SELECTOR, selector)[:3]  # Max 3 samples
                
                for elem in review_elements:
                    try:
                        review = {}
                        
                        # Author
                        try:
                            author_elem = elem.find_element(By.CSS_SELECTOR, ".d4r55, .TSUbDb")
                            review['author'] = author_elem.text.strip()
                        except:
                            review['author'] = "Anonymous"
                        
                        # Rating
                        try:
                            rating_elem = elem.find_element(By.CSS_SELECTOR, "[aria-label*='star']")
                            aria_label = rating_elem.get_attribute('aria-label') or ''
                            rating_match = re.search(r'(\d+)', aria_label)
                            review['rating'] = int(rating_match.group(1)) if rating_match else 0
                        except:
                            review['rating'] = 0
                        
                        # Text
                        try:
                            text_elem = elem.find_element(By.CSS_SELECTOR, ".wiI7pd, [data-expandable-section]")
                            review['text'] = text_elem.text.strip()
                        except:
                            review['text'] = ""
                        
                        if review['author'] != "Anonymous" or review['text']:
                            sample_reviews.append(review)
                            
                    except:
                        continue
                        
                if sample_reviews:
                    break  # Found reviews with this selector
                    
            except:
                continue
    
    except:
        pass
    
    return sample_reviews

def interactive_scrape_specific_location(business_name: str, location: Optional[str] = None, max_reviews: int = 10) -> Tuple[Dict, List[Dict]]:
    """
    Interactive mode: user selects location, gets detailed reviews
    Returns (location_info, detailed_reviews)
    """
    query = f"{business_name}, {location}" if location else business_name
    driver = None
    
    try:
        print(f"🎯 Interactive scraping: {query}")
        driver = get_stable_chrome_driver()
        
        # Search
        driver.get("https://www.google.com/maps")
        time.sleep(3)
        
        search_box = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "searchboxinput"))
        )
        search_box.clear()
        search_box.send_keys(query)
        
        search_button = driver.find_element(By.ID, "searchbox-searchbutton")
        search_button.click()
        time.sleep(5)
        
        # Find locations for selection
        business_cards = driver.find_elements(By.CSS_SELECTOR, "div[role='article']")[:10]
        
        if not business_cards:
            print("❌ No locations found")
            return {}, []
        
        # Extract basic info for selection
        locations = []
        for i, card in enumerate(business_cards):
            try:
                # Name
                try:
                    name_elem = card.find_element(By.CSS_SELECTOR, ".qBF1Pd, h3")
                    name = name_elem.text.strip()
                except:
                    name = f"Location {i+1}"
                
                # Address
                try:
                    addr_elem = card.find_element(By.CSS_SELECTOR, ".W4Efsd:last-child")
                    address = addr_elem.text.strip()
                except:
                    address = "Address not available"
                
                # Rating
                try:
                    rating_elem = card.find_element(By.CSS_SELECTOR, "span[aria-label*='star']")
                    rating = rating_elem.get_attribute('aria-label')
                except:
                    rating = "No rating"
                
                # Find clickable link
                try:
                    link = card.find_element(By.CSS_SELECTOR, "a.hfpxzc, a[href*='place/']")
                    locations.append({
                        'index': i,
                        'name': name,
                        'address': address,
                        'rating': rating,
                        'element': link
                    })
                except:
                    print(f"⚠️ No clickable link found for location {i}")
                    continue
                    
            except Exception as e:
                print(f"Error processing location {i}: {e}")
                continue
        
        if not locations:
            print("❌ No clickable locations found")
            return {}, []
        
        # Display options
        print(f"\n🏢 Found {len(locations)} locations:")
        print("=" * 60)
        for loc in locations:
            print(f"{loc['index']}. {loc['name']}")
            print(f"   📍 {loc['address']}")
            print(f"   ⭐ {loc['rating']}")
            print("-" * 30)
        
        # Get user selection
        while True:
            try:
                choice = input(f"\n👆 Select location (0-{len(locations)-1}) or 'q' to quit: ").strip().lower()
                
                if choice == 'q':
                    return {}, []
                
                index = int(choice)
                if 0 <= index < len(locations):
                    selected = locations[index]
                    print(f"\n✅ Selected: {selected['name']}")
                    
                    # Click the selected location
                    driver.execute_script("arguments[0].click();", selected['element'])
                    time.sleep(5)
                    
                    # Extract detailed location info
                    location_info = extract_detailed_location_info(driver, selected['name'])
                    
                    # Extract detailed reviews
                    detailed_reviews = scrape_detailed_reviews(driver, max_reviews)
                    
                    return location_info, detailed_reviews
                else:
                    print("❌ Invalid selection")
            except (ValueError, KeyboardInterrupt):
                return {}, []
        
    except Exception as e:
        print(f"❌ Error in interactive scraping: {e}")
        return {}, []
    finally:
        if driver:
            input("\n👀 Press Enter to close browser...")
            try:
                driver.quit()
            except:
                pass

def extract_detailed_location_info(driver, name: str) -> Dict:
    """Extract detailed info from the business page"""
    info = {'name': name}
    
    try:
        # Business name (refined)
        try:
            name_elem = driver.find_element(By.CSS_SELECTOR, "h1")
            info['name'] = name_elem.text.strip()
        except:
            pass
        
        # Address
        try:
            addr_elem = driver.find_element(By.CSS_SELECTOR, "button[data-item-id='address']")
            info['address'] = addr_elem.text.strip()
        except:
            info['address'] = "Address not found"
        
        # Phone
        try:
            phone_elem = driver.find_element(By.CSS_SELECTOR, "button[data-item-id*='phone']")
            info['phone'] = phone_elem.text.strip()
        except:
            info['phone'] = "Phone not found"
        
        # Website
        try:
            website_elem = driver.find_element(By.CSS_SELECTOR, "a[data-item-id='authority']")
            info['website'] = website_elem.get_attribute('href')
        except:
            info['website'] = "Website not found"
        
        # Hours
        try:
            hours_button = driver.find_element(By.CSS_SELECTOR, "button[data-item-id*='oh']")
            info['hours'] = hours_button.get_attribute('aria-label') or hours_button.text
        except:
            info['hours'] = "Hours not found"
        
        # Overall rating and count
        try:
            rating_elem = driver.find_element(By.CSS_SELECTOR, ".F7nice")
            rating_text = rating_elem.text
            rating_match = re.search(r'(\d+\.?\d*)', rating_text)
            count_match = re.search(r'\((\d+)\)', rating_text)
            
            info['overall_rating'] = float(rating_match.group(1)) if rating_match else 0
            info['review_count'] = int(count_match.group(1)) if count_match else 0
        except:
            info['overall_rating'] = 0
            info['review_count'] = 0
        
        # Coordinates from URL
        try:
            url = driver.current_url
            coord_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', url)
            if coord_match:
                info['latitude'] = float(coord_match.group(1))
                info['longitude'] = float(coord_match.group(2))
        except:
            pass
        
        # Generate place_id
        place_query = f"{info['name']}, {info.get('address', '')}"
        info['place_id'] = str(int(hashlib.md5(place_query.encode()).hexdigest()[:12], 16))
        
        info['extraction_type'] = 'interactive_detailed'
        info['extracted_at'] = datetime.utcnow()
        
    except Exception as e:
        print(f"Error extracting detailed info: {e}")
    
    return info

def scrape_detailed_reviews(driver, max_reviews: int) -> List[Dict]:
    """Scrape detailed reviews from business page"""
    reviews = []
    
    try:
        # Click reviews tab
        try:
            reviews_tab = driver.find_element(By.CSS_SELECTOR, "button[aria-label*='reviews']")
            driver.execute_script("arguments[0].click();", reviews_tab)
            time.sleep(3)
        except:
            pass
        
        # Scroll to load reviews
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        
        # Find review containers
        review_containers = driver.find_elements(By.CSS_SELECTOR, ".jftiEf")[:max_reviews]
        
        for i, container in enumerate(review_containers):
            try:
                review = {}
                
                # Author
                try:
                    author_elem = container.find_element(By.CSS_SELECTOR, ".d4r55")
                    review['author_name'] = author_elem.text.strip()
                except:
                    review['author_name'] = "Unknown"
                
                # Rating with better extraction
                try:
                    star_elements = container.find_elements(By.CSS_SELECTOR, "span[aria-label*='star']")
                    for star_elem in star_elements:
                        aria_label = star_elem.get_attribute('aria-label') or ''
                        rating_match = re.search(r'(\d+)', aria_label)
                        if rating_match and 1 <= int(rating_match.group(1)) <= 5:
                            review['rating'] = int(rating_match.group(1))
                            break
                    else:
                        review['rating'] = 0
                except:
                    review['rating'] = 0
                
                # Text
                try:
                    text_elem = container.find_element(By.CSS_SELECTOR, ".wiI7pd")
                    review['text'] = text_elem.text.strip()
                except:
                    review['text'] = ""
                
                # Time
                try:
                    time_elem = container.find_element(By.CSS_SELECTOR, ".rsqaWe")
                    review['relative_time'] = time_elem.text.strip()
                except:
                    review['relative_time'] = ""
                
                review['review_id'] = str(uuid.uuid4())
                review['extracted_at'] = datetime.utcnow()
                
                reviews.append(review)
                print(f"✅ Review {i+1}: {review['author_name']} - {review['rating']}⭐")
                
            except Exception as e:
                print(f"Error extracting review {i+1}: {e}")
                continue
    
    except Exception as e:
        print(f"Error scraping detailed reviews: {e}")
    
    return reviews

# Main functions for different use cases
def scrape_for_rag_system(business_name: str, location: Optional[str] = None, max_locations: int = 20) -> List[Dict]:
    """
    For RAG: Get overview data from ALL locations quickly
    """
    return bulk_scrape_all_locations(business_name, location, max_locations)

def scrape_specific_location_detailed(business_name: str, location: Optional[str] = None, max_reviews: int = 10) -> Tuple[Dict, List[Dict]]:
    """
    For detailed analysis: User picks location, get full review data
    """
    return interactive_scrape_specific_location(business_name, location, max_reviews)

def scrape_both_modes(business_name: str, location: Optional[str] = None, max_locations: int = 20, max_reviews: int = 10):
    """
    Combined: Get bulk data for RAG + detailed data for specific location
    """
    print("🚀 Starting combined scraping...\n")
    
    # Mode 1: Bulk scrape for RAG
    print("=" * 60)
    print("📊 MODE 1: BULK SCRAPING FOR RAG SYSTEM")
    print("=" * 60)
    
    bulk_data = scrape_for_rag_system(business_name, location, max_locations)
    
    print(f"\n✅ RAG data collected: {len(bulk_data)} locations")
    
    # Mode 2: Interactive detailed scraping
    if bulk_data:
        print("\n" + "=" * 60)
        print("🎯 MODE 2: INTERACTIVE DETAILED SCRAPING")
        print("=" * 60)
        
        choice = input("Do you want to get detailed reviews for a specific location? (y/n): ").strip().lower()
        
        if choice == 'y':
            location_info, detailed_reviews = scrape_specific_location_detailed(business_name, location, max_reviews)
            
            return {
                'bulk_data': bulk_data,
                'detailed_location': location_info,
                'detailed_reviews': detailed_reviews
            }
    
    return {
        'bulk_data': bulk_data,
        'detailed_location': {},
        'detailed_reviews': []
    }