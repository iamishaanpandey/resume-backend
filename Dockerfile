# Use official Python runtime
FROM python:3.9-slim

# Install LaTeX (Heavy but necessary)
RUN apt-get update && apt-get install -y \
    texlive-latex-base \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-latex-extra \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Run app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]