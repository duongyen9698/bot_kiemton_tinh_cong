#!/bin/bash
# File: /root/tinh_cong/run_kiemton.sh
# Purpose: Run kiemton.py using uv and log output

# Set working directory
cd /root/tinh_cong || exit 1

# Add user's local bin to PATH (so uv can be found)
export PATH="/root/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# Run the command
/root/.local/bin/uv run kiemton.py >> /root/tinh_cong/kiemton.log 2>&1
