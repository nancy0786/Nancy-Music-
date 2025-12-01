FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt update && apt install -y \
    ffmpeg \
    git \
    build-essential \
    pkg-config \
    libffi-dev \
    libssl-dev \
    libopus-dev \
    libsndfile1-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip setuptools wheel cython
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "main.py"]
