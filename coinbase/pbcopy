#!/usr/bin/env python3
"""
trade.py

Example usage:

# Default is a market order (Market IOC by default). 
# If you do NOT provide --option, it will place a "market" order:
python trade.py --side BUY --product BTC-USD --amount 0.01

# Provide explicit --option for different order types:

# Market IOC
python trade.py --side BUY --product BTC-USD --amount 0.01 --option market_ioc

# Limit IOC
python trade.py --side BUY --product BTC-USD --amount 0.01 --option limit_ioc --limit-price 18000

# Limit GTC
python trade.py --side SELL --product ETH-USD --amount 0.05 --option limit_gtc --limit-price 2200

# Limit GTD (requires --end-time)
python trade.py --side BUY --product BTC-USD --amount 0.01 --option limit_gtd --limit-price 18000 --end-time 2025-01-06T23:59:59Z

# Limit FOK
python trade.py --side SELL --product BTC-USD --amount 0.02 --option limit_fok --limit-price 18500

# Stop-Limit GTC
python trade.py --side BUY --product BTC-USD --amount 0.01 --option stop_limit_gtc --limit-price 25000 --stop-price 24000 --stop-direction STOP_DIRECTION_STOP_UP

# Stop-Limit GTD (requires --end-time)
python trade.py --side SELL --product ETH-USD --amount 0.05 --option stop_limit_gtd --limit-price 1800 --stop-price 1900 --stop-direction STOP_DIRECTION_STOP_DOWN --end-time 2025-01-06T12:00:00Z

# Bracket GTC
python trade.py --side BUY --product BTC-USD --amount 0.05 --option bracket_gtc --limit-price 35000 --stop-trigger-price 34000

# Bracket GTD (requires --end-time)
python trade.py --side SELL --product ETH-USD --amount 0.03 --option bracket_gtd --limit-price 36000 --stop-trigger-price 35500 --end-time 2025-01-07T18:00:00Z
"""

import argparse
import logging
import sys
import json
import os
import re
from datetime import datetime, timezone
from coinbase.rest import RESTClient

# --------------------------------------------------
# GLOBAL / STATIC CONFIGURATIONS
# --------------------------------------------------
API_KEY_FILE = "perpetuals_trade_cdp_api_key.json"

LEVERAGE = ""     
MARGIN_TYPE = ""  

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
    """
    last_order_id = 1000

    if os.path.exists(ORDER_ID_FILE):
        with open(ORDER_ID_FILE, "r") as f:
            lines = f.read().strip().splitlines()
            if lines:
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

    # Positional (optional) arguments
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

    # Extended order type arguments
    parser.add_argument(
        "--option",
        default="market",
        choices=[
            "market",
            "market_ioc",
            "limit_ioc",
            "limit_gtc",
            "limit_gtd",
            "limit_fok",
            "stop_limit_gtc",
            "stop_limit_gtd",
            "bracket_gtc",
            "bracket_gtd",
        ],
        help=(
            "Specify the order type. Default is 'market' if not provided. "
            "Available: market, market_ioc, limit_ioc, limit_gtc, limit_gtd, "
            "limit_fok, stop_limit_gtc, stop_limit_gtd, bracket_gtc, bracket_gtd."
        ),
    )

    # Convenience flags to avoid using --option for each order type
    # Example: --limit-gtc translates to option="limit_gtc"
    parser.add_argument("--limit-gtc", action="store_true",
                        help="Shortcut for specifying limit_gtc.")
    parser.add_argument("--limit-fok", action="store_true",
                        help="Shortcut for specifying limit_fok.")
    parser.add_argument("--market-ioc", action="store_true",
                        help="Shortcut for specifying market_ioc.")
    parser.add_argument("--limit-ioc", action="store_true",
                        help="Shortcut for specifying limit_ioc.")
    parser.add_argument("--limit-gtd", action="store_true",
                        help="Shortcut for specifying limit_gtd.")
    # Add additional convenience flags if desired for stop_limit_gtc, stop_limit_gtd, bracket_gtc, bracket_gtd, etc.

    parser.add_argument("--limit-price", default=None,
                        help="Required for limit or stop-limit orders.")
    parser.add_argument("--stop-price", default=None,
                        help="Required for stop-limit orders.")
    parser.add_argument("--stop-direction", default=None,
                        choices=["STOP_DIRECTION_STOP_UP", "STOP_DIRECTION_STOP_DOWN"],
                        help="For stop-limit orders.")
    parser.add_argument("--post-only", default=None,
                        help="For limit orders, 'true' or 'false' (default false).")
    parser.add_argument("--end-time", default=None,
                        help="For GTD (Good 'Til Date) orders (ISO8601, e.g. 2025-01-06T23:59:59Z).")
    parser.add_argument("--stop-trigger-price", default=None,
                        help="For bracket orders: The stop trigger price.")

    args = parser.parse_args()

    # If user provided any of the convenience flags, override args.option
    if args.limit_gtc:
        args.option = "limit_gtc"
    if args.limit_fok:
        args.option = "limit_fok"
    if args.market_ioc:
        args.option = "market_ioc"
    if args.limit_ioc:
        args.option = "limit_ioc"
    if args.limit_gtd:
        args.option = "limit_gtd"
    # etc. for any other convenience flags you add

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
    post_only: bool = False,
    end_time: str = None,
    stop_trigger_price: str = None
) -> dict:
    """
    Create the 'order_configuration' dictionary based on the specified order type.
    The default (if order_type = 'market') is an immediate-or-cancel market order.
    """
    if order_type == "market":
        # Equivalent to "market_market_ioc"
        return {
            "market_market_ioc": {
                "base_size": base_size
            }
        }
    elif order_type == "market_ioc":
        return {
            "market_market_ioc": {
                "base_size": base_size
            }
        }
    elif order_type == "limit_ioc":
        config = {
            "limit_limit_ioc": {
                "base_size": base_size
            }
        }
        if limit_price:
            config["limit_limit_ioc"]["limit_price"] = limit_price
        if post_only:
            config["limit_limit_ioc"]["post_only"] = post_only
        return config
    elif order_type == "limit_gtc":
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
    elif order_type == "limit_gtd":
        config = {
            "limit_limit_gtd": {
                "base_size": base_size,
                "end_time": end_time
            }
        }
        if limit_price:
            config["limit_limit_gtd"]["limit_price"] = limit_price
        if post_only:
            config["limit_limit_gtd"]["post_only"] = post_only
        return config
    elif order_type == "limit_fok":
        config = {
            "limit_limit_fok": {
                "base_size": base_size
            }
        }
        if limit_price:
            config["limit_limit_fok"]["limit_price"] = limit_price
        if post_only:
            config["limit_limit_fok"]["post_only"] = post_only
        return config
    elif order_type == "stop_limit_gtc":
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
    elif order_type == "stop_limit_gtd":
        config = {
            "stop_limit_stop_limit_gtd": {
                "base_size": base_size,
                "end_time": end_time
            }
        }
        if limit_price:
            config["stop_limit_stop_limit_gtd"]["limit_price"] = limit_price
        if stop_price:
            config["stop_limit_stop_limit_gtd"]["stop_price"] = stop_price
        if stop_direction:
            config["stop_limit_stop_limit_gtd"]["stop_direction"] = stop_direction
        return config
    elif order_type == "bracket_gtc":
        config = {
            "trigger_bracket_gtc": {
                "base_size": base_size
            }
        }
        if limit_price:
            config["trigger_bracket_gtc"]["limit_price"] = limit_price
        if stop_trigger_price:
            config["trigger_bracket_gtc"]["stop_trigger_price"] = stop_trigger_price
        return config
    elif order_type == "bracket_gtd":
        config = {
            "trigger_bracket_gtd": {
                "base_size": base_size,
                "end_time": end_time
            }
        }
        if limit_price:
            config["trigger_bracket_gtd"]["limit_price"] = limit_price
        if stop_trigger_price:
            config["trigger_bracket_gtd"]["stop_trigger_price"] = stop_trigger_price
        return config
    else:
        raise ValueError(
            f"Unsupported --option '{order_type}'. "
            "Valid choices: 'market', 'market_ioc', 'limit_ioc', 'limit_gtc', 'limit_gtd', "
            "'limit_fok', 'stop_limit_gtc', 'stop_limit_gtd', 'bracket_gtc', 'bracket_gtd'."
        )

def parse_failure_reason(response_dict: dict) -> str:
    """
    Extract a 'reason' string from the error_response object if success=False.
    """
    if "error_response" not in response_dict:
        return "UNKNOWN"

    error_obj = response_dict["error_response"]
    reason = (
        error_obj.get("preview_failure_reason")
        or error_obj.get("message")
        or error_obj.get("error_details")
        or "UNKNOWN"
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
        post_only=post_only_bool,
        end_time=args.end_time,
        stop_trigger_price=args.stop_trigger_price
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
        logging.info(json.dumps(response, indent=2, default=str))

        if isinstance(response, dict) and not response.get("success", False):
            reason = parse_failure_reason(response)
            status_str = f"failed reason: {reason}"

    except Exception as e:
        logging.error(f"Error placing order: {e}")

        # Attempt to extract a shorter reason from the error string
        reason_extracted = str(e)
        match = re.search(r'(\{.*\})', reason_extracted)
        if match:
            json_part = match.group(1)
            try:
                error_json = json.loads(json_part)
                reason_extracted = (
                    error_json.get("error_details")
                    or error_json.get("message")
                    or error_json.get("error")
                    or reason_extracted
                )
            except json.JSONDecodeError:
                pass

        status_str = f"failed reason: {reason_extracted}"

    # Write to order_id.txt with final status
    write_order_log(new_order_id, side, product, amount, status_str)

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