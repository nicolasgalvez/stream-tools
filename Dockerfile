FROM python:3.11-slim AS builder

WORKDIR /build
COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

FROM python:3.11-slim

RUN useradd --create-home appuser

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/yt /usr/local/bin/yt

USER appuser
WORKDIR /home/appuser

ENTRYPOINT ["yt"]
