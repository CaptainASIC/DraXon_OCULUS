"""Test script for RSI scraper functionality"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

import requests
import json
from lxml import html
from urllib.parse import urljoin
import lxml.etree as etree

from src.utils.constants import RSI_CONFIG

# Headers that match a regular browser
headers = {
    'Accept-Language': 'en-US,en;q=0.9',
    'User-Agent': RSI_CONFIG['USER_AGENT'],
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache'
}

def get_user_info(handle: str):
    """Test RSI user info scraping"""
    print(f"\nTesting user info for handle: {handle}")
    
    # First check the user's organizations page
    orgs_url = f"{RSI_CONFIG['BASE_URL']}/citizens/{handle}/organizations"
    print(f"\nChecking organizations page: {orgs_url}")
    
    response = requests.get(orgs_url, headers=headers)
    print(f"Organizations page response status: {response.status_code}")
    
    # Extract user info
    result = {
        "profile": {
            "handle": handle,
            "display": "",
            "enlisted": "",
            "image": ""
        },
        "organization": {},
        "affiliation": []
    }
    
    if response.status_code == 200:
        tree = html.fromstring(response.content)
        
        # Print all organization blocks for debugging
        print("\nSearching for organization blocks...")
        
        # Find main organization
        main_org = tree.xpath('//div[contains(@class, "box-content") and contains(@class, "org") and contains(@class, "main")]')
        if main_org:
            print("\nProcessing main organization:")
            print(etree.tostring(main_org[0], pretty_print=True).decode())
            print("-" * 80)
            
            org_data = {}
            
            # Get org SID
            sid = main_org[0].xpath('.//span[contains(@class, "label") and contains(text(), "Spectrum Identification")]/following-sibling::strong[contains(@class, "value")]/text()')
            if sid:
                org_data["sid"] = sid[0].strip()
                print(f"Found SID: {org_data['sid']}")
            
            # Get org name
            name = main_org[0].xpath('.//p[contains(@class, "entry")]/a[contains(@class, "value")]/text()')
            if name:
                org_data["name"] = name[0].strip()
                print(f"Found name: {org_data['name']}")
            
            # Get rank
            rank = main_org[0].xpath('.//span[contains(@class, "label") and contains(text(), "Organization rank")]/following-sibling::strong[contains(@class, "value")]/text()')
            if rank:
                org_data["rank"] = rank[0].strip()
                print(f"Found rank: {org_data['rank']}")
            
            # Get stars
            stars = len(main_org[0].xpath('.//div[contains(@class, "ranking")]//span[contains(@class, "active")]'))
            if stars > 0:
                org_data["stars"] = stars
                print(f"Found stars: {org_data['stars']}")
            
            if org_data:
                print("Setting as main organization")
                result["organization"] = org_data
        
        # Find affiliate organizations
        affiliates = tree.xpath('//div[contains(@class, "box-content") and contains(@class, "org") and contains(@class, "affiliation")]')
        print(f"\nFound {len(affiliates)} affiliate organizations")
        
        for affiliate in affiliates:
            print("\nProcessing affiliate organization:")
            print(etree.tostring(affiliate, pretty_print=True).decode())
            print("-" * 80)
            
            org_data = {}
            
            # Get org SID
            sid = affiliate.xpath('.//span[contains(@class, "label") and contains(text(), "Spectrum Identification")]/following-sibling::strong[contains(@class, "value")]/text()')
            if sid:
                org_data["sid"] = sid[0].strip()
                print(f"Found SID: {org_data['sid']}")
            
            # Get org name
            name = affiliate.xpath('.//p[contains(@class, "entry")]/a[contains(@class, "value")]/text()')
            if name:
                org_data["name"] = name[0].strip()
                print(f"Found name: {org_data['name']}")
            
            # Get rank
            rank = affiliate.xpath('.//span[contains(@class, "label") and contains(text(), "Organization rank")]/following-sibling::strong[contains(@class, "value")]/text()')
            if rank:
                org_data["rank"] = rank[0].strip()
                print(f"Found rank: {org_data['rank']}")
            
            # Get stars
            stars = len(affiliate.xpath('.//div[contains(@class, "ranking")]//span[contains(@class, "active")]'))
            if stars > 0:
                org_data["stars"] = stars
                print(f"Found stars: {org_data['stars']}")
            
            if org_data:
                print("Adding to affiliations")
                result["affiliation"].append(org_data)
    
    # Now get the user's profile for basic info
    profile_url = f"{RSI_CONFIG['BASE_URL']}/citizens/{handle}"
    print(f"\nChecking profile page: {profile_url}")
    
    response = requests.get(profile_url, headers=headers)
    print(f"Profile response status: {response.status_code}")
    
    if response.status_code == 200:
        tree = html.fromstring(response.content)
        
        # Get basic profile info
        display = tree.xpath('//*[contains(@class, "profile")]//*[contains(@class, "info")]//*[contains(@class, "value")]/text()')
        if display:
            result["profile"]["display"] = display[0].strip()
            print(f"Found display name: {result['profile']['display']}")
        
        enlisted = tree.xpath('//*[contains(@class, "profile-content")]//*[contains(@class, "left-col")]//*[contains(@class, "value")]/text()')
        if enlisted:
            result["profile"]["enlisted"] = enlisted[0].strip()
            print(f"Found enlistment date: {result['profile']['enlisted']}")
    
    return result

def main():
    """Test RSI scraping functionality"""
    # Test with a handle
    handle = input("Enter RSI handle to test: ")
    result = get_user_info(handle)
    
    if result:
        print("\nFull result:")
        print(json.dumps(result, indent=2))
        
        # Check DraXon membership
        is_main_org = result["organization"].get("sid") == RSI_CONFIG["ORGANIZATION_SID"]
        is_affiliate = any(
            org.get("sid") == RSI_CONFIG["ORGANIZATION_SID"]
            for org in result["affiliation"]
        )
        
        print("\nDraXon membership status:")
        print(f"Is main org member: {is_main_org}")
        print(f"Is affiliate member: {is_affiliate}")

if __name__ == "__main__":
    main()
