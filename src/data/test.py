import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from pydantic import ValidationError
import uuid
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

def get_stable_chrome_driver():
    """Get a more stable Chrome driver with updated options"""
    options = Options()
    
    # Essential anti-detection options
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
        
        # Execute stealth scripts
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        return driver
    except Exception as e:
        print(f"Error creating Chrome driver: {e}")
        return None

def wait_and_find_elements(driver, selectors, timeout=10, min_elements=1):
    """Try multiple selectors and return the first one that finds elements"""
    for selector in selectors:
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, selector)) >= min_elements
            )
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if len(elements) >= min_elements:
                print(f"Found {len(elements)} elements with selector: {selector}")
                return elements
        except:
            continue
    return []

def search_google_maps(driver, query):
    """Enhanced search function with better error handling"""
    try:
        print(f"Navigating to Google Maps...")
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
                print(f"Found search box with: {selector}")
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
                    print(f"Clicked search button: {selector}")
                    break
                except:
                    continue
            else:
                # Fallback to Enter key
                search_box.send_keys(Keys.RETURN)
                print("Used Enter key to search")
        
        except Exception as e:
            print(f"Error with search button, trying Enter key: {e}")
            search_box.send_keys(Keys.RETURN)
        
        # Wait for results to load
        time.sleep(5)
        
        # Scroll to load more results
        print("Scrolling to load results...")
        for i in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            print(f"Scroll {i+1}/3")
        
        return True
        
    except Exception as e:
        print(f"Error in search: {e}")
        return False

def bulk_scrape_all_locations_fixed(business_name: str, location: Optional[str] = None, max_locations: int = 20) -> List[Dict]:
    """
    Fixed version of bulk scraping with updated selectors
    """
    query = f"{business_name}, {location}" if location else business_name
    driver = None
    all_locations_data = []
    
    try:
        print(f"Bulk scraping: {query}")
        driver = get_stable_chrome_driver()
        
        if not driver:
            print("Failed to create driver")
            return []
        
        # Search for business
        if not search_google_maps(driver, query):
            print("Search failed")
            return []
        
        print("Extracting location data...")
        
        # Updated selectors for business cards - Google Maps frequently changes these
        business_card_selectors = [
            "div[role='article']",  # Most common
            ".Nv2PK",              # Alternative
            "[data-result-index]",  # Sometimes used
            ".lI9IFe",             # Another option
            "[jsaction*='mouseover']",  # Interactive elements
            "div[data-cid]",       # Business with CID
            ".hfpxzc",             # Link containers
        ]
        
        business_cards = wait_and_find_elements(driver, business_card_selectors, timeout=10, min_elements=1)
        
        if not business_cards:
            print("No business cards found. Trying alternative approach...")
            
            # Alternative: look for any clickable business links
            link_selectors = [
                "a[href*='/maps/place/']",
                "a[data-cid]",
                "a[href*='@']"  # Coordinate-based links
            ]
            
            business_cards = wait_and_find_elements(driver, link_selectors, timeout=5)
            
            if business_cards:
                print(f"Found {len(business_cards)} business links as fallback")
            else:
                print("No business data found at all")
                # Debug: save page source
                with open("debug_page_source.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print("Saved page source to debug_page_source.html")
                return []
        
        # Limit results
        business_cards = business_cards[:max_locations]
        print(f"Processing {len(business_cards)} locations")
        
        for i, card in enumerate(business_cards):
            try:
                location_data = {}
                print(f"\nProcessing location {i+1}...")
                
                # Extract business name with multiple strategies
                name_selectors = [
                    ".qBF1Pd",                    # Common name selector
                    ".fontHeadlineSmall",         # Alternative
                    "h3",                         # Header
                    ".fqFHhd",                    # Another option
                    "[role='button'] span",       # Button text
                    "a[aria-label]"               # Link with aria-label
                ]
                
                name_found = False
                for selector in name_selectors:
                    try:
                        name_elem = card.find_element(By.CSS_SELECTOR, selector)
                        name_text = name_elem.text.strip()
                        if name_text and len(name_text) > 2 and len(name_text) < 100:
                            location_data['name'] = name_text
                            name_found = True
                            print(f"  Name: {name_text}")
                            break
                    except:
                        continue
                
                if not name_found:
                    location_data['name'] = f"{business_name} Location {i+1}"
                
                # Extract address with better logic
                address_selectors = [
                    ".W4Efsd",                    # Common address class
                    "[data-value='Address']",     # Data attribute
                    ".fontBodyMedium",            # Font style
                    ".UaQhfb",                    # Alternative
                    "div[style*='color']:last-child"  # Styled divs
                ]
                
                address_found = False
                for selector in address_selectors:
                    try:
                        addr_elements = card.find_elements(By.CSS_SELECTOR, selector)
                        for addr_elem in addr_elements:
                            addr_text = addr_elem.text.strip()
                            # Check if it looks like an address
                            if (len(addr_text) > 10 and 
                                (any(keyword in addr_text.lower() for keyword in 
                                    ['street', 'road', 'ave', 'blvd', 'drive', 'singapore', 'block', 'mall', 'centre']) or 
                                re.search(r'\d{3,}', addr_text) or  # Postal codes
                                'Singapore' in addr_text)):
                                location_data['address'] = addr_text
                                address_found = True
                                print(f"  Address: {addr_text[:50]}...")
                                break
                        if address_found:
                            break
                    except:
                        continue
                
                if not address_found:
                    location_data['address'] = "Address not found"
                
                # Extract rating with improved selectors
                rating_selectors = [
                    "span[aria-label*='star']",
                    "span[aria-label*='rating']",
                    ".MW4etd",
                    "[role='img'][aria-label*='star']"
                ]
                
                rating_found = False
                for selector in rating_selectors:
                    try:
                        rating_elem = card.find_element(By.CSS_SELECTOR, selector)
                        aria_label = rating_elem.get_attribute('aria-label') or ''
                        
                        # Extract rating from aria-label
                        rating_patterns = [
                            r'(\d+\.?\d*)\s*star',
                            r'(\d+\.?\d*)\s*out of',
                            r'Rated (\d+\.?\d*)',
                            r'(\d+\.?\d*)/5'
                        ]
                        
                        for pattern in rating_patterns:
                            match = re.search(pattern, aria_label, re.IGNORECASE)
                            if match:
                                rating_value = float(match.group(1))
                                if 0 <= rating_value <= 5:
                                    location_data['overall_rating'] = rating_value
                                    rating_found = True
                                    print(f"  Rating: {rating_value}")
                                    break
                        
                        if rating_found:
                            break
                            
                    except:
                        continue
                
                if not rating_found:
                    location_data['overall_rating'] = 0.0
                
                # Extract review count
                review_count_selectors = [
                    "span[aria-label*='review']",
                    ".UY7F9",
                    "button[aria-label*='review']",
                    "[class*='review'][class*='count']"
                ]
                
                review_count_found = False
                for selector in review_count_selectors:
                    try:
                        count_elem = card.find_element(By.CSS_SELECTOR, selector)
                        count_text = count_elem.get_attribute('aria-label') or count_elem.text
                        
                        # Extract number from text
                        count_patterns = [
                            r'(\d+)\s*review',
                            r'\((\d+)\)',
                            r'(\d+)\s*rating'
                        ]
                        
                        for pattern in count_patterns:
                            match = re.search(pattern, count_text, re.IGNORECASE)
                            if match:
                                count_value = int(match.group(1))
                                location_data['review_count'] = count_value
                                review_count_found = True
                                print(f"  Review count: {count_value}")
                                break
                        
                        if review_count_found:
                            break
                            
                    except:
                        continue
                
                if not review_count_found:
                    location_data['review_count'] = 0
                
                # Extract business category/type
                category_selectors = [
                    ".W4Efsd:first-child",
                    ".fontBodyMedium:first-child",
                    "[class*='category']",
                    ".YhemCb"
                ]
                
                category_found = False
                for selector in category_selectors:
                    try:
                        cat_elem = card.find_element(By.CSS_SELECTOR, selector)
                        cat_text = cat_elem.text.strip()
                        
                        # Skip if it looks like address, rating, or hours
                        if (cat_text and len(cat_text) < 50 and
                            not re.search(r'\d+\.?\d*\s*star', cat_text.lower()) and 
                            not re.search(r'\d+.*(?:street|road|ave|singapore)', cat_text.lower()) and
                            not re.search(r'open|closed|hours', cat_text.lower())):
                            location_data['category'] = cat_text
                            category_found = True
                            print(f"  Category: {cat_text}")
                            break
                    except:
                        continue
                
                if not category_found:
                    location_data['category'] = "Restaurant"
                
                # Generate place_id
                place_query = f"{location_data['name']}, {location_data['address']}"
                location_data['place_id'] = str(int(hashlib.md5(place_query.encode()).hexdigest()[:12], 16))
                
                # Add metadata
                location_data['extraction_type'] = 'bulk_search_results'
                location_data['extracted_at'] = datetime.utcnow()
                location_data['business_query'] = query
                
                all_locations_data.append(location_data)
                print(f"  Successfully extracted location {i+1}")
                
            except Exception as e:
                print(f"Error extracting location {i+1}: {e}")
                continue
        
        print(f"\nBulk extraction complete: {len(all_locations_data)} locations")
        
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

# Test function
def test_scraper():
    """Test the scraper with a simple query"""
    print("Testing scraper...")
    results = bulk_scrape_all_locations_fixed("McDonald's", "Singapore", max_locations=5)
    
    print(f"\nTest Results: {len(results)} locations found")
    for i, loc in enumerate(results):
        print(f"\n{i+1}. {loc.get('name', 'Unknown')}")
        print(f"   Address: {loc.get('address', 'N/A')}")
        print(f"   Rating: {loc.get('overall_rating', 0)} ({loc.get('review_count', 0)} reviews)")
        print(f"   Category: {loc.get('category', 'N/A')}")

if __name__ == "__main__":
    test_scraper()