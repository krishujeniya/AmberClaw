import argparse
import sys
import time

from loguru import logger


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock RL Server for AmberClaw")
    parser.add_argument("--type", type=str, required=True)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    logger.info(f"Mock server '{args.type}' starting on port {args.port}...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info(f"Mock server '{args.type}' stopping...")
        sys.exit(0)


if __name__ == "__main__":
    main()
