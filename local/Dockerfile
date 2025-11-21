FROM ubuntu:25.04

# Install nginx with RTMP module, ffmpeg, supervisord, and python3 for jinja2 templating
RUN apt-get update && \
    apt-get install -y \
        nginx \
        libnginx-mod-rtmp \
        ffmpeg \
        supervisor \
        curl \
        python3 \
        python3-jinja2 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create nginx-rtmp config directory
RUN mkdir -p /etc/nginx-rtmp

# Copy nginx configuration templates
COPY app/nginx-web.conf /tmp/nginx-web.conf.template
COPY app/nginx-rtmp.conf /tmp/nginx-rtmp.conf.template
COPY app/index.html /var/www/html/index.html

# Copy supervisord configuration
COPY local/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy template rendering script
COPY local/render-template.py /usr/local/bin/render-template.py
RUN chmod +x /usr/local/bin/render-template.py

# Default environment variables (can be overridden)
ENV WEB_PORT=8080
ENV RTMP_PORT=8081

# Render configuration files from templates
RUN python3 /usr/local/bin/render-template.py /tmp/nginx-web.conf.template /etc/nginx/nginx.conf && \
    python3 /usr/local/bin/render-template.py /tmp/nginx-rtmp.conf.template /etc/nginx-rtmp/nginx.conf && \
    rm /tmp/nginx-web.conf.template /tmp/nginx-rtmp.conf.template

# Expose ports: 8080 for web, 8081 for RTMP
EXPOSE 8080 8081

# Start supervisord to manage both nginx processes
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
