import os
from dotenv import load_dotenv

# Load directly from the API.env file
load_dotenv('endpoint.env')

# Get webhook data from environment variables
WEBHOOK_CONFIG = {}

# Direct Mapping: Optimized for time complexity
webhook_mappings = [
    ("BLINK_FNF_WEBHOOK_URL", "BLINK_FNF_CHANNEL_ID"),
    ("BLINK_MONITORS_WEBHOOK_URL", "BLINK_MONITORS_CHANNEL_ID"),
    ("MATT_FNF_WEBHOOK_URL", "MATT_FNF_CHANNEL_ID")
]

# Webhook Configuration
for webhook_key, channel_key in webhook_mappings:
    webhook_url = os.getenv(webhook_key)
    channel_id = os.getenv(channel_key)
    
    if webhook_url and channel_id:
        WEBHOOK_CONFIG[webhook_url] = channel_id
    else:
        print(f"Warning: Missing environment variable for {webhook_key} or {channel_key}")

# Create list of webhook URLs
WEBHOOK_URLS = list(WEBHOOK_CONFIG.keys())
# print(WEBHOOK_URLS)
