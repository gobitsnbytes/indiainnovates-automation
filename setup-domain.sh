#!/usr/bin/env bash
# Quick setup script for multi-core deployment with domain

set -Eeuo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"

if [[ -z "$DOMAIN" ]]; then
  echo "Usage: $0 <your-domain.com> <your-email@example.com>"
  echo "Example: $0 evaluation.gobitsnbytes.org gobitsnbytes@gmail.com"
  exit 1
fi

if [[ -z "$EMAIL" ]]; then
  echo "Error: Email address is required for SSL certificate"
  exit 1
fi

echo "==> Setting up multi-core deployment for $DOMAIN"

# Install required packages
echo "==> Installing Nginx and Certbot"
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx

# Copy and configure systemd service
echo "==> Installing systemd service"
sudo cp indiainnovates-automation.service /etc/systemd/system/indiainnovates-automation@.service

# Enable and start all 4 instances
echo "==> Starting 4 Streamlit instances"
sudo systemctl daemon-reload
for i in {1..4}; do
  sudo systemctl enable indiainnovates-automation@$i
  sudo systemctl start indiainnovates-automation@$i
done

# Wait a moment for services to start
sleep 3

# Check service status
echo "==> Checking service status"
sudo systemctl status indiainnovates-automation@{1,2,3,4} --no-pager || true

# Update Nginx configuration with actual domain
echo "==> Configuring Nginx"
sed "s/your-domain.com/$DOMAIN/g" nginx-site.conf > /tmp/nginx-site.conf
sudo cp /tmp/nginx-site.conf /etc/nginx/sites-available/indiainnovates
sudo ln -sf /etc/nginx/sites-available/indiainnovates /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Edit nginx config to temporarily comment out SSL lines for initial setup
sudo sed -i 's|ssl_certificate|# ssl_certificate|g' /etc/nginx/sites-available/indiainnovates
sudo sed -i 's|listen 443|listen 80|g' /etc/nginx/sites-available/indiainnovates

# Test and reload Nginx
echo "==> Testing Nginx configuration"
sudo nginx -t
sudo systemctl restart nginx

# Set up SSL with Let's Encrypt
echo "==> Setting up SSL certificate"
sudo certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --email "$EMAIL" --agree-tos --no-eff-email --redirect || {
  echo "Warning: SSL setup failed. Please run manually:"
  echo "  sudo certbot --nginx -d $DOMAIN --email $EMAIL --agree-tos --no-eff-email"
}

# Update firewall
echo "==> Configuring firewall"
sudo ufw allow 'Nginx Full' || echo "Note: ufw not active, skipping firewall configuration"

echo ""
echo "==> Setup complete!"
echo ""
echo "Your app should now be available at:"
echo "  https://$DOMAIN"
echo ""
echo "Make sure your DNS A records point to this server's IP address:"
echo "  @ (root) -> $(curl -s ifconfig.me)"
echo "  www -> $(curl -s ifconfig.me)"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status indiainnovates-automation@{1,2,3,4}  # Check status"
echo "  sudo journalctl -u 'indiainnovates-automation@*' -f       # View logs"
echo "  sudo systemctl restart indiainnovates-automation@{1,2,3,4} # Restart all"
echo "  htop                                                       # Monitor CPU usage"
