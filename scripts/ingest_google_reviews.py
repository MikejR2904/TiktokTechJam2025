from src.data.ingest import *

business_name = "McDonald's"
location = "Singapore"
    
bulk_data = scrape_for_rag_system("McDonald's", "Singapore", max_locations=25)
for location in bulk_data:
    print(f"Name: {location['name']}")
    print(f"Address: {location['address']}")
    print(f"Rating: {location['overall_rating']} ({location['review_count']} reviews)")
    print(f"Sample reviews: {location['sample_reviews']}")