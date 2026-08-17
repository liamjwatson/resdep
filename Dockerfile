# Use an official Python runtime as a parent image
FROM python:3.9.23

WORKDIR /usr/local/app

# Install the application dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install EGL and OpenGL dependencies for PySide6
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libegl1 \
    libgl1 \
    libdbus-1-3 \
    libxkbcommon-x11-0 \
    && rm -rf /var/lib/apt/lists/*

ENV QT_QPA_PLATFORM=offscreen

# Copy in the source code
COPY . .
EXPOSE 8080

# Make data folder as root
RUN mkdir -p /usr/local/app/data
# Setup an app user so the container doesn't run as the root user
RUN useradd newuser
# give newuser write permissions in data folder
RUN chown newuser /usr/local/app/data
# switch docker from root to newuser
USER newuser



ENTRYPOINT [ "python3", "-m" ]

CMD ["pytest", "./tests/ResonantDepolarisation_test.py"]
