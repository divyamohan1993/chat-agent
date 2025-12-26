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
    SEARCH_TIMEOUT = 30000  # 30 seconds
    
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
        budget_max: Optional[int] = None
    ) -> PropertySearchResult:
        """
        Search for properties on realtyassistant.in.
        
        Args:
            location: Location/area to search
            property_type: "Residential" or "Commercial"
            topology: BHK type or commercial subtype
            budget_min: Minimum budget in INR
            budget_max: Maximum budget in INR
            
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
                location, property_type, topology, budget_min, budget_max
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
                    await page.wait_for_load_state("networkidle", timeout=self.SEARCH_TIMEOUT)
                    
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
                            "budget_max": budget_max
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
                    "budget_max": budget_max
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
        budget_max: Optional[int]
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
        
        params['submit'] = 'Search'
        
        # Build URL
        query_string = urlencode(params)
        return f"{base_path}?{query_string}"

    
    async def _extract_results(self, page) -> tuple:
        """
        Extract property count and listings from realtyassistant.in.
        
        Args:
            page: Playwright page object
            
        Returns:
            Tuple of (count, properties list with links)
        """
        count = 0
        properties = []
        
        try:
            # Wait for property cards to load
            await page.wait_for_selector('.col-md-4, .property-card, .card', timeout=10000)
            
            # Try multiple selectors for property cards on realtyassistant.in
            property_selectors = [
                '.col-md-4 .card',  # Main property card structure
                '.property-box',
                '.property-card',
                '.listing-card',
                '[class*="property"]'
            ]
            
            elements = []
            for selector in property_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements and len(elements) > 0:
                        logger.info(f"Found {len(elements)} elements with selector: {selector}")
                        break
                except Exception:
                    continue
            
            count = len(elements)
            
            # Extract property details from cards
            for i, elem in enumerate(elements[:10]):  # Limit to 10 for performance
                try:
                    property_info = {'index': i + 1}
                    
                    # Try to get title (h5, h4, or any heading)
                    title_selectors = ['h5 a', 'h5', 'h4 a', 'h4', '.card-title', '.title', 'a.property-title']
                    for sel in title_selectors:
                        title_elem = await elem.query_selector(sel)
                        if title_elem:
                            property_info['title'] = (await title_elem.inner_text()).strip()
                            break
                    
                    # Try to get link
                    link_selectors = ['a[href*="property"]', 'a[href*="project"]', 'h5 a', 'h4 a', '.card a', 'a']
                    for sel in link_selectors:
                        link_elem = await elem.query_selector(sel)
                        if link_elem:
                            href = await link_elem.get_attribute('href')
                            if href:
                                if not href.startswith('http'):
                                    href = f"https://realtyassistant.in{href}"
                                property_info['link'] = href
                                break
                    
                    # Try to get location
                    location_selectors = ['p i.fa-map-marker', '.location', 'span.location', 'p:has(i.fa-map-marker)']
                    for sel in location_selectors:
                        loc_elem = await elem.query_selector(sel)
                        if loc_elem:
                            loc_text = await loc_elem.get_attribute('title') or await loc_elem.inner_text()
                            property_info['location'] = loc_text.strip() if loc_text else ''
                            break
                    
                    # Try to get area/size
                    area_selectors = ['p i.fa-home', '.area', '.size', 'span:has(i.fa-home)']
                    for sel in area_selectors:
                        area_elem = await elem.query_selector(sel)
                        if area_elem:
                            area_text = await area_elem.inner_text()
                            property_info['area'] = area_text.strip() if area_text else ''
                            break
                    
                    # Try to get price
                    price_selectors = ['.price', 'span:contains("₹")', 'span:contains("Request")', '.property-price', 'p:contains("₹")']
                    for sel in ['span.text-success', 'span:has-text("Request")', '.price']:
                        price_elem = await elem.query_selector(sel)
                        if price_elem:
                            property_info['price'] = (await price_elem.inner_text()).strip()
                            break
                    
                    # Try to get status
                    status_selectors = ['span.badge', '.status', '.project-status']
                    for sel in status_selectors:
                        status_elem = await elem.query_selector(sel)
                        if status_elem:
                            property_info['status'] = (await status_elem.inner_text()).strip()
                            break
                    
                    # Only add if we have at least a title
                    if property_info.get('title'):
                        properties.append(property_info)
                        
                except Exception as e:
                    logger.debug(f"Error extracting property {i}: {e}")
                    continue
            
            # If we couldn't extract from cards, count visible cards
            if count == 0:
                # Try alternate counting methods
                all_links = await page.query_selector_all('a[href*="property"], a[href*="project"]')
                count = min(len(all_links), 20)  # Cap at reasonable number
                
        except Exception as e:
            logger.error(f"Error extracting results: {e}")
        
        logger.info(f"Found {count} properties, extracted {len(properties)} details")
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
        budget_max: Optional[int] = None
    ) -> PropertySearchResult:
        """
        Synchronous version of search.
        
        Args:
            location: Search location
            property_type: Property type
            topology: BHK/subtype
            budget_min: Min budget
            budget_max: Max budget
            
        Returns:
            PropertySearchResult
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.search(location, property_type, topology, budget_min, budget_max)
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
