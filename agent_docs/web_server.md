# Overview
- Software: nginx HTTP server: `nginx`
- Responsibility:
  - Serve SparrowCam web interface
  - Serve HLS playlist and segments from `/var/www/html/hls/`
  - Serve bird detection annotations from `/var/www/html/annotations/bird.json`
## Related Files
- Web nginx config template: `app/nginx-web.conf`
- Web interface HTML: `app/index.html`
- Local web Dockerfile: `local/Dockerfile.web`
- Local Docker Compose: `local/docker-compose.yml`
    - service name is `web`
- Infrastructure playbook: `infra/ansible/setup_web.yml`