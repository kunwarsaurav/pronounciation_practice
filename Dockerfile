FROM python:3.10-slim

WORKDIR /workspace

# Install system dependencies (ffmpeg is required for librosa and pydub)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install PyTorch CPU first to keep image size small (crucial for VPS deployment)
RUN pip install --no-cache-dir torch torchaudio --extra-index-url https://download.pytorch.org/whl/cpu

# Install the rest of the requirements
# We remove torch and torchaudio from requirements.txt temporarily during this step 
# to prevent pip from pulling the massive GPU versions again
RUN grep -v "torch" requirements.txt > req_no_torch.txt && \
    pip install --no-cache-dir -r req_no_torch.txt

# Copy the rest of the application code
COPY . .

# Expose port
EXPOSE 8000

# Run the FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
