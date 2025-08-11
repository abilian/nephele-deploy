# Use a lightweight, official Python image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the application file into the working directory
COPY app.py .

# Install Flask
RUN pip install --no-cache-dir Flask

# Expose port 5000 to the network
EXPOSE 5000

# Command to run the application when the container starts
CMD ["python", "app.py"]
