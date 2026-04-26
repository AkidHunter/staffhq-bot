FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
  CMD test $(find /tmp/staffhq_bot_alive -mmin -2 2>/dev/null | wc -l) -gt 0 || exit 1

RUN addgroup --system app && adduser --system --ingroup app app && chown -R app:app /app
USER app

CMD ["python", "main.py"]
