FROM nvidia/cuda:12.1.0-base-ubuntu22.04
# Multi-OS Support
RUN apt-get update && apt-get install -y python3 rustc
COPY . /app
WORKDIR /app
CMD ["python3", "src/main.py"]
