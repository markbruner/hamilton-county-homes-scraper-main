"""
Command-line entry point for the scraper package.

Examples:
  python -m hch_scraper scrape
  python -m hch_scraper daily --min_days_ago 1 --max_days_ago 3
"""

import argparse

from hch_scraper.pipelines import scrape


def _parse_args() -> argparse.Namespace:
    """Parse package CLI arguments for the scraper and demo entry points."""
    parser = argparse.ArgumentParser(description="Hamilton County homes scraper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("scrape", help="Run interactive date range scraper")

    daily = subparsers.add_parser("daily", help="Run daily range scraper")
    daily.add_argument("--min_days_ago", type=int, required=True)
    daily.add_argument("--max_days_ago", type=int, required=True)

    web_demo = subparsers.add_parser("web-demo", help="Run similarity web demo")
    web_demo.add_argument("--host", default="127.0.0.1")
    web_demo.add_argument("--port", type=int, default=8000)
    web_demo.add_argument("--data-path", default=None)
    web_demo.add_argument("--source", choices=("csv", "supabase"), default="csv")
    web_demo.add_argument("--supabase-schema", default="public")
    web_demo.add_argument("--supabase-table", default="sales_enriched_api")
    web_demo.add_argument(
        "--supabase-key-type",
        choices=("anon", "service_role"),
        default="anon",
    )

    return parser.parse_args()


def main() -> None:
    """Dispatch the selected subcommand to the matching pipeline entry point."""
    args = _parse_args()
    if args.command == "scrape":
        scrape.run_scraper_pipeline()
    elif args.command == "daily":
        scrape.run_scraper_pipeline(
            argparse.Namespace(
                min_days_ago=args.min_days_ago, max_days_ago=args.max_days_ago
            )
        )
    elif args.command == "web-demo":
        from hch_scraper import web_demo

        web_demo.run_demo_server(
            host=args.host,
            port=args.port,
            data_path=args.data_path,
            source=args.source,
            supabase_schema=args.supabase_schema,
            supabase_table=args.supabase_table,
            supabase_key_type=args.supabase_key_type,
        )


if __name__ == "__main__":
    main()
