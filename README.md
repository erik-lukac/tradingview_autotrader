# TradingView Auto-Trader

A containerized solution to receive TradingView webhooks and automate trades on Coinbase Advanced Trading. This repository includes:

- A **Flask-based webhook listener** (`webhook_listener`) for receiving TradingView alerts
- An **Nginx reverse proxy** (`nginx_proxy`) for secure handling of requests
- **Python scripts** to place or query trades using the Coinbase Advanced Trading API
- A **Docker Compose** setup to orchestrate everything

---

## Table of Contents

1. [Overview](#overview)  
2. [Features](#features)  
3. [Project Structure](#project-structure)  
4. [Docker Setup](#docker-setup)  
5. [Webhook Usage](#webhook-usage)  
   - [Data Format](#data-format)  
   - [TradingView Alert Configuration](#tradingview-alert-configuration)  
6. [Scripts](#scripts)  
   - [1. `info.py`](#1-infopy)  
   - [2. `order_info.py`](#2-order_infopy)  
   - [3. `order.py`](#3-orderpy)  
   - [4. `parse_alert.py`](#4-parse_alertpy)  
   - [5. `trade.py`](#5-tradepy)  
7. [API Key Configuration](#api-key-configuration)  
8. [Contributing](#contributing)  
9. [License](#license)  

---

## Overview

The **TradingView Auto-Trader** listens for [TradingView webhooks](https://www.tradingview.com/support/solutions/43000529348-about-webhooks/) containing buy/sell signals. Once a signal is received, it can:

1. Parse the alert message in multiple formats:
   - Basic: `BUY;SOLUSDC;1.5432`
   - With Stop Loss: `BUY;SOLUSDC;1.5432;20.123`
   - Complete: `BUY;SOLUSDC;1.5432;20.123;25.678` (includes Take Profit)
2. Place an order or sequence of orders (e.g., market entry + stop-loss + take-profit)
3. Log and track order statuses

This setup provides a straightforward, **hands-free** approach to execute trades automatically on Coinbase Advanced Trading based on TradingView alerts.

---

## Features

- **Secure & Scalable**: Nginx acts as a proxy for the Flask-based webhook service.
- **Auto-trading**: Pass TradingView alerts to Python scripts that place orders on Coinbase.
- **Versatile Order Types**: Market, limit, stop-limit, bracket, etc.
- **Multi-step Trades**: Entry, stop-loss, and take-profit in one shot.
- **Flexible Alert Format**: 
  - Supports both standard (SOLUSDC) and processed (SOL-PERP-INTX) ticker formats
  - Optional stop-loss and take-profit parameters
  - 3-decimal precision for price levels
- **Easy Logging**: Order details stored in a simple CSV file (`order_id.txt`).

---

## Project Structure

```bash
.
├── Dockerfile                # Docker build (used by the 'webhook' service)
├── docker-compose.yml        # Defines services configuration
├── requirements.txt          # Python dependencies
├── app/                      # Flask application directory
│   └── webhook.py           # Webhook listener implementation
├── nginx/                    # Nginx configuration
│   ├── nginx.conf           # Reverse-proxy configuration
│   └── logs/                # Nginx log files
├── coinbase/                 # Coinbase trading scripts
│   ├── coins.txt            # Supported coins list
│   ├── info.py             # Get market information
│   ├── order.py            # Place orders
│   ├── order_id.txt        # Order tracking log
│   ├── order_info.py       # Query order status
│   ├── parse_alert.py      # Parse TradingView alerts
│   ├── perpetuals.txt      # Supported perpetual contracts
│   ├── trade.py            # Trading logic implementation
│   └── perpetuals_trade_cdp_api_key.json  # API credentials
├── other/                   # Additional resources
│   ├── coinbase_order_instructions.txt
│   ├── example_close_order.txt
│   ├── example_list_orders.txt
│   ├── example_order.txt
│   ├── example_positions.txt
│   ├── python_guideline.txt
│   └── webhook_example_data_RSI.txt
└── strategies/              # Trading strategies
    ├── guideline.txt
    ├── momentum.txt
    ├── momentum_bias.txt
    └── zerolag.txt
```

---
