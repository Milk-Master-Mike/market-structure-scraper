FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MARKET_STRUCTURE_CACHE_DIR=/var/cache/market-structure-scraper
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir . && \
    addgroup --system app && adduser --system --ingroup app app && \
    mkdir -p /var/cache/market-structure-scraper && chown app:app /var/cache/market-structure-scraper
USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"
CMD ["uvicorn", "market_structure_scraper.api:app", "--host", "0.0.0.0", "--port", "8080"]

