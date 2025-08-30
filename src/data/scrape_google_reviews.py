import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from pydantic import ValidationError
import uuid, os
import csv
import re
import hashlib
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

def get_chrome_driver():
    options = Options()
    
    # Essential anti-detection options
    options.add_argument("--headless")
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-features=VizDisplayCompositor')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Updated user agent
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Window and performance options
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--start-maximized')
    options.add_argument('--disable-logging')
    options.add_argument('--log-level=3')
    options.add_argument('--disable-notifications')
    
    try:
        driver = webdriver.Chrome(options=options)
        
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        return driver
    except Exception as e:
        print(f"Error creating Chrome driver: {e}")
        return None

def wait_and_find_elements(driver, selectors, timeout=10, min_elements=1):
    for selector in selectors:
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, selector)) >= min_elements
            )
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if len(elements) >= min_elements:
                return elements
        except:
            continue
    return []

def search_google_maps(driver, query):
    try:
        driver.get("https://www.google.com/maps")
        time.sleep(3)
        
        # Accept cookies if present
        try:
            accept_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'I agree')]")
            accept_button.click()
            time.sleep(2)
        except:
            pass
        
        # Find search box with multiple selectors
        search_selectors = [
            "#searchboxinput",
            "input[aria-label*='Search']",
            "input[placeholder*='Search']",
            "input[data-value='Search Google Maps']"
        ]
        
        search_box = None
        for selector in search_selectors:
            try:
                search_box = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                break
            except:
                continue
        
        if not search_box:
            print("Could not find search box")
            return False
        
        # Clear and enter search query
        search_box.clear()
        time.sleep(1)
        search_box.send_keys(query)
        time.sleep(2)
        
        # Try to click search button or press enter
        try:
            search_button_selectors = [
                "#searchbox-searchbutton",
                "button[aria-label*='Search']",
                "button[data-value='Search']"
            ]
            
            for selector in search_button_selectors:
                try:
                    search_button = driver.find_element(By.CSS_SELECTOR, selector)
                    search_button.click()
                    break
                except:
                    continue
            else:
                search_box.send_keys(Keys.RETURN)
                print("Used Enter key to search")
        
        except Exception as e:
            print(f"Error with search button, trying Enter key: {e}")
            search_box.send_keys(Keys.RETURN)
        
        time.sleep(5)
        for i in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        
        return True
        
    except Exception as e:
        print(f"Error in search: {e}")
        return False

def bulk_scrape_locations(business_name: str, location: Optional[str] = None, max_locations: int = 20) -> List[Dict]:
    query = f"{business_name}, {location}" if location else business_name
    driver = None
    all_locations_data = []
    
    try:
        driver = get_chrome_driver()
        
        if not driver:
            return []
        
        if not search_google_maps(driver, query):
            return []
        
        business_card_selectors = [
            "div[role='article']",
            ".Nv2PK",
            "[data-result-index]",
            ".lI9IFe",
            "[jsaction*='mouseover']",
            "div[data-cid]",
            ".hfpxzc",
        ]
        
        business_cards = wait_and_find_elements(driver, business_card_selectors, timeout=10, min_elements=1)
        
        if not business_cards:
            link_selectors = [
                "a[href*='/maps/place/']",
                "a[data-cid]",
                "a[href*='@']"
            ]
            business_cards = wait_and_find_elements(driver, link_selectors, timeout=5)
            
            if not business_cards:
                return []
        
        business_cards = business_cards[:max_locations]
        
        for i, card in enumerate(business_cards):
            try:
                location_data = {}
                
                # Extract business name
                name_selectors = [".qBF1Pd", ".fontHeadlineSmall", "h3", ".fqFHhd", "[role='button'] span", "a[aria-label]"]
                name_found = False
                for selector in name_selectors:
                    try:
                        name_elem = card.find_element(By.CSS_SELECTOR, selector)
                        name_text = name_elem.text.strip()
                        if name_text and len(name_text) > 2 and len(name_text) < 100:
                            location_data['name'] = name_text
                            name_found = True
                            break
                    except:
                        continue
                if not name_found:
                    location_data['name'] = f"{business_name} Location {i+1}"
                
                # Extract address
                address_found = False
                description_parts = []
                
                text_elements = card.find_elements(By.CSS_SELECTOR, "span, div")
                for elem in text_elements:
                    text = elem.text.strip()
                    if not text:
                        continue
                    if re.search(r'Blk\s*\d+|street|road|avenue|bldg|building|centre|mall|#\d+-\d+|Singapore', text, re.IGNORECASE):
                        if not re.search(r'review|star|rating|open|closed|hours|mon|tue|wed|thu|fri|sat|sun|\$', text, re.IGNORECASE):
                            location_data['address'] = text
                            address_found = True
                    elif re.search(r'^\d{4}\s?\d{4}$', text.replace(' ', '')):
                        location_data['phone_number'] = text
                    elif len(text) > 10 and len(text) < 100:
                        description_parts.append(text)
                
                if address_found:
                    final_description = " · ".join(part for part in description_parts if location_data['address'] not in part)
                else:
                    final_description = " · ".join(description_parts)
                    location_data['address'] = "Address not found"

                location_data['description'] = final_description
                

                if not address_found:
                    try:
                        text_elements = card.find_elements(By.CSS_SELECTOR, "span, div")
                        for elem in text_elements:
                            text = elem.text.strip()
                            if 'Singapore' in text or re.search(r'\d{6}', text):
                                if not re.search(r'\d+\.?\d*\s*star', text.lower()) and not re.search(r'open|closed|hours', text.lower()):
                                    location_data['address'] = text
                                    address_found = True
                                    break
                        if not address_found:
                            location_data['address'] = "Address not found"
                    except:
                        location_data['address'] = "Address not found"
                
                # Extract overall rating
                rating_selectors = ["span[aria-label*='star']", "span[aria-label*='rating']", ".MW4etd", "[role='img'][aria-label*='star']"]
                rating_found = False
                for selector in rating_selectors:
                    try:
                        rating_elem = card.find_element(By.CSS_SELECTOR, selector)
                        aria_label = rating_elem.get_attribute('aria-label') or ''
                        rating_patterns = [r'(\d+\.?\d*)\s*star', r'(\d+\.?\d*)\s*out of', r'Rated (\d+\.?\d*)', r'(\d+\.?\d*)/5']
                        for pattern in rating_patterns:
                            match = re.search(pattern, aria_label, re.IGNORECASE)
                            if match:
                                rating_value = float(match.group(1))
                                if 0 <= rating_value <= 5:
                                    location_data['overall_rating'] = rating_value
                                    rating_found = True
                                    break
                        if rating_found:
                            break
                    except:
                        continue
                if not rating_found:
                    location_data['overall_rating'] = 0.0

                # Extract review count
                review_count_selectors = ["span[aria-label*='review']", ".UY7F9", "button[aria-label*='review']", "[class*='review'][class*='count']"]
                review_count_found = False
                for selector in review_count_selectors:
                    try:
                        count_elem = card.find_element(By.CSS_SELECTOR, selector)
                        count_text = count_elem.get_attribute('aria-label') or count_elem.text
                        count_patterns = [r'(\d+)\s*review', r'\((\d+)\)', r'(\d+)\s*rating']
                        for pattern in count_patterns:
                            match = re.search(pattern, count_text, re.IGNORECASE)
                            if match:
                                count_value = int(match.group(1))
                                location_data['review_count'] = count_value
                                review_count_found = True
                                break
                        if review_count_found:
                            break
                    except:
                        continue
                if not review_count_found:
                    location_data['review_count'] = 0
                
                # Extract business category/type
                category_selectors = [".W4Efsd:first-child", ".fontBodyMedium:first-child", "[class*='category']", ".YhemCb"]
                category_found = False
                location_data['category'] = "Restaurant"

                for selector in category_selectors:
                    try:
                        cat_elem = card.find_element(By.CSS_SELECTOR, selector)
                        cat_text = cat_elem.text.strip()
                        parts = re.split(r'\s*·\s*|,', cat_text)
                        for part in parts:
                            part = part.strip()
                            if (part and len(part) < 50 and not re.search(r'\d+\.?\d*\s*star|\$|open|closed|street|road|avenue|Blk|#\d+-\d+|\d{6}|dine-in|takeaway|delivery', part, re.IGNORECASE)):
                                location_data['category'] = part
                                category_found = True
                                break
                        if category_found:
                            break
                            
                    except Exception as e:
                        continue

                # Generate place_id
                place_query = f"{location_data.get('name', '')}, {location_data.get('address', '')}"
                location_data['place_id'] = str(int(hashlib.md5(place_query.encode()).hexdigest()[:12], 16))
                
                # Add metadata
                location_data['extraction_type'] = 'bulk_search_results'
                location_data['extracted_at'] = datetime.utcnow().isoformat()
                location_data['business_query'] = query
                
                all_locations_data.append(location_data)
                
            except Exception as e:
                print(f"Error extracting location {i+1}: {e}")
                continue
        
    except Exception as e:
        print(f"Error in bulk scraping: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    return all_locations_data

def scrape_google_reviews(business_name: str, location: Optional[str] = None, max_reviews: int = 10) -> List[Dict]:
    query = f"{business_name}, {location}" if location else business_name
    reviews = []
    driver = None
    
    try:
        driver = get_chrome_driver()
        if not driver:
            return []
        base_url = "https://www.google.com/maps"
        driver.get(base_url)
        time.sleep(1)
        
        # Search for the business
        try:
            search_box = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "searchboxinput"))
            )
            search_box.clear()
            search_box.send_keys(query)
            time.sleep(1)
            
            search_button = driver.find_element(By.ID, "searchbox-searchbutton")
            search_button.click()
            time.sleep(2)
            
        except Exception as e:
            print(f"❌ Error with search: {e}")
            search_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
            driver.get(search_url)
            time.sleep(2)
        
        # Wait for results and click on first business
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[role='main']"))
            )
            time.sleep(1)
            business_selectors = [
                "a[data-value='Directions']",  # Directions link
                "div[role='article'] h3 a",   # Business title link
                "a.hfpxzc",                    # Classic selector
                "[data-value='Directions'] a", # Alternative directions
                ".Nv2PK a"                     # Another possible selector
            ]
            
            clicked = False
            for selector in business_selectors:
                try:
                    business_link = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    driver.execute_script("arguments[0].click();", business_link)
                    clicked = True
                    break
                except:
                    continue
            
            if not clicked:
                print("❌ Could not click on any business result")
                return []
            time.sleep(1)
        except Exception as e:
            print(f"❌ Error clicking business: {e}")
            return []
        
        # Wait for business details to load
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))
            )
        except:
            print("❌ Business details did not load")
            return []
        
        # Try to navigate to reviews section
        try:
            reviews_selectors = [
                "button[data-value='Sort reviews']",
                "div[data-value='Reviews'] button",
                ".F7nice button[data-tab-index='1']",
                "button[aria-label*='reviews']",
                "button[jsaction*='review']"
            ]
            
            for selector in reviews_selectors:
                try:
                    reviews_tab = driver.find_element(By.CSS_SELECTOR, selector)
                    driver.execute_script("arguments[0].click();", reviews_tab)
                    time.sleep(3)
                    break
                except:
                    continue
                    
        except Exception as e:
            print(f"⚠️ Could not find reviews tab: {e}")
        
        # Scroll to load reviews
        try:
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
        except:
            pass
        
        review_containers = []
        
        # Look for review containers
        container_selectors = [
            ".jftiEf",
            "[data-review-id]",
            "div[jsaction*='review']",
            ".WMbnJf",
            ".gws-localreviews__google-review"
        ]
        
        for selector in container_selectors:
            try:
                containers = driver.find_elements(By.CSS_SELECTOR, selector)
                if containers:
                    review_containers = containers[:max_reviews]
                    break
            except:
                continue
        
        if not review_containers:
            print("❌ No review containers found, trying alternative approach...")
            
            # Alternative: look for any elements that might contain reviews
            alt_selectors = [
                "div[role='article']",
                ".review",
                "[class*='review']",
                "div[class*='Review']"
            ]
            
            for selector in alt_selectors:
                try:
                    containers = driver.find_elements(By.CSS_SELECTOR, selector)
                    if len(containers) > 1:  # Likely reviews if multiple found
                        review_containers = containers[:max_reviews]
                        break
                except:
                    continue
        
        if not review_containers:
            print("❌ No review elements found at all")
            return []
        
        # Extract data from review containers
        for i, container in enumerate(review_containers):
            try:
                review_data = {'location': location}
                
                # Extract author name
                author_found = False
                author_selectors = [
                    ".d4r55",
                    "[data-value*='contributor']",
                    ".TSUbDb a",
                    "span[class*='TSUbDb']",
                    ".reviewer-name",
                    "a[data-href*='contrib']"
                ]
                
                review_data["business_name"] = business_name
                for selector in author_selectors:
                    try:
                        author_elem = container.find_element(By.CSS_SELECTOR, selector)
                        review_data['author_name'] = author_elem.text.strip()
                        if review_data['author_name']:
                            author_found = True
                            break
                    except:
                        continue
                
                if not author_found:
                    review_data['author_name'] = "Unknown"
                
                # Extract rating
                try:
                    rating_elem = container.find_element(By.CSS_SELECTOR, "span[aria-label*='star']")
                    aria_label = rating_elem.get_attribute("aria-label")
                    rating_match = re.search(r'^(\d+)', aria_label)
                    if rating_match:
                        review_data['rating'] = int(rating_match.group(1))
                    else:
                        review_data['rating'] = 0
                except:
                    review_data['rating'] = 0
                
                # Extract review text
                text_found = False
                text_selectors = [
                    ".wiI7pd",
                    "[data-expandable-section]",
                    ".review-text",
                    "span[jsaction*='review']",
                    ".MyEned span"
                ]
                
                for selector in text_selectors:
                    try:
                        text_elem = container.find_element(By.CSS_SELECTOR, selector)
                        review_text = text_elem.text.strip()
                        if len(review_text) > 10:  # Ensure it's actual review text
                            review_data['text'] = review_text
                            text_found = True
                            break
                    except:
                        continue
                
                if not text_found:
                    review_data['text'] = ""
                
                # Extract time
                try:
                    time_selectors = [
                        ".rsqaWe",
                        "[class*='time']",
                        ".review-time"
                    ]
                    
                    for selector in time_selectors:
                        try:
                            time_elem = container.find_element(By.CSS_SELECTOR, selector)
                            review_data['relative_time'] = time_elem.text.strip()
                            break
                        except:
                            continue
                    else:
                        review_data['relative_time'] = ""
                        
                except:
                    review_data['relative_time'] = ""

                # Only add review if we found at least author or rating
                if (review_data.get("text") != "" and len(review_data["text"].strip()) > 0) and review_data['author_name'] != "Unknown" and review_data['rating'] > 0:
                    reviews.append(review_data)
                else:
                    pass
                
            except Exception as e:
                print(f"❌ Error processing review {i+1}: {e}")
                continue
        
    except Exception as e:
        print(f"❌ Main error in scraping: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

    return reviews

def save_to_csv(review_data: List[dict], filename: str):
    df_new = pd.DataFrame(review_data)
    if os.path.exists(filename) and os.path.getsize(filename) > 0:
        df_new.to_csv(filename, mode='a', header=False, index=False)
    else:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        df_new.to_csv(filename, mode='w', header=True, index=False)
