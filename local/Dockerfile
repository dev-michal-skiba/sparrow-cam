FROM ubuntu:25.04

ARG DEBIAN_FRONTEND=noninteractive

# Install only what is required to serve HTTP + RTMP and run supervisord
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        nginx \
        libnginx-mod-rtmp \
        supervisor \
        curl \
        netcat-openbsd \
        gettext-base && \
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

# Default build-time ports (overridable through build args)
ARG WEB_PORT=8080
ARG RTMP_PORT=8081
ENV WEB_PORT=${WEB_PORT}
ENV RTMP_PORT=${RTMP_PORT}

# Render configuration files from templates
RUN envsubst '${WEB_PORT}' < /tmp/nginx-web.conf.template > /etc/nginx/nginx.conf && \
    envsubst '${RTMP_PORT}' < /tmp/nginx-rtmp.conf.template > /etc/nginx-rtmp/nginx.conf && \
    rm /tmp/nginx-web.conf.template /tmp/nginx-rtmp.conf.template

# Expose ports: 8080 for web, 8081 for RTMP
EXPOSE 8080 8081

# Start supervisord to manage both nginx processes
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
