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
    
    def __init__(self, session, redis):
        """Initialize the scraper
        
        Args:
            session: Discord bot's aiohttp session (not used for RSI requests)
            redis: Redis connection for caching
        """
        self.redis = redis
        # Headers that match a regular browser
        self.headers = {
            'Accept-Language': 'en-US,en;q=0.9',
            'User-Agent': RSI_CONFIG['USER_AGENT'],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        # Get proxy settings from environment
        self.proxies = {}
        if os.getenv('HTTP_PROXY'):
            self.proxies = {'http': os.environ['HTTP_PROXY']}

    def _make_request(self, url: str, method: str = "get", json_data: Dict = None) -> Optional[requests.Response]:
        """Make a request to RSI website using requests library"""
        try:
            args = {
                "url": url,
                "headers": self.headers,
                "stream": False,
                "timeout": 5,
                "proxies": self.proxies,
                "verify": True
            }

            if json_data is not None:
                args["json"] = json_data

            if method.lower() == "post":
                return requests.post(**args)
            elif method.lower() == "get":
                return requests.get(**args)
            else:
                return None

        except Exception as e:
            logger.error(f"Error making request: {e}")
            return None

    async def get_user_info(self, handle: str) -> Optional[Dict[str, Any]]:
        """Get user information including organizations"""
        try:
            # Check cache first
            cache_key = f'rsi_user:{handle.lower()}'
            cached = await self.redis.get(cache_key)
            if cached:
                return json.loads(cached)

            # Get user's organizations page
            orgs_url = f"{RSI_CONFIG['BASE_URL']}/citizens/{handle}/organizations"
            response = self._make_request(orgs_url)
            if not response or response.status_code != 200:
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

            # Find main organization
            main_org = tree.xpath('//div[contains(@class, "box-content") and contains(@class, "org") and contains(@class, "main")]')
            if main_org:
                org_data = {}
                
                # Get org SID
                sid = main_org[0].xpath('.//span[contains(@class, "label") and contains(text(), "Spectrum Identification")]/following-sibling::strong[contains(@class, "value")]/text()')
                if sid:
                    org_data["sid"] = sid[0].strip()
                
                # Get org name
                name = main_org[0].xpath('.//p[contains(@class, "entry")]/a[contains(@class, "value")]/text()')
                if name:
                    org_data["name"] = name[0].strip()
                
                # Get rank
                rank = main_org[0].xpath('.//span[contains(@class, "label") and contains(text(), "Organization rank")]/following-sibling::strong[contains(@class, "value")]/text()')
                if rank:
                    org_data["rank"] = rank[0].strip()
                
                # Get stars
                stars = len(main_org[0].xpath('.//div[contains(@class, "ranking")]//span[contains(@class, "active")]'))
                if stars > 0:
                    org_data["stars"] = stars
                
                if org_data:
                    result["organization"] = org_data

            # Find affiliate organizations
            affiliates = tree.xpath('//div[contains(@class, "box-content") and contains(@class, "org") and contains(@class, "affiliation")]')
            for affiliate in affiliates:
                org_data = {}
                
                # Get org SID
                sid = affiliate.xpath('.//span[contains(@class, "label") and contains(text(), "Spectrum Identification")]/following-sibling::strong[contains(@class, "value")]/text()')
                if sid:
                    org_data["sid"] = sid[0].strip()
                
                # Get org name
                name = affiliate.xpath('.//p[contains(@class, "entry")]/a[contains(@class, "value")]/text()')
                if name:
                    org_data["name"] = name[0].strip()
                
                # Get rank
                rank = affiliate.xpath('.//span[contains(@class, "label") and contains(text(), "Organization rank")]/following-sibling::strong[contains(@class, "value")]/text()')
                if rank:
                    org_data["rank"] = rank[0].strip()
                
                # Get stars
                stars = len(affiliate.xpath('.//div[contains(@class, "ranking")]//span[contains(@class, "active")]'))
                if stars > 0:
                    org_data["stars"] = stars
                
                if org_data:
                    result["affiliation"].append(org_data)

            # Get basic profile info from profile page
            profile_url = f"{RSI_CONFIG['BASE_URL']}/citizens/{handle}"
            response = self._make_request(profile_url)
            if response and response.status_code == 200:
                tree = html.fromstring(response.content)
                
                # Get display name
                display = tree.xpath('//*[contains(@class, "profile")]//*[contains(@class, "info")]//*[contains(@class, "value")]/text()')
                if display:
                    result["profile"]["display"] = display[0].strip()
                
                # Get enlisted date
                enlisted = tree.xpath('//*[contains(@class, "profile-content")]//*[contains(@class, "left-col")]//*[contains(@class, "value")]/text()')
                if enlisted:
                    result["profile"]["enlisted"] = enlisted[0].strip()
                
                # Get avatar
                image = tree.xpath('//*[contains(@class, "thumb")]/img/@src')
                if image:
                    result["profile"]["image"] = urljoin(RSI_CONFIG['BASE_URL'], image[0])

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

    async def get_organization_info(self, sid: str) -> Optional[Dict[str, Any]]:
        """Get organization information"""
        try:
            # Check cache first
            cache_key = f'org_info:{sid}'
            cached = await self.redis.get(cache_key)
            if cached:
                return json.loads(cached)

            # Make request using the direct URL pattern
            url = f"{RSI_CONFIG['BASE_URL']}/orgs/{sid}"
            response = self._make_request(url)
            if not response:
                return None
            if response.status_code == 404:
                return {}
            if response.status_code != 200:
                return None

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

            # Get org name
            name = tree.xpath('//*[@id="organization"]//h1/text()')
            if name:
                result["name"] = name[0].strip('/ ')

            # Get logo
            logo = tree.xpath('//*[contains(@class, "logo") and contains(@class, "noshadow")]/img/@src')
            if logo:
                result["logo"] = urljoin(RSI_CONFIG['BASE_URL'], logo[0])

            # Get banner
            banner = tree.xpath('//*[contains(@class, "banner")]/img/@src')
            if banner:
                result["banner"] = urljoin(RSI_CONFIG['BASE_URL'], banner[0])

            # Get focus info
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

            # Get member count
            members = tree.xpath('//*[contains(@class, "member-count")]/text()')
            if members:
                try:
                    result["members"] = int(members[0].strip())
                except:
                    pass

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
        """Get organization members"""
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
                "pagesize": 32,
                "page": page
            }

            response = self._make_request(f"{RSI_CONFIG['BASE_URL']}/api/orgs/getOrgMembers", "post", json_data)
            if not response or response.status_code != 200:
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

            # Process each member
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
