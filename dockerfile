FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl unzip ca-certificates && \
    rm -rf /var/lib/apt/lists/*


RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh -s -- -y
ENV PATH="/usr/local/bin:${PATH}"

WORKDIR /app

COPY req.txt .
RUN pip install --no-cache-dir -r req.txt

RUN playwright install chromium --with-deps

COPY . .

CMD ["python", "main.py"]