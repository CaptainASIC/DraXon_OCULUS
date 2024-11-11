"""RSI Scraper adapter for OCULUS"""

import aiohttp
import asyncio
import logging
import json
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin
from lxml import html, etree
import re
import random

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
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'User-Agent': RSI_CONFIG['USER_AGENT'],
            'Cache-Control': 'no-cache',
            'Cookie': 'Rsi-Token=',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'DNT': '1',
            'Pragma': 'no-cache'
        }
        self.retry_statuses = {408, 429, 500, 502, 503, 504}
        self.max_retries = 5

    async def _make_request(self, url: str, method: str = "get", json_data: Dict = None) -> Optional[aiohttp.ClientResponse]:
        """Make a request to RSI website with exponential backoff retry
        
        Args:
            url (str): URL to request
            method (str, optional): HTTP method. Defaults to "get".
            json_data (Dict, optional): JSON data for POST requests. Defaults to None.
        
        Returns:
            Optional[aiohttp.ClientResponse]: Response if successful, None otherwise
        """
        try:
            timeout = aiohttp.ClientTimeout(
                total=30,
                connect=10,
                sock_read=20,
                sock_connect=10
            )

            for attempt in range(self.max_retries):
                try:
                    # Add jitter to prevent thundering herd
                    if attempt > 0:
                        jitter = random.uniform(0.1, 0.5)
                        await asyncio.sleep(min(2 ** attempt + jitter, 10))

                    # Clone headers and add random request ID for debugging
                    request_headers = dict(self.headers)
                    request_headers['X-Request-ID'] = f'oculus-{random.randint(1000, 9999)}'

                    if method.lower() == "get":
                        async with self.session.get(url, headers=request_headers, timeout=timeout) as response:
                            if response.status == 200:
                                return response
                            elif response.status in self.retry_statuses:
                                logger.warning(
                                    f"Request failed with status {response.status} "
                                    f"(attempt {attempt + 1}/{self.max_retries})"
                                )
                                continue
                            else:
                                logger.error(
                                    f"Request failed with status {response.status}: "
                                    f"{await response.text()}"
                                )
                                return None
                    else:  # POST
                        async with self.session.post(url, headers=request_headers, json=json_data, timeout=timeout) as response:
                            if response.status == 200:
                                return response
                            elif response.status in self.retry_statuses:
                                logger.warning(
                                    f"Request failed with status {response.status} "
                                    f"(attempt {attempt + 1}/{self.max_retries})"
                                )
                                continue
                            else:
                                logger.error(
                                    f"Request failed with status {response.status}: "
                                    f"{await response.text()}"
                                )
                                return None

                except asyncio.TimeoutError:
                    logger.warning(
                        f"Request timed out (attempt {attempt + 1}/{self.max_retries})"
                    )
                except aiohttp.ClientError as e:
                    logger.warning(
                        f"Client error on attempt {attempt + 1}/{self.max_retries}: {str(e)}"
                    )
                except Exception as e:
                    logger.error(f"Unexpected error during request: {str(e)}")
                    return None

            logger.error(f"All {self.max_retries} attempts failed for URL: {url}")
            return None

        except Exception as e:
            logger.error(f"Error making request: {str(e)}")
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
            if not content.strip():
                logger.error("Received empty response from RSI website")
                return None

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

            # Extract basic info with error handling
            try:
                name_elem = tree.xpath('//*[@id="organization"]//h1/text()')
                if name_elem:
                    result["name"] = name_elem[0].strip('/ ')

                logo_elem = tree.xpath('//*[contains(@class, "logo") and contains(@class, "noshadow")]/img/@src')
                if logo_elem:
                    result["logo"] = urljoin(RSI_CONFIG['BASE_URL'], logo_elem[0])

                banner_elem = tree.xpath('//*[contains(@class, "banner")]/img/@src')
                if banner_elem:
                    result["banner"] = urljoin(RSI_CONFIG['BASE_URL'], banner_elem[0])

                # Extract focus info
                primary_img = tree.xpath('//*[contains(@class, "primary") and contains(@class, "tooltip-wrap")]/img/@src')
                if primary_img:
                    result["focus"]["primary"]["image"] = urljoin(RSI_CONFIG['BASE_URL'], primary_img[0])

                primary_name = tree.xpath('//*[contains(@class, "primary") and contains(@class, "tooltip-wrap")]/img/@alt')
                if primary_name:
                    result["focus"]["primary"]["name"] = primary_name[0].strip()

                secondary_img = tree.xpath('//*[contains(@class, "secondary") and contains(@class, "tooltip-wrap")]/img/@src')
                if secondary_img:
                    result["focus"]["secondary"]["image"] = urljoin(RSI_CONFIG['BASE_URL'], secondary_img[0])

                secondary_name = tree.xpath('//*[contains(@class, "secondary") and contains(@class, "tooltip-wrap")]/img/@alt')
                if secondary_name:
                    result["focus"]["secondary"]["name"] = secondary_name[0].strip()

            except Exception as e:
                logger.error(f"Error extracting organization info: {str(e)}")
                return None

            # Get member count from search API
            try:
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

            except Exception as e:
                logger.error(f"Error getting member count: {str(e)}")
                # Continue with the data we have

            # Verify we got meaningful data
            if not result["name"]:
                logger.error("Failed to extract organization name")
                return None

            # Cache the result
            await self.redis.set(
                cache_key,
                json.dumps(result),
                ex=CACHE_SETTINGS['ORG_DATA_TTL']
            )

            return result

        except Exception as e:
            logger.error(f"Error fetching org info: {str(e)}")
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
                logger.error(f"Invalid response format for members page {page}")
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
                    logger.error(f"Error processing member: {str(e)}")
                    continue

            if not result:
                logger.warning(f"No members found on page {page}")
                return []

            # Cache the result
            await self.redis.set(
                cache_key,
                json.dumps(result),
                ex=CACHE_SETTINGS['MEMBER_DATA_TTL']
            )

            return result

        except Exception as e:
            logger.error(f"Error fetching org members: {str(e)}")
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
            if not content.strip():
                logger.error("Received empty response for user profile")
                return None

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

            try:
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

            except Exception as e:
                logger.error(f"Error extracting user info: {str(e)}")
                return None

            # Verify we got meaningful data
            if not result["profile"]["display"]:
                logger.error("Failed to extract user display name")
                return None

            # Cache the result
            await self.redis.set(
                cache_key,
                json.dumps(result),
                ex=CACHE_SETTINGS['MEMBER_DATA_TTL']
            )

            return result

        except Exception as e:
            logger.error(f"Error fetching user info: {str(e)}")
            return None
