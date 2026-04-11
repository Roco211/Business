FROM python:3.12-slim

WORKDIR /app

COPY demo_app/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY demo_app /app/demo_app/

ENV PYTHONPATH=/app

EXPOSE 8081

CMD ["uvicorn", "demo_app.main:app", "--host", "0.0.0.0", "--port", "8081"]
