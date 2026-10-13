FROM python:3.13-slim
COPY uv /usr/local/bin/uv
WORKDIR /source
COPY source/ /source/
RUN uv sync --frozen --group dev
COPY fixture/ /fixture/
ENV PATH="/source/.venv/bin:$PATH"
ENV PYTHONPATH="/fixture:/source"
