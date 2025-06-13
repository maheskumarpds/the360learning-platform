# the360learning - Educational Platform

A comprehensive Django-based educational platform that leverages AI technologies to create engaging, personalized learning experiences with advanced administrative tools and interactive support features.

## Features

### Core Functionality
- **User Management**: Role-based authentication (Students, Teachers, Admins)
- **Class-Level Access Control**: Content restricted by class enrollment
- **AI-Powered Tutoring**: OpenAI integration for personalized learning
- **Video Conferencing**: Zoom API and SDK integration
- **Study Materials**: File uploads and management
- **Assignments**: Creation, submission, and grading system
- **Recording Management**: Session recordings with analytics
- **Email Notifications**: Automated alerts for users and meetings

### Advanced Features
- **ChatGPT-like AI Interface**: Professional chat UI with history
- **Weekly Learning Summaries**: Visual progress reports
- **Quiz System**: Skill assessments and tracking
- **Areas of Improvement**: Performance analytics
- **Responsive Design**: Bootstrap 5 with green theme
- **Payment Integration**: Stripe support (temporarily disabled)

## Technology Stack

- **Backend**: Django 5.2, Python 3.11+
- **Database**: PostgreSQL
- **Frontend**: Bootstrap 5, JavaScript, HTML5/CSS3
- **AI Integration**: OpenAI GPT-4o
- **Video**: Zoom API & SDK
- **Email**: SendGrid
- **Payments**: Stripe
- **Storage**: AWS S3 (optional)

## Installation

### Prerequisites
- Python 3.11+
- PostgreSQL
- Git

### Environment Variables
Create a `.env` file in the project root with:

```env
# Database
DATABASE_URL=postgresql://username:password@localhost/dbname

# AI Services
OPENAI_API_KEY=your_openai_api_key

# Email Service
SENDGRID_API_KEY=your_sendgrid_api_key

# Video Conferencing
ZOOM_API_KEY=your_zoom_api_key
ZOOM_API_SECRET=your_zoom_api_secret
ZOOM_CLIENT_ID=your_zoom_client_id
ZOOM_CLIENT_SECRET=your_zoom_client_secret
ZOOM_ACCOUNT_ID=your_zoom_account_id

# Payment Processing (Optional)
STRIPE_SECRET_KEY=your_stripe_secret_key

# AWS Storage (Optional)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_STORAGE_BUCKET_NAME=your_bucket_name

# Security
SECRET_KEY=your_django_secret_key
DEBUG=False
```

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd learning_is_easy
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Database setup**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

4. **Run the development server**
   ```bash
   python manage.py runserver 0.0.0.0:5000
   ```

## Project Structure

```
learning_is_easy/
├── core/                   # Main application
│   ├── models.py          # Database models
│   ├── views.py           # View controllers
│   ├── forms.py           # Django forms
│   ├── ai_service.py      # AI integration
│   ├── email_service.py   # Email functionality
│   └── stripe_service.py  # Payment processing
├── templates/             # HTML templates
├── static/               # CSS, JS, images
├── media/                # User uploads
└── learning_is_easy/     # Django settings
```

## Configuration

### User Roles
- **Students**: Access to enrolled class content
- **Teachers**: Content creation and class management
- **Admins**: Full system administration

### Class Levels
- Primary classes (1st-5th)
- Middle school (6th-8th)
- High school (9th-12th)
- Advanced levels

### AI Tutoring
The platform uses OpenAI's GPT-4o model for:
- Personalized learning assistance
- Age-appropriate content delivery
- Subject-specific guidance
- Practice question generation

## Deployment

### Production Checklist
- [ ] Set `DEBUG=False`
- [ ] Configure secure database
- [ ] Set up email service
- [ ] Configure static file serving
- [ ] Set up SSL/TLS
- [ ] Configure monitoring

### Environment-Specific Settings
- Development: SQLite, debug mode
- Production: PostgreSQL, secure settings
- Testing: In-memory database

## API Integration

### Zoom Integration
- OAuth 2.0 authentication
- Meeting creation and management
- SDK embedding for web conferences
- Recording management

### OpenAI Integration
- GPT-4o for AI tutoring
- Context-aware responses
- Educational content generation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Security

- Role-based access control
- CSRF protection
- SQL injection prevention
- XSS protection
- Secure password handling

## License

This project is proprietary. All rights reserved.

## Support

For technical support or questions, please contact the development team.

## Version History

- v1.0.0: Initial release with core functionality
- v1.1.0: Added AI tutoring features
- v1.2.0: Integrated video conferencing
- v1.3.0: Added payment processing
- v1.4.0: Enhanced UI/UX with green theme
- v1.5.0: Complete rebranding to "the360learning"