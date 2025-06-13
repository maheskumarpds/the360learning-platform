# Deployment Guide for the360learning

## Connecting to Your GitHub Repository

Since you have the GitHub repository at `https://github.com/maheskumarpds/the360-learning.git`, follow these steps:

### Step 1: Download Your Project Files
Download all the files from this Replit environment to your local machine. The project structure is:
```
learning_is_easy/
├── core/                   # Main Django app
├── templates/             # HTML templates
├── static/               # CSS, JS, images
├── learning_is_easy/     # Django settings
├── requirements.txt      # Python dependencies
├── README.md            # Project documentation
├── .env.example         # Environment variables template
├── .gitignore          # Git ignore rules
└── manage.py           # Django management script
```

### Step 2: Set Up Local Repository
On your local machine, navigate to where you want to store the project and run:

```bash
# Clone your existing repository
git clone https://github.com/maheskumarpds/the360-learning.git
cd the360-learning

# Copy all the project files into this directory
# (Copy the contents of the learning_is_easy folder from Replit)

# Add all files to git
git add .

# Commit the changes
git commit -m "Initial commit: Complete the360learning educational platform

- Django-based educational platform with AI tutoring
- User management with role-based access control
- Video conferencing integration with Zoom API
- Study materials and assignment management
- Email notifications and weekly summaries
- Bootstrap 5 responsive design with green theme
- OpenAI GPT-4o integration for AI tutoring
- Stripe payment processing (temporarily disabled)
- Complete rebranding to the360learning"

# Push to your GitHub repository
git push origin main
```

### Step 3: Environment Setup
1. Copy `.env.example` to `.env`
2. Fill in your actual API keys and database credentials
3. Install dependencies: `pip install -r requirements.txt`
4. Set up PostgreSQL database
5. Run migrations: `python manage.py migrate`
6. Create superuser: `python manage.py createsuperuser`

### Step 4: Production Deployment
For production deployment, consider:
- Heroku with PostgreSQL addon
- AWS EC2 with RDS
- DigitalOcean Droplet
- Google Cloud Platform

### Required Environment Variables
```env
DATABASE_URL=postgresql://username:password@localhost/the360learning_db
OPENAI_API_KEY=your_openai_api_key
SENDGRID_API_KEY=your_sendgrid_api_key
ZOOM_API_KEY=your_zoom_api_key
ZOOM_API_SECRET=your_zoom_api_secret
ZOOM_CLIENT_ID=your_zoom_client_id
ZOOM_CLIENT_SECRET=your_zoom_client_secret
ZOOM_ACCOUNT_ID=your_zoom_account_id
STRIPE_SECRET_KEY=your_stripe_secret_key
SECRET_KEY=your_django_secret_key
```

### Continuous Development
To keep your repository updated:
1. Make changes locally
2. Test thoroughly
3. Commit changes: `git add . && git commit -m "Description of changes"`
4. Push to GitHub: `git push origin main`

Your complete the360learning platform is now ready for GitHub storage and deployment!