# AI Social Bot — Node.js Python X API Image generation Auto-reply
# Tommy Shamamba 9+ years FLEXIBILITY true — 2.5M+ impressions
FROM python:3.11-slim
WORKDIR /app
ENV FLEXIBILITY=true
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
EXPOSE 8003
CMD ["uvicorn", "src.bot:app", "--host", "0.0.0.0", "--port", "8003"]
