# Use an official Python runtime as a parent image
FROM python:3.9.23
ARG HOME

# Install EPICS
RUN apt-get update && \
    apt-get install -y \
    build-essential \
    libreadline-dev

RUN mkdir $HOME/EPICS
RUN wget -P $HOME/EPICS https://epics-controls.org/download/base/base-7.0.8.1.tar.gz
RUN tar -xvf $HOME/EPICS/base-7.0.8.1.tar.gz
RUN make $HOME/EPICS/base-7.0.8.1.tar.gz

# set dir for app software
RUN mkdir -p /usr/local/app
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
# delete data folder (if it exists in repo - permission issues)
RUN rm -rf /usr/local/app/data
EXPOSE 8080


# Setup an app user so the container doesn't run as the root user
RUN useradd newuser
# give newuser write permissions in data folder
RUN chown newuser /usr/local/app
# switch docker from root to newuser
USER newuser

# EPICS db test
ENTRYPOINT [ "softIoc", "-d", "./test_IOC/test.db" ]
CMD [ "dbl" ]

# # pytest
# ENTRYPOINT [ "python3", "-m" ]
# CMD ["pytest", "./tests/"]
