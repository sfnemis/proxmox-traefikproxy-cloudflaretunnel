# Complete Setup Guide: Traefik + Cloudflare Tunnel on Proxmox LXC

This repository contains configuration files and setup instructions for deploying Traefik Reverse Proxy with Cloudflare Tunnel on Proxmox LXC containers. This setup provides a secure way to expose your services to the internet without opening any ports on your firewall.

### Features
* Traefik Reverse Proxy running in a Proxmox LXC container
* Cloudflare Tunnel for secure connectivity without exposing ports 80/443
* Automatic DNS record creation in Cloudflare for new services
* Example configuration for n8n workflow automation
* Comprehensive security with HTTP headers and Cloudflare's protection

## Getting Started

This guide will walk you through setting up Traefik Reverse Proxy with Cloudflare Tunnel on Proxmox LXC containers. The setup will:

- Run Traefik in one LXC container
- Run Cloudflare Tunnel in another LXC container
- Automatically create DNS records in Cloudflare when you add new services to Traefik
- Not expose ports 80/443 to the internet

### Prerequisites

Proxmox VE server 8+
- Cloudflare account with your domain
- Cloudflare API Token with Zone:DNS:Edit permissions
- Cloudflare Zero Trust account (free tier is sufficient)

### Folder Structure
```plaintext
/
├── traefik/
│   ├── etc/
│   │   ├── traefik/
│   │   │   ├── traefik.yml              # /etc/traefik/traefik.yml
│   │   │   └── dynamic/
│   │   │       ├── fileConfig.yml       # /etc/traefik/dynamic/fileConfig.yml
│   │   │       ├── n8n.yml              # /etc/traefik/dynamic/n8n.yml
│   │   │       ├── homeassistant.yml    # /etc/traefik/dynamic/homeassistant.yml
│   │   │       └── other-services.yml   # /etc/traefik/dynamic/other-services.yml
│   │   └── systemd/
│   │       └── system/
│   │           └── traefik.service      # /etc/systemd/system/traefik.service
│   └── opt/
│       └── scripts/
│           └── traefik-dns.py           # /opt/scripts/traefik-dns.py
└── cloudflared/
    ├── etc/
    │   ├── cloudflared/
    │   │   └── config.yml               # /etc/cloudflared/config.yml
    │   └── systemd/
    │       └── system/
    │           └── cloudflared.service  # /etc/systemd/system/cloudflared.service
```
### Installing

You can use for lxc templates https://community-scripts.github.io/ProxmoxVE/

#### Set Up Traefik LXC : https://community-scripts.github.io/ProxmoxVE/scripts?id=traefik
~~~sh
bash -c "$(wget -qLO - https://github.com/community-scripts/ProxmoxVE/raw/main/ct/traefik.sh)"
~~~
 
When setup is finished open the console or ssh to Traefik : 
~~~sh
apt update && apt upgrade -y
apt install -y curl wget gnupg sudo python3 python3-pip nano
pip3 install requests pyyaml
~~~
~~~sh
mkdir -p /etc/traefik/dynamic
touch /etc/traefik/acme.json
chmod 600 /etc/traefik/acme.json
~~~
~~~sh
nano /etc/traefik/traefik.yml
~~~
Paste the Traefik configuration (check Traefik Configuration file).

- Create the dynamic configuration:
~~~sh
nano /etc/traefik/dynamic/fileConfig.yml
~~~
Paste the fileConfig.yml (check Dynamic Configuration file).
Inside the fileConfig.yml do not forget password to change to yours;
~~~sh
# Install apache2-utils if not already installed
apt-get install apache2-utils -y

# Generate the password hash (BCrypt format, which is more secure)
htpasswd -nbB admin yourpassword
~~~
- Create Traefik Service:

~~~sh
# Create systemd service
cat > /etc/systemd/system/traefik.service << EOF
[Unit]
Description=Traefik
Documentation=https://doc.traefik.io/traefik/
After=network-online.target

[Service]
Type=simple
User=root
Group=root
ExecStart=/usr/bin/traefik --configfile=/etc/traefik/traefik.yml
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# Enable and start Traefik
systemctl daemon-reload
systemctl enable traefik
systemctl start traefik
~~~

- Set Up DNS Automation Script
~~~sh
# Create script directory
mkdir -p /opt/scripts

# Create the DNS script
nano /opt/scripts/traefik-dns.py
~~~
Paste the Python script (check Traefik DNS Automation Script).
~~~sh
# Make it executable
chmod +x /opt/scripts/traefik-dns.py

# Replace placeholder values  
nano /opt/scripts/traefik-dns.py
~~~
Replace the:

* CF_API_TOKEN with **your Cloudflare API token**
* ZONE_ID with **your Cloudflare zone ID**
* BASE_DOMAIN with **your domain**

**Add a cron job:**
~~~sh
# Add to crontab
(crontab -l 2>/dev/null; echo "*/2 * * * * /usr/bin/python3 /opt/scripts/traefik-dns.py >> /var/log/traefik-dns.log 2>&1") | crontab -
~~~
***
#### Set Up Cloudflared LXC : https://community-scripts.github.io/ProxmoxVE/scripts?id=cloudflared
~~~sh
bash -c "$(wget -qLO - https://github.com/community-scripts/ProxmoxVE/raw/main/ct/cloudflared.sh)"
~~~
When setup is finished open the console or ssh to Cloudflared LXC :

####  Configure Cloudflare Tunnel:

~~~sh
# Create directories
mkdir -p /etc/cloudflared
mkdir -p /var/log/cloudflared

# Authenticate with Cloudflare
cloudflared tunnel login

# Create a tunnel
cloudflared tunnel create traefik-tunnel

# Get the tunnel ID
TUNNEL_ID=$(cloudflared tunnel list | grep traefik-tunnel | awk '{print $1}')
echo "Tunnel ID: $TUNNEL_ID"

# Create configuration file
nano /etc/cloudflared/config.yml
~~~
Paste the Cloudflare configuration (check Cloudflare Tunnel Configuration) and replace:

- TUNNEL_ID with **your tunnel ID**
- TRAEFIK_IP with the **IP of your Traefik container**
- example.com with **your domain**

#### Create the systemd service:
~~~sh
# Create service file
cat > /etc/systemd/system/cloudflared.service << EOF
[Unit]
Description=Cloudflare Tunnel
After=network-online.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/cloudflared tunnel run
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable cloudflared
systemctl start cloudflared
~~~
#### Create DNS entries for the tunnel:
~~~sh
# Route DNS through the tunnel
cloudflared tunnel route dns $TUNNEL_ID example.com
cloudflared tunnel route dns $TUNNEL_ID "*.example.com"
~~~

#### Copy the credentials file to the expected location:
~~~sh
# Replace TUNNEL_ID with your actual tunnel ID from the find command
cp /root/.cloudflared/TUNNEL_ID.json /etc/cloudflared/credentials.json
~~~

#### Restart the service:
~~~sh
systemctl restart cloudflared
~~~

## Running the tests


### Add a Test Service to Traefik

SSH into the Traefik container:
~~~sh
# Create test service
cat > /etc/traefik/dynamic/test.yml << EOF
http:
  routers:
    test:
      rule: "Host(\`test.example.com\`)"
      service: "test-service"
      middlewares:
        - security-headers
  
  services:
    test-service:
      loadBalancer:
        servers:
          - url: "http://127.0.0.1:8080"
EOF

# Restart Traefik
systemctl restart traefik
~~~
   

### Trigger DNS Creation

~~~sh
# Run DNS script manually
python3 /opt/scripts/traefik-dns.py
~~~

### Verify Everything is Working
1. Check that Traefik is running:
  **systemctl status traefik**
2. Check that Cloudflared is running: **systemctl status cloudflared**
3. Check DNS records in **Cloudflare dashboard**
4. Try accessing your test service: **https://test.example.com**

### Adding Services
*To add a new service to Traefik:*

1. Create a new YAML file in /etc/traefik/dynamic/ directory
~~~sh
http:
  routers:
    myservice:
      rule: "Host(`myservice.example.com`)"
      service: "myservice"
      middlewares:
        - security-headers
  
  services:
    myservice:
      loadBalancer:
        servers:
          - url: "http://internal-service-ip:port"
~~~
2. The DNS automation script will detect the new host and create a DNS record automatically.
***
### Troubleshooting
#### Check Logs 


- **Traefik logs:**
   ```bash
   tail -f /var/log/traefik/traefik.log
   ```

- **Cloudflared logs:**
   ```bash
   journalctl -u cloudflared -f
   ```

- **DNS automation logs:**
   ```bash
   tail -f /var/log/traefik-dns.log
   ```

### Common Issues

- **Cloudflare Tunnel not connecting:**  
  Check that the Tunnel credentials file exists and has proper permissions.

- **DNS records not being created:**  
  Check API token permissions and the DNS automation logs.

- **Services not accessible:**  
  Verify that the Traefik configuration is correct and that the backend service is running.

### Security Considerations

- Secure the Traefik dashboard with strong authentication.
- Regularly update both containers.
- Consider setting up Zero Trust policies in Cloudflare.

# Final Notes

This setup provides:

- A secure reverse proxy with Traefik
- No exposed ports to the internet
- Automatic DNS record creation
- Traffic tunneled through Cloudflare's network

All requests to your services now flow through Cloudflare's network and are protected by their security features.

# BONUS N8N LXC with Traefik Proxy
#### Set Up n8n LXC : https://community-scripts.github.io/ProxmoxVE/scripts?id=n8n
~~~sh
bash -c "$(wget -qLO - https://github.com/community-scripts/ProxmoxVE/raw/main/ct/n8n.sh)"
~~~

When setup is finished open the console or ssh to n8n LXC : 
~~~sh
nano /etc/systemd/system/n8n.service 
~~~
~~~sh
[Unit]
Description=n8n

[Service]
Type=simple
Environment="N8N_SECURE_COOKIE=false"
Environment="N8N_HOST=0.0.0.0"
Environment="N8N_PORT=5678"
Environment="N8N_PROTOCOL=http"
Environment="NODE_ENV=production"
Environment="WEBHOOK_URL=https://n8n.example.com"
Environment="N8N_PATH=/"
Environment="N8N_LISTEN_ADDRESS=0.0.0.0"
Environment="N8N_SKIP_WEBHOOK_DEREGISTRATION_SHUTDOWN=true"
Environment="N8N_DIAGNOSTICS_ENABLED=false"
Environment="N8N_USER_FOLDER=/home/n8n/.n8n"
Environment="GENERIC_TIMEZONE=Europe/Istanbul"
Environment="N8N_RUNNERS_ENABLED=true"
Environment="WEBHOOK_VERIFY_CHECK_INTERVAL=2000"
Environment="WEBHOOK_VERIFY_RETRY_COUNT=6"
Environment="WEBHOOK_TUNNEL_URL=https://n8n.example.com"
ExecStart=n8n start

[Install]
WantedBy=multi-user.target
~~~

Replace **Environment="WEBHOOK_URL=https://n8n.example.com"** with your domain and save it!

~~~sh
systemctl daemon-reload 
systemctl restart n8n
~~~
***
## TRAEFIK REVERSE PROXY N8N LXC YML

Console or ssh to Traefik LXC:

1. Create a new YAML file in /etc/traefik/dynamic/ directory
Paste the Cloudflare configuration (check n8n YAML File) and replace with **your domain and save it!**

2. Trigger DNS Creation
~~~sh
# Run DNS script manually
python3 /opt/scripts/traefik-dns.py
~~~

