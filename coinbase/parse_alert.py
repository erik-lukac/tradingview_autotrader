#!/usr/bin/env python3
"""
Usage:
    ./parse_alert.py 'alert text'

Example:
    ./parse_alert.py "eGPT - Zero Lag Trend Signals (MTF) [AlgoAlpha] (10, 5, 70, 1.2, 5, 15, 60, 240, 1D): order buy @ 10 filled on MKRUSDT. New strategy position is 10"
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
    Processes the ticker string by stripping a trailing 'USDT', 'USDTC', or 'USD'
    (in that order) and then appending '-PERP-INTX' to the remaining symbol.

    Args:
        ticker (str): The original ticker string (e.g., 'MKRUSDT').

    Returns:
        str: The processed ticker (e.g., 'MKR-PERP-INTX').
    """
    suffixes = ["USDTC", "USDT", "USD"]
    for suffix in suffixes:
        if ticker.endswith(suffix):
            ticker = ticker[:-len(suffix)]
            break
    processed_ticker = f"{ticker}-PERP-INTX"
    logger.info("Processed ticker: %s", processed_ticker)
    return processed_ticker

def parse_alert(alert_line: str) -> Optional[Dict[str, Union[str, int, float]]]:
    """
    Parse a TradingView alert line to extract the action, contract, ticker, and position.

    The expected alert format is:
      ...: order <action> @ <contracts> filled on <ticker>. New strategy position is <position>

    Args:
        alert_line (str): The alert text string.

    Returns:
        Optional[Dict[str, Union[str, int, float]]]: A dictionary with keys 'action', 'contract', 'ticker',
            and 'position' if the alert can be parsed; otherwise, None.
    """
    # Regex breakdown:
    # - r'order (\w+)'           : captures the action (buy or sell)
    # - r' @ ([\d\.]+)'          : captures the number of contracts (allowing decimals)
    # - r' filled on ([A-Z0-9]+)'  : captures the ticker (alphanumeric, typically uppercase)
    # - r'\. New strategy position is (-?\d+)' : captures the new strategy position (allowing negatives)
    pattern = re.compile(
        r'order (\w+) @ ([\d\.]+) filled on ([A-Z0-9]+)\. New strategy position is (-?\d+)',
        re.IGNORECASE
    )

    match = pattern.search(alert_line)
    if match:
        action, contract, ticker, position = match.groups()

        try:
            contract_value: Union[int, float] = float(contract) if '.' in contract else int(contract)
        except ValueError:
            contract_value = contract  # fallback to string if conversion fails

        try:
            position_value: int = int(position)
        except ValueError:
            position_value = position  # fallback to string if conversion fails

        # Process the ticker further as per requirement.
        processed_ticker: str = process_ticker(ticker)

        result: Dict[str, Union[str, int, float]] = {
            'action': action.lower(),
            'contract': contract_value,
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
        # Output the result as JSON on the console.
        print(json.dumps(parsed_data))
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()