#!/bin/bash

attempt=0

while true; do
    ffmpeg \
        -f v4l2 \
        -input_format mjpeg \
        -video_size 1920x1080 \
        -i /dev/video0 \
        -vf "fps=8,crop=iw/2:ih/2:(iw-iw/2)/2:(ih-ih/2)/2" \
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
        -hls_segment_filename "/var/www/html/hls/sparrow_cam-%d.ts" /var/www/html/hls/sparrow_cam.m3u8

    exit_code=$?

    if [ $attempt -eq 0 ]; then
        delay=10
    elif [ $attempt -eq 1 ]; then
        delay=30
    else
        delay=60
    fi

    echo "ffmpeg exited with code $exit_code (attempt $((attempt + 1))). Restarting in ${delay}s"
    sleep $delay
    attempt=$((attempt + 1))
done
