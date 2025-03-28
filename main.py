import discord
from discord import Webhook, Embed
from dotenv import load_dotenv
import os
import json
import random
import re
import logging
import requests
import asyncio
from datetime import datetime
from webhooks import WEBHOOK_CONFIG, WEBHOOK_URLS
import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Local environment variables
load_dotenv('endpoint.env')

PROXY_CONFIG = {
    "host": os.getenv('PROXY_HOST'),
    "port": os.getenv('PROXY_PORT'),
    "user": os.getenv('PROXY_USER'),
    "pass": os.getenv('PROXY_PASS')
}


proxy = f"http://{PROXY_CONFIG['user']}:{PROXY_CONFIG['pass']}@{PROXY_CONFIG['host']}:{PROXY_CONFIG['port']}"
proxies = {
    "http": proxy,
    "https": proxy
}

def get_random_user_agent():
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 5.1; rv:109.0) Gecko/20100101 Firefox/115.0",
        "Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 5.1; rv:78.0) Gecko/20100101 Firefox/78.0 Mypal/68.14.5",
        "Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 5.1; rv:102.0) Gecko/20100101 Goanna/4.0 Firefox/102.0 Basilisk/20231124",
        "Mozilla/5.0 (Windows NT 5.1; rv:88.0) Gecko/20100101 Firefox/88.0",
        "Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36",
        "Mozilla/5.0 (Windows NT 5.1; rv:6.7) Goanna/6.7 PaleMoon/33.2",
        "Mozilla/5.0 (Windows NT 5.1; rv:68.9.0) Gecko/20100101 Goanna/4.8 Firefox/68.9.0 Basilisk/52.9.0"
    ]
    return random.choice(user_agents)


class BlinkMonitor:
    def __init__(self):
        self.session = None  # Initialize as None
        self.rate_limited = False

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        await self.session.close()

    async def send_notification(self, product_data):
        if self.rate_limited:
            return

        embed = self.create_embed(product_data)  # Create FIRST
        
        try:
            tasks = []
            for url in WEBHOOK_URLS:
                try:
                    role_id = WEBHOOK_CONFIG[url]
                    webhook = Webhook.from_url(url, session=self.session)
                    tasks.append(webhook.send(content=f"<@&{role_id}>", embed=embed))
                    logging.debug(f"Queued webhook for {url[:15]}... with role {role_id}")
                except KeyError:
                    logging.error(f"No role ID found for webhook {url}")
                except Exception as e:
                    logging.error(f"Webhook setup error: {str(e)}")

            await asyncio.gather(*tasks)
            
        except discord.HTTPException as e:
            if e.status == 429:
                self.rate_limited = True
                await asyncio.sleep(e.retry_after + 1)
                self.rate_limited = False
        except Exception as e:
            logging.error(f"Webhook error: {str(e)}")

    def create_embed(self, product_data):
        embed = Embed(title='Blink Monitor', color=discord.Color.purple())
        price = 'MSRP'
        
        # Price handling
        if product_data.get('offers'):
            price_info = product_data['offers'][0].get('priceInfo', {})
            price = price_info.get('price', 'MSRP')

        # Image handling
        if product_data.get('images'):
            embed.set_thumbnail(url=product_data['images'][0])

        product_link = product_data.get('link', '')
        product_name = product_data.get('title', 'N/A')
        product_name_with_link = f"[{product_name}]({product_link})" if product_link else product_name

        embed.add_field(
            name="Product Details",
            value=(
                f"**{product_name_with_link}**\n"
                f"**SKU:** {product_data.get('asin', 'N/A')}\n"
                f"**Price:** {price}\n"
                f"**Condition:** New\n"
                f"**Sold By:** Amazon.com"
            ),
            inline=False
        )
        
        embed.set_footer(text=f"Blink FNF | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return embed

def parse_json(response_data):
    """Parse Amazon API response and extract key product data"""
    parsed_list = []
    try:
        # Handle different response structures
        products = response_data if isinstance(response_data, list) else response_data.get('products', [])
        
        for product in products:
            item = {
                'asin': product.get('asin', 'N/A'),
                'title': product.get('title', 'N/A'),
                'in_stock': product.get('canAddToCart', False),  # Direct check
                'link': f"https://www.amazon.com/dp/{product.get('asin', '')}",
                'images': [
                    img.get('hiRes', {}).get('url') 
                    for img in product.get('productImages', {}).get('images', [])
                    if img and img.get('hiRes', {}).get('url')
                ]
            }
            
            # Handle title formatting (some come as dicts)
            if isinstance(item['title'], dict):
                item['title'] = item['title'].get('displayString', 'N/A')
                
            parsed_list.append(item)
            
        return parsed_list
        
    except Exception as e:
        logging.error(f"Parsing error: {str(e)}")
        return []

async def check_stock(session, asins):
    """Check product stock status for up to 25 ASINs"""
    if len(asins) > 25:
        logging.warning("Maximum 25 ASINs allowed per request. Truncating list.")
        asins = asins[:25]


    session_id = f"{random.randint(100, 999)}-{random.randint(10**6, 10**7-1)}-{random.randint(10**6, 10**7-1)}"
    
    data = {
        "requestContext": {
            "obfuscatedMarketplaceId": os.getenv("MARKETPLACE_ID"),
            "obfuscatedMerchantId": os.getenv("MERCHANT_ID"),
            "language": "en-US",
            "sessionId": session_id,
            "currency": "USD",
            "amazonApiAjaxEndpoint": "data.amazon.com",
            "slateToken": await get_slate_token(session),
        },
        "content": {"includeOutOfStock": False},
        "includeOutOfStock": True,
        "endpoint": "ajax-data",
        "ASINList": asins,
    }

    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
        "Origin": "https://www.amazon.com",
        "Referer": "https://www.amazon.com/",
    }

    try:
        async with session.post(
            os.getenv('AMAZON_ENDPOINT'),
            headers=headers,
            json=data,
            proxy=proxy,
            timeout=5
        ) as response:
            response.raise_for_status()
            response_data = await response.json()
            parsed_data = parse_json(response_data)
            return parsed_data
    
    except aiohttp.ClientError as e:
        logging.error(f"Request failed: {str(e)}")
    except json.JSONDecodeError:
        logging.error("Failed to parse JSON response")
    except Exception as e:
        logging.error(f"Unexpected error during stock check: {str(e)}")
    return None

async def get_slate_token(session):
    """Retrieve slate token from Amazon page"""
    proxies = {
        "http": proxy,
        "https": proxy
    }

    try:
        async with session.get(
            os.getenv('AMAZON_URL'),
            headers={"User-Agent": get_random_user_agent()},
            proxy=proxy,
            timeout=5
        ) as response:
            response.raise_for_status()
            text = await response.text()
            match = re.search(r'"slateToken"\s*:\s*"([^"]+)"', text)
            return match.group(1) if match else None
    except Exception as e:
        logging.error(f"Failed to get slate token: {str(e)}")
        return None

"""
    RTX5080 = ["B0CQMRKRV5"]

    RTX5090 = ["B07L4QGYLV"]

    RTX5080 = [
            "B0DTPG3B1N", "B0DSWP51N3", "B0DSXKZ2T9", "B0DTJFZ4YS", "B0DSX9Y24P",
            "B0DSXGNFJL", "B0DSXNXTSS", "B0DQSD7YQC", "B0DT7JVPVH", "B0DSWQNGYF",
            "B0DT7FT1P5", "B0DTJDR3V9", "B0DT7H5JYL", "B0DQSLHSP2", "B0DS2R6948",
            "B0DTZ441G7", "B0DTZ48TCY", "B0DSWRLSD4", "B0DQSMMCSH", "B0DT7HKND2",
            "B0DSXH2P3L", "B0DSXJ5QF4", "B0DT7HVT16", "B0DS2R7N4F", "B0DSWR8WMB"
    ]

    RTX5090 = [
        "B0DT7L98J1", "B0DTJFSSZG", "B0DTJF8YT4", "B0DS2WQZ2M",
        "B0DT7JS6BG", "B0DT7GHQMD", "B0DT7L992Z", "B0DT7GBNWQ",
        "B0DT7GMXHB", "B0DT7KGND2", "B0DT7K9VV3", "B0DS2Z8854",
        "B0DS2X13PH"
    ]

    NVIDIA = [
        "B0DT7L98J1", "B0DTJFSSZG", "B0DTJF8YT4", "B0DS2WQZ2M", "B0DT7JS6BG",
        "B0DT7GHQMD", "B0DT7L992Z", "B0DT7GBNWQ", "B0DT7GMXHB", "B0DT7KGND2",
        "B0DS2Z8854", "B0DS2X13PH", "B0DSWP51N3", "B0DTJDR3V9", "B0DS2R6948",
        "B0DSWP51N3", "B0DSXKZ2T9", "B0DTJFZ4YS", "B0DSX9Y24P", "B0DSXGNFJL",
        "B0DSXNXTSS", "B0DQSD7YQC", "B0DT7JVPVH", "B0DSWQNGYF", "B0DS2R7N4F"
    ]

"""

async def main():

    NVIDIA = [
        "B0DT7L98J1", "B0DTJFSSZG", "B0DTJF8YT4", "B0DS2WQZ2M", "B0DT7JS6BG",
        "B0DT7GHQMD", "B0DT7L992Z", "B0DT7GBNWQ", "B0DT7GMXHB", "B0DT7KGND2",
        "B0DS2Z8854", "B0DS2X13PH", "B0DSWP51N3", "B0DTJDR3V9", "B0DS2R6948",
        "B0DTPG3B1N", "B0DSXH2P3L", "B0DTJFZ4YS", "B0DSX9Y24P", "B0DSXGNFJL",
        "B0DSXNXTSS", "B0DQSD7YQC", "B0DT7JVPVH", "B0DSWQNGYF", "B0DS2R7N4F"
    ]
    async with aiohttp.ClientSession() as session:
        async with BlinkMonitor() as monitor_5080:
            while True:
                try:
                    results = await check_stock(session, NVIDIA)
                    if results:
                        processed_asins = set()
                        for product in results:
                            asin = product.get('asin', 'UNKNOWN_ASIN')
                            processed_asins.add(asin)
                            status = "IN_STOCK" if product['in_stock'] else "OUT_OF_STOCK"
                            logging.info(f"ASIN {asin}: {status}")
                            if product['in_stock']:
                                await monitor_5080.send_notification(product)
                        
                        missing_asins = set(NVIDIA) - processed_asins
                        for asin in missing_asins:
                            logging.error(f"ASIN {asin}: MISSING_FROM_RESPONSE")
                        
                        valid_count = len(processed_asins)
                        logging.info(f"Batch complete: {valid_count}/{len(NVIDIA)} ASINs verified")
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logging.error(f"Main loop error: {str(e)}")
                await asyncio.sleep(0.1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Program terminated by user")
