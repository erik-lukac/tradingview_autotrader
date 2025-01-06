# Use a lightweight Python image
FROM python:slim

# Set working directory inside the container
WORKDIR /app

# Copy application files to the container
COPY app/ /app

# Install Flask
RUN pip install flask

# Expose the port Flask will run on
EXPOSE 5002

# Run the webhook listener
CMD ["python", "webhook.py"]
