"""RSI Scraper adapter for OCULUS"""

import logging
import json
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin
from lxml import html, etree
import re
import requests
import os

from .constants import RSI_CONFIG, CACHE_SETTINGS

logger = logging.getLogger('DraXon_OCULUS')

class RSIScraper:
    """Handles direct RSI website scraping"""
    
    # Match the working API's URL patterns
    __url_organization = "https://robertsspaceindustries.com/orgs/{0}"
    __url_search_orgs = "https://robertsspaceindustries.com/api/orgs/getOrgs"
    __url_organization_members = "https://robertsspaceindustries.com/api/orgs/getOrgMembers"
    
    def __init__(self, session, redis):
        """Initialize the scraper
        
        Args:
            session: Discord bot's aiohttp session (not used for RSI requests)
            redis: Redis connection for caching
        """
        self.redis = redis
        # Match the working API's headers exactly
        self.headers = {
            'Accept-Language': 'en-US,en;q=0.5',
            'User-Agent': RSI_CONFIG['USER_AGENT'],
            'Cache-Control': 'no-cache',
            'Cookie': 'Rsi-Token='
        }
        # Get proxy settings from environment
        self.proxies = {}
        if os.getenv('HTTP_PROXY'):
            self.proxies = {'http': os.environ['HTTP_PROXY']}

    def _make_request(self, url: str, method: str = "get", json_data: Dict = None) -> Optional[requests.Response]:
        """Make a request to RSI website using requests library
        
        Args:
            url (str): URL to request
            method (str, optional): HTTP method. Defaults to "get".
            json_data (Dict, optional): JSON data for POST requests. Defaults to None.
        
        Returns:
            Optional[requests.Response]: Response if successful, None otherwise
        """
        try:
            args = {
                "url": url,
                "headers": self.headers,
                "stream": False,
                "timeout": 5,  # Match the working API's timeout
                "proxies": self.proxies,
                "verify": True  # Enable SSL verification
            }

            if json_data is not None:
                args["json"] = json_data

            if method.lower() == "post":
                return requests.post(**args)
            elif method.lower() == "get":
                return requests.get(**args)
            else:
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
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

            # Make request using the direct URL pattern
            url = self.__url_organization.format(sid)
            response = self._make_request(url, "get")
            if not response:
                return None
            if response.status_code == 404:
                return {}
            if response.status_code != 200:
                return None

            # get html contents
            tree = html.fromstring(response.content)

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

            # Get member count using the search API
            search_data = {
                "activity": [],
                "commitment": [],
                "language": [],
                "model": [],
                "pagesize": 12,
                "recruiting": [],
                "roleplay": [],
                "search": sid,
                "page": 1,
                "size": [],
                "sort": ""
            }
            
            search_response = self._make_request(self.__url_search_orgs, "post", search_data)
            if search_response and search_response.status_code == 200:
                search_data = search_response.json()
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

            # Make request using direct URL
            json_data = {
                "symbol": sid,
                "search": "",
                "pagesize": 32,  # Match the working API's page size
                "page": page
            }

            response = self._make_request(self.__url_organization_members, "post", json_data)
            if not response:
                return []
            if response.status_code != 200:
                return []

            data = response.json()
            if data.get('success') != 1:
                if data.get('code') == 'ErrApiThrottled':
                    logger.warning("Failed, retrying")
                else:
                    logger.error(f"Failed ({data.get('msg')})")
                return []

            if not data.get('data', {}).get('html', '').strip():
                return []

            tree = html.fromstring(data['data']['html'])
            result = []

            # Match the working API's member parsing logic
            index = 1
            for _ in tree.xpath("//*[contains(@class, 'member-item')]"):
                try:
                    user = {}
                    
                    # Get handle
                    handle = tree.xpath(f"//*[contains(@class, 'member-item')][{index}]//*[contains(@class, 'nick')]/text()")
                    if not handle:
                        continue
                    user["handle"] = handle[0].strip()
                    
                    # Skip if handle already exists
                    if any(existing["handle"] == user["handle"] for existing in result):
                        continue

                    # Get display name
                    display = tree.xpath(f"//*[contains(@class, 'member-item')][{index}]//*[contains(@class, ' name')]/text()")
                    user["display"] = display[0].strip() if display else user["handle"]

                    # Get rank
                    rank = tree.xpath(f"//*[contains(@class, 'member-item')][{index}]//*[contains(@class, 'rank')]")
                    if rank and rank[0].attrib['class'] == 'rank':
                        user["rank"] = rank[0].text.strip()
                    else:
                        user["rank"] = ""

                    # Get stars
                    stars_elem = tree.xpath(f"//*[contains(@class, 'member-item')][{index}]//*[contains(@class, 'stars') and contains(@style, .)]")
                    if stars_elem:
                        style = stars_elem[0].attrib["style"]
                        match = re.search(r":\s*([0-9]*)\%", style, re.IGNORECASE)
                        if match:
                            user["stars"] = int(int(match.group(1)) / 20)
                    else:
                        user["stars"] = 0

                    # Get roles
                    user["roles"] = []
                    roles = tree.xpath(f"//*[contains(@class, 'member-item')][{index}]//*[contains(@class, 'rolelist')]/li/text()")
                    for role in roles:
                        user["roles"].append(role.strip())

                    # Get image
                    image = tree.xpath(f"//*[contains(@class, 'member-item')][{index}]//img/@src")
                    if image:
                        user["image"] = urljoin(RSI_CONFIG['BASE_URL'], image[0].strip())

                    # Only add if we have valid data
                    if user and user["handle"] and user["handle"] != "":
                        result.append(user)
                    
                    index += 1

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
            response = self._make_request(url)
            if not response:
                return None
            if response.status_code != 200:
                return None

            tree = html.fromstring(response.content)

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
