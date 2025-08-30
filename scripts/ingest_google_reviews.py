import pandas as pd
import uuid
import os
from typing import List, Dict, Any
from datetime import datetime

from src.data.schema import Review
from src.data.ingest import ingest_scraped_data

business_name = "McDonald's"
location = "Singapore"

def scrap_data(business_name, location):
    scraped_data = ingest_scraped_data(business_name, location)
    return scraped_data

ingest_scraped_data(business_name, location)

# scraped_data = bulk_scrape_locations(business_name=business_name, location=location, max_locations=5)

# if scraped_data:
#     print("\nScraped Data Output:")
#     for item in scraped_data:
#         print("-----------------------------------")
#         print(f"Name: {item.get('name', 'N/A')}")
#         print(f"Address: {item.get('address', 'N/A')}")
#         print(f"Description: {item.get('description', 'N/A')}")
#         print(f"Phone Number: {item.get('phone_number', 'N/A')}")
#         print(f"Overall Rating: {item.get('overall_rating', 'N/A')}")
#         print(f"Review Count: {item.get('review_count', 'N/A')}")
#         print(f"Category: {item.get('category', 'N/A')}")
#         print(f"Place ID: {item.get('place_id', 'N/A')}")
# else:
#     print("No data was scraped.")
