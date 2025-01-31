#!/usr/bin/env python3
"""
order.py

EXAMPLES:

1) Provide side, product, and amount as positional arguments:
   python order.py BUY BTC-USD 10

2) (Default) Market IOC order using named flags:
   python order.py --side BUY --product BTC-USD --amount 0.01

3) Market IOC explicitly:
   python order.py --side BUY --product BTC-USD --amount 0.01 --option market_ioc

4) Limit IOC (with limit price):
   python order.py --side SELL --product ETH-USD --amount 0.02 --option limit_ioc --limit-price 2000

5) Limit GTC (Good 'Til Canceled):
   python order.py --side BUY --product BTC-USD --amount 0.01 --option limit_gtc --limit-price 18000

6) Limit GTD (Good 'Til Date) with expiration time:
   python order.py --side SELL --product ETH-USD --amount 0.05 --option limit_gtd --limit-price 1900 --end-time 2025-05-01T00:00:00Z

7) Limit FOK (Fill-Or-Kill):
   python order.py --side SELL --product BTC-USD --amount 0.02 --option limit_fok --limit-price 18500

8) Stop-Limit GTC:
   python order.py --side BUY --product BTC-USD --amount 0.01 --option stop_limit_gtc --limit-price 26000 --stop-price 24500 --stop-direction STOP_DIRECTION_STOP_UP

9) Stop-Limit GTD (with end time):
   python order.py --side SELL --product ETH-USD --amount 0.05 --option stop_limit_gtd --limit-price 1700 --stop-price 1800 --stop-direction STOP_DIRECTION_STOP_DOWN --end-time 2025-06-10T12:00:00Z

10) Bracket GTC:
    python order.py --side BUY --product BTC-USD --amount 0.04 --option bracket_gtc --limit-price 31000 --stop-trigger-price 30000

11) Bracket GTD (expiring at a date/time):
    python order.py --side SELL --product ETH-USD --amount 0.03 --option bracket_gtd --limit-price 40000 --stop-trigger-price 39500 --end-time 2025-07-01T12:00:00Z

DESCRIPTION:
  This script connects to Coinbase Advanced Trade via RESTClient, allowing users
  to create different order types. It supports both positional and named
  arguments for side, product, and amount.

  If --option is not specified, it defaults to a 'market' IOC order.

  Order records are written to 'order_id.txt' with status logged. If an
  order fails, the script exits with a non-zero return code.
"""

import argparse
import logging
import sys
import json
import os
import re
from datetime import datetime, timezone
from coinbase.rest import RESTClient
from typing import Tuple, Dict, Any

# --------------------------------------------------
# CONFIGURATIONS
# --------------------------------------------------
# Toggle logging on/off here:
ENABLE_LOGGING = True

API_KEY_FILE = "perpetuals_trade_cdp_api_key.json"
ORDER_ID_FILE = "order_id.txt"

# Leverage & Margin (optional: only passed if not empty)
LEVERAGE = ""
MARGIN_TYPE = ""


def init_logger() -> None:
    """
    Initialize Python's built-in logging for console output.
    Logging is ON by default, controlled by ENABLE_LOGGING.
    """
    if ENABLE_LOGGING:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
        )
        logging.info("Logging is enabled.")
    else:
        # Disable all logging
        logging.disable(logging.CRITICAL)


def get_next_order_id() -> int:
    """
    Reads the last order ID from 'order_id.txt' if available.
    Returns the next integer ID.
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


def write_order_log(order_id: int, side: str, product: str, amount: str, status_str: str) -> None:
    """
    Appends a line to 'order_id.txt' in CSV format:
    order_id,timestamp,side,product,amount,status
    """
    now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    line = f"{order_id},{now_utc},{side},{product},{amount},{status_str}\n"

    with open(ORDER_ID_FILE, "a") as f:
        f.write(line)


def parse_args() -> Tuple[argparse.ArgumentParser, argparse.Namespace]:
    """
    Defines and parses CLI arguments, returning the parser and parsed results.
    """
    parser = argparse.ArgumentParser(
        description="Submit an order to Coinbase Advanced. Defaults to MARKET IOC."
    )

    # Optional positional arguments
    parser.add_argument("pos_side", nargs="?", default=None,
                        help="Side (BUY or SELL), if used positionally.")
    parser.add_argument("pos_product", nargs="?", default=None,
                        help="Product code (e.g., BTC-USD), if used positionally.")
    parser.add_argument("pos_amount", nargs="?", default=None,
                        help="Order amount/base size, if used positionally.")

    # Named arguments
    parser.add_argument("--side", help="BUY or SELL.")
    parser.add_argument("--product", help="Instrument code, e.g. BTC-USD.")
    parser.add_argument("--amount", help="Base size (quantity) to trade.")

    # Extended arguments for order types
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
            "Order configuration. Defaults to 'market' (IOC). "
            "Available: market, market_ioc, limit_ioc, limit_gtc, limit_gtd, "
            "limit_fok, stop_limit_gtc, stop_limit_gtd, bracket_gtc, bracket_gtd."
        ),
    )

    # Convenience flags that override --option if used
    parser.add_argument("--limit-gtc", action="store_true",
                        help="Shortcut for limit_gtc.")
    parser.add_argument("--limit-fok", action="store_true",
                        help="Shortcut for limit_fok.")
    parser.add_argument("--market-ioc", action="store_true",
                        help="Shortcut for market_ioc.")
    parser.add_argument("--limit-ioc", action="store_true",
                        help="Shortcut for limit_ioc.")
    parser.add_argument("--limit-gtd", action="store_true",
                        help="Shortcut for limit_gtd.")
    # More could be added for stop_limit_gtc, bracket_gtc, etc.

    parser.add_argument("--limit-price", default=None,
                        help="For limit or stop-limit orders.")
    parser.add_argument("--stop-price", default=None,
                        help="Required for stop-limit orders.")
    parser.add_argument("--stop-direction", default=None,
                        choices=["STOP_DIRECTION_STOP_UP", "STOP_DIRECTION_STOP_DOWN"],
                        help="Stop-limit trigger direction.")
    parser.add_argument("--post-only", default=None,
                        help="For limit orders (true/false). Default false.")
    parser.add_argument("--end-time", default=None,
                        help="Used for GTD orders (ISO8601 datetime).")
    parser.add_argument("--stop-trigger-price", default=None,
                        help="For bracket orders.")

    args = parser.parse_args()

    # Apply convenience flags if used
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

    return parser, args


def consolidate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> Tuple[str, str, str]:
    """
    Resolve side, product, and amount from positional or named arguments.
    Exits the program with help if any are missing.
    """
    final_side = args.side if args.side else args.pos_side
    final_product = args.product if args.product else args.pos_product
    final_amount = args.amount if args.amount else args.pos_amount

    if not final_side:
        logging.error("Missing side (BUY or SELL). Use positional or --side.")
        parser.print_help()
        sys.exit(1)
    if not final_product:
        logging.error("Missing product (e.g., BTC-USD). Use positional or --product.")
        parser.print_help()
        sys.exit(1)
    if not final_amount:
        logging.error("Missing amount (base size). Use positional or --amount.")
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
) -> Dict[str, Any]:
    """
    Build the dictionary specifying order configuration for the REST API call.
    """
    if order_type == "market":
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
            f"Unsupported --option '{order_type}'. Valid choices: "
            "market, market_ioc, limit_ioc, limit_gtc, limit_gtd, "
            "limit_fok, stop_limit_gtc, stop_limit_gtd, bracket_gtc, bracket_gtd."
        )


def parse_failure_reason(response_dict: Dict[str, Any]) -> str:
    """
    If an API call fails, attempt to extract a meaningful error message.
    """
    if "error_response" not in response_dict:
        return "UNKNOWN"

    error_obj = response_dict["error_response"]
    return (
        error_obj.get("preview_failure_reason")
        or error_obj.get("message")
        or error_obj.get("error_details")
        or "UNKNOWN"
    )


def place_order(side: str, product: str, amount: str, args: argparse.Namespace) -> None:
    """
    Use the RESTClient to place the order, then log the result to a local file.
    Exits with code 1 if the order fails.
    """
    post_only_bool = (args.post_only.lower() == "true") if args.post_only else False

    # Build the final JSON config for the order
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

    # Assign a new order ID
    new_order_id = get_next_order_id()

    logging.info(f"Order configuration: {order_config}")
    logging.info(f"Generated Client Order ID: {new_order_id}")

    # Create REST client
    try:
        client = RESTClient(key_file=API_KEY_FILE)
    except FileNotFoundError:
        logging.error(f"API key file '{API_KEY_FILE}' not found.")
        sys.exit(1)

    # Optional parameters if LEVERAGE or MARGIN_TYPE are set
    optional_params: Dict[str, str] = {}
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
        logging.info("Server response:")
        logging.info(json.dumps(response, indent=2, default=str))

        # Check if success is False
        if isinstance(response, dict) and not response.get("success", False):
            reason = parse_failure_reason(response)
            status_str = f"failed reason: {reason}"

    except Exception as e:
        logging.error(f"Error placing the order: {e}")

        # Attempt to parse any JSON snippet in the exception for a clearer error
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

    # Write the final status (executed or failed reason) to the log file
    write_order_log(new_order_id, side, product, amount, status_str)

    # Exit with a non-zero code if the order failed
    if status_str.startswith("failed"):
        sys.exit(1)


def main() -> None:
    """
    Main driver: sets up logging, processes CLI arguments, and sends the order.
    """
    init_logger()
    parser, args = parse_args()
    side, product, amount = consolidate_args(args, parser)
    place_order(side, product, amount, args)


if __name__ == "__main__":
    main()