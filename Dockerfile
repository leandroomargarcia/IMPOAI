FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY llm.py ./
COPY api/ api/
COPY graph/ graph/
COPY ncm/ ncm/

RUN pip install --no-cache-dir \
    "langchain>=1.3.14" \
    "langchain-openai>=1.4.1" \
    "langchain-tavily>=0.2.18" \
    "langgraph>=1.0.0" \
    "langfuse>=3.0.0" \
    "pypdf>=5.0.0" \
    "python-dotenv>=1.2.2" \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.32.0"

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["sh", "-c", "uvicorn api.main:api --host 0.0.0.0 --port ${PORT:-8000}"]
