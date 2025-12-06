FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# --- System deps + Firefox + geckodriver ---
ARG GECKODRIVER_VERSION=0.34.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    firefox-esr \
    ca-certificates \
    wget \
    libnss3 \
    libdbus-glib-1-2 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    # install geckodriver
    && wget -q "https://github.com/mozilla/geckodriver/releases/download/v${GECKODRIVER_VERSION}/geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz" \
    && tar -xzf geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz -C /usr/local/bin \
    && rm geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create non-root user and give them ownership of /app
RUN useradd -m appuser \
    && mkdir -p /app/logs \
    && chown -R appuser:appuser /app

USER appuser

# Now we can import `hch_scraper` directly because /app/src is on PYTHONPATH
CMD ["python", "-m", "hch_scraper.pipelines.scrape"]
