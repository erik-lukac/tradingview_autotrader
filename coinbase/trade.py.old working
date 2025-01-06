#!/usr/bin/env python3
"""
trade.py

Example usage:
python trade.py SELL BTC-USD 0.001

# Market Orders
python trade.py --side BUY --product BTC-USD --amount 0.01 --option market_market_ioc
python trade.py --side SELL --product ETH-USD --amount 0.02 --option market_market_ioc

# Limit Orders
python trade.py --side BUY --product BTC-USD --amount 0.01 --option limit_limit_gtc --limit-price 18000
python trade.py --side SELL --product ETH-USD --amount 0.05 --option limit_limit_gtc --limit-price 2200
python trade.py --side BUY --product BTC-USD --amount 0.01 --option limit_limit_gtd --limit-price 18000 --end-time 2025-01-06T23:59:59Z
python trade.py --side SELL --product BTC-USD --amount 0.02 --option limit_limit_fok --limit-price 18500

# Stop-Limit Orders
python trade.py --side BUY --product BTC-USD --amount 0.01 --option stop_limit_stop_limit_gtc --limit-price 25000 --stop-price 24000 --stop-direction STOP_DIRECTION_STOP_UP
python trade.py --side SELL --product ETH-USD --amount 0.05 --option stop_limit_stop_limit_gtc --limit-price 1800 --stop-price 1900 --stop-direction STOP_DIRECTION_STOP_DOWN
python trade.py --side BUY --product BTC-USD --amount 0.01 --option stop_limit_stop_limit_gtd --limit-price 25000 --stop-price 24000 --stop-direction STOP_DIRECTION_STOP_UP --end-time 2025-01-06T12:00:00Z

# Trigger Bracket Orders
python trade.py --side BUY --product BTC-USD --amount 0.05 --option trigger_bracket_gtc --limit-price 35000 --stop-trigger-price 34000
python trade.py --side SELL --product ETH-USD --amount 0.03 --option trigger_bracket_gtd --limit-price 36000 --stop-trigger-price 35500 --end-time 2025-01-07T18:00:00Z
"""

import argparse
import logging
import sys
import json
import os
from datetime import datetime, timezone
from coinbase.rest import RESTClient

# --------------------------------------------------
# GLOBAL / STATIC CONFIGURATIONS
# --------------------------------------------------
API_KEY_FILE = "perpetuals_trade_cdp_api_key.json"

# By default, we won't pass any leverage/margin_type unless you populate them.
LEVERAGE = ""     # Use empty string to indicate "no leverage"
MARGIN_TYPE = ""  # Use empty string to indicate "no margin type"

ORDER_ID_FILE = "order_id.txt"
# CSV format for each line:
# order_id,timestamp,side,product,amount,executed OR failed reason: <details>

def init_logger():
    """
    Initialize logging with the specified format.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    logging.info("Logger initialized.")

def get_next_order_id() -> int:
    """
    Retrieve the next order ID by reading the last line in order_id.txt,
    then incrementing it.
    
    Does NOT write to file (that happens after success/fail).
    Defaults to 1000 if empty or file doesn't exist,
    meaning the first new order will be 1001.
    """
    last_order_id = 1000

    if os.path.exists(ORDER_ID_FILE):
        with open(ORDER_ID_FILE, "r") as f:
            lines = f.read().strip().splitlines()
            if lines:
                # Grab the last line
                last_line = lines[-1]
                parts = last_line.split(",")
                if len(parts) >= 1:
                    try:
                        last_order_id = int(parts[0])
                    except ValueError:
                        last_order_id = 1000
    return last_order_id + 1

def write_order_log(order_id: int, side: str, product: str, amount: str, status_str: str):
    """
    Write a single line to order_id.txt in the format:
      order_id,timestamp,side,product,amount,<status_str>

    status_str can be either 'executed' or 'failed reason: <reason>'
    """
    now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    line = f"{order_id},{now_utc},{side},{product},{amount},{status_str}\n"

    with open(ORDER_ID_FILE, "a") as f:
        f.write(line)

def parse_args():
    """
    Parse command-line arguments (positional and optional).
    Returns (parser, args).
    """
    parser = argparse.ArgumentParser(
        description="Create a trade on Coinbase Advanced (default is MARKET IOC)."
    )

    # Positional arguments (optional)
    parser.add_argument("pos_side", nargs="?", default=None,
                        help="Order side (BUY or SELL) if provided positionally.")
    parser.add_argument("pos_product", nargs="?", default=None,
                        help="Product (e.g., BTC-USD) if provided positionally.")
    parser.add_argument("pos_amount", nargs="?", default=None,
                        help="Base size (e.g., 0.001) if provided positionally.")

    # Named arguments
    parser.add_argument("--side", help="Order side (BUY or SELL).")
    parser.add_argument("--product", help="Trading pair (e.g. BTC-USD).")
    parser.add_argument("--amount", help="Base size (e.g. 0.001).")

    # Optional arguments that define the order configuration
    parser.add_argument("--option", default="market",
                        help="Order type: 'market' (default), 'limit', or 'stop-limit'.")

    parser.add_argument("--limit-price", default=None,
                        help="Required for limit or stop-limit orders.")
    parser.add_argument("--stop-price", default=None,
                        help="Required for stop-limit orders.")
    parser.add_argument("--stop-direction", default=None,
                        choices=["STOP_DIRECTION_STOP_UP", "STOP_DIRECTION_STOP_DOWN"],
                        help="For stop-limit orders.")
    parser.add_argument("--post-only", default=None,
                        help="For limit orders, 'true' or 'false' (default false).")

    args = parser.parse_args()
    return parser, args

def consolidate_args(args: argparse.Namespace, parser: argparse.ArgumentParser):
    """
    Consolidate side, product, and amount from positional or named arguments.
    """
    final_side = args.side if args.side else args.pos_side
    final_product = args.product if args.product else args.pos_product
    final_amount = args.amount if args.amount else args.pos_amount

    if not final_side:
        logging.error("Missing side (BUY or SELL). Provide either as positional or --side.")
        parser.print_help()
        sys.exit(1)
    if not final_product:
        logging.error("Missing product (e.g., BTC-USD). Provide either as positional or --product.")
        parser.print_help()
        sys.exit(1)
    if not final_amount:
        logging.error("Missing amount (base_size). Provide either as positional or --amount.")
        parser.print_help()
        sys.exit(1)

    return final_side.upper(), final_product.upper(), final_amount

def build_order_configuration(
    order_type: str,
    base_size: str,
    limit_price: str = None,
    stop_price: str = None,
    stop_direction: str = None,
    post_only: bool = False
) -> dict:
    """
    Create the 'order_configuration' dictionary based on the specified order type.
    - Default is market_market_ioc if order_type='market'.
    - 'limit' => limit_limit_gtc
    - 'stop-limit' => stop_limit_stop_limit_gtc
    """
    if order_type == "market":
        return {
            "market_market_ioc": {
                "base_size": base_size
            }
        }
    elif order_type == "limit":
        config = {
            "limit_limit_gtc": {
                "base_size": base_size
            }
        }
        if limit_price:
            config["limit_limit_gtc"]["limit_price"] = limit_price
        if post_only:
            config["limit_limit_gtc"]["post_only"] = post_only
        return config
    elif order_type == "stop-limit":
        config = {
            "stop_limit_stop_limit_gtc": {
                "base_size": base_size
            }
        }
        if limit_price:
            config["stop_limit_stop_limit_gtc"]["limit_price"] = limit_price
        if stop_price:
            config["stop_limit_stop_limit_gtc"]["stop_price"] = stop_price
        if stop_direction:
            config["stop_limit_stop_limit_gtc"]["stop_direction"] = stop_direction
        return config
    else:
        raise ValueError(
            f"Unsupported --option '{order_type}'. "
            "Valid choices: 'market', 'limit', 'stop-limit'."
        )

def parse_failure_reason(response_dict: dict) -> str:
    """
    Extract a 'reason' string from the error_response object if success=False.
    Tries fields in order: 'preview_failure_reason', 'message', 'error_details'.
    Fallback: 'UNKNOWN'
    """
    if "error_response" not in response_dict:
        return "UNKNOWN"

    error_obj = response_dict["error_response"]
    reason = (
        error_obj.get("preview_failure_reason") or
        error_obj.get("message") or
        error_obj.get("error_details") or
        "UNKNOWN"
    )
    return reason

def place_order(side: str, product: str, amount: str, args: argparse.Namespace):
    """
    Place the order on Coinbase Advanced using RESTClient, then log the result.
    """
    post_only_bool = (args.post_only.lower() == "true") if args.post_only else False

    # Build order configuration
    order_config = build_order_configuration(
        order_type=args.option,
        base_size=amount,
        limit_price=args.limit_price,
        stop_price=args.stop_price,
        stop_direction=args.stop_direction,
        post_only=post_only_bool
    )

    # Generate new order ID (but don't write to file yet)
    new_order_id = get_next_order_id()

    logging.info(f"Order config: {order_config}")
    logging.info(f"Client Order ID: {new_order_id}")

    # Initialize REST client
    try:
        client = RESTClient(key_file=API_KEY_FILE)
    except FileNotFoundError:
        logging.error(f"Could not find API key file '{API_KEY_FILE}'.")
        sys.exit(1)

    # Prepare optional leverage/margin params (only pass if not empty)
    optional_params = {}
    if LEVERAGE:
        optional_params["leverage"] = LEVERAGE
    if MARGIN_TYPE:
        optional_params["margin_type"] = MARGIN_TYPE

    # We'll store the final status string here
    status_str = "executed"

    try:
        response = client.create_order(
            client_order_id=str(new_order_id),
            product_id=product,
            side=side,
            order_configuration=order_config,
            **optional_params
        )
        logging.info("Order response:")
        # Using default=str to avoid "Object not JSON serializable" errors
        logging.info(json.dumps(response, indent=2, default=str))

        # Check if it's a dict
        if isinstance(response, dict):
            if not response.get("success"):
                # It's a failure => parse reason
                reason = parse_failure_reason(response)
                status_str = f"failed reason: {reason}"

    except Exception as e:
        logging.error(f"Error placing order: {e}")
        # If an exception occurs, store that in status_str
        status_str = f"failed reason: {str(e)}"

    # Now write to order_id.txt with final status
    write_order_log(new_order_id, side, product, amount, status_str)

    # If failed, optionally exit non-zero
    if status_str.startswith("failed"):
        sys.exit(1)

def main():
    """
    Main function orchestrates argument parsing, order building, and placing.
    """
    init_logger()
    parser, args = parse_args()
    side, product, amount = consolidate_args(args, parser)
    place_order(side, product, amount, args)

if __name__ == "__main__":
    main()
