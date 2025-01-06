from __future__ import annotations

import logging
from logging import Logger
from flask import Flask, request, jsonify
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger: Logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """
    Create and configure the Flask application.
    """
    app = Flask(__name__)

    @app.route("/tradingview", methods=["POST"])
    def tradingview_webhook() -> Any:
        """
        Handle incoming data from TradingView, supporting multiple formats.
        """
        try:
            # Get content type and raw data
            content_type = request.content_type or "unknown"
            raw_data = request.data.decode("utf-8", errors="replace")  # Decode raw bytes
            parsed_data = None

            # Handle different content types
            if "application/json" in content_type:
                try:
                    parsed_data = request.json
                except Exception as json_exc:
                    logger.warning(f"Failed to parse JSON data: {json_exc}")
                    parsed_data = {"error": "Invalid JSON"}
            elif "text/plain" in content_type or "unknown" in content_type:
                # For plain text or unknown content types, assume raw text
                parsed_data = {"text": raw_data}
            elif "tradingview-format" in content_type:
                # Example: Special parsing for TradingView-specific formats
                parsed_data = parse_tradingview_format(raw_data)
            else:
                parsed_data = {"warning": "Unrecognized content type"}

            # Log raw and parsed data
            logger.info(f"Raw Data Received:\n{raw_data}")
            logger.info(f"Parsed Data:\n{parsed_data}")

            # Respond with acknowledgment and parsed data
            return jsonify({"status": "received", "parsed_data": parsed_data}), 200
        except Exception as exc:
            logger.exception("Error processing webhook:")
            return jsonify({"status": "error", "message": str(exc)}), 400

    return app


def parse_tradingview_format(raw_data: str) -> dict[str, Any]:
    """
    Parse data in TradingView-specific format (custom logic as needed).

    This is a placeholder function. Replace with actual parsing rules
    based on your requirements.
    """
    try:
        # Example: Parse key-value pairs separated by newlines
        lines = raw_data.splitlines()
        data = {}
        for line in lines:
            if "=" in line:
                key, value = line.split("=", 1)
                data[key.strip()] = value.strip()
        return {"tradingview_data": data}
    except Exception as exc:
        logger.warning(f"Failed to parse TradingView format: {exc}")
        return {"error": "Invalid TradingView format"}


def main() -> None:
    """
    Entrypoint for running the Flask application.
    """
    app = create_app()
    app.run(host="0.0.0.0", port=5002)


if __name__ == "__main__":
    main()
