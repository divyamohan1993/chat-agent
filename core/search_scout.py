# =============================================================================
# RealtyAssistant AI Agent - Property Search Engine
# =============================================================================
"""
Web scraping engine for realtyassistant.in property search.
Uses Playwright for headless browser automation.
"""

import os
import re
import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from urllib.parse import urlencode, quote_plus

logger = logging.getLogger(__name__)


@dataclass
class PropertySearchResult:
    """Result from property search."""
    count: int
    properties: List[Dict[str, Any]]
    query_params: Dict[str, Any]
    success: bool
    error: Optional[str] = None
    source_url: str = ""


class PropertySearcher:
    """
    Property search engine for realtyassistant.in.
    
    Features:
    - Headless browser automation with Playwright
    - Dynamic search query building
    - Property count extraction
    - Property listing parsing
    - Retry logic for reliability
    """
    
    BASE_URL = "https://realtyassistant.in"
    SEARCH_TIMEOUT = 45000  # 45 seconds
    
    def __init__(self, headless: bool = True):
        """
        Initialize the property searcher.
        
        Args:
            headless: Run browser in headless mode
        """
        self.headless = headless
        self._browser = None
        self._context = None
        self._playwright = None
        self._initialized = False
    
    async def initialize(self) -> bool:
        """
        Initialize the Playwright browser.
        
        Returns:
            True if initialization successful
        """
        if self._initialized:
            return True
            
        try:
            from playwright.async_api import async_playwright
            
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu'
                ]
            )
            # Context is now created per-request
            # self._context = await self._browser.new_context(...)
            
            self._initialized = True
            logger.info("Playwright browser initialized")
            return True
            
        except ImportError as e:
            logger.error(f"Playwright not installed: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            return False
    
    async def search(
        self,
        location: str,
        property_type: str,
        topology: Optional[str] = None,
        budget_min: Optional[int] = None,
        budget_max: Optional[int] = None,
        project_status: Optional[str] = None,
        possession: Optional[str] = None
    ) -> PropertySearchResult:
        """
        Search for properties on realtyassistant.in.
        
        Args:
            location: Location/area to search
            property_type: "Residential" or "Commercial"
            topology: BHK type or commercial subtype
            budget_min: Minimum budget in INR
            budget_max: Maximum budget in INR
            project_status: Launching soon, New Launch, Under Construction, Ready to move in
            possession: 3 Months, 6 Months, 1 year, 2+ years, Ready To Move
            
        Returns:
            PropertySearchResult with matching properties
        """
        if not self._initialized:
            if not await self.initialize():
                return PropertySearchResult(
                    count=0,
                    properties=[],
                    query_params={},
                    success=False,
                    error="Browser initialization failed"
                )
        
        try:
            # Build search URL
            search_url = self._build_search_url(
                location, property_type, topology, budget_min, budget_max,
                project_status, possession
            )
            
            logger.info(f"Searching: {search_url}")
            
            # Create new context for this search (auto-create session)
            context = await self._browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent=(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                )
            )
            
            try:
                # Perform search
                page = await context.new_page()
                
                try:
                    await page.goto(search_url, timeout=self.SEARCH_TIMEOUT)
                    # Use domcontentloaded instead of networkidle for faster/more reliable loading
                    await page.wait_for_load_state("domcontentloaded", timeout=self.SEARCH_TIMEOUT)
                    # Give a small delay for dynamic content
                    await page.wait_for_timeout(3000)
                    
                    # Extract property count and listings
                    count, properties = await self._extract_results(page)
                    
                    return PropertySearchResult(
                        count=count,
                        properties=properties,
                        query_params={
                            "location": location,
                            "property_type": property_type,
                            "topology": topology,
                            "budget_min": budget_min,
                            "budget_max": budget_max,
                            "project_status": project_status,
                            "possession": possession
                        },
                        success=True,
                        source_url=search_url
                    )
                    
                finally:
                    await page.close()
            
            finally:
                # Close context (session)
                await context.close()
                
        except Exception as e:
            logger.error(f"Search error: {e}")
            return PropertySearchResult(
                count=0,
                properties=[],
                query_params={
                    "location": location,
                    "property_type": property_type,
                    "topology": topology,
                    "budget_min": budget_min,
                    "budget_max": budget_max,
                    "project_status": project_status,
                    "possession": possession
                },
                success=False,
                error=str(e)
            )
    
    # City ID mapping for realtyassistant.in
    CITY_IDS = {
        'noida': 10,
        'greater noida': 5,
        'greater noida west': 21,
        'lucknow': 6,
        'gurugram': 9,
        'gurgaon': 9,
        'ghaziabad': 16,
        'pune': 8,
        'thane': 17,
        'mumbai': 1,
        'navi mumbai': 11,
        'dehradun': 18,
        'agra': 19,
        'vrindavan': 20,
        'delhi': 4,
        'varanasi': 15,
        'bengaluru': 2,
        'bangalore': 2,
        # Mumbai areas
        'andheri': 1, 'bandra': 1, 'malad': 1, 'goregaon': 1, 'powai': 1,
        'worli': 1, 'borivali': 1, 'kandivali': 1, 'juhu': 1, 'kurla': 1,
    }

    # Property type options from the form
    PROPERTY_TYPES_RESIDENTIAL = [
        'Apartments', 'Villas', 'Residential Plots', 'Independent Floor',
        'Residential Studio', 'Residential Prelease', 'Other Residential'
    ]
    
    PROPERTY_TYPES_COMMERCIAL = [
        'Shop', 'Office Space', 'Commercial Plot', 'Warehouse', 'Industrial'
    ]

    def _build_search_url(
        self,
        location: str,
        property_type: str,
        topology: Optional[str],
        budget_min: Optional[int],
        budget_max: Optional[int],
        project_status: Optional[str] = None,
        possession: Optional[str] = None
    ) -> str:
        """
        Build the search URL for realtyassistant.in/properties.
        
        Returns:
            Complete search URL with proper query parameters matching the form
        """
        # Base URL with properties endpoint
        base_path = f"{self.BASE_URL}/properties"
        
        # Build query parameters matching the form
        params = {}
        
        # City - find city ID from location (sort by length to match longer names first)
        if location:
            location_lower = location.lower()
            sorted_cities = sorted(self.CITY_IDS.items(), key=lambda x: len(x[0]), reverse=True)
            for city, city_id in sorted_cities:
                if city in location_lower:
                    params['city'] = city_id
                    break
        
        # Property category: 1 = Residential, 4 = Commercial
        if property_type:
            ptype = property_type.lower()
            if 'commercial' in ptype or 'office' in ptype or 'shop' in ptype:
                params['property_category'] = 4
                # Map to commercial subtypes
                if 'shop' in ptype:
                    params['property_type'] = 'Shop'
                elif 'office' in ptype:
                    params['property_type'] = 'Office Space'
                elif 'plot' in ptype:
                    params['property_type'] = 'Commercial Plot'
            else:
                params['property_category'] = 1
                # Map to residential subtypes
                if 'villa' in ptype:
                    params['property_type'] = 'Villas'
                elif 'plot' in ptype:
                    params['property_type'] = 'Residential Plots'
                elif 'floor' in ptype or 'independent' in ptype:
                    params['property_type'] = 'Independent Floor'
                elif 'studio' in ptype:
                    params['property_type'] = 'Residential Studio'
                else:
                    params['property_type'] = 'Apartments'  # Default
        
        # Bedroom/Typology
        if topology:
            topology_lower = topology.lower()
            bhk_match = re.search(r'(\d+)\s*bhk', topology_lower)
            if bhk_match:
                bhk_num = int(bhk_match.group(1))
                if bhk_num <= 5:
                    params['bedroom'] = f"{bhk_num} BHK"
                else:
                    params['bedroom'] = "5 BHK"  # Max supported
            elif 'studio' in topology_lower:
                params['bedroom'] = 'Studio'
        
        # Project Status - exact values from form
        if project_status:
            # Exact values: Launching soon, New Launch, Under Construction, Ready to move in
            params['project_status'] = project_status
        
        # Possession within - exact values from form
        if possession:
            # Exact values: 3 Months, 6 Months, 1 year, 2+ years, Ready To Move
            params['possession'] = possession
        
        params['submit'] = 'Search'
        
        # Build URL
        query_string = urlencode(params)
        return f"{base_path}?{query_string}"


    
    async def _extract_results(self, page) -> tuple:
        """
        Extract property count and listings from realtyassistant.in.
        Uses exact selectors matching the site's HTML structure.
        
        HTML Structure (from site):
        - .property_item - Main property card container
        - .image img - Property image
        - h2.property-name-wrap a - Title and link
        - .proerty_text p - Location (with i.fa-map-marker icon)
        - span.area-icon - Area info
        - span.price-sec - Price
        - .prop-price-wrap span (near icon-document-time) - Status
        
        Args:
            page: Playwright page object
            
        Returns:
            Tuple of (count, properties list with unique links)
        """
        count = 0
        properties = []
        seen_urls = set()  # Track unique URLs to avoid duplicates
        
        try:
            # Wait for the property container to load first
            await page.wait_for_selector('#property, .properties', timeout=10000)
            
            # Give additional time for dynamic content
            await page.wait_for_timeout(2000)
            
            # Wait for actual property items to appear
            try:
                await page.wait_for_selector('.property_item', timeout=10000)
            except:
                logger.warning("No .property_item found, trying alternate selectors")
            
            # Get all property cards - use the exact selector from the HTML
            elements = await page.query_selector_all('.property_item')
            
            if not elements or len(elements) == 0:
                # Fallback: try within the grid columns
                elements = await page.query_selector_all('.col-lg-4 .property_item')
            
            if not elements or len(elements) == 0:
                # Another fallback: try just the grid column that contains property cards
                elements = await page.query_selector_all('.tab-content .col-lg-4')
            
            logger.info(f"Found {len(elements)} property card elements")
            count = len(elements)
            
            # Extract property details from each card
            for i, elem in enumerate(elements[:10]):  # Limit to 10 for performance
                try:
                    property_info = {'index': i + 1}
                    
                    # Get title and link from h2.property-name-wrap a
                    # Exact HTML: <h2 class="property-name-wrap"><a href="...">Title</a></h2>
                    link_elem = await elem.query_selector('h2.property-name-wrap a')
                    if not link_elem:
                        # Fallback: try the proerty_text path (note the typo in the actual site)
                        link_elem = await elem.query_selector('.proerty_text h2 a')
                    if not link_elem:
                        # Fallback: try any property link
                        link_elem = await elem.query_selector('a[href*="/property/"]')
                    
                    if link_elem:
                        href = await link_elem.get_attribute('href')
                        title_text = await link_elem.inner_text()
                        
                        if href and '/property/' in href:
                            if not href.startswith('http'):
                                href = f"https://realtyassistant.in{href}"
                            
                            # Skip duplicates
                            if href in seen_urls:
                                continue
                            
                            property_info['link'] = href
                            property_info['title'] = title_text.strip() if title_text else ''
                            seen_urls.add(href)
                    
                    # Skip if no link found
                    if not property_info.get('link'):
                        continue
                    
                    # Get location from .proerty_text p (contains fa-map-marker icon)
                    # Exact HTML: <p><i class="fa fa-map-marker"></i> Location Text</p>
                    loc_elem = await elem.query_selector('.proerty_text p')
                    if loc_elem:
                        loc_text = await loc_elem.inner_text()
                        if loc_text:
                            property_info['location'] = loc_text.strip()
                    
                    # Get area from span.area-icon
                    # Exact HTML: <span class="area-icon"><img ...>Area Value</span>
                    area_elem = await elem.query_selector('span.area-icon')
                    if area_elem:
                        area_text = await area_elem.inner_text()
                        if area_text:
                            # Clean area text - remove extra whitespace
                            property_info['area'] = ' '.join(area_text.split())
                    
                    # Get price from span.price-sec
                    # Exact HTML: <span class="price-sec pull-right">₹Price</span>
                    price_elem = await elem.query_selector('span.price-sec')
                    if price_elem:
                        price_text = await price_elem.inner_text()
                        if price_text:
                            property_info['price'] = price_text.strip()
                    
                    # Set default price if not found
                    if not property_info.get('price'):
                        property_info['price'] = '₹On Request'
                    
                    # Get status (possession/construction status)
                    # HTML has span with class like "possesion=wrap" (note the typo in the site)
                    # Near <i class="icon-document-time"> icon
                    status_found = False
                    
                    # First try to get all prop-price-wrap elements and look for status text
                    prop_wraps = await elem.query_selector_all('.prop-price-wrap')
                    for wrap in prop_wraps:
                        try:
                            wrap_text = await wrap.inner_text()
                            if wrap_text:
                                wrap_text = wrap_text.strip()
                                # Check for common status keywords
                                if 'New Launch' in wrap_text:
                                    property_info['status'] = 'New Launch'
                                    status_found = True
                                    break
                                elif 'Ready to move' in wrap_text or 'Ready To Move' in wrap_text:
                                    property_info['status'] = 'Ready to move in'
                                    status_found = True
                                    break
                                elif 'Under Construction' in wrap_text:
                                    property_info['status'] = 'Under Construction'
                                    status_found = True
                                    break
                                elif 'Launching soon' in wrap_text:
                                    property_info['status'] = 'Launching soon'
                                    status_found = True
                                    break
                        except:
                            continue
                    
                    # Get image from .image img
                    # Exact HTML: <div class="image"><a href="..."><img src="..." alt="..."></a></div>
                    img_elem = await elem.query_selector('.image img')
                    if img_elem:
                        img_src = await img_elem.get_attribute('src')
                        if img_src:
                            property_info['image'] = img_src
                    
                    # Only add if we have title and link
                    if property_info.get('title') and property_info.get('link'):
                        properties.append(property_info)
                        logger.debug(f"Extracted property {i+1}: {property_info.get('title', 'No title')}")
                        
                except Exception as e:
                    logger.debug(f"Error extracting property {i}: {e}")
                    continue
            
            # Fallback: if no properties extracted from cards, try to get links directly
            if len(properties) == 0:
                logger.info("Card extraction failed, trying link fallback")
                all_links = await page.query_selector_all('a[href*="/property/"]')
                unique_properties_from_links = []
                
                for link_elem in all_links[:30]:  # Check more links
                    try:
                        href = await link_elem.get_attribute('href')
                        if href and '/property/' in href and href not in seen_urls:
                            if not href.startswith('http'):
                                href = f"https://realtyassistant.in{href}"
                            
                            title = await link_elem.inner_text()
                            if title and title.strip() and len(title.strip()) > 5:  # Filter out short non-title text
                                seen_urls.add(href)
                                unique_properties_from_links.append({
                                    'index': len(unique_properties_from_links) + 1,
                                    'title': title.strip(),
                                    'link': href,
                                    'price': '₹On Request'
                                })
                    except:
                        continue
                
                # Take unique properties only
                properties = unique_properties_from_links[:10]
                count = max(count, len(properties))
                logger.info(f"Fallback extracted {len(properties)} properties from links")
                
        except Exception as e:
            logger.error(f"Error extracting results: {e}")
        
        logger.info(f"Found {count} total property cards, extracted {len(properties)} with unique URLs")
        return count, properties
    
    async def close(self):
        """Close the browser and cleanup resources."""
        try:
            # if self._context:
            #     await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            
            self._initialized = False
            logger.info("Browser closed")
            
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
    
    def search_sync(
        self,
        location: str,
        property_type: str,
        topology: Optional[str] = None,
        budget_min: Optional[int] = None,
        budget_max: Optional[int] = None,
        project_status: Optional[str] = None,
        possession: Optional[str] = None
    ) -> PropertySearchResult:
        """
        Synchronous version of search.
        
        Args:
            location: Search location
            property_type: Property type
            topology: BHK/subtype
            budget_min: Min budget
            budget_max: Max budget
            project_status: Launching soon, New Launch, Under Construction, Ready to move in
            possession: 3 Months, 6 Months, 1 year, 2+ years, Ready To Move
            
        Returns:
            PropertySearchResult
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.search(location, property_type, topology, budget_min, budget_max,
                       project_status, possession)
        )

    
    @staticmethod
    def parse_budget(budget_str: str) -> tuple:
        """
        Parse budget string into min/max values.
        
        Args:
            budget_str: Budget string like "50 lakhs", "1-2 crore", etc.
            
        Returns:
            Tuple of (min_budget, max_budget) in rupees
        """
        if not budget_str:
            return None, None
        
        # Clean and normalize the budget string
        budget_lower = budget_str.lower().strip()
        
        # Remove common non-numeric phrases
        budget_lower = re.sub(r'(around|approximately|about|give or take|roughly|maybe|nearly|almost)', '', budget_lower)
        budget_lower = re.sub(r'\s+', ' ', budget_lower).strip()
        
        # Conversion factors
        lakh = 100000
        crore = 10000000
        
        # Extract numbers (handle commas and decimals properly)
        # Remove commas from numbers first
        budget_clean = re.sub(r'(\d),(\d)', r'\1\2', budget_lower)
        
        # Find numbers (only valid decimal numbers, not just periods)
        numbers = re.findall(r'\d+(?:\.\d+)?', budget_clean)
        
        if not numbers:
            return None, None
        
        # Filter out any invalid numbers (like just '.')
        valid_numbers = []
        for num in numbers:
            try:
                val = float(num)
                if val > 0:
                    valid_numbers.append(num)
            except ValueError:
                continue
        
        if not valid_numbers:
            return None, None
        
        # Helper to determine multiplier based on context
        def get_multiplier_for_value(value_str, budget_text, is_second=False):
            """Determine the correct multiplier for a value based on surrounding text."""
            val = float(value_str)
            
            # For ranges like "75 lakhs to 1 crore", split on common separators
            separators = [' to ', ' - ', '-', ' and ', ',']
            parts = [budget_text]
            for sep in separators:
                new_parts = []
                for p in parts:
                    new_parts.extend(p.split(sep))
                parts = new_parts
            
            # Get the relevant part based on position
            if is_second and len(parts) > 1:
                context = parts[1] if len(parts) > 1 else parts[0]
            else:
                context = parts[0] if parts else budget_text
            
            context = context.lower().strip()
            
            # Look for unit in the relevant context
            if 'crore' in context or ' cr' in context or context.endswith('cr'):
                return crore
            elif 'lakh' in context or 'lac' in context:
                return lakh
            elif 'k' in context:
                return 1000
            
            # No explicit unit - use heuristics based on value magnitude
            if val < 10:
                # Very small number - likely crores
                return crore
            elif val < 500:
                # Reasonable range for lakhs
                return lakh
            else:
                return 1
        
        try:
            if len(valid_numbers) == 1:
                # Single value - use as max, set min as 70% of max
                multiplier = get_multiplier_for_value(valid_numbers[0], budget_clean, False)
                max_val = int(float(valid_numbers[0]) * multiplier)
                min_val = int(max_val * 0.7)
                return min_val, max_val
            else:
                # Range - determine multiplier for each number independently
                mult1 = get_multiplier_for_value(valid_numbers[0], budget_clean, False)
                mult2 = get_multiplier_for_value(valid_numbers[1], budget_clean, True)
                
                min_val = int(float(valid_numbers[0]) * mult1)
                max_val = int(float(valid_numbers[1]) * mult2)
                
                # Ensure min <= max
                if min_val > max_val:
                    min_val, max_val = max_val, min_val
                return min_val, max_val
        except (ValueError, IndexError):
            return None, None
    
    def is_available(self) -> bool:
        """Check if Playwright is available."""
        try:
            from playwright.async_api import async_playwright
            return True
        except ImportError:
            return False


# Singleton instance
_searcher_instance: Optional[PropertySearcher] = None


def get_property_searcher(headless: bool = True) -> PropertySearcher:
    """
    Get or create a singleton PropertySearcher instance.
    
    Args:
        headless: Run in headless mode
        
    Returns:
        PropertySearcher instance
    """
    global _searcher_instance
    
    if _searcher_instance is None:
        _searcher_instance = PropertySearcher(headless=headless)
    
    return _searcher_instance
