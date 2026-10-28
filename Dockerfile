FROM python:3.12-slim

WORKDIR /app

# Evitar buffers en logs y bytecode innecesario
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MCP_TRANSPORT=sse \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY app/ ./app
COPY pyproject.toml .
COPY README.md .

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["python", "-m", "app.mcp_server"]
