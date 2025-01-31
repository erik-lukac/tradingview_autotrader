#!/usr/bin/env python3
"""
trade.py
========

Place three orders (market, stop_limit_gtc, limit_gtc) via ./order.py,
then run ./info.py to show the final overview.

Example usage:
    ./trade.py --side LONG --product SUI-PERP-INTX --size 3 \
               --stop-loss-price 4.01 \
               --entry-price 4.10
"""

import argparse
import logging
import sys
import subprocess
from typing import Optional

def main() -> None:
    # ----------------------------
    # Configuration
    # ----------------------------
    ENABLE_LOGGING = True
    DEFAULT_PROFIT_LOSS_RATIO = 1.5
    # Set stop offset to 0.5%
    DEFAULT_STOP_OFFSET_PERCENT = 0.005

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
    parser = argparse.ArgumentParser(
        description="Place three orders (market, stop_limit_gtc, limit_gtc) via ./order.py, then run ./info.py."
    )
    parser.add_argument("--side", required=True, choices=["LONG", "SHORT"],
                        help="Trade side: LONG or SHORT.")
    parser.add_argument("--product", required=True,
                        help="Product to trade, e.g. SUI-PERP-INTX.")
    parser.add_argument("--size", type=float, required=True,
                        help="Position size.")
    parser.add_argument("--stop-loss-price", type=float, required=True,
                        help="Stop-loss price (used as the limit price).")
    parser.add_argument("--entry-price", type=float, required=True,
                        help="Approximate entry price (used for Take-Profit calculation).")
    parser.add_argument("--profit-loss-ratio", type=float,
                        default=DEFAULT_PROFIT_LOSS_RATIO,
                        help="Risk/Reward ratio (default 1.5).")
    parser.add_argument("--no-logging", action="store_true",
                        help="Disable console logging.")
    args = parser.parse_args()

    # ----------------------------
    # Handle Logging Preference
    # ----------------------------
    if not ENABLE_LOGGING or args.no_logging:
        logger.setLevel(logging.WARNING)
        console_handler.setLevel(logging.WARNING)

    side = args.side.upper()
    product = args.product
    size = args.size
    stop_loss_price = args.stop_loss_price
    entry_price = args.entry_price
    ratio = args.profit_loss_ratio

    # ----------------------------
    # Determine Order Sides
    # ----------------------------
    if side == "LONG":
        open_side = "buy"   # open LONG
        close_side = "sell" # close LONG
    else:
        open_side = "sell"  # open SHORT
        close_side = "buy"  # close SHORT

    # ----------------------------
    # Calculate Stop/Limit Prices
    # ----------------------------
    # The user-supplied --stop-loss-price is the limit price on the stop-limit order.
    # We offset the stop-trigger price above/below that limit price.
    offset = stop_loss_price * DEFAULT_STOP_OFFSET_PERCENT

    if side == "LONG":
        # Stop trigger slightly above the stop-loss (limit) price
        stop_price_for_stop_loss = stop_loss_price + offset
        limit_price_for_stop_loss = stop_loss_price

        # Take-Profit calculation:
        #   TP = Entry + (Entry - StopLoss) * Ratio
        take_profit_price = entry_price + (entry_price - stop_loss_price) * ratio

    else:  # SHORT
        # Stop trigger slightly below the stop-loss (limit) price
        stop_price_for_stop_loss = stop_loss_price - offset
        limit_price_for_stop_loss = stop_loss_price

        # Take-Profit calculation (inverted for SHORT):
        #   TP = Entry - (StopLoss - Entry) * Ratio
        take_profit_price = entry_price - (stop_loss_price - entry_price) * ratio

    # ----------------------------
    # Build the Three Orders
    # ----------------------------
    # 1) Market (open)
    order1 = f"./order.py {open_side} {product} {size}"

    # 2) Stop-limit GTC (stop-loss)
    order2 = (
        f"./order.py {close_side.upper()} {product} {size} "
        f"--option stop_limit_gtc "
        f"--stop-price {stop_price_for_stop_loss:.6f} "
        f"--limit-price {limit_price_for_stop_loss:.6f}"
    )

    # 3) Limit GTC (take profit)
    order3 = (
        f"./order.py {close_side.upper()} {product} {size} "
        f"--option limit_gtc "
        f"--limit-price {take_profit_price:.6f}"
    )

    # ----------------------------
    # Logging: Plan
    # ----------------------------
    logger.info("=== TRADE PLANNING ===")
    logger.info("Side: %s | Product: %s | Size: %.2f", side, product, size)
    logger.info("--- Price Levels ---")
    logger.info("Entry Price:        %.4f", entry_price)
    logger.info("Stop-Limit Price:   %.4f", limit_price_for_stop_loss)
    logger.info("Stop-Trigger Price: %.4f", stop_price_for_stop_loss)
    logger.info("Take-Profit Price:  %.4f", take_profit_price)
    logger.info("--- Risk Parameters ---")
    logger.info("Stop-Loss Price (argument): %.4f", stop_loss_price)
    logger.info("Stop Trigger Offset (%.2f%%): %.4f",
                (DEFAULT_STOP_OFFSET_PERCENT * 100), offset)
    logger.info("Profit/Loss Ratio:          %.2f", ratio)

    logger.info("--- Orders to be placed ---")
    logger.info("Market (Open)    : %s", order1)
    logger.info("Stop-Limit (SL)  : %s", order2)
    logger.info("Limit (TP)       : %s", order3)

    # ----------------------------
    # Execution
    # ----------------------------
    logger.info("=== EXECUTION ===")
    commands = [order1, order2, order3]

    for cmd in commands:
        logger.info("Executing: %s", cmd)
        result = subprocess.run(cmd.split(), capture_output=True, text=True)
        if result.stdout.strip():
            logger.info("stdout:\n%s", result.stdout.strip())
        if result.stderr.strip():
            logger.warning("stderr:\n%s", result.stderr.strip())
        if result.returncode != 0:
            logger.error("Command failed: %s", cmd)
            sys.exit(1)

    # ----------------------------
    # Final Info
    # ----------------------------
    logger.info("=== RESULT INFO ===")
    info_result = subprocess.run(["./info.py"], capture_output=True, text=True)
    if info_result.stdout.strip():
        logger.info("\n%s", info_result.stdout.strip())
    if info_result.stderr.strip():
        logger.error("info.py stderr:\n%s", info_result.stderr.strip())
    if info_result.returncode != 0:
        logger.error("Failed to run ./info.py.")
        sys.exit(1)

if __name__ == "__main__":
    main()