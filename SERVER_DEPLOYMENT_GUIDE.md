# Server Deployment Guide with CI/CD

This guide sets up automatic deployment to your server with separate development and production branches.

## Server Setup

### 1. Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3 python3-pip python3-venv nginx postgresql postgresql-contrib git

# Create application directories
sudo mkdir -p /var/www/the360learning-production
sudo mkdir -p /var/www/the360learning-development

# Set ownership
sudo chown -R $USER:$USER /var/www/the360learning-production
sudo chown -R $USER:$USER /var/www/the360learning-development
```

### 2. Clone Repository

```bash
# Production setup
cd /var/www/the360learning-production
git clone https://github.com/maheskumarpds/the360learning-platform.git .
git checkout main

# Development setup
cd /var/www/the360learning-development
git clone https://github.com/maheskumarpds/the360learning-platform.git .
git checkout -b development
git push -u origin development
```

### 3. Python Environment Setup

```bash
# Production environment
cd /var/www/the360learning-production
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Development environment
cd /var/www/the360learning-development
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Environment Configuration

Create production environment file:
```bash
# /var/www/the360learning-production/.env
DATABASE_URL=postgresql://prod_user:prod_password@localhost/the360learning_prod
OPENAI_API_KEY=your_openai_api_key
SENDGRID_API_KEY=your_sendgrid_api_key
ZOOM_API_KEY=your_zoom_api_key
ZOOM_API_SECRET=your_zoom_api_secret
ZOOM_CLIENT_ID=your_zoom_client_id
ZOOM_CLIENT_SECRET=your_zoom_client_secret
ZOOM_ACCOUNT_ID=your_zoom_account_id
STRIPE_SECRET_KEY=your_stripe_secret_key
SECRET_KEY=your_production_secret_key
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
```

Create development environment file:
```bash
# /var/www/the360learning-development/.env
DATABASE_URL=postgresql://dev_user:dev_password@localhost/the360learning_dev
OPENAI_API_KEY=your_openai_api_key
SENDGRID_API_KEY=your_sendgrid_api_key
ZOOM_API_KEY=your_zoom_api_key
ZOOM_API_SECRET=your_zoom_api_secret
ZOOM_CLIENT_ID=your_zoom_client_id
ZOOM_CLIENT_SECRET=your_zoom_client_secret
ZOOM_ACCOUNT_ID=your_zoom_account_id
STRIPE_SECRET_KEY=your_stripe_test_key
SECRET_KEY=your_development_secret_key
DEBUG=True
ALLOWED_HOSTS=dev.your-domain.com,localhost
```

### 5. Database Setup

```bash
# Create PostgreSQL databases
sudo -u postgres createdb the360learning_prod
sudo -u postgres createdb the360learning_dev
sudo -u postgres createuser prod_user
sudo -u postgres createuser dev_user

# Set passwords and permissions
sudo -u postgres psql -c "ALTER USER prod_user PASSWORD 'prod_password';"
sudo -u postgres psql -c "ALTER USER dev_user PASSWORD 'dev_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE the360learning_prod TO prod_user;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE the360learning_dev TO dev_user;"
```

### 6. Django Setup

```bash
# Production
cd /var/www/the360learning-production
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser

# Development
cd /var/www/the360learning-development
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

## Systemd Service Configuration

### Production Service
Create `/etc/systemd/system/the360learning-prod.service`:

```ini
[Unit]
Description=the360learning Production
After=network.target

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=/var/www/the360learning-production
Environment=PATH=/var/www/the360learning-production/venv/bin
ExecStart=/var/www/the360learning-production/venv/bin/gunicorn --workers 3 --bind unix:/var/www/the360learning-production/the360learning.sock learning_is_easy.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Development Service
Create `/etc/systemd/system/the360learning-dev.service`:

```ini
[Unit]
Description=the360learning Development
After=network.target

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=/var/www/the360learning-development
Environment=PATH=/var/www/the360learning-development/venv/bin
ExecStart=/var/www/the360learning-development/venv/bin/gunicorn --workers 2 --bind unix:/var/www/the360learning-development/the360learning.sock learning_is_easy.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Enable Services
```bash
sudo systemctl daemon-reload
sudo systemctl enable the360learning-prod
sudo systemctl enable the360learning-dev
sudo systemctl start the360learning-prod
sudo systemctl start the360learning-dev
```

## Nginx Configuration

### Production Site
Create `/etc/nginx/sites-available/the360learning-prod`:

```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /var/www/the360learning-production;
    }
    
    location /media/ {
        root /var/www/the360learning-production;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/the360learning-production/the360learning.sock;
    }
}
```

### Development Site
Create `/etc/nginx/sites-available/the360learning-dev`:

```nginx
server {
    listen 80;
    server_name dev.your-domain.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /var/www/the360learning-development;
    }
    
    location /media/ {
        root /var/www/the360learning-development;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/the360learning-development/the360learning.sock;
    }
}
```

### Enable Sites
```bash
sudo ln -s /etc/nginx/sites-available/the360learning-prod /etc/nginx/sites-enabled
sudo ln -s /etc/nginx/sites-available/the360learning-dev /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

## GitHub Actions Setup

### Repository Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add these secrets:

**Production Secrets:**
- `PROD_HOST`: Your server IP address
- `PROD_USERNAME`: SSH username
- `PROD_SSH_KEY`: Private SSH key content
- `PROD_PORT`: SSH port (usually 22)

**Development Secrets:**
- `DEV_HOST`: Your development server IP (can be same server)
- `DEV_USERNAME`: SSH username
- `DEV_SSH_KEY`: Private SSH key content
- `DEV_PORT`: SSH port (usually 22)

### GitHub Workflow Files

Copy the deployment files to the correct GitHub Actions directory:

```bash
mkdir -p .github/workflows
cp deploy-production.yml .github/workflows/
cp deploy-development.yml .github/workflows/
```

## Branch Strategy

### Main Branch (Production)
- Always stable, production-ready code
- Direct pushes trigger automatic deployment to production
- Protected branch with pull request requirements

### Development Branch
- Active development and testing
- Pushes trigger automatic deployment to development server
- Merge to main when features are complete

### Workflow
1. Create feature branches from `development`
2. Work on features in feature branches
3. Create pull request to merge feature → `development`
4. Test on development server
5. Create pull request to merge `development` → `main`
6. Deploy automatically to production

## SSL Setup (Optional)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificates
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
sudo certbot --nginx -d dev.your-domain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

## Monitoring Setup

### Log Management
```bash
# View application logs
sudo journalctl -u the360learning-prod -f
sudo journalctl -u the360learning-dev -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Health Checks
Create `/var/www/health-check.sh`:

```bash
#!/bin/bash
# Check if services are running
systemctl is-active --quiet the360learning-prod && echo "Production: OK" || echo "Production: FAILED"
systemctl is-active --quiet the360learning-dev && echo "Development: OK" || echo "Development: FAILED"
systemctl is-active --quiet nginx && echo "Nginx: OK" || echo "Nginx: FAILED"
```

Your server is now configured for automatic deployment with separate development and production environments.