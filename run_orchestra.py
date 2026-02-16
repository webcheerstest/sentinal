#!/usr/bin/env python3
"""
Sentinal Orchestra - Standalone runner for multi-channel honeypot orchestration.

Usage:
    python3 run_orchestra.py
"""

import asyncio
import json
import logging
import signal
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import orchestra components
from orchestra.gateway import OrchestraGateway


async def main():
    """Main entry point for Orchestra."""
    logger.info("=" * 60)
    logger.info("  SENTINAL ORCHESTRA - Multi-Channel Honeypot Gateway")
    logger.info("  Inspired by PicoClaw | Built for Scam Detection")
    logger.info("=" * 60)
    
    # Load configuration
    config_path = Path("config/orchestra.json")
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        logger.error("Please create config/orchestra.json with your bot tokens")
        return
    
    with open(config_path) as f:
        config = json.load(f)
    
    # Create and initialize gateway
    gateway = OrchestraGateway(config)
    await gateway.initialize()
    
    # Setup signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()
    
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start gateway
    try:
        # Run until shutdown signal
        gateway_task = asyncio.create_task(gateway.start())
        await shutdown_event.wait()
    except Exception as e:
        logger.error(f"Gateway error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        await gateway.stop()
        logger.info("Goodbye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
