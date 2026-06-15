# Imagen base con Python + ffmpeg ya incluido
FROM python:3.11-slim

# ffmpeg para montar los .mp4
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render inyecta PORT; el server lo lee de entorno
EXPOSE 10000
CMD ["python", "app.py"]
