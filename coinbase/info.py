#!/usr/bin/env python3
"""
info.py

read only script that fetches the latest orders, positions, and perpetuals information from Coinbase Advanced Trading.
Also displays internal order IDs from order_id.txt.
"""

import argparse
import asyncio
import datetime
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from coinbase.rest import RESTClient


# -------------------------------------------------------------------
# Enums, DataClasses, and Constants
# -------------------------------------------------------------------
class Side(Enum):
    """
    Enum representing buy or sell side for an order/position.
    """
    BUY = "BUY"
    SELL = "SELL"
    UNKNOWN = "UNKNOWN"


@dataclass
class Order:
    """
    Data class for a Coinbase order.
    """
    product_id: str
    base_size: str
    side: Side
    created_time: str
    average_filled_price: str
    order_type: str
    order_id: str
    internal_id: Optional[str] = None  # Added field for internal order ID


@dataclass
class Position:
    """
    Data class for a Coinbase position.
    """
    product_id: str
    side: str
    size: str
    created_time: str
    entry_price: str


# -------------------------------------------------------------------
# Order ID Mapping Functions
# -------------------------------------------------------------------
def load_order_id_mapping(filepath: str = "order_id.txt") -> Dict[str, str]:
    """
    Load the mapping between Coinbase order IDs and internal order IDs from the order_id.txt file.
    
    :param filepath: Path to the order_id.txt file
    :return: Dictionary mapping Coinbase order IDs to internal order IDs
    """
    order_map = {}
    try:
        with open(filepath, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 8:  # Ensure the line has enough parts
                    internal_id = parts[0]
                    coinbase_id = parts[7]  # The Coinbase order ID is the 8th element (index 7)
                    order_map[coinbase_id] = internal_id
    except FileNotFoundError:
        logging.warning(f"Order ID file '{filepath}' not found. Internal IDs will not be displayed.")
    except Exception as e:
        logging.error(f"Error reading order ID file: {e}")
    
    if not order_map:
        logging.warning("No order ID mappings were found in the file. Check the file format and content.")
    else:
        logging.info(f"Loaded {len(order_map)} order ID mappings")
    
    return order_map


# -------------------------------------------------------------------
# Table Formatter
# -------------------------------------------------------------------
def print_table(headers: List[str], rows: List[List[str]]) -> None:
    """
    Prints a table using string manipulation.

    :param headers: List of column headers.
    :param rows: List of rows, where each row is a list of strings.
    """
    if not rows:
        return

    # Calculate column widths based on the headers and the rows
    column_widths = [max(len(str(item)) for item in col) for col in zip(headers, *rows)]

    # Create a horizontal separator
    separator = "+" + "+".join("-" * (width + 2) for width in column_widths) + "+"

    # Format and print headers
    header_row = "| " + " | ".join(f"{header.ljust(width)}" for header, width in zip(headers, column_widths)) + " |"

    print(separator)
    print(header_row)
    print(separator)

    # Format and print each row
    for row in rows:
        formatted_row = "| " + " | ".join(f"{str(item).ljust(width)}" for item, width in zip(row, column_widths)) + " |"
        print(formatted_row)
    print(separator)


# -------------------------------------------------------------------
# Asynchronous Helper Functions
# -------------------------------------------------------------------
async def fetch_orders_and_positions(client: RESTClient, order_id_map: Dict[str, str]) -> Tuple[List[Order], List[Position]]:
    """
    Asynchronously fetch orders and positions from the Coinbase client.

    :param client: The RESTClient for interacting with the Coinbase API.
    :param order_id_map: Mapping of Coinbase order IDs to internal order IDs.
    :return: A tuple containing a list of Orders and a list of Positions.
    """
    loop = asyncio.get_running_loop()

    def _list_orders() -> dict:
        return client.list_orders().to_dict()

    orders_dict = await loop.run_in_executor(None, _list_orders)
    orders_raw = orders_dict.get("orders", [])

    orders: List[Order] = []
    for odict in orders_raw:
        product_id = odict.get("product_id", "N/A")
        raw_side = odict.get("side", "UNKNOWN").upper()
        side_enum = Side(raw_side) if raw_side in Side._value2member_map_ else Side.UNKNOWN
        created_time = odict.get("created_time", "N/A")
        avg_price = odict.get("average_filled_price", "N/A")
        order_type = odict.get("order_type", "N/A")
        order_id = odict.get("order_id", "N/A")
        
        # Look up internal ID from the mapping
        internal_id = order_id_map.get(order_id, "N/A")

        base_size = "N/A"
        order_config = odict.get("order_configuration", {})
        market_config = order_config.get("market_market_ioc")
        if market_config:
            base_size = market_config.get("base_size", "N/A")

        orders.append(
            Order(
                product_id=product_id,
                base_size=base_size,
                side=side_enum,
                created_time=created_time,
                average_filled_price=avg_price,
                order_type=order_type,
                order_id=order_id,
                internal_id=internal_id
            )
        )

    def _list_positions() -> dict:
        return client.list_positions().to_dict()

    positions: List[Position] = []
    try:
        positions_dict = await loop.run_in_executor(None, _list_positions)
        positions_raw = positions_dict.get("positions", [])
        for pdict in positions_raw:
            positions.append(
                Position(
                    product_id=pdict.get("product_id", "N/A"),
                    side=pdict.get("side", "N/A"),
                    size=pdict.get("size", "N/A"),
                    created_time=pdict.get("created_time", "N/A"),
                    entry_price=pdict.get("entry_price", "N/A"),
                )
            )
    except AttributeError:
        logging.warning("`list_positions()` method not found. Positions will be empty.")

    return orders, positions


async def fetch_perpetuals_info(client: RESTClient, portfolio_uuid: str) -> List[dict]:
    """
    Asynchronously fetch perpetuals positions information from Coinbase.

    :param client: The RESTClient for interacting with the Coinbase API.
    :param portfolio_uuid: The portfolio UUID to query perpetual positions.
    :return: A list of perpetual position dictionaries.
    """
    loop = asyncio.get_running_loop()

    def _list_perps_positions() -> dict:
        return client.list_perps_positions(portfolio_uuid).to_dict()

    perp_dict = await loop.run_in_executor(None, _list_perps_positions)
    return perp_dict.get("positions", [])


async def main_async(num_records: int) -> None:
    """
    Main asynchronous function that fetches and displays Coinbase data.

    :param num_records: Number of transactions to show for each category.
    """
    key_file_path = Path("perpetuals_trade_cdp_api_key.json")
    
    # Load order ID mapping
    order_id_map = load_order_id_mapping()

    try:
        client = RESTClient(key_file=str(key_file_path))
    except Exception as e:
        logging.error(f"Error initializing RESTClient with {key_file_path}: {e}")
        return

    try:
        orders, positions = await fetch_orders_and_positions(client, order_id_map)
    except Exception as e:
        logging.error(f"Error fetching orders/positions: {e}")
        return

    # Process and display orders
    if orders:
        sliced_orders = orders[:num_records]
        headers_orders = ["Product", "Side", "Size", "Price", "Type", "Time", "Order ID", "Client Order ID"]  # Added Internal ID
        rows_orders = []
        for o in sliced_orders:
            try:
                dt = datetime.datetime.fromisoformat(o.created_time.replace("Z", "+00:00"))
                formatted_time = dt.strftime("%d%b%y %H:%M")
            except Exception:
                formatted_time = o.created_time

            rows_orders.append([
                o.product_id,
                o.side.value,
                o.base_size,
                o.average_filled_price,
                o.order_type,
                formatted_time,
                o.order_id,
                o.internal_id  # Added internal ID to the output
            ])

        print_table(headers_orders, rows_orders)

    # Process and display positions if they exist
    if positions:
        sliced_positions = positions[:num_records]
        headers_positions = ["Product", "Side", "Size", "Created Time", "Entry Price"]
        rows_positions = []
        for p in sliced_positions:
            rows_positions.append([
                p.product_id,
                p.side,
                p.size,
                p.created_time,
                p.entry_price,
            ])

        print_table(headers_positions, rows_positions)

    # Display perpetuals information
    portfolio_uuid = "01939152-3367-7138-a24c-8ed09a9d89f0"  # Replace with your portfolio UUID if different
    try:
        perpetuals_positions = await fetch_perpetuals_info(client, portfolio_uuid)
    except Exception as e:
        logging.error(f"Error fetching perpetuals info: {e}")
        return

    if perpetuals_positions:
        # Change the header from "Unrealized PnL" to "PnL"
        headers_perp = ["Symbol", "Entry Price", "Current Price", "Size", "Total Value", "PnL", "Side"]
        rows_perp = []
        for pos in perpetuals_positions[:num_records]:
            symbol = pos.get("symbol", "N/A")
            entry_price = pos.get("entry_vwap", {}).get("value", "N/A")
            current_price = pos.get("mark_price", {}).get("value", "N/A")
            size = pos.get("net_size", "N/A")
            total_value = pos.get("position_notional", {}).get("value", "N/A")
            # Fetch aggregated_pnl rather than unrealized_pnl
            pnl = pos.get("aggregated_pnl", {}).get("value", "N/A")
            side = pos.get("position_side", "N/A")
            rows_perp.append([symbol, entry_price, current_price, size, total_value, pnl, side])

        print_table(headers_perp, rows_perp)


def main() -> None:
    """
    Entry point for the script, handles CLI arguments and sets up logging.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    parser = argparse.ArgumentParser(
        description="Show the latest orders, positions, and perpetuals info from Coinbase Advanced Trading."
    )
    parser.add_argument(
        "number",
        type=int,
        nargs='?',
        default=3,
        help="Number of records to show for each category (default: 3).",
    )
    args = parser.parse_args()
    num_records: int = args.number

    asyncio.run(main_async(num_records))


if __name__ == "__main__":
    main()