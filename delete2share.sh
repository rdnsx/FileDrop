#!/bin/bash

# Define the directory path
directory="/mnt/SSS/DockerData/drop2share.de"

# Find files older than 24 hours in the specified directory
find "$directory" -type f -mtime +1 -exec rm {} \;
