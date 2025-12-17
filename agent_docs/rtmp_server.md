# Overview
- Software: nginx with RTMP plugin: `nginx-rtmp`
- Responsibility:
    - Receive RTMP video streams on `/live/sparrow_cam`
    - Generate HLS segments and playlists to `/var/www/html/hls/`
## Related Files
- RTMP nginx config template: `app/nginx-rtmp.conf`
- RTMP systemd service file: `app/nginx-rtmp.service`
    - Used only on production
- Local RTMP Dockerfile: `local/Dockerfile.rtmp`
- Local Docker Compose: `local/docker-compose.yml`
    - Service name is `rtmp`
- Deployment playbook: `deploy/ansible/rtmp.yml`