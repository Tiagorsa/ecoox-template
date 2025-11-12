FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Sistema básico
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App
COPY main.py .
COPY start.sh .
RUN chmod +x /app/start.sh

# Variáveis padrão (ajuste no EasyPanel)
ENV HOST=0.0.0.0 \
    PORT=8000 \
    BASE_URL=https://api4.ecosim.com.br \
    APP_ROOT_PATH=""

EXPOSE 8000

CMD ["/app/start.sh"]
