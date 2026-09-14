#!/bin/bash
# Removes drop2share uploads older than the advertised retention window.
# Deployed by the Jenkins pipeline to /mnt/SSS/DockerData/scripts/.
set -u

directory="/mnt/SSS/DockerData/drop2share.de"
retention_minutes="${RETENTION_MINUTES:-1440}"   # 24 h, matching the website copy

[ -d "$directory" ] || { echo "missing directory: $directory" >&2; exit 1; }

# -mmin, not -mtime: -mtime +1 keeps files for up to 48 h.
find "$directory" -type f -mmin "+${retention_minutes}" -delete
