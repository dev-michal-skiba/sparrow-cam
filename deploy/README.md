# Deployment Guide

Automated deployment to Raspberry Pi or similar devices using Dockerized Ansible.

## Prerequisites

### Target Server Requirements
- **Device**: Raspberry Pi 4/5 or similar ARM/x64 device
- **OS**: Ubuntu Server 25.04 64-bit (or compatible Linux distribution)
- **Network**: Must be on the same local network as your development machine
- **SSH**: SSH server installed and running on port 22
- **User**: A user account with sudo privileges

### Development Machine Requirements
- Docker and Docker Compose installed
- SSH key pair for authentication
- Network access to target server

## Initial Setup

### 1. Configure SSH Access

Generate an SSH key pair if you don't have one:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/sparrowcam_deploy
```

Copy your public key to the target server:
```bash
ssh-copy-id -i ~/.ssh/sparrowcam_deploy.pub <username>@<target-ip>
```

Copy your private key to the deploy directory:
```bash
cp ~/.ssh/sparrowcam_deploy ansible/ssh_key
chmod 600 ansible/ssh_key
```

### 2. Configure Ansible Variables

Copy the example variables file:
```bash
cp ansible/group_vars/all.yml.example ansible/group_vars/all.yml
```

Edit `ansible/group_vars/all.yml` with your target server details:
```yaml
ansible_target_host: "192.168.1.100"  # Your Raspberry Pi IP address
ansible_target_user: "pi"              # Your SSH username
```

### 3. Build the Deployment Container

Build the Docker image containing Ansible and required tools:
```bash
make -C deploy build
```

This creates a `sparrow_cam_deploy` Docker image with:
- Alpine Linux 3.22.1
- Ansible
- OpenSSH client
- SSH utilities

## Available Commands

Run these commands from the project root

### Help
```bash
make -C deploy help
# or simply
make -C deploy
```
Shows all available deployment commands.

### Build Container
```bash
make -C deploy build
```
Builds the deployment Docker container with Ansible installed.

### Test Connectivity
```bash
make -C deploy ping
```
Tests SSH connectivity to your target server using Ansible's ping module. This verifies:
- SSH key authentication works
- Target server is reachable
- Ansible can connect successfully

## Testing Your Setup

After completing the initial setup, verify connectivity:

```bash
make -C deploy ping
```

Expected output:
```
server | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

If you see errors:
- Verify target server IP address is correct in `ansible/group_vars/all.yml`
- Check that target server is accessible: `ping <target-ip>`
- Test manual SSH connection: `ssh -i ansible/ssh_key <user>@<target-ip>`
- Verify port 22 is open on target server: `nc -zv <target-ip> 22`

## File Structure

```
deploy/
├── Makefile                          # Deployment commands
├── Dockerfile                        # Ansible container definition
├── docker-compose.yml                # Container orchestration
├── README.md                         # This file
└── ansible/
    ├── inventory.yml                 # Ansible inventory (uses variables)
    ├── ssh_key                       # SSH private key (git-ignored)
    └── group_vars/
        ├── all.yml                   # Your actual variables (git-ignored)
        └── all.yml.example           # Template for variables (tracked in git)
```
