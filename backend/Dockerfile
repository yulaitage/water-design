FROM python:3.11-bookworm
WORKDIR /app

RUN find /etc/apt -name "*.list" -o -name "*.sources" 2>/dev/null | xargs rm -f 2>/dev/null; \
    echo 'deb https://mirrors.aliyun.com/debian bookworm main' > /etc/apt/sources.list && \
    echo 'deb https://mirrors.aliyun.com/debian bookworm-updates main' >> /etc/apt/sources.list && \
    echo 'deb https://mirrors.aliyun.com/debian-security bookworm-security main' >> /etc/apt/sources.list && \
    apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir uv && uv pip install --system --no-cache-dir --index-url https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com .

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
