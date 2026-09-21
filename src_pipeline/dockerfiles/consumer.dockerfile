# Ritningen för consumerns container.
FROM python:3.11-slim

# Hämtar uv-programmet från dess officiella image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Utan denna rad buffrar Python sina utskrifter och
# "docker compose logs consumer" visar ingenting.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Beroenden först - då återanvänds lagret om bara koden ändras.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-install-project

COPY consumer.py ./

# Gör den virtuella miljöns python till standard.
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "consumer.py"]