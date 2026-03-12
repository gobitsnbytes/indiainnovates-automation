# Stable Deployment with Domain Setup

## Overview
This configuration runs a single Streamlit instance behind Nginx.

> Important: `st.file_uploader` uses process-local Streamlit session state. Running multiple
> Streamlit replicas behind Nginx can cause intermittent `400 Invalid session_id` upload failures.
> Use one backend instance unless you introduce a deployment architecture that guarantees a
> single Streamlit process per browser session end-to-end.

## Prerequisites
- VPS with 4 vCPUs
- Domain name pointed to your VPS IP
- Ubuntu/Debian Linux

## Step 1: Install Nginx and Certbot

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

## Step 1.5: Install evaluator system dependencies

These packages are needed for:
- OCR fallback on image-based PDFs
- PPT/PPTX browser preview conversion
- GPT-4.1 vision mode for PDF/PPT/PPTX slide rendering

```bash
sudo apt update
sudo apt install -y python3-venv poppler-utils tesseract-ocr libreoffice libreoffice-impress
```

## Step 2: Set Up Application

```bash
# Clone into the directory you actually want to run from
git clone <your-repo-url> /root/indiainnovates-automation
cd /root/indiainnovates-automation
git pull
REPO_DIR="$(pwd -P)"

# Activate virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate  # or: source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Optional environment settings:

```bash
# Increase/decrease the in-app processing limit (default: 50MB)
export II2026_MAX_UPLOAD_MB=50
```

If your repo is not in `/root/indiainnovates-automation`, use that real path everywhere below.
The included scripts now auto-detect the current repo directory instead of assuming `/opt/...`.

## Step 3: Install Systemd Service

```bash
# Patch the unit with the real repo path, then install it
sed "s|__APP_DIR__|$REPO_DIR|g" indiainnovates-automation.service | \
    sudo tee /etc/systemd/system/indiainnovates-automation@.service > /dev/null

# Enable and start the app instance
sudo systemctl daemon-reload
sudo systemctl enable indiainnovates-automation@1

sudo systemctl start indiainnovates-automation@1

# Check status
sudo systemctl status indiainnovates-automation@1

# Verify installed service paths
sudo systemctl cat indiainnovates-automation@1
```

Note: `setup-domain.sh` patches the service with the current repo path automatically.

## Step 4: Configure Nginx

```bash
# Edit nginx-site.conf and replace 'your-domain.com' with your actual domain
nano nginx-site.conf

# Copy to Nginx sites-available
sudo cp nginx-site.conf /etc/nginx/sites-available/indiainnovates

# Enable site
sudo ln -s /etc/nginx/sites-available/indiainnovates /etc/nginx/sites-enabled/

# Remove default site if present
sudo rm /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Restart Nginx (without SSL first)
sudo systemctl restart nginx
```

## Step 5: Set Up SSL with Let's Encrypt

```bash
sudo certbot --nginx -d evaluation.gobitsnbytes.org --email gobitsnbytes@gmail.com --agree-tos --no-eff-email

# Test automatic renewal
sudo certbot renew --dry-run
```

## Step 6: Update Firewall

```bash
# Allow HTTP and HTTPS
sudo ufw allow 'Nginx Full'

# Remove old port 8501 rule if present
sudo ufw delete allow 8501

# Check firewall status
sudo ufw status
```

## Step 7: DNS Configuration

Point your subdomain to your VPS:
1. Go to your DNS provider for gobitsnbytes.org
2. Add/Update DNS record:
   - **A Record**: `evaluation` → Your VPS IP address
3. Wait for DNS propagation (can take up to 24 hours, usually 5-30 minutes)

## Management Commands

### View logs
```bash
sudo journalctl -u indiainnovates-automation@1 -f
```

### Restart services
```bash
sudo systemctl restart indiainnovates-automation@1
```

### Check Nginx status
```bash
sudo systemctl status nginx
sudo nginx -t  # Test configuration
```

### Monitor CPU usage
```bash
# Watch CPU usage by process
htop

# Check Streamlit processes
ps aux | grep streamlit
```

## Performance Verification

### Test load balancing:
```bash
# Make multiple requests and check which backend handles them
for i in {1..20}; do
    curl -s https://evaluation.gobitsnbytes.org -o /dev/null -w "Backend: %{remote_ip}\n"
    sleep 0.1
done
```

### Monitor Nginx connections:
```bash
sudo tail -f /var/log/nginx/access.log
```

## Troubleshooting

### If Streamlit instances won't start:
```bash
# Check logs
sudo journalctl -u indiainnovates-automation@1 -n 50

# Verify ports are available
sudo netstat -tlnp | grep 850

# Test manually
cd "$REPO_DIR"
source "$REPO_DIR"/.venv/bin/activate
streamlit run "$REPO_DIR"/ii2026_evaluator.py --server.port=8501
```

### If OCR or PPT/PPTX browser preview fails:
```bash
# Verify required binaries are installed
which pdftoppm
which tesseract
which soffice

# Reinstall if needed
sudo apt install -y python3-venv poppler-utils tesseract-ocr libreoffice libreoffice-impress

# Reinstall Python packages if needed
source "$REPO_DIR"/.venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### If Nginx returns 502 Bad Gateway:
```bash
# Check if Streamlit is running
sudo systemctl status indiainnovates-automation@1

# Check Nginx error log
sudo tail -f /var/log/nginx/error.log
```

### If SSL certificate fails:
```bash
# Ensure ports 80 and 443 are open
sudo ufw status

# Check Nginx is running
sudo systemctl status nginx

# Retry certbot
sudo certbot --nginx -d evaluation.gobitsnbytes.org
```

## Performance Notes

- **Upload stability**: Single-backend routing avoids `Invalid session_id` failures during uploads.
- **Session correctness**: Streamlit session state stays inside one Python process.
- **Scale path**: If you need more throughput, prefer a larger single instance or redesign uploads/storage around a different frontend/backend split.

## Monitoring

Consider adding monitoring tools:
```bash
# Install htop for real-time monitoring
sudo apt install htop

# Check current load
uptime
```

Access your app at: **https://evaluation.gobitsnbytes.org**
