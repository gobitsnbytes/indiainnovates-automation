# Deploying on an Ubuntu VPS

## Prerequisites

- Ubuntu 22.04+ VPS with at least 1 GB RAM
- Root or sudo access
- An OpenAI API key

## 1. Initial server setup

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git ufw
```

## 2. Create a non-root user (if running as root)

```bash
adduser evaluator
usermod -aG sudo evaluator
su - evaluator
```

## 3. Clone / copy the project

```bash
cd ~
# Option A: git clone
git clone <your-repo-url> indiainnovates-automation

# Option B: scp from local machine
# scp -r ./indiainnovates-automation evaluator@<vps-ip>:~/indiainnovates-automation
```

## 4. Set up Python environment

```bash
cd ~/indiainnovates-automation
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install streamlit python-pptx openai tiktoken pandas
```

## 5. Configure the API key

```bash
echo 'OPENAI_API_KEY="sk-..."' > ~/.env_evaluator
chmod 600 ~/.env_evaluator
```

## 6. Firewall

Allow only SSH and the Streamlit port. Restrict port 8501 to trusted IPs:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow from <your-ip> to any port 8501
sudo ufw enable
```

> **Do not** run `ufw allow 8501` without an IP restriction — that exposes the app to the entire internet.

## 7. Run with systemd (recommended)

Create a service file so the app starts on boot and restarts on failure:

```bash
sudo tee /etc/systemd/system/evaluator.service > /dev/null <<'EOF'
[Unit]
Description=India Innovates 2026 Evaluator
After=network.target

[Service]
User=evaluator
WorkingDirectory=/home/evaluator/indiainnovates-automation
EnvironmentFile=/home/evaluator/.env_evaluator
ExecStart=/home/evaluator/indiainnovates-automation/venv/bin/streamlit run ii2026_evaluator.py --server.port 8501 --server.address 0.0.0.0
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable evaluator
sudo systemctl start evaluator
```

Check status:

```bash
sudo systemctl status evaluator
sudo journalctl -u evaluator -f
```

At this point the app is live at `http://<vps-ip>:8501` — no reverse proxy needed.

If you want HTTPS or to hide Streamlit behind a proper web server, continue with sections 8 and 9 below. Otherwise skip to **section 10**.

---

## 8. (Optional) Reverse proxy with Nginx

Serving through Nginx lets you add HTTPS and avoid exposing Streamlit directly.

If you use Nginx, first change the systemd bind address to localhost so Streamlit is not directly reachable:

```bash
# Edit the service file
sudo sed -i 's/--server.address 0.0.0.0/--server.address 127.0.0.1/' /etc/systemd/system/evaluator.service
sudo systemctl daemon-reload
sudo systemctl restart evaluator
```

```bash
sudo apt install -y nginx
```

Create the site config:

```bash
sudo tee /etc/nginx/sites-available/evaluator > /dev/null <<'EOF'
server {
    listen 80;
    server_name <your-domain-or-ip>;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
EOF
```

Enable and start:

```bash
sudo ln -s /etc/nginx/sites-available/evaluator /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

Update firewall to allow HTTP/HTTPS instead of 8501:

```bash
sudo ufw allow 'Nginx Full'
sudo ufw delete allow from <your-ip> to any port 8501
```

## 9. HTTPS with Let's Encrypt (optional but recommended)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d <your-domain>
```

Certbot auto-renews via a systemd timer. Verify with:

```bash
sudo certbot renew --dry-run
```

## 10. Updating the app

```bash
cd ~/indiainnovates-automation
git pull
sudo systemctl restart evaluator
```

## Quick smoke test

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8501
# Should print 200
```
