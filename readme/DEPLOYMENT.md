# Deployment Guide - Student Platform

This guide covers deploying the Student Platform to production environments.

## Pre-Deployment Checklist

Before deploying to production:

### Security
- [ ] `serviceAccountKey.json` is NOT in version control
- [ ] `.gitignore` includes sensitive files
- [ ] Flask secret key is a fixed, secure random string (not `os.urandom(24)`)
- [ ] Firestore security rules are set to production mode
- [ ] HTTPS/SSL is configured
- [ ] Environment variables are used for sensitive data

### Code
- [ ] All features tested (see TESTING_GUIDE.md)
- [ ] No debug mode in production
- [ ] Error handling is comprehensive
- [ ] Logging is configured
- [ ] Code is documented

### Firebase
- [ ] Production Firebase project created (separate from development)
- [ ] Firestore indexes created if needed
- [ ] Backup strategy in place
- [ ] Monitoring enabled

---

## Production Configuration

### 1. Update Flask Configuration

Edit `app.py`:

```python
import os

# Production secret key - use environment variable
app.secret_key = os.environ.get('SECRET_KEY', 'your-secure-random-key-here')

# Disable debug mode in production
if __name__ == '__main__':
    # Check environment
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
```

### 2. Update Firestore Security Rules

In Firebase Console → Firestore → Rules:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Users collection
    match /users/{userId} {
      // Only authenticated users can access their own data
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
    
    // Prevent access to other collections
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

### 3. Environment Variables

Create `.env` file (add to `.gitignore`):

```env
# Flask Configuration
SECRET_KEY=your-very-secure-random-secret-key-minimum-32-characters
FLASK_ENV=production

# Firebase Configuration (Optional - for service account path)
FIREBASE_SERVICE_ACCOUNT=/path/to/serviceAccountKey.json
```

Update `firebase_config.py` to use environment variables:

```python
import os
from dotenv import load_dotenv

load_dotenv()

def initialize_firebase():
    try:
        firebase_admin.get_app()
    except ValueError:
        # Try environment variable first, then default path
        cred_path = os.environ.get(
            'FIREBASE_SERVICE_ACCOUNT',
            os.path.join(os.path.dirname(__file__), 'serviceAccountKey.json')
        )
        
        if not os.path.exists(cred_path):
            raise FileNotFoundError(
                "Service account key not found. Set FIREBASE_SERVICE_ACCOUNT env variable."
            )
        
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
```

---

## Deployment Options

### Option 1: Traditional VPS/Server

#### Requirements
- Ubuntu 20.04+ or similar Linux server
- Python 3.8+
- Nginx or Apache
- SSL certificate (Let's Encrypt recommended)

#### Steps

1. **Install System Dependencies**
```bash
sudo apt update
sudo apt install python3-pip python3-venv nginx certbot python3-certbot-nginx
```

2. **Clone Your Application**
```bash
cd /var/www
sudo git clone your-repository-url student-platform
cd student-platform
```

3. **Create Virtual Environment**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

4. **Add Service Account Key**
```bash
# Upload serviceAccountKey.json securely
sudo nano serviceAccountKey.json
# Paste content and save
sudo chmod 600 serviceAccountKey.json
```

5. **Configure Gunicorn**

Install Gunicorn:
```bash
pip install gunicorn
```

Create `wsgi.py`:
```python
from app import app

if __name__ == "__main__":
    app.run()
```

Test Gunicorn:
```bash
gunicorn --bind 0.0.0.0:8000 wsgi:app
```

6. **Create Systemd Service**

Create `/etc/systemd/system/student-platform.service`:
```ini
[Unit]
Description=Student Platform Flask Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/student-platform
Environment="PATH=/var/www/student-platform/venv/bin"
Environment="SECRET_KEY=your-secret-key"
Environment="FLASK_ENV=production"
ExecStart=/var/www/student-platform/venv/bin/gunicorn --workers 3 --bind unix:student-platform.sock -m 007 wsgi:app

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable student-platform
sudo systemctl start student-platform
sudo systemctl status student-platform
```

7. **Configure Nginx**

Create `/etc/nginx/sites-available/student-platform`:
```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/student-platform/student-platform.sock;
    }

    location /static {
        alias /var/www/student-platform/static;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/student-platform /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

8. **Setup SSL with Let's Encrypt**
```bash
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

---

### Option 2: Heroku

#### Prerequisites
- Heroku account
- Heroku CLI installed

#### Steps

1. **Create Heroku Files**

Create `Procfile`:
```
web: gunicorn app:app
```

Create `runtime.txt`:
```
python-3.11.0
```

2. **Update Requirements**
```bash
pip freeze > requirements.txt
```

3. **Initialize Git (if not already)**
```bash
git init
git add .
git commit -m "Initial commit"
```

4. **Create Heroku App**
```bash
heroku create student-platform-yourname
```

5. **Set Environment Variables**
```bash
heroku config:set SECRET_KEY=your-secret-key
heroku config:set FLASK_ENV=production
```

6. **Add Service Account Key**

Encode as base64:
```bash
base64 serviceAccountKey.json > key.txt
```

Then:
```bash
heroku config:set FIREBASE_CREDENTIALS="$(cat key.txt)"
```

Update `firebase_config.py` to decode:
```python
import base64
import json

def initialize_firebase():
    try:
        firebase_admin.get_app()
    except ValueError:
        # For Heroku, use base64 encoded credentials
        cred_base64 = os.environ.get('FIREBASE_CREDENTIALS')
        if cred_base64:
            cred_json = base64.b64decode(cred_base64)
            cred_dict = json.loads(cred_json)
            cred = credentials.Certificate(cred_dict)
        else:
            # Local development
            cred_path = 'serviceAccountKey.json'
            cred = credentials.Certificate(cred_path)
        
        firebase_admin.initialize_app(cred)
```

7. **Deploy**
```bash
git push heroku main
```

8. **Open Application**
```bash
heroku open
```

---

### Option 3: Google Cloud Run

#### Prerequisites
- Google Cloud account
- gcloud CLI installed
- Docker installed

#### Steps

1. **Create Dockerfile**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
ENV FLASK_ENV=production

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
```

2. **Create `.dockerignore`**
```
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env
venv
serviceAccountKey.json
.git
.gitignore
```

3. **Build and Deploy**
```bash
# Authenticate
gcloud auth login

# Set project
gcloud config set project YOUR_PROJECT_ID

# Build container
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/student-platform

# Deploy to Cloud Run
gcloud run deploy student-platform \
  --image gcr.io/YOUR_PROJECT_ID/student-platform \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

---

### Option 4: Docker Compose (Self-Hosted)

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "5000:5000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - FLASK_ENV=production
    volumes:
      - ./serviceAccountKey.json:/app/serviceAccountKey.json:ro
    restart: unless-stopped

  nginx:
    image: nginx:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - web
    restart: unless-stopped
```

Deploy:
```bash
docker-compose up -d
```

---

## Post-Deployment Tasks

### 1. Monitoring Setup

Add basic logging to `app.py`:

```python
import logging
from logging.handlers import RotatingFileHandler

if not app.debug:
    file_handler = RotatingFileHandler('logs/student-platform.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Student Platform startup')
```

### 2. Firebase Monitoring

In Firebase Console:
- Enable Analytics
- Set up Alerts for authentication failures
- Monitor Firestore usage

### 3. Backup Strategy

Set up automated backups:
```bash
# Firestore export (run daily)
gcloud firestore export gs://your-backup-bucket
```

### 4. Performance Monitoring

- Enable Firebase Performance Monitoring
- Set up application metrics (response times, error rates)
- Monitor server resources (CPU, RAM, disk)

---

## Maintenance

### Regular Tasks

**Daily:**
- Check application logs
- Monitor error rates
- Verify backups completed

**Weekly:**
- Review Firebase usage
- Check for security updates
- Update dependencies

**Monthly:**
- Review and rotate service account keys
- Analyze user growth
- Performance optimization

### Update Procedure

1. Test updates in development
2. Create backup
3. Deploy to staging (if available)
4. Test thoroughly
5. Deploy to production during low-traffic period
6. Monitor for issues
7. Rollback if necessary

---

## Troubleshooting Production Issues

### Application Won't Start
```bash
# Check logs
sudo journalctl -u student-platform -n 50

# Verify service account key
ls -la serviceAccountKey.json

# Test Flask directly
python app.py
```

### High Memory Usage
```bash
# Check processes
top

# Restart service
sudo systemctl restart student-platform
```

### Firestore Connection Issues
- Verify service account permissions
- Check network connectivity
- Review Firestore quotas

---

## Scaling Considerations

### When to Scale

- Response times > 2 seconds
- CPU usage consistently > 80%
- Memory usage > 90%
- Growing user base

### Scaling Options

1. **Vertical Scaling**: Increase server resources
2. **Horizontal Scaling**: Add more application instances
3. **Database Optimization**: Add Firestore indexes
4. **Caching**: Implement Redis for session management

---

## Security Best Practices

1. **Regular Updates**
   ```bash
   pip list --outdated
   pip install --upgrade package-name
   ```

2. **Security Headers**
   Add to Flask app:
   ```python
   @app.after_request
   def set_security_headers(response):
       response.headers['X-Content-Type-Options'] = 'nosniff'
       response.headers['X-Frame-Options'] = 'DENY'
       response.headers['X-XSS-Protection'] = '1; mode=block'
       return response
   ```

3. **Rate Limiting**
   Install Flask-Limiter:
   ```bash
   pip install Flask-Limiter
   ```

4. **HTTPS Only**
   Redirect all HTTP to HTTPS in Nginx config

---

## Cost Optimization

### Firebase Free Tier Limits
- Authentication: 50,000 MAU (Monthly Active Users)
- Firestore: 1 GB storage, 50K reads/day, 20K writes/day

### Cost Monitoring
- Enable billing alerts in Firebase
- Review usage monthly
- Optimize queries to reduce reads

---

## Support & Maintenance Contacts

- Firebase Support: https://firebase.google.com/support
- Server Provider Support: [Your hosting provider]
- Emergency Contact: [Your contact info]

---

**Deployment complete! Your Student Platform is now live! 🚀**
