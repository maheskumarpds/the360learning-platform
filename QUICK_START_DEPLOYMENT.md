# Quick Start Deployment Guide

## Prerequisites
- Ubuntu/Debian server with root access
- Domain name pointing to your server
- GitHub account with repository access

## 1. Server Setup (5 minutes)
```bash
# Connect to your server
ssh username@your-server-ip

# Run the automated setup script
curl -sSL https://raw.githubusercontent.com/maheskumarpds/the360learning-platform/main/setup.sh | bash
```

## 2. Configure Environment Variables
Edit the environment files with your actual API keys:
```bash
# Production environment
nano /var/www/the360learning-production/.env

# Development environment  
nano /var/www/the360learning-development/.env
```

Required keys:
- `OPENAI_API_KEY` - For AI tutoring features
- `SENDGRID_API_KEY` - For email notifications
- `ZOOM_*` keys - For video conferencing
- `STRIPE_SECRET_KEY` - For payments (optional)

## 3. GitHub Secrets Setup
Add these secrets in GitHub repository → Settings → Secrets:

| Secret | Value |
|--------|--------|
| `PROD_HOST` | Your server IP |
| `PROD_USERNAME` | SSH username |
| `PROD_SSH_KEY` | SSH private key |
| `DEV_HOST` | Your server IP |
| `DEV_USERNAME` | SSH username |
| `DEV_SSH_KEY` | SSH private key |

## 4. Update Domain Configuration
Replace `your-domain.com` in nginx configs:
```bash
sudo sed -i 's/your-domain.com/yourdomain.com/g' /etc/nginx/sites-available/the360learning-*
sudo systemctl reload nginx
```

## 5. SSL Setup
```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
sudo certbot --nginx -d dev.yourdomain.com
```

## Testing Deployment
- Push to `development` branch → deploys to dev.yourdomain.com
- Push to `main` branch → deploys to yourdomain.com

## Troubleshooting
Check service status:
```bash
sudo systemctl status the360learning-prod
sudo systemctl status the360learning-dev
sudo journalctl -u the360learning-prod -f
```

Your platform will be live at:
- **Production**: https://yourdomain.com
- **Development**: https://dev.yourdomain.com