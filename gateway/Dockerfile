FROM python:3.11-slim

WORKDIR /opt/qwesdk
COPY gateway/requirements.txt /opt/qwesdk/gateway/requirements.txt
RUN pip install --no-cache-dir -r /opt/qwesdk/gateway/requirements.txt
COPY m /opt/qwesdk/m
COPY gateway /opt/qwesdk/gateway

ENV PYTHONPATH=/opt/qwesdk:/opt/qwesdk/gateway
RUN useradd --create-home --uid 10001 helix
USER helix
EXPOSE 8090
CMD ["python", "/opt/qwesdk/gateway/app.py"]
