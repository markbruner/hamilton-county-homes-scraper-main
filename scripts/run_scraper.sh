#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Wrapper to launch the Hamilton County homes scraper
# -----------------------------------------------------------------------------

# 1) (Optional) Activate your virtual environment
#    Uncomment and adjust if you use a venv at the repo root:
# source ../.venv/bin/activate

# 2) Run the scraper via the package entry point
python -m hch_scraper.main "$@"