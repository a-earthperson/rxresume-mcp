"""
Entry point for RxResume MCP server.
"""

import logging
import sys

from rxresume_mcp import config
from rxresume_mcp.server import mcp

logging.basicConfig(
    level=config.MCP.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main():
    """Main function for server startup."""
    try:
        log_level = getattr(logging, config.MCP.log_level)
        logging.getLogger().setLevel(log_level)

        logger.info("Starting RxResume MCP server")
        if config.RXRESUME.base_url:
            logger.info(
                "Reactive Resume API is expected to be available at: %s",
                config.RXRESUME.base_url,
            )
        else:
            logger.warning("Reactive Resume API base URL is not configured")

        if config.RXRESUME.api_key:
            logger.info("API key is configured")
        else:
            logger.warning("No API key provided")

        mcp.run(transport=config.TRANSPORT, mount_path=config.MCP.mount_path)

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.exception("Error starting server: %s", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
