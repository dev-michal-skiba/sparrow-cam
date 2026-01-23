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

# Set proper permissions for SSH key
RUN if [ -f /ansible/ssh_key ]; then \
        chmod 600 /ansible/ssh_key && \
        chown ansible:ansible /ansible/ssh_key; \
    fi

# Switch to ansible user
USER ansible
