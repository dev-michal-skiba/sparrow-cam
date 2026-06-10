#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/stream.conf"

load_config() {
    source "$CONFIG_FILE"
    if [ "$ROI_RIGHT" -gt "$ROI_LEFT" ] && [ "$ROI_BOTTOM" -gt "$ROI_TOP" ] && \
       [ "$ROI_LEFT" -ge 0 ] && [ "$ROI_RIGHT" -le 100 ] && \
       [ "$ROI_TOP" -ge 0 ] && [ "$ROI_BOTTOM" -le 100 ]; then
        CROP_PARAM="iw*(${ROI_RIGHT}-${ROI_LEFT})/100:ih*(${ROI_BOTTOM}-${ROI_TOP})/100:iw*${ROI_LEFT}/100:ih*${ROI_TOP}/100"
        VF_FILTER="fps=8,crop=${CROP_PARAM}"
        echo "Config loaded: ROI left=${ROI_LEFT} top=${ROI_TOP} right=${ROI_RIGHT} bottom=${ROI_BOTTOM}, crop=${CROP_PARAM}"
    else
        VF_FILTER="fps=8"
        echo "Config loaded: invalid ROI (left=${ROI_LEFT} top=${ROI_TOP} right=${ROI_RIGHT} bottom=${ROI_BOTTOM}), skipping crop"
    fi
}

attempt=0

while true; do
    load_config
    config_mtime=$(stat -c %Y "$CONFIG_FILE")

    ffmpeg \
        -f v4l2 \
        -input_format mjpeg \
        -video_size 1920x1080 \
        -i /dev/video0 \
        -vf "${VF_FILTER}" \
        -c:v libx264 \
        -preset ultrafast \
        -tune zerolatency \
        -g 8 \
        -keyint_min 8 \
        -sc_threshold 0 \
        -pix_fmt yuv420p \
        -an \
        -f hls \
        -hls_time 1 \
        -hls_list_size 60 \
        -hls_flags delete_segments+append_list \
        -hls_segment_filename "/var/www/html/hls/sparrow_cam-%d.ts" /var/www/html/hls/sparrow_cam.m3u8 &

    ffmpeg_pid=$!
    config_changed=false

    while kill -0 $ffmpeg_pid 2>/dev/null; do
        sleep 1
        new_mtime=$(stat -c %Y "$CONFIG_FILE")
        if [ "$new_mtime" != "$config_mtime" ]; then
            echo "Config file changed, restarting ffmpeg with new crop settings"
            kill $ffmpeg_pid
            config_changed=true
            break
        fi
    done

    wait $ffmpeg_pid
    exit_code=$?

    if [ "$config_changed" = true ]; then
        attempt=0
        continue
    fi

    if [ $attempt -eq 0 ]; then
        delay=2
    elif [ $attempt -eq 1 ]; then
        delay=5
    else
        delay=10
    fi

    echo "ffmpeg exited with code $exit_code (attempt $((attempt + 1))). Restarting in ${delay}s"
    sleep $delay
    attempt=$((attempt + 1))
done
