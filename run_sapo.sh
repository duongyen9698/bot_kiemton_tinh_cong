#!/bin/bash
# File: /root/tinh_cong/run_sapo.sh
# Purpose: Chạy sapo_cron.py (đối soát + gửi Telegram) qua uv, ghi log
# Lịch cron: chạy trước run_kiemton.sh 2 phút (vd. 08:27 vs 08:29, 14:57 vs 14:59).

cd /root/tinh_cong || exit 1

export PATH="/root/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

/root/.local/bin/uv run sapo_cron.py >> /root/tinh_cong/sapo_cron.log 2>&1
