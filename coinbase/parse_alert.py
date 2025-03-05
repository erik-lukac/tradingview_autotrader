#!/usr/bin/env python3
"""
parse_alert.py

Utility to parse alert text in the new format into structured data, for automated trading.

Usage:
    ./parse_alert.py 'alert text'

Format:
    ACTION;TICKER;QUANTITY[;STOP_LOSS[;TAKE_PROFIT]]

Examples:
    # Basic format with standard ticker
    ./parse_alert.py "BUY;SOLUSDC;1.5432"
    
    # Basic format with processed ticker
    ./parse_alert.py "BUY;SOL-PERP-INTX;1.5432"
    
    # With stop loss (3 decimal precision)
    ./parse_alert.py "SELL;BTCUSDT;0.5;19.123"
    
    # With both stop loss and take profit
    ./parse_alert.py "BUY;SOLUSDC;1.5432;20.123;25.678"
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
    Processes the ticker string, accepting both formats:
    - Standard format (e.g., 'SOLUSDC')
    - Already processed format (e.g., 'SOL-PERP-INTX')

    Args:
        ticker (str): The ticker string in either format.

    Returns:
        str: The processed ticker with -PERP-INTX suffix.
    """
    # Check if already in correct format
    if ticker.endswith('-PERP-INTX'):
        return ticker

    # Process standard format
    suffixes = ["USDC", "USDT", "USD"]
    for suffix in suffixes:
        if ticker.endswith(suffix):
            ticker = ticker[:-len(suffix)]
            break
    return f"{ticker}-PERP-INTX"

def parse_alert(alert_line: str) -> Optional[Dict[str, Union[str, int, float]]]:
    """
    Parse an alert line in the format: ACTION;TICKER;QTY[;SL[;TP]]
    Examples:
    - "BUY;SOLUSDC;1.5432"
    - "BUY;SOLUSDC;1"
    - "BUY;SOL-PERP-INTX;1.5432;23.456"
    - "BUY;SOL-PERP-INTX;1;23;25"
    """
    # Updated regex to handle both integers and decimals
    pattern = re.compile(
        r'^(BUY|SELL);\s*([A-Z0-9-]+);\s*(\d+\.?\d*|\.\d+)(?:;\s*(\d+\.?\d*|\.\d+))?(?:;\s*(\d+\.?\d*|\.\d+))?$',
        re.IGNORECASE
    )
    
    match = pattern.search(alert_line)
    if not match:
        logger.error("Failed to parse the alert line: %s", alert_line)
        return None

    action, ticker, qty, sl, tp = match.groups()

    try:
        # Parse position value
        position_value = float(qty)
        
        result: Dict[str, Union[str, int, float]] = {
            'action': action.lower(),
            'ticker': process_ticker(ticker),
            'position': position_value
        }

        # Add stop loss if provided
        if sl is not None:
            sl_value = float(sl)
            result['stop_loss'] = round(sl_value, 3)

        # Add take profit if provided
        if tp is not None:
            if sl is None:
                logger.error("Take profit provided without stop loss")
                return None
            tp_value = float(tp)
            result['take_profit'] = round(tp_value, 3)

        logger.info("Parsed result: %s", result)
        return result

    except ValueError as e:
        logger.error("Error parsing numeric values: %s", str(e))
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