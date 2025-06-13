# Complete Server Setup Guide - Step by Step

Follow these exact steps to set up automatic deployment for your the360learning platform.

## Part 1: Server Preparation

### Step 1: Access Your Server
```bash
ssh username@your-server-ip
```

### Step 2: Update System and Install Dependencies
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3 python3-pip python3-venv nginx postgresql postgresql-contrib git supervisor
```

### Step 3: Create Directory Structure
```bash
# Create application directories
sudo mkdir -p /var/www/the360learning-production
sudo mkdir -p /var/www/the360learning-development

# Set ownership (replace 'username' with your actual username)
sudo chown -R $USER:$USER /var/www/the360learning-production
sudo chown -R $USER:$USER /var/www/the360learning-development
```

## Part 2: Database Setup

### Step 4: Configure PostgreSQL
```bash
# Switch to postgres user and create databases
sudo -u postgres psql << EOF
CREATE DATABASE the360learning_prod;
CREATE DATABASE the360learning_dev;
CREATE USER prod_user WITH PASSWORD 'SecurePassword123!';
CREATE USER dev_user WITH PASSWORD 'DevPassword123!';
GRANT ALL PRIVILEGES ON DATABASE the360learning_prod TO prod_user;
GRANT ALL PRIVILEGES ON DATABASE the360learning_dev TO dev_user;
\q
EOF
```

## Part 3: Repository Setup

### Step 5: Clone Repository (Production)
```bash
cd /var/www/the360learning-production
git clone https://github.com/maheskumarpds/the360learning-platform.git .
git checkout main
```

### Step 6: Clone Repository (Development)
```bash
cd /var/www/the360learning-development
git clone https://github.com/maheskumarpds/the360learning-platform.git .
```

### Step 7: Create Development Branch
```bash
cd /var/www/the360learning-development
git checkout -b development
git push -u origin development
```

## Part 4: Python Environment Setup

### Step 8: Setup Production Environment
```bash
cd /var/www/the360learning-production
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

### Step 9: Setup Development Environment
```bash
cd /var/www/the360learning-development
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

## Part 5: Environment Configuration

### Step 10: Create Production Environment File
```bash
cat > /var/www/the360learning-production/.env << 'EOF'
# Database Configuration
DATABASE_URL=postgresql://prod_user:SecurePassword123!@localhost/the360learning_prod

# Django Settings
SECRET_KEY=your-super-secret-production-key-here-make-it-long-and-random
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# AI Services (Replace with your actual keys)
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Email Service
SENDGRID_API_KEY=your_sendgrid_api_key_here

# Video Conferencing
ZOOM_API_KEY=your_zoom_api_key_here
ZOOM_API_SECRET=your_zoom_api_secret_here
ZOOM_CLIENT_ID=your_zoom_client_id_here
ZOOM_CLIENT_SECRET=your_zoom_client_secret_here
ZOOM_ACCOUNT_ID=your_zoom_account_id_here

# Payment Processing
STRIPE_SECRET_KEY=your_stripe_secret_key_here

# Email Backend
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Default From Email
DEFAULT_FROM_EMAIL=noreply@your-domain.com
EOF
```

### Step 11: Create Development Environment File
```bash
cat > /var/www/the360learning-development/.env << 'EOF'
# Database Configuration
DATABASE_URL=postgresql://dev_user:DevPassword123!@localhost/the360learning_dev

# Django Settings
SECRET_KEY=your-development-secret-key-different-from-production
DEBUG=True
ALLOWED_HOSTS=dev.your-domain.com,localhost,127.0.0.1

# AI Services (Same keys as production for testing)
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Email Service
SENDGRID_API_KEY=your_sendgrid_api_key_here

# Video Conferencing
ZOOM_API_KEY=your_zoom_api_key_here
ZOOM_API_SECRET=your_zoom_api_secret_here
ZOOM_CLIENT_ID=your_zoom_client_id_here
ZOOM_CLIENT_SECRET=your_zoom_client_secret_here
ZOOM_ACCOUNT_ID=your_zoom_account_id_here

# Payment Processing (Use test keys)
STRIPE_SECRET_KEY=your_stripe_test_secret_key_here

# Email Backend
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=dev@your-domain.com
EOF
```

## Part 6: Django Application Setup

### Step 12: Initialize Production Application
```bash
cd /var/www/the360learning-production
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
deactivate
```

### Step 13: Initialize Development Application
```bash
cd /var/www/the360learning-development
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
deactivate
```

## Part 7: Gunicorn Configuration

### Step 14: Create Gunicorn Configuration Files

Production Gunicorn config:
```bash
cat > /var/www/the360learning-production/gunicorn.conf.py << 'EOF'
bind = "unix:/var/www/the360learning-production/gunicorn.sock"
workers = 3
user = "www-data"
group = "www-data"
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 2
preload_app = True
EOF
```

Development Gunicorn config:
```bash
cat > /var/www/the360learning-development/gunicorn.conf.py << 'EOF'
bind = "unix:/var/www/the360learning-development/gunicorn.sock"
workers = 2
user = "www-data"
group = "www-data"
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 2
preload_app = True
EOF
```

## Part 8: Systemd Service Configuration

### Step 15: Create Production Service
```bash
sudo tee /etc/systemd/system/the360learning-prod.service << 'EOF'
[Unit]
Description=the360learning Production Application
After=network.target postgresql.service

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=/var/www/the360learning-production
Environment=PATH=/var/www/the360learning-production/venv/bin
ExecStart=/var/www/the360learning-production/venv/bin/gunicorn -c gunicorn.conf.py learning_is_easy.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### Step 16: Create Development Service
```bash
sudo tee /etc/systemd/system/the360learning-dev.service << 'EOF'
[Unit]
Description=the360learning Development Application
After=network.target postgresql.service

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=/var/www/the360learning-development
Environment=PATH=/var/www/the360learning-development/venv/bin
ExecStart=/var/www/the360learning-development/venv/bin/gunicorn -c gunicorn.conf.py learning_is_easy.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### Step 17: Enable and Start Services
```bash
# Set proper permissions
sudo chown -R www-data:www-data /var/www/the360learning-production
sudo chown -R www-data:www-data /var/www/the360learning-development

# Reload systemd and enable services
sudo systemctl daemon-reload
sudo systemctl enable the360learning-prod
sudo systemctl enable the360learning-dev
sudo systemctl start the360learning-prod
sudo systemctl start the360learning-dev

# Check status
sudo systemctl status the360learning-prod
sudo systemctl status the360learning-dev
```

## Part 9: Nginx Configuration

### Step 18: Create Production Site Configuration
```bash
sudo tee /etc/nginx/sites-available/the360learning-prod << 'EOF'
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    client_max_body_size 100M;

    location = /favicon.ico { 
        access_log off; 
        log_not_found off; 
    }
    
    location /static/ {
        root /var/www/the360learning-production;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        root /var/www/the360learning-production;
        expires 30d;
        add_header Cache-Control "public";
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/the360learning-production/gunicorn.sock;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $http_host;
        proxy_redirect off;
    }
}
EOF
```

### Step 19: Create Development Site Configuration
```bash
sudo tee /etc/nginx/sites-available/the360learning-dev << 'EOF'
server {
    listen 80;
    server_name dev.your-domain.com;

    client_max_body_size 100M;

    location = /favicon.ico { 
        access_log off; 
        log_not_found off; 
    }
    
    location /static/ {
        root /var/www/the360learning-development;
    }
    
    location /media/ {
        root /var/www/the360learning-development;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/the360learning-development/gunicorn.sock;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $http_host;
        proxy_redirect off;
    }
}
EOF
```

### Step 20: Enable Sites and Restart Nginx
```bash
# Enable sites
sudo ln -s /etc/nginx/sites-available/the360learning-prod /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/the360learning-dev /etc/nginx/sites-enabled/

# Test nginx configuration
sudo nginx -t

# Restart nginx
sudo systemctl restart nginx
```

## Part 10: GitHub Secrets Configuration

### Step 21: Generate SSH Key for GitHub Actions
```bash
# Generate SSH key
ssh-keygen -t rsa -b 4096 -C "github-actions@your-domain.com" -f ~/.ssh/github_actions -N ""

# Add public key to authorized_keys
cat ~/.ssh/github_actions.pub >> ~/.ssh/authorized_keys

# Display private key (copy this for GitHub secrets)
echo "Copy this private key for PROD_SSH_KEY and DEV_SSH_KEY:"
cat ~/.ssh/github_actions
```

### Step 22: Configure GitHub Repository Secrets

Go to your GitHub repository: https://github.com/maheskumarpds/the360learning-platform

1. Click **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add these secrets:

| Secret Name | Value |
|------------|--------|
| `PROD_HOST` | Your server IP address |
| `PROD_USERNAME` | Your SSH username |
| `PROD_SSH_KEY` | Private key from Step 21 |
| `PROD_PORT` | `22` (or your SSH port) |
| `DEV_HOST` | Your server IP address (same as prod) |
| `DEV_USERNAME` | Your SSH username |
| `DEV_SSH_KEY` | Private key from Step 21 |
| `DEV_PORT` | `22` (or your SSH port) |

## Part 11: Test Deployment

### Step 23: Create Development Branch on GitHub
```bash
# On your local machine or server
cd /var/www/the360learning-development
git push -u origin development
```

### Step 24: Test Automatic Deployment

Make a small change to test the deployment:
```bash
# Edit a file to trigger deployment
echo "<!-- Test deployment -->" >> /var/www/the360learning-development/templates/base.html
git add .
git commit -m "Test development deployment"
git push origin development
```

Check GitHub Actions in your repository to see if deployment triggered.

## Part 12: SSL Setup (Optional but Recommended)

### Step 25: Install SSL Certificates
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificates
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
sudo certbot --nginx -d dev.your-domain.com

# Test auto-renewal
sudo certbot renew --dry-run
```

## Verification Commands

Check if everything is working:
```bash
# Check services
sudo systemctl status the360learning-prod
sudo systemctl status the360learning-dev
sudo systemctl status nginx

# Check logs
sudo journalctl -u the360learning-prod -f
sudo journalctl -u the360learning-dev -f

# Test connections
curl -I http://your-domain.com
curl -I http://dev.your-domain.com
```

## Workflow Summary

After setup:
1. **Development**: Push to `development` branch → Auto-deploys to dev.your-domain.com
2. **Production**: Push to `main` branch → Auto-deploys to your-domain.com

Your CI/CD pipeline is now complete with automatic deployments!