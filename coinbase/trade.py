#!/usr/bin/env python3
"""
trade.py
========

Example Usage:
    ./trade.py --side SHORT --product W-PERP-INTX --size 52 --stop-loss-price 0.2564

Description:
    - Places a Market order to open a position.
    - Uses the fill price from `./order.py`, or polls `./order_info.py` if needed.
    - Places a Stop-Limit GTC order (stop-loss).
    - Places a Limit GTC order (take-profit).

Arguments:
    --side {LONG,SHORT}: Direction of the trade.
    --product PRODUCT:   What to trade (e.g. BTC-USD, W-PERP-INTX).
    --size SIZE:         Amount/base_size for the Market order.
    --stop-loss-price STOP_LOSS_PRICE:
                         Your chosen stop-loss limit price.
    [--profit-loss-ratio PROFIT_LOSS_RATIO]: (Default = 1.5)
    [--no-logging]:      Disable console logging.
"""

import argparse
import json
import logging
import sys
import subprocess
import time
from typing import Optional

# ------------------------------------------------------------------------------
# Poll for the correct fill price (Only if needed)
# ------------------------------------------------------------------------------
def fetch_final_fill_price(order_id: str, max_wait=10, poll_interval=1) -> Optional[float]:
    """
    Polls `./order_info.py <order_id>` until 'status' == 'FILLED' or `max_wait` seconds.
    Returns the final `average_filled_price` as float, or None if not filled.
    """
    end_time = time.time() + max_wait
    while time.time() < end_time:
        cmd = ["./order_info.py", order_id]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            try:
                info = json.loads(result.stdout.strip())
                if info.get("status") == "FILLED":
                    fill_price_str = info.get("average_filled_price", "0")
                    fill_price = float(fill_price_str)
                    if fill_price > 0:
                        return fill_price
            except (json.JSONDecodeError, ValueError):
                pass
        time.sleep(poll_interval)
    return None

def main():
    # ----------------------------
    # Configuration
    # ----------------------------
    ENABLE_LOGGING = True
    DEFAULT_PROFIT_LOSS_RATIO = 1.5
    DEFAULT_STOP_OFFSET_PERCENT = 0.005  # Offset stop price slightly

    # ----------------------------
    # Logging Setup
    # ----------------------------
    logger = logging.getLogger("trade_logger")
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # ----------------------------
    # Argument Parsing
    # ----------------------------
    parser = argparse.ArgumentParser(description="Place three orders: Market -> Stop-Limit GTC -> Limit GTC.")
    parser.add_argument("--side", required=True, choices=["LONG", "SHORT"],
                        help="Trade side: LONG or SHORT.")
    parser.add_argument("--product", required=True,
                        help="Product to trade, e.g. BTC-USD or W-PERP-INTX.")
    parser.add_argument("--size", type=float, required=True,
                        help="Position size for the Market order.")
    parser.add_argument("--stop-loss-price", type=float, required=True,
                        help="Stop-loss limit price (used in stop-limit GTC).")
    parser.add_argument("--profit-loss-ratio", type=float, default=DEFAULT_PROFIT_LOSS_RATIO,
                        help="Risk/Reward ratio. Default = 1.5")
    parser.add_argument("--no-logging", action="store_true",
                        help="Disable console logging.")
    args = parser.parse_args()

    # Adjust logging based on --no-logging
    if args.no_logging:
        logger.setLevel(logging.WARNING)
        console_handler.setLevel(logging.WARNING)

    side = args.side.upper()
    product = args.product
    size = args.size
    stop_loss_price = args.stop_loss_price
    ratio = args.profit_loss_ratio

    # Determine order directions
    if side == "LONG":
        open_side = "buy"
        close_side = "sell"
    else:  # SHORT
        open_side = "sell"
        close_side = "buy"

    # ----------------------------
    # 1) Market Order (Entry)
    # ----------------------------
    order1_cmd = f"./order.py {open_side} {product} {size}"
    logger.info("=== STEP 1: Market (Open) ===")
    logger.info("Executing: %s", order1_cmd)
    result1 = subprocess.run(order1_cmd.split(), capture_output=True, text=True)
    if result1.returncode != 0:
        logger.error("Market order command failed.")
        sys.exit(1)

    # Extract order ID & fill price from order.py response
    coinbase_id = None
    fill_price = None
    try:
        resp = json.loads(result1.stdout.strip())
        coinbase_id = resp.get("coinbase_order_id")
        fill_price = float(resp.get("average_filled_price", "0"))
    except json.JSONDecodeError:
        logger.warning("Could not parse JSON from first order response.")

    # **If price is already available, use it**
    if fill_price and fill_price > 0:
        logger.info("Market fill price (from order.py) = %.6f", fill_price)
    else:
        # **Otherwise, poll order_info.py**
        logger.info("Polling for execution price...")
        fill_price = fetch_final_fill_price(coinbase_id, max_wait=10, poll_interval=1)
        if fill_price is None or fill_price == 0:
            logger.error("Failed to fetch valid execution price.")
            sys.exit(1)

    # ----------------------------
    # 2) Stop-Limit GTC (Stop-Loss)
    # ----------------------------
    logger.info("=== STEP 2: Stop-Limit (Stop-Loss) ===")

    stop_offset = stop_loss_price * DEFAULT_STOP_OFFSET_PERCENT
    stop_trigger_price = round(stop_loss_price - stop_offset, 4) if side == "SHORT" else round(stop_loss_price + stop_offset, 4)
    stop_loss_price = round(stop_loss_price, 4)  # Round to valid precision

    order2_cmd = (
        f"./order.py {close_side.upper()} {product} {size} "
        f"--option stop_limit_gtc "
        f"--stop-price {stop_trigger_price:.4f} "
        f"--limit-price {stop_loss_price:.4f}"
    )
    logger.info("Executing: %s", order2_cmd)
    result2 = subprocess.run(order2_cmd.split(), capture_output=True, text=True)
    if result2.returncode != 0:
        logger.error("Stop-limit order command failed.")
        sys.exit(1)

    # ----------------------------
    # 3) Limit GTC (Take-Profit)
    # ----------------------------
    logger.info("=== STEP 3: Limit (Take-Profit) ===")

    take_profit_price = (
        round(fill_price + (fill_price - stop_loss_price) * ratio, 4)
        if side == "LONG" else
        round(fill_price - (stop_loss_price - fill_price) * ratio, 4)
    )

    order3_cmd = (
        f"./order.py {close_side.upper()} {product} {size} "
        f"--option limit_gtc "
        f"--limit-price {take_profit_price:.4f}"
    )
    logger.info("Executing: %s", order3_cmd)
    result3 = subprocess.run(order3_cmd.split(), capture_output=True, text=True)
    if result3.returncode != 0:
        logger.error("Limit order command failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()