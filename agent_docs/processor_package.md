# Overview
- Software: Python package `processor`
- Responsibility:
  - Monitor the HLS playlist for new segments
  - Run bird detection on the first frame of each segment using YOLOv8 nano (COCO class ID 14, birds)
  - Updates bird detection annotations in `/var/www/html/annotations/bird.json`
## Package Layout
- Package location: `app/processor/`
- Entrypoint for `python -m processor`: `app/processor/processor/__main__.py`
## Related Files
- Local web Dockerfile: `local/Dockerfile.processor`
- Local Docker Compose: `local/docker-compose.yml`
    - service name is `processor`
- Infrastructure playbook: `infra/ansible/setup_processor.yml`