FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright (matching your working resolver)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libpango-1.0-0 libasound2 libxshmfence1 \
    libxfixes3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7001
CMD ["python", "anime_resolver.py"]
