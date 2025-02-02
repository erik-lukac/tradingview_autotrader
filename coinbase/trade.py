#!/usr/bin/env python3
"""
trade.py

This script places three consecutive orders:
  1. An entry market order.
  2. A stop loss order.
  3. A take profit order.

The take profit price is automatically calculated based on the entry price
and the supplied stop loss price using a risk/reward ratio (default 2.0).

The stop loss order uses a 0.5% buffer:
  - For LONG positions, the trigger remains as supplied while the limit price is 0.5% lower.
  - For SHORT positions, the trigger remains as supplied while the limit price is 0.5% higher.

Price values for entry and take profit orders are formatted to 4 decimals,
while stop loss order prices are formatted to 3 decimals.

At the end, a concise financial summary is printed (without log prefixes).

Usage example:
  ./trade.py --side LONG --product NEO-PERP-INTX --size 1 --stop-loss-price 13.5

Optional:
  --rr-ratio: Risk reward ratio for take profit calculation (default 2.0)

Notes:
- For a LONG position, the entry order is a BUY and the exit orders (stop loss and take profit)
  are SELL orders.
- For a SHORT position, the entry order is a SELL and the exit orders are BUY orders.
- The take profit price is calculated using:
    For LONG: take_profit = entry_price + (entry_price - stop_loss_price) * rr_ratio
    For SHORT: take_profit = entry_price - (stop_loss_price - entry_price) * rr_ratio
"""

import argparse
import logging
import sys
import os
import subprocess
import re
import json
from datetime import datetime, timezone
from coinbase.rest import RESTClient
from typing import Dict, Any, Optional

# --------------------------------------------------
# HELPER FUNCTIONS FOR FORMATTING
# --------------------------------------------------
def format_float(value: float, precision: int) -> str:
    """Format a float with a given precision, removing unnecessary trailing zeroes."""
    s = f"{value:.{precision}f}"
    return s.rstrip('0').rstrip('.') if '.' in s else s

def format_percent(value: float) -> str:
    """Format a percentage value with one decimal, removing trailing zeros."""
    s = f"{value:+.1f}%"
    if s.endswith(".0%"):
        s = s.replace(".0%", "%")
    return s

# --------------------------------------------------
# CONFIGURATIONS
# --------------------------------------------------
ENABLE_LOGGING = True
API_KEY_FILE = "perpetuals_trade_cdp_api_key.json"
ORDER_ID_FILE = "order_id.txt"

# Optional parameters (if needed by your account)
LEVERAGE = ""
MARGIN_TYPE = ""

# New constants for buffers and price precision
STOP_LOSS_BUFFER_PERCENT = 0.5    # 0.5% buffer for stop loss orders
PRICE_PRECISION = 4               # 4 decimals for entry and take profit orders
STOP_LOSS_PRICE_PRECISION = 3     # 3 decimals for stop loss orders

# --------------------------------------------------
# LOGGING AND ORDER LOGGING
# --------------------------------------------------
def init_logger() -> None:
    """Initialize console logging."""
    if ENABLE_LOGGING:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
        )
        logging.info("Logging is enabled.")
    else:
        logging.disable(logging.CRITICAL)

def get_next_order_id() -> int:
    """
    Read the last local order ID from ORDER_ID_FILE and return the next ID.
    Starts at 1000 if no file exists.
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

def write_order_log(
    local_id: int,
    order_type: str,
    side: str,
    product: str,
    size: str,
    status_str: str,
    avg_filled_price: str = "",
    coinbase_order_id: str = ""
) -> None:
    """
    Append a CSV-formatted line to ORDER_ID_FILE with the order details.
    Format:
      local_id,timestamp,order_type,side,product,size,status,average_filled_price,coinbase_order_id
    """
    now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    line = (
        f"{local_id},{now_utc},{order_type},{side},{product},{size},"
        f"{status_str},{avg_filled_price},{coinbase_order_id}\n"
    )
    with open(ORDER_ID_FILE, "a") as f:
        f.write(line)

# --------------------------------------------------
# ARGUMENT PARSING
# --------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Execute entry, stop loss, and take profit orders consecutively."
    )
    parser.add_argument("--side", required=True,
                        help="Position side: LONG or SHORT.")
    parser.add_argument("--product", required=True,
                        help="Instrument code, e.g., NEO-PERP-INTX.")
    parser.add_argument("--size", required=True,
                        help="Order size (quantity) to trade.")
    parser.add_argument("--stop-loss-price", required=True, type=float,
                        help="Price at which the stop loss order should trigger.")
    parser.add_argument("--rr-ratio", required=False, type=float, default=2.0,
                        help="Risk reward ratio for take profit calculation (default 2.0).")
    return parser.parse_args()

# --------------------------------------------------
# ORDER CONFIGURATION BUILDERS
# --------------------------------------------------
def build_order_configuration(
    order_type: str,
    size: str,
    price: Optional[float] = None,
    stop_price: Optional[float] = None,
    stop_direction: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build the order configuration dictionary for the REST API call.
    order_type can be:
      - "market" for an entry market order,
      - "stop_loss" for a stop-limit order,
      - "take_profit" for a limit order.
      
    Price fields are converted to strings formatted with the appropriate precision.
    For stop loss orders, we use STOP_LOSS_PRICE_PRECISION; otherwise, PRICE_PRECISION.
    """
    if order_type == "market":
        return {"market_market_ioc": {"base_size": size}}
    elif order_type == "stop_loss":
        config = {"stop_limit_stop_limit_gtc": {"base_size": size}}
        if price is not None:
            config["stop_limit_stop_limit_gtc"]["limit_price"] = f"{price:.{STOP_LOSS_PRICE_PRECISION}f}"
        if stop_price is not None:
            config["stop_limit_stop_limit_gtc"]["stop_price"] = f"{stop_price:.{STOP_LOSS_PRICE_PRECISION}f}"
        if stop_direction:
            config["stop_limit_stop_limit_gtc"]["stop_direction"] = stop_direction
        return config
    elif order_type == "take_profit":
        config = {"limit_limit_gtc": {"base_size": size}}
        if price is not None:
            config["limit_limit_gtc"]["limit_price"] = f"{price:.{PRICE_PRECISION}f}"
        return config
    else:
        raise ValueError(f"Unsupported order type '{order_type}'.")

# --------------------------------------------------
# ERROR HANDLING AND ORDER INFO
# --------------------------------------------------
def parse_failure_reason(response_obj) -> str:
    """
    Extract a failure reason from the API response.
    """
    if not hasattr(response_obj, "error_response") or response_obj.error_response is None:
        return "UNKNOWN"
    err = response_obj.error_response
    if isinstance(err, dict):
        return (
            err.get("preview_failure_reason")
            or err.get("message")
            or err.get("error_details")
            or err.get("error")
            or "UNKNOWN"
        )
    else:
        return (
            getattr(err, "preview_failure_reason", None)
            or getattr(err, "message", None)
            or getattr(err, "error_details", None)
            or getattr(err, "error", None)
            or "UNKNOWN"
        )

def run_order_info_script(coinbase_order_id: str) -> Optional[dict]:
    """
    Run the external script './order_info.py' to fetch additional order details.
    Returns a dictionary if JSON is successfully parsed.
    """
    cmd = ["./order_info.py", coinbase_order_id]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        logging.error("order_info.py not found or not executable.")
        return None
    if result.returncode != 0:
        logging.warning(f"order_info.py returned code {result.returncode}")
    for line in result.stdout.splitlines():
        match = re.search(r"Order info:\s+(\{.*\})", line)
        if match:
            info_json = match.group(1)
            try:
                info_dict = json.loads(info_json)
                return info_dict
            except json.JSONDecodeError:
                logging.error("Failed to parse JSON from order_info.py output.")
                return None
    return None

# --------------------------------------------------
# ORDER EXECUTION
# --------------------------------------------------
def place_single_order(client: RESTClient, side: str, product: str, size: str,
                       order_type: str, price: Optional[float] = None,
                       stop_price: Optional[float] = None,
                       stop_direction: Optional[str] = None) -> Dict[str, Any]:
    """
    Place a single order using the REST API.
    Returns a dictionary containing details about the order.
    """
    local_id = get_next_order_id()
    order_config = build_order_configuration(order_type, size, price, stop_price, stop_direction)
    logging.info(f"Placing {order_type.upper()} order (local_id: {local_id}): {order_config}")
    
    # Optional extra parameters
    optional_params: Dict[str, str] = {}
    if LEVERAGE:
        optional_params["leverage"] = LEVERAGE
    if MARGIN_TYPE:
        optional_params["margin_type"] = MARGIN_TYPE
    
    coinbase_order_id = None
    avg_fill_price_str = None
    exit_code = 0
    status_str = "executed"
    
    try:
        response = client.create_order(
            client_order_id=str(local_id),
            product_id=product,
            side=side,
            order_configuration=order_config,
            **optional_params
        )
        logging.info(f"Response for {order_type.upper()} order (local_id: {local_id}): {response}")
        if not response.success:
            reason = parse_failure_reason(response)
            status_str = f"failed_{reason}"
            exit_code = 1
        else:
            sr = response.success_response
            if isinstance(sr, dict):
                coinbase_order_id = sr.get("order_id", None)
            else:
                coinbase_order_id = getattr(sr, "order_id", None)
    except Exception as e:
        logging.error(f"Error placing {order_type.upper()} order (local_id: {local_id}): {e}")
        status_str = f"failed_{e}"
        exit_code = 1
    
    # Optionally, try to fetch the average filled price
    if not status_str.startswith("failed") and coinbase_order_id:
        info_dict = run_order_info_script(coinbase_order_id)
        if info_dict and "average_filled_price" in info_dict:
            avg_fill_price_str = str(info_dict["average_filled_price"])
            logging.info(f"Fetched average_filled_price={avg_fill_price_str} for {order_type.upper()} order (local_id: {local_id})")
        else:
            logging.info(f"Could not retrieve average_filled_price for {order_type.upper()} order (local_id: {local_id})")
    
    # Log order details locally
    write_order_log(local_id, order_type, side, product, size,
                    status_str,
                    avg_fill_price_str if avg_fill_price_str else "",
                    coinbase_order_id if coinbase_order_id else "")
    
    return {
        "local_order_id": local_id,
        "coinbase_order_id": coinbase_order_id,
        "average_filled_price": avg_fill_price_str,
        "status": status_str,
        "exit_code": exit_code,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

# --------------------------------------------------
# MAIN FUNCTION
# --------------------------------------------------
def main() -> None:
    init_logger()
    args = parse_args()
    
    # Determine order sides based on input.
    side_input = args.side.upper()
    if side_input in ["LONG", "BUY"]:
        entry_side = "BUY"
        exit_side = "SELL"
        stop_direction = "STOP_DIRECTION_STOP_DOWN"
    elif side_input in ["SHORT", "SELL"]:
        entry_side = "SELL"
        exit_side = "BUY"
        stop_direction = "STOP_DIRECTION_STOP_UP"
    else:
        logging.error("Invalid side. Use LONG or SHORT.")
        sys.exit(1)
    
    product = args.product.upper()
    size = args.size  # as provided
    stop_loss_price = args.stop_loss_price
    rr_ratio = args.rr_ratio
    
    # Create the REST client.
    try:
        client = RESTClient(key_file=API_KEY_FILE)
    except FileNotFoundError:
        logging.error(f"API key file '{API_KEY_FILE}' not found.")
        sys.exit(1)
    
    # === ENTRY ORDER ===
    logging.info("\n===== ENTRY ORDER =====")
    entry_order = place_single_order(
        client=client,
        side=entry_side,
        product=product,
        size=size,
        order_type="market"
    )
    
    if entry_order["exit_code"] != 0:
        logging.error("Entry order failed. Aborting subsequent orders.")
        sys.exit(1)
    
    if not entry_order["average_filled_price"]:
        logging.error("No average filled price returned from entry order. Cannot calculate take profit price.")
        sys.exit(1)
    
    try:
        entry_price = float(entry_order["average_filled_price"])
    except ValueError:
        logging.error("Invalid average filled price returned from entry order.")
        sys.exit(1)
    
    # Calculate take profit price based on risk reward ratio.
    if entry_side == "BUY":  # LONG position
        risk = entry_price - stop_loss_price
        if risk <= 0:
            logging.error("Invalid stop loss price: it must be below the entry price for a LONG position.")
            sys.exit(1)
        take_profit_price = entry_price + risk * rr_ratio
    else:  # SHORT position
        risk = stop_loss_price - entry_price
        if risk <= 0:
            logging.error("Invalid stop loss price: it must be above the entry price for a SHORT position.")
            sys.exit(1)
        take_profit_price = entry_price - risk * rr_ratio
    
    take_profit_price = round(take_profit_price, PRICE_PRECISION)
    logging.info(f"Computed take profit price: {take_profit_price:.{PRICE_PRECISION}f} based on entry price: {entry_price:.{PRICE_PRECISION}f} and risk reward ratio: {rr_ratio}")
    
    # Calculate stop loss order prices with buffer.
    buffer_decimal = STOP_LOSS_BUFFER_PERCENT / 100.0
    if entry_side == "BUY":  # LONG: trigger remains; limit is lower.
        stop_loss_trigger = stop_loss_price
        stop_loss_limit = round(stop_loss_price * (1 - buffer_decimal), STOP_LOSS_PRICE_PRECISION)
    else:  # SHORT: trigger remains; limit is higher.
        stop_loss_trigger = stop_loss_price
        stop_loss_limit = round(stop_loss_price * (1 + buffer_decimal), STOP_LOSS_PRICE_PRECISION)
    
    logging.info(f"Using stop loss trigger: {stop_loss_trigger:.{STOP_LOSS_PRICE_PRECISION}f} and limit: {stop_loss_limit:.{STOP_LOSS_PRICE_PRECISION}f} for a {side_input} position.")
    
    # === STOP LOSS ORDER ===
    logging.info("\n===== STOP LOSS ORDER =====")
    stop_loss_order = place_single_order(
        client=client,
        side=exit_side,
        product=product,
        size=size,
        order_type="stop_loss",
        price=stop_loss_limit,         # Limit price with buffer (3 decimals)
        stop_price=stop_loss_trigger,    # Trigger price as supplied (3 decimals)
        stop_direction=stop_direction
    )
    
    # === TAKE PROFIT ORDER ===
    logging.info("\n===== TAKE PROFIT ORDER =====")
    take_profit_order = place_single_order(
        client=client,
        side=exit_side,
        product=product,
        size=size,
        order_type="take_profit",
        price=take_profit_price
    )
    
    # ----- FINANCIAL SUMMARY -----
    # Compute differences relative to entry price.
    if entry_side == "BUY":  # LONG position
        diff_tp = (take_profit_price - entry_price) / entry_price * 100
        diff_sl = (stop_loss_price - entry_price) / entry_price * 100
        # For LONG: columns: TP (left), entry (center), SL (right)
        col1_title, col2_title, col3_title = "Take Profit", "Entry Price", "Stop Loss"
        # Use the take profit and stop loss trigger for display.
        price_tp = take_profit_price
        price_entry = entry_price
        price_sl = stop_loss_price
        diff_tp_val = diff_tp
        diff_sl_val = diff_sl
    else:  # SHORT position
        diff_sl = (stop_loss_price - entry_price) / entry_price * 100
        diff_tp = (take_profit_price - entry_price) / entry_price * 100
        # For SHORT: columns: SL (left), entry (center), TP (right)
        col1_title, col2_title, col3_title = "Stop Loss", "Entry Price", "Take Profit"
        price_sl = stop_loss_price
        price_entry = entry_price
        price_tp = take_profit_price
        diff_sl_val = diff_sl
        diff_tp_val = diff_tp

    # Format numbers without trailing zeroes.
    entry_str = format_float(entry_price, PRICE_PRECISION)
    tp_str = format_float(price_tp, PRICE_PRECISION)
    sl_str = format_float(price_sl, PRICE_PRECISION)
    diff_tp_str = format_percent(diff_tp_val)
    diff_sl_str = format_percent(diff_sl_val)
    
    col_width = 15
    header_line = f"{'':10}{col1_title:<{col_width}}{col2_title:<{col_width}}{col3_title:<{col_width}}"
    price_row = f"{'Price':10}{tp_str if entry_side=='BUY' else sl_str:<{col_width}}{entry_str:<{col_width}}{sl_str if entry_side=='BUY' else tp_str:<{col_width}}"
    diff_row = f"{'Diff':10}{diff_tp_str if entry_side=='BUY' else diff_sl_str:<{col_width}}{'0%':<{col_width}}{diff_sl_str if entry_side=='BUY' else diff_tp_str:<{col_width}}"
    
    # Format risk-profit ratio replacing dot with comma.
    rr_str = str(rr_ratio).replace('.', ',')
    
    final_summary = f"""===== FINANCIAL SUMMARY =====
Product: {product} | Size: {size} | Side: {side_input} | Risk-Profit Ratio: {rr_str}
{header_line}
{price_row}
{diff_row}
{'=' * 50}"""
    
    # Print the final summary without logging prefixes.
    print(final_summary)
    
    # Exit with error if any order failed.
    if (entry_order["exit_code"] != 0 or
        stop_loss_order["exit_code"] != 0 or
        take_profit_order["exit_code"] != 0):
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()