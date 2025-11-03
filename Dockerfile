FROM python:3.11-slim

# install system deps and bio tools
RUN apt-get update && apt-get install -y \
    bwa \
    samtools \
    curl \
    wget \
    unzip \
    git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# install cutadapt (needed by Trim Galore)
RUN pip install --no-cache-dir cutadapt

# install Trim Galore (no FastQC)
RUN curl -L https://github.com/FelixKrueger/TrimGalore/archive/0.6.10.tar.gz -o /tmp/tg.tar.gz && \
    cd /tmp && tar -xzf tg.tar.gz && \
    mv TrimGalore-0.6.10/trim_galore /usr/local/bin/ && \
    chmod +x /usr/local/bin/trim_galore && \
    rm -rf /tmp/*

WORKDIR /app
COPY . /app

# install python deps for your app
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
