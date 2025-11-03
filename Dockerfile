# =========================
# WormSeq.io Dockerfile
# =========================

# Base image with Python and system tools
FROM python:3.11-slim

# Install OS dependencies for bioinformatics tools
RUN apt-get update && apt-get install -y \
    bwa \
    samtools \
    curl \
    wget \
    unzip \
    git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Trim Galore (via Cutadapt and FastQC)
RUN pip install cutadapt fastqc
RUN curl -L https://github.com/FelixKrueger/TrimGalore/archive/0.6.10.tar.gz -o trim_galore.tar.gz && \
    tar -xzf trim_galore.tar.gz && \
    mv TrimGalore-0.6.10/trim_galore /usr/local/bin/ && \
    chmod +x /usr/local/bin/trim_galore && \
    rm -rf TrimGalore*

# Create working directory
WORKDIR /app

# Copy repo contents into the container
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the web port
EXPOSE 8000

# Command to start FastAPI app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
