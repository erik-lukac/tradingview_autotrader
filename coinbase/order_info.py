#!/usr/bin/env python3
"""
order_info.py

lightweight query tool to retrieve information abount single order, providing order ID

"""


import argparse
import logging
import sys
import json
from typing import Any
from requests.exceptions import HTTPError

# Replace this with the correct import for your Coinbase client library.
# E.g., "from coinbase_advanced_trade import ..." or similar if needed.
try:
    from coinbase.rest import RESTClient
except ImportError:
    print("Please install the correct coinbase REST client library.")
    sys.exit(1)


def to_serializable(obj: Any) -> Any:
    """
    Recursively convert objects (including nested ones) into JSON-serializable structures.

    :param obj: The object to convert.
    :return: A JSON-serializable form (dict, list, str, etc.).
    """
    # If it's already a dict, convert values recursively
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}

    # If it's a list (or tuple), convert each element
    if isinstance(obj, (list, tuple)):
        return [to_serializable(x) for x in obj]

    # If it has a __dict__, convert that
    if hasattr(obj, "__dict__"):
        return {k: to_serializable(v) for k, v in vars(obj).items()}

    # If none of the above, return as-is (this handles str, int, float, bool, None, etc.)
    return obj


def fetch_order_info(order_id: str, key_file: str = "perpetuals_trade_cdp_api_key.json") -> Any:
    """
    Fetch the order data from Coinbase (or relevant service) and return it.

    :param order_id: The ID of the order to retrieve.
    :param key_file: The path to your API key JSON file.
    :return: Order information (possibly nested objects/dicts).
    :raises HTTPError: If an HTTP error occurs (400, 404, etc.).
    :raises Exception: For other unexpected errors.
    """
    client = RESTClient(key_file=key_file)

    # The library might return either a dict or a typed object
    response = client.get_order(order_id)

    # If it's a dict, look for "order" key
    if isinstance(response, dict):
        return response.get("order", {})

    # If it's a typed object, try to get the 'order' attribute
    if hasattr(response, "order"):
        return response.order

    return {}


def main() -> None:
    """
    Fetch and display Coinbase order information as single-line JSON.

    Example usage:
      ./order_info.py 5cb95c14-2d8e-41e5-bce4-ce366a6d5fcd

    Example output:
      2025-01-31 08:36:25,893 [INFO] Order info: {"order_id":"5cb95c14-2d8e-41e5-bce4-ce366a6d5fcd","product_id":"BTC-PERP-INTX",...}
    """
    parser = argparse.ArgumentParser(
        description=(
            "Retrieve and display information about a specific Coinbase order.\n\n"
            "Example usage:\n"
            "  ./order_info.py 5cb95c14-2d8e-41e5-bce4-ce366a6d5fcd\n\n"
            "Example output (one-line JSON):\n"
            "  2025-01-31 08:36:25,893 [INFO] Order info: {\"order_id\":\"5cb95c14-2d8e-41e5-bce4-ce366a6d5fcd\",\"product_id\":\"BTC-PERP-INTX\",...}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "order_id",
        type=str,
        help="The ID of the order to retrieve. Example: 5cb95c14-2d8e-41e5-bce4-ce366a6d5fcd"
    )
    parser.add_argument(
        "--key-file",
        default="perpetuals_trade_cdp_api_key.json",
        help="Path to your Coinbase API key JSON file (default: %(default)s)."
    )
    args = parser.parse_args()

    # Set up concise logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    # Suppress the extra error logs from the coinbase client
    # so we only see one error message on HTTP errors
    logging.getLogger("coinbase.RESTClient").setLevel(logging.CRITICAL)

    order_id = args.order_id
    key_file = args.key_file

    logging.info(f"Fetching info for order ID: {order_id}")

    try:
        order_data = fetch_order_info(order_id=order_id, key_file=key_file)
        # Convert any objects into fully JSON-serializable data
        serializable_data = to_serializable(order_data)
        # Encode as single-line JSON
        compact_json = json.dumps(serializable_data, separators=(",", ":"))
        logging.info(f"Order info: {compact_json}")

    except HTTPError as http_err:
        # Log the error once and exit
        logging.error(f"HTTP Error: {http_err}")
        sys.exit(1)

    except Exception as e:
        # Catch any other exceptions (e.g., serialization issues)
        logging.error(f"An error occurred while fetching the order: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
