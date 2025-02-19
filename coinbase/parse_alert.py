#!/usr/bin/env python3
"""
parse_alert.py

Utility to parse alert text in the new format into structured data, for automated trading.

Usage:
    ./parse_alert.py 'alert text'

Example:
    ./parse_alert.py "BUY;SOLUSDC;1.5432"
"""

import sys
import re
import json
import logging
from typing import Optional, Dict, Union

# Set up console logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def process_ticker(ticker: str) -> str:
    """
    Processes the ticker string by stripping a trailing 'USDC', 'USDT', or 'USD'
    and then appending '-PERP-INTX' to the remaining symbol.

    Args:
        ticker (str): The original ticker string (e.g., 'MKRUSDT').

    Returns:
        str: The processed ticker (e.g., 'MKR-PERP-INTX').
    """
    # IMPORTANT: Here we replaced "USDTC" with "USDC" 
    suffixes = ["USDC", "USDT", "USD"]
    for suffix in suffixes:
        if ticker.endswith(suffix):
            ticker = ticker[:-len(suffix)]  # Remove that suffix
            break
    processed_ticker = f"{ticker}-PERP-INTX"
    logger.info("Processed ticker: %s", processed_ticker)
    return processed_ticker

def parse_alert(alert_line: str) -> Optional[Dict[str, Union[str, int, float]]]:
    """
    Parse an alert line in the format: ACTION;TICKER;QTY
    (e.g. "BUY;SOLUSDC;1.5432" or "SELL;BTCUSDT;0.5")

    Args:
        alert_line (str): The alert text string.

    Returns:
        Optional[Dict[str, Union[str, int, float]]]: 
            A dictionary with keys 'action', 'ticker', and 'position' 
            if the alert can be parsed; otherwise, None.
    """
    # Regex breakdown:
    # - ^(BUY|SELL)          : Matches the action (BUY or SELL)
    # - ;\s*([A-Z0-9]+)      : Matches the ticker (alphanumeric, uppercase)
    # - ;\s*([\d\.]+)$       : Matches the quantity (position size, decimals ok)
    pattern = re.compile(
        r'^(BUY|SELL);\s*([A-Z0-9]+);\s*([\d\.]+)$',
        re.IGNORECASE
    )
    match = pattern.search(alert_line)
    if match:
        action, ticker, qty = match.groups()

        try:
            # Convert qty to float if it has a dot, else to int
            position_value: Union[int, float] = float(qty) if '.' in qty else int(qty)
        except ValueError:
            logger.error("Quantity could not be parsed as number: %s", qty)
            return None

        # Process the ticker to remove stable-coin suffix and append -PERP-INTX
        processed_ticker: str = process_ticker(ticker)

        result: Dict[str, Union[str, int, float]] = {
            'action': action.lower(),
            'ticker': processed_ticker,
            'position': position_value
        }
        logger.info("Parsed result: %s", result)
        return result
    else:
        logger.error("Failed to parse the alert line: %s", alert_line)
        return None

def main() -> None:
    if len(sys.argv) != 2:
        logger.error("Usage: %s 'alert text'", sys.argv[0])
        sys.exit(1)

    alert_text: str = sys.argv[1]
    parsed_data: Optional[Dict[str, Union[str, int, float]]] = parse_alert(alert_text)
    if parsed_data is not None:
        # Output the result as JSON on stdout
        print(json.dumps(parsed_data))
        sys.exit(0)
    else:
        # Parsing failed; exit nonzero so the webhook script sees the error
        sys.exit(1)

if __name__ == '__main__':
    main()