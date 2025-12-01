FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 ENV PYTHONUNBUFFERED=1
Install apt build deps and libraries commonly required by ntgcalls/pytgcalls
RUN apt-get update && apt-get install -y --no-install-recommends 
build-essential 
git 
ffmpeg 
pkg-config 
cmake 
ninja-build 
libffi-dev 
libssl-dev 
libopus-dev 
libsndfile1-dev 
libavcodec-dev 
libavformat-dev 
libavutil-dev 
libswresample-dev 
libasound2-dev 
wget 
curl 
ca-certificates 
&& rm -rf /var/lib/apt/lists/*
Install Rust toolchain (required for some subpackages)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y ENV PATH="/root/.cargo/bin:${PATH}"
WORKDIR /app
Copy requirements and install python build tools first
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip setuptools wheel cython
Increase build parallelism if desired — CMAKE_BUILD_PARALLEL_LEVEL used by some builds
ENV CMAKE_BUILD_PARALLEL_LEVEL=4
Install python requirements (ntgcalls/pytgcalls will be built from source)
RUN pip install --no-cache-dir -r /app/requirements.txt
Copy application files
COPY . /app
Environment vars default (override on Render)
ENV BOT_TOKEN="" ENV SESSION_STRING="" ENV API_ID="" ENV API_HASH="" ENV OWNER_ID=""
CMD ["python", "main.py"]
