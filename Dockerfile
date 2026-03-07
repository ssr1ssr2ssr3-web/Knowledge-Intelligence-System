# Matching your local 3.13 environment
FROM python:3.13-slim

WORKDIR /app

# Copy and install requirements first (better for Docker caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Streamlit port
EXPOSE 8501

# Run command
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]

 