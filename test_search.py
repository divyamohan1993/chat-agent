
import asyncio
import logging
import sys
from core.search_scout import PropertySearcher

# Configure simple logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def test_search():
    print("\n" + "="*50)
    print("TESTING REALTYASSISTANT.IN SEARCH FUNCTIONALITY")
    print("="*50 + "\n")
    
    searcher = PropertySearcher(headless=True) # Visible browser for debugging if needed, but keeping headless for consistency
    initialized = await searcher.initialize()
    
    if not initialized:
        print("[ERROR] Failed to initialize PropertySearcher (is Playwright installed?)")
        return

    test_cases = [
        {
            "name": "2 BHK Apartments in Noida",
            "params": {
                "location": "Noida",
                "property_type": "residential",
                "topology": "2 BHK"
            }
        },
        {
            "name": "Commercial Office in Gurugram",
            "params": {
                "location": "Gurugram",
                "property_type": "commercial",
                "topology": "Office"
            }
        },
        {
            "name": "Villas in Greater Noida",
            "params": {
                "location": "Greater Noida",
                "property_type": "residential",
                "topology": "Villas" # Will be mapped in searcher logic if passed as property_type usually
            }
        }
    ]

    for test in test_cases:
        print(f"🔍 Executing: {test['name']}")
        print(f"   Params: {test['params']}")
        
        try:
            result = await searcher.search(
                location=test['params']['location'],
                property_type=test['params']['property_type'],
                topology=test['params']['topology']
            )
            
            if result.success:
                print(f"   [SUCCESS] Found {result.count} properties")
                print(f"   Source URL: {result.source_url}")
                if result.count > 0:
                    first_prop = result.properties[0]
                    print(f"   Sample Property: {first_prop.get('title', 'No Title')} - {first_prop.get('price', 'No Price')}")
                    print(f"      Location: {first_prop.get('location', 'Unknown')}")
            else:
                print(f"   [FAILED] {result.error}")
                print(f"   Source URL: {result.source_url}")
                
        except Exception as e:
            print(f"   [EXCEPTION] {str(e)}")
        
        print("\n" + "-"*50 + "\n")

    await searcher.close()

if __name__ == "__main__":
    asyncio.run(test_search())
