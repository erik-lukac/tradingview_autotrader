"""
Webhook Listener Script

This script implements a Flask web server that listens for incoming TradingView webhook
requests on the `/tradingview` endpoint. When a webhook is received, the script:

  1. Logs and processes the raw webhook payload.
  2. Executes the external `parse_alert.py` script to convert the alert text into JSON.
  3. If the parsed alert contains the required keys (action, ticker, position), it executes
     the external `order.py` script (located in the coinbase directory) to execute the order.
  4. Logs all steps of the process, including successes and errors.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import subprocess
from logging import Logger
from flask import Flask, request, jsonify
from typing import Any, Dict

# -----------------------
# Constants and Path Settings
# -----------------------

BASE_DIR = os.path.dirname(__file__)
COINBASE_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "coinbase"))
PARSE_ALERT_SCRIPT_PATH = os.path.join(COINBASE_DIR, "parse_alert.py")
ORDER_SCRIPT_PATH = os.path.join(COINBASE_DIR, "order.py")
PYTHON_COMMAND = "python"  # Change to "python3" if needed.
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5002

# Add the coinbase directory to PYTHONPATH so we can import if needed.
sys.path.insert(0, COINBASE_DIR)

# -----------------------
# Logging Configuration
# -----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger: Logger = logging.getLogger(__name__)

# -----------------------
# Helper Functions
# -----------------------

def parse_input_data(content_type: str, raw_data: str) -> Dict[str, Any]:
    """
    Parse the incoming raw data based on its content type.
    """
    if "application/json" in content_type:
        try:
            data = request.json
            logger.info("JSON parsed successfully.")
            return data
        except Exception as e:
            logger.warning("Failed to parse JSON data: %s", e)
            return {"error": "Invalid JSON"}
    elif "text/plain" in content_type or "unknown" in content_type:
        logger.info("Using raw text as input.")
        return {"text": raw_data}
    elif "tradingview-format" in content_type:
        data = parse_tradingview_format(raw_data)
        logger.info("Parsed TradingView-specific format.")
        return data
    else:
        logger.warning("Unrecognized content type: %s", content_type)
        return {"warning": "Unrecognized content type"}


def execute_parse_alert(alert_text: str) -> Dict[str, Any]:
    """
    Execute the external parse_alert.py script with the given alert text.
    
    Returns:
        dict: The parsed alert as a dictionary.
    """
    try:
        cmd = [PYTHON_COMMAND, PARSE_ALERT_SCRIPT_PATH, alert_text]
        logger.info("Executing parse_alert command: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info("parse_alert output: %s", result.stdout)
        # Attempt to decode JSON output.
        alert_data = json.loads(result.stdout.strip())
        return alert_data
    except subprocess.CalledProcessError as e:
        logger.error("parse_alert execution failed: %s", e)
        return {"error": str(e)}
    except Exception as e:
        logger.error("Unexpected error in execute_parse_alert: %s", e)
        return {"error": str(e)}


def execute_order(alert: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the external order.py script using the parsed alert data.
    The order parameters are passed as a single argument string.

    Returns:
        dict: The result of the order execution (stdout or error message).
    """
    try:
        action = alert["action"].upper()
        ticker = alert["ticker"]
        position = str(alert["position"])
        logger.info("Preparing to execute order: action=%s, ticker=%s, position=%s", action, ticker, position)

        # Build one string argument, e.g. "BUY GIGA-PERP-INTX 900"
        single_arg = f"{action} {ticker} {position}"

        # Pass everything as a single argument.
        cmd = [PYTHON_COMMAND, ORDER_SCRIPT_PATH, single_arg]
        logger.info("Executing order command: %s", " ".join(cmd))
        
        # Set cwd to COINBASE_DIR so that relative paths inside order.py work correctly.
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=COINBASE_DIR)
        logger.info("Order executed successfully. Output:\n%s", result.stdout)
        return {"stdout": result.stdout}
    except subprocess.CalledProcessError as e:
        logger.error("Order execution failed: %s", e)
        return {"error": str(e)}
    except Exception as e:
        logger.error("Unexpected error executing order: %s", e)
        return {"error": str(e)}


def process_webhook() -> Dict[str, Any]:
    """
    Process the incoming webhook:
      - Parse the input data.
      - If a 'text' field is found, execute parse_alert.py to convert it into structured data.
      - If the parsed alert contains the required keys, execute order.py to place the order.
    """
    content_type = request.content_type or "unknown"
    raw_data = request.data.decode("utf-8", errors="replace")
    logger.info("Received webhook with content type: %s", content_type)
    logger.info("Raw Data Received:\n%s", raw_data)

    parsed_data = parse_input_data(content_type, raw_data)
    logger.info("Initial Parsed Data:\n%s", parsed_data)

    if "text" in parsed_data and isinstance(parsed_data["text"], str) and parsed_data["text"].strip():
        try:
            logger.info("Executing parse_alert for text: %s", parsed_data["text"])
            alert_parsed = execute_parse_alert(parsed_data["text"])
            parsed_data["alert_parsed"] = alert_parsed
            logger.info("Alert Parsed Data:\n%s", alert_parsed)

            # Check for required keys before executing the order.
            if all(key in alert_parsed for key in ["action", "ticker", "position"]):
                logger.info("Required keys found in alert. Executing order...")
                order_response = execute_order(alert_parsed)
                parsed_data["order_result"] = order_response
            else:
                logger.warning("Parsed alert does not contain required keys for order execution.")
        except Exception as e:
            logger.error("Error processing alert text: %s", e)
            parsed_data["alert_parsed_error"] = str(e)
    else:
        logger.info("No valid 'text' field found in parsed data. Skipping parse_alert and order execution.")

    return parsed_data


def parse_tradingview_format(raw_data: str) -> Dict[str, Any]:
    """
    Parse data in TradingView-specific format.
    This is a placeholder; customize it to your specific format.
    """
    try:
        lines = raw_data.splitlines()
        data = {}
        for line in lines:
            if "=" in line:
                key, value = line.split("=", 1)
                data[key.strip()] = value.strip()
        return {"tradingview_data": data}
    except Exception as exc:
        logger.warning("Failed to parse TradingView format: %s", exc)
        return {"error": "Invalid TradingView format"}


# -----------------------
# Flask Application Setup
# -----------------------

def create_app() -> Flask:
    """
    Create and configure the Flask application.
    """
    app = Flask(__name__)

    @app.route("/tradingview", methods=["POST"])
    def tradingview_webhook() -> Any:
        """
        Flask route that handles TradingView webhook requests.
        """
        try:
            processed_data = process_webhook()
            logger.info("Final processed data: %s", processed_data)
            return jsonify({"status": "received", "parsed_data": processed_data}), 200
        except Exception as exc:
            logger.exception("Error processing webhook:")
            return jsonify({"status": "error", "message": str(exc)}), 400

    return app


def main() -> None:
    """
    Entrypoint for running the Flask application.
    """
    app = create_app()
    logger.info("Starting Flask app on %s:%s", FLASK_HOST, FLASK_PORT)
    app.run(host=FLASK_HOST, port=FLASK_PORT)


if __name__ == "__main__":
    main()