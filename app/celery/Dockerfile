FROM python:3.13.3

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

COPY ../../req.txt /app/

RUN pip install --no-cache-dir -r req.txt

COPY . /app/

CMD ["celery", "-A", "app.celery.worker", "worker", "--loglevel=info", "--pool=threads", "--concurrency=4"]
