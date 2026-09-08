# ProTrader web/mobile server (same engine as desktop, no Qt). docker build -t protrader . && docker run -p 8765:8765 protrader
FROM python:3.11-slim
WORKDIR /app
COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt
COPY . .
ENV PROTRADER_DATA=/data PROTRADER_WEB_PORT=8765
VOLUME ["/data"]
EXPOSE 8765
CMD ["python", "main.py", "--web"]
