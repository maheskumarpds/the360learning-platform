#!/bin/bash

# the360learning Platform - Automated Server Setup Script
# This script sets up the complete production and development environment

set -e

echo "🚀 Starting the360learning Platform Setup..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root. Please run as a regular user with sudo privileges."
   exit 1
fi

# Update system
print_status "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install required packages
print_status "Installing required packages..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    nginx \
    postgresql \
    postgresql-contrib \
    git \
    supervisor \
    curl \
    software-properties-common \
    certbot \
    python3-certbot-nginx

# Create directory structure
print_status "Creating application directories..."
sudo mkdir -p /var/www/the360learning-production
sudo mkdir -p /var/www/the360learning-development

# Set ownership
sudo chown -R $USER:$USER /var/www/the360learning-production
sudo chown -R $USER:$USER /var/www/the360learning-development

# Configure PostgreSQL
print_status "Configuring PostgreSQL databases..."
sudo -u postgres psql << EOF
CREATE DATABASE the360learning_prod;
CREATE DATABASE the360learning_dev;
CREATE USER prod_user WITH PASSWORD 'SecurePassword123!';
CREATE USER dev_user WITH PASSWORD 'DevPassword123!';
GRANT ALL PRIVILEGES ON DATABASE the360learning_prod TO prod_user;
GRANT ALL PRIVILEGES ON DATABASE the360learning_dev TO dev_user;
\q
EOF

# Clone repository - Production
print_status "Cloning repository for production..."
cd /var/www/the360learning-production
if [ ! -d ".git" ]; then
    git clone https://github.com/maheskumarpds/the360learning-platform.git .
fi
git checkout main
git pull origin main

# Clone repository - Development
print_status "Cloning repository for development..."
cd /var/www/the360learning-development
if [ ! -d ".git" ]; then
    git clone https://github.com/maheskumarpds/the360learning-platform.git .
fi

# Create and checkout development branch
if ! git show-ref --verify --quiet refs/heads/development; then
    git checkout -b development
else
    git checkout development
fi

# Setup Python environments
print_status "Setting up Python virtual environments..."

# Production environment
cd /var/www/the360learning-production
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

# Development environment
cd /var/www/the360learning-development
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

# Create environment files
print_status "Creating environment configuration files..."

# Production .env
cat > /var/www/the360learning-production/.env << 'EOF'
# Database Configuration
DATABASE_URL=postgresql://prod_user:SecurePassword123!@localhost/the360learning_prod

# Django Settings
SECRET_KEY=your-super-secret-production-key-here-make-it-long-and-random-change-this
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

# Development .env
cat > /var/www/the360learning-development/.env << 'EOF'
# Database Configuration
DATABASE_URL=postgresql://dev_user:DevPassword123!@localhost/the360learning_dev

# Django Settings
SECRET_KEY=your-development-secret-key-different-from-production-change-this
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

# Create Gunicorn configuration files
print_status "Creating Gunicorn configuration..."

# Production Gunicorn config
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

# Development Gunicorn config
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

# Initialize Django applications
print_status "Initializing Django applications..."

# Production
cd /var/www/the360learning-production
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
deactivate

# Development
cd /var/www/the360learning-development
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
deactivate

# Create systemd service files
print_status "Creating systemd services..."

# Production service
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

# Development service
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

# Create Nginx configuration
print_status "Configuring Nginx..."

# Production site
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

# Development site
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

# Set proper permissions
print_status "Setting proper permissions..."
sudo chown -R www-data:www-data /var/www/the360learning-production
sudo chown -R www-data:www-data /var/www/the360learning-development

# Enable services
print_status "Enabling and starting services..."
sudo systemctl daemon-reload
sudo systemctl enable the360learning-prod
sudo systemctl enable the360learning-dev
sudo systemctl start the360learning-prod
sudo systemctl start the360learning-dev

# Enable Nginx sites
sudo ln -sf /etc/nginx/sites-available/the360learning-prod /etc/nginx/sites-enabled/
sudo ln -sf /etc/nginx/sites-available/the360learning-dev /etc/nginx/sites-enabled/

# Remove default Nginx site
sudo rm -f /etc/nginx/sites-enabled/default

# Test and restart Nginx
sudo nginx -t && sudo systemctl restart nginx

# Generate SSH key for GitHub Actions
print_status "Generating SSH key for GitHub Actions..."
if [ ! -f ~/.ssh/github_actions ]; then
    ssh-keygen -t rsa -b 4096 -C "github-actions@your-domain.com" -f ~/.ssh/github_actions -N ""
    cat ~/.ssh/github_actions.pub >> ~/.ssh/authorized_keys
    chmod 600 ~/.ssh/authorized_keys
fi

# Display setup completion
print_status "Setup completed successfully!"

echo ""
echo "=============================================="
echo "🎉 the360learning Platform Setup Complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Edit environment files with your API keys:"
echo "   nano /var/www/the360learning-production/.env"
echo "   nano /var/www/the360learning-development/.env"
echo ""
echo "2. Update domain names in Nginx configs:"
echo "   Replace 'your-domain.com' with your actual domain"
echo ""
echo "3. Add GitHub secrets with this SSH private key:"
cat ~/.ssh/github_actions
echo ""
echo "4. Create admin users:"
echo "   cd /var/www/the360learning-production && source venv/bin/activate && python manage.py createsuperuser"
echo "   cd /var/www/the360learning-development && source venv/bin/activate && python manage.py createsuperuser"
echo ""
echo "5. Test the services:"
echo "   sudo systemctl status the360learning-prod"
echo "   sudo systemctl status the360learning-dev"
echo ""
echo "Your platform will be available at:"
echo "- Production: http://your-domain.com"
echo "- Development: http://dev.your-domain.com"
echo ""
echo "CI/CD is configured - push to 'main' deploys to production, 'development' deploys to staging"
echo "=============================================="