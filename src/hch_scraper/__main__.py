"""
Command-line entry point for the scraper package.

Examples:
  python -m hch_scraper scrape
  python -m hch_scraper daily --min_days_ago 1 --max_days_ago 3
"""

import argparse

from hch_scraper.pipelines import scrape, daily_scraper


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hamilton County homes scraper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("scrape", help="Run interactive date range scraper")

    daily = subparsers.add_parser("daily", help="Run daily range scraper")
    daily.add_argument("--min_days_ago", type=int, required=True)
    daily.add_argument("--max_days_ago", type=int, required=True)

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.command == "scrape":
        scrape.run_scraper_pipeline()
    elif args.command == "daily":
        daily_scraper.run_scraper_pipeline(
            argparse.Namespace(
                min_days_ago=args.min_days_ago, max_days_ago=args.max_days_ago
            )
        )


if __name__ == "__main__":
    main()
