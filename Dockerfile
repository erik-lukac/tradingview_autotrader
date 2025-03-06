# Use a lightweight Python image
FROM python:slim

# Set working directory inside the container
WORKDIR /app

# Copy application files to the container
COPY app/ /app
# COPY coinbase/ /coinbase/ ## not needed because the files need to be mounted instead of copied


# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Flask
RUN pip install flask

# Expose the port Flask will run on
EXPOSE 5002

# Run the webhook listener
CMD ["python", "webhook.py"]
