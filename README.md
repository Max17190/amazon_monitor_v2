# Amazon Stock Monitor

A real-time monitor for Amazon products.

## Overview

This tool monitors specified Amazon products (identified by ASIN) and sends immediate notifications to Discord when items come in stock. Built with asynchronous processing for efficient monitoring of multiple products simultaneously.

## Features

- Real-time stock monitoring for Amazon products
- Batch ASIN requests
- Proxy & user-agent rotation
- Rate-limit handling
- Webhook integration
- Formatted embeds

## Setup

1. Create an `endpoint.env` file with the following variables:
   - Amazon API credentials
   - Proxy configuration
   - Discord webhook URLs and role IDs

2. Configure product ASINs to monitor in `main.py`

3. Run the monitor:
   ```
   python main.py
   ```

## Configuration

The system uses webhook mappings defined in `webhooks.py` to send notifications to different Discord channels based on product categories.

## Requirements

- Python 3.7+
- Required packages: discord, aiohttp, python-dotenv

## Notes

- Uses rotating user agents for improved reliability
- Designed for continuous operation
