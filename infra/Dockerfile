FROM alpine:3.22.1

# Install ansible and openssh
RUN apk add --no-cache \
    ansible \
    openssh-client \
    sshpass \
    acl \
    && rm -rf /var/cache/apk/*

# Create ansible user and directory
RUN adduser -D -s /bin/sh ansible
WORKDIR /ansible

# Copy ansible configuration
COPY ansible/ /ansible/

# Switch to ansible user
USER ansible
