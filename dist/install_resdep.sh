#!/bin/sh

# Find the only .whl file in the current directory
WHEEL_FILE_NAME=$(ls *.whl)

# Install using pip with your required flags
pip install "$WHEEL_FILE_NAME" --find-links ./ --no-index --no-deps
