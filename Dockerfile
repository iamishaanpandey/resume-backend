# Use lightweight Python image
FROM python:3.9-slim

# 1. Install System Dependencies (LaTeX)
# Added 'texlive-latex-recommended' to fix the margin/geometry crash
RUN apt-get update && apt-get install -y \
    texlive-latex-base \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-latex-extra \
    texlive-latex-recommended \
    && rm -rf /var/lib/apt/lists/*

# 2. Set working directory
WORKDIR /app

# 3. Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy App Code
COPY . .

# 5. Start the Server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]