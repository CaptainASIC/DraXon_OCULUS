"""RSI Scraper adapter for OCULUS"""

import aiohttp
import asyncio
import logging
import json
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin
from lxml import html, etree
import re

from .constants import RSI_CONFIG, CACHE_SETTINGS

logger = logging.getLogger('DraXon_OCULUS')

class RSIScraper:
    """Handles direct RSI website scraping"""
    
    def __init__(self, session: aiohttp.ClientSession, redis):
        """Initialize the scraper
        
        Args:
            session (aiohttp.ClientSession): Aiohttp session for requests
            redis: Redis connection for caching
        """
        self.session = session
        self.redis = redis
        self.headers = {
            'Accept-Language': 'en-US,en;q=0.5',
            'User-Agent': RSI_CONFIG['USER_AGENT'],
            'Cache-Control': 'no-cache',
            'Cookie': 'Rsi-Token='
        }

    async def _make_request(self, url: str, method: str = "get", json_data: Dict = None) -> Optional[aiohttp.ClientResponse]:
        """Make a request to RSI website
        
        Args:
            url (str): URL to request
            method (str, optional): HTTP method. Defaults to "get".
            json_data (Dict, optional): JSON data for POST requests. Defaults to None.
        
        Returns:
            Optional[aiohttp.ClientResponse]: Response if successful, None otherwise
        """
        try:
            for attempt in range(3):
                try:
                    if method.lower() == "get":
                        async with self.session.get(url, headers=self.headers) as response:
                            if response.status == 200:
                                return response
                            elif response.status == 429:  # Rate limit
                                await asyncio.sleep(2 ** attempt)
                            else:
                                logger.error(f"Request failed with status {response.status}")
                                return None
                    else:  # POST
                        async with self.session.post(url, headers=self.headers, json=json_data) as response:
                            if response.status == 200:
                                return response
                            elif response.status == 429:  # Rate limit
                                await asyncio.sleep(2 ** attempt)
                            else:
                                logger.error(f"Request failed with status {response.status}")
                                return None
                except Exception as e:
                    logger.error(f"Request attempt {attempt + 1} failed: {e}")
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
            return None
        except Exception as e:
            logger.error(f"Error making request: {e}")
            return None

    async def get_organization_info(self, sid: str) -> Optional[Dict[str, Any]]:
        """Get organization information
        
        Args:
            sid (str): Organization SID
            
        Returns:
            Optional[Dict[str, Any]]: Organization info if successful, None otherwise
        """
        try:
            # Check cache first
            cache_key = f'org_info:{sid}'
            cached = await self.redis.get(cache_key)
            if cached:
                return json.loads(cached)

            # Make request
            url = f"{RSI_CONFIG['BASE_URL']}/orgs/{sid}"
            response = await self._make_request(url)
            if not response:
                return None

            content = await response.text()
            tree = html.fromstring(content)

            # Extract organization info
            result = {
                "url": url,
                "sid": sid,
                "name": "",
                "logo": "",
                "banner": "",
                "members": 0,
                "focus": {
                    "primary": {"name": "", "image": ""},
                    "secondary": {"name": "", "image": ""}
                }
            }

            # Extract basic info
            for v in tree.xpath('//*[@id="organization"]//h1/text()'):
                result["name"] = v.strip('/ ')
                break

            for v in tree.xpath('//*[contains(@class, "logo") and contains(@class, "noshadow")]/img/@src'):
                result["logo"] = urljoin(RSI_CONFIG['BASE_URL'], v)
                break

            for v in tree.xpath('//*[contains(@class, "banner")]/img/@src'):
                result["banner"] = urljoin(RSI_CONFIG['BASE_URL'], v)
                break

            # Extract focus info
            for v in tree.xpath('//*[contains(@class, "primary") and contains(@class, "tooltip-wrap")]/img/@src'):
                result["focus"]["primary"]["image"] = urljoin(RSI_CONFIG['BASE_URL'], v)
                break
            for v in tree.xpath('//*[contains(@class, "primary") and contains(@class, "tooltip-wrap")]/img/@alt'):
                result["focus"]["primary"]["name"] = v.strip()
                break

            for v in tree.xpath('//*[contains(@class, "secondary") and contains(@class, "tooltip-wrap")]/img/@src'):
                result["focus"]["secondary"]["image"] = urljoin(RSI_CONFIG['BASE_URL'], v)
                break
            for v in tree.xpath('//*[contains(@class, "secondary") and contains(@class, "tooltip-wrap")]/img/@alt'):
                result["focus"]["secondary"]["name"] = v.strip()
                break

            # Get member count from search API
            search_url = f"{RSI_CONFIG['BASE_URL']}/api/orgs/getOrgs"
            search_data = {
                "search": sid,
                "pagesize": 1,
                "page": 1
            }
            search_response = await self._make_request(search_url, "post", search_data)
            if search_response:
                search_data = await search_response.json()
                if search_data.get('success') == 1:
                    search_tree = html.fromstring(search_data['data']['html'])
                    for org_data in search_tree.xpath('//*[contains(@class, "org-cell")]'):
                        org_sid = org_data.xpath('.//*[@class="symbol"]/text()')
                        if org_sid and org_sid[0].strip() == sid:
                            members = org_data.xpath('.//*[contains(@class, "value")]/text()')[-1]
                            result["members"] = int(members)
                            break

            # Cache the result
            await self.redis.set(
                cache_key,
                json.dumps(result),
                ex=CACHE_SETTINGS['ORG_DATA_TTL']
            )

            return result

        except Exception as e:
            logger.error(f"Error fetching org info: {e}")
            return None

    async def get_organization_members(self, sid: str, page: int = 1) -> List[Dict[str, Any]]:
        """Get organization members
        
        Args:
            sid (str): Organization SID
            page (int, optional): Page number. Defaults to 1.
            
        Returns:
            List[Dict[str, Any]]: List of member data
        """
        try:
            # Check cache first
            cache_key = f'org_members:{sid}:page:{page}'
            cached = await self.redis.get(cache_key)
            if cached:
                return json.loads(cached)

            # Make request
            url = f"{RSI_CONFIG['BASE_URL']}/api/orgs/getOrgMembers"
            json_data = {
                "symbol": sid,
                "search": "",
                "pagesize": RSI_CONFIG['MEMBERS_PER_PAGE'],
                "page": page
            }

            response = await self._make_request(url, "post", json_data)
            if not response:
                return []

            data = await response.json()
            if data.get('success') != 1 or not data.get('data', {}).get('html'):
                return []

            tree = html.fromstring(data['data']['html'])
            result = []

            for member_item in tree.xpath("//*[contains(@class, 'member-item')]"):
                try:
                    user = {}
                    
                    # Get handle
                    handle = member_item.xpath(".//*[contains(@class, 'nick')]/text()")
                    if not handle:
                        continue
                    user["handle"] = handle[0].strip()

                    # Get display name
                    display = member_item.xpath(".//*[contains(@class, ' name')]/text()")
                    user["display"] = display[0].strip() if display else user["handle"]

                    # Get rank
                    rank = member_item.xpath(".//*[contains(@class, 'rank')]/text()")
                    user["rank"] = rank[0].strip() if rank else ""

                    # Get stars
                    stars_elem = member_item.xpath(".//*[contains(@class, 'stars') and contains(@style, .)]")
                    if stars_elem:
                        style = stars_elem[0].attrib["style"]
                        match = re.search(r":\s*([0-9]*)\%", style, re.IGNORECASE)
                        if match:
                            user["stars"] = int(int(match.group(1)) / 20)
                    else:
                        user["stars"] = 0

                    # Get roles
                    user["roles"] = []
                    roles = member_item.xpath(".//*[contains(@class, 'rolelist')]/li/text()")
                    for role in roles:
                        user["roles"].append(role.strip())

                    # Get image
                    image = member_item.xpath(".//img/@src")
                    if image:
                        user["image"] = urljoin(RSI_CONFIG['BASE_URL'], image[0].strip())

                    result.append(user)

                except Exception as e:
                    logger.error(f"Error processing member: {e}")
                    continue

            # Cache the result
            await self.redis.set(
                cache_key,
                json.dumps(result),
                ex=CACHE_SETTINGS['MEMBER_DATA_TTL']
            )

            return result

        except Exception as e:
            logger.error(f"Error fetching org members: {e}")
            return []

    async def get_user_info(self, handle: str) -> Optional[Dict[str, Any]]:
        """Get user information
        
        Args:
            handle (str): RSI handle
            
        Returns:
            Optional[Dict[str, Any]]: User info if successful, None otherwise
        """
        try:
            # Check cache first
            cache_key = f'rsi_user:{handle.lower()}'
            cached = await self.redis.get(cache_key)
            if cached:
                return json.loads(cached)

            # Make request to user profile page
            url = f"{RSI_CONFIG['BASE_URL']}/citizens/{handle}"
            response = await self._make_request(url)
            if not response:
                return None

            content = await response.text()
            tree = html.fromstring(content)

            # Extract user info
            result = {
                "profile": {
                    "id": "",
                    "handle": handle,
                    "display": "",
                    "enlisted": "",
                    "image": ""
                },
                "organization": {},
                "affiliation": []
            }

            # Get basic profile info
            display = tree.xpath('//*[contains(@class, "profile")]//*[contains(@class, "info")]//*[contains(@class, "value")]/text()')
            if display:
                result["profile"]["display"] = display[0].strip()
            else:
                result["profile"]["display"] = handle

            enlisted = tree.xpath('//*[contains(@class, "profile-content")]//*[contains(@class, "left-col")]//*[contains(@class, "value")]/text()')
            if enlisted:
                result["profile"]["enlisted"] = enlisted[0].strip()

            image = tree.xpath('//*[contains(@class, "thumb")]/img/@src')
            if image:
                result["profile"]["image"] = urljoin(RSI_CONFIG['BASE_URL'], image[0])

            # Get organization info
            org_blocks = tree.xpath('//*[contains(@class, "main-org") or contains(@class, "affiliate-org")]')
            for org_block in org_blocks:
                org_data = {}
                
                sid = org_block.xpath('.//*[contains(@class, "symbol")]/text()')
                if not sid:
                    continue
                    
                org_data["sid"] = sid[0].strip()
                
                name = org_block.xpath('.//*[contains(@class, "name")]/text()')
                org_data["name"] = name[0].strip() if name else ""
                
                rank = org_block.xpath('.//*[contains(@class, "rank")]/text()')
                org_data["rank"] = rank[0].strip() if rank else ""
                
                stars = org_block.xpath('.//*[contains(@class, "stars")]/@style')
                if stars:
                    match = re.search(r":\s*([0-9]*)\%", stars[0], re.IGNORECASE)
                    if match:
                        org_data["stars"] = int(int(match.group(1)) / 20)
                else:
                    org_data["stars"] = 0

                if 'main-org' in org_block.attrib.get('class', ''):
                    result["organization"] = org_data
                else:
                    result["affiliation"].append(org_data)

            # Cache the result
            await self.redis.set(
                cache_key,
                json.dumps(result),
                ex=CACHE_SETTINGS['MEMBER_DATA_TTL']
            )

            return result

        except Exception as e:
            logger.error(f"Error fetching user info: {e}")
            return None
