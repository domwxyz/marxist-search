#!/bin/bash
#
# Download Alibaba-NLP/gte-base-en-v1.5 model locally
# This bypasses the trust_remote_code interactive prompt issue
#

set -e

# Configuration
MODEL_NAME="Alibaba-NLP/gte-base-en-v1.5"
LOCAL_MODEL_DIR="/var/lib/marxist-search/models/gte-base-en-v1.5"
APP_USER="marxist"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}Downloading Model Locally${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""
echo "Model: $MODEL_NAME"
echo "Destination: $LOCAL_MODEL_DIR"
echo ""

# Create model directory
echo -e "${BLUE}Creating model directory...${NC}"
mkdir -p "$LOCAL_MODEL_DIR"
chown -R "$APP_USER:$APP_USER" "$(dirname $LOCAL_MODEL_DIR)"

# Download model using Python
echo -e "${BLUE}Downloading model files...${NC}"
echo "This may take a few minutes (model is ~200MB)"
echo ""

cd /opt/marxist-search/backend

sudo -u "$APP_USER" ../venv/bin/python3 << 'PYTHON_SCRIPT'
from huggingface_hub import snapshot_download
import os

model_name = "Alibaba-NLP/gte-base-en-v1.5"
local_dir = "/var/lib/marxist-search/models/gte-base-en-v1.5"

print(f"Downloading {model_name}...")
print(f"To: {local_dir}")
print("")

# Download all model files
# Note: trust_remote_code is not needed for downloading, only for loading
snapshot_download(
    repo_id=model_name,
    local_dir=local_dir,
    local_dir_use_symlinks=False
)

print("")
print("✓ Model downloaded successfully!")
print(f"✓ Model location: {local_dir}")
PYTHON_SCRIPT

# Set ownership
chown -R "$APP_USER:$APP_USER" "$LOCAL_MODEL_DIR"

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Model Download Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Model location: $LOCAL_MODEL_DIR"
echo ""
echo "Next steps:"
echo "  1. The model config has been updated to use the local path"
echo "  2. Run the rebuild script: sudo ./rebuild_all.sh"
echo ""
echo "Model files:"
ls -lh "$LOCAL_MODEL_DIR"
echo ""
