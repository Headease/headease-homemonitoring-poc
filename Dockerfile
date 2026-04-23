FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libsodium-dev libssl-dev git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /liboprf

RUN git clone --depth 1 --branch v0.9.3 https://github.com/stef/liboprf.git . && \
    cd src && \
    make

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsodium23 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# Copy compiled libraries
COPY --from=builder /liboprf/src/noise_xk/lib*.so /usr/local/lib/
COPY --from=builder /liboprf/src/lib*.so /usr/local/lib/
RUN ldconfig

COPY app/ app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
