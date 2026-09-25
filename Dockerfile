FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml .
RUN python -c "import tomllib; from pathlib import Path; Path('/tmp/requirements.txt').write_text('\n'.join(tomllib.loads(Path('pyproject.toml').read_text())['project']['dependencies']))" \
    && pip install --no-cache-dir --upgrade 'pip>=26.2' \
    && pip install --no-cache-dir -r /tmp/requirements.txt
COPY app ./app
RUN pip install --no-cache-dir --no-deps .
COPY alembic ./alembic
COPY alembic.ini .
RUN useradd --create-home bot
USER bot
CMD ["python","-m","app.main"]
