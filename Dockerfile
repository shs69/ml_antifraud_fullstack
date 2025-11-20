FROM python:3.13.3

WORKDIR /app/
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY ./req.txt /app/
RUN pip install --no-cache-dir -r req.txt

COPY . /app/

CMD ["fastapi", "run", "--workers", "4", "app/main.py"]