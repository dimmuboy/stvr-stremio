FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py ./
USER 65534:65534
EXPOSE 7000
CMD ["waitress-serve", "--listen=0.0.0.0:7000", "app:app"]
