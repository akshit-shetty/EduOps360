# EduOps360 Render Deployment Guide

## ✅ Pre-Deployment Checklist (COMPLETED)

- [x] Updated requirements.txt with all dependencies
- [x] Updated Procfile for gunicorn deployment
- [x] Created .env.example file
- [x] Pushed code to GitHub repository
- [x] Configured app.py for production

## 🚀 Deploy to Render

### Step 1: Create Render Account
1. Go to [render.com](https://render.com)
2. Sign up or log in with your GitHub account

### Step 2: Create New Web Service
1. Click "New +" button
2. Select "Web Service"
3. Connect your GitHub account if not already connected
4. Select repository: `akshit-shetty/eduops360-2-`

### Step 3: Configure Deployment Settings
```
Name: eduops360
Environment: Python 3
Region: Choose closest to your users
Branch: main
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
```

### Step 4: Set Environment Variables
Add these environment variables in Render dashboard:

**Required Variables:**
```
FLASK_ENV=production
SECRET_KEY=your-super-secret-key-here-make-it-long-and-random
OPENAI_API_KEY=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
OPENAI_BASE_URL=https://integrate.api.nvidia.com/v1
```

**Email Configuration (Optional but recommended):**
```
GMAIL_EMAIL=your-email@gmail.com
GMAIL_PASSWORD=your-gmail-app-password
```

### Step 5: Deploy
1. Click "Create Web Service"
2. Wait for deployment to complete (5-10 minutes)
3. Your app will be available at: `https://your-app-name.onrender.com`

## 🔧 Post-Deployment Setup

### 1. Database Initialization
- The SQLite database (eduops360.db) is included in the repository
- No additional database setup required

### 2. Admin Access
- Use the existing admin account or create one via the application
- Default admin email: akshit1.shetty@upgrad.com

### 3. Email Configuration
- Set up Gmail App Password for email functionality
- Update environment variables in Render dashboard

## 📋 Environment Variables Details

### SECRET_KEY
Generate a secure secret key:
```python
import secrets
print(secrets.token_hex(32))
```

### OPENAI_API_KEY
- Your NVIDIA API key is already configured
- Current key: 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

### Gmail App Password Setup
1. Enable 2-Factor Authentication on Gmail
2. Go to Google Account Settings > Security > App Passwords
3. Generate app password for "Mail"
4. Use this password in GMAIL_PASSWORD variable

## 🔍 Troubleshooting

### Common Issues:

**Build Fails:**
- Check requirements.txt for correct package versions
- Ensure all imports are available

**App Won't Start:**
- Verify Procfile: `web: gunicorn app:app`
- Check environment variables are set

**Database Issues:**
- SQLite database is included in repository
- Check file permissions if needed

**Email Not Working:**
- Verify Gmail app password is correct
- Check GMAIL_EMAIL and GMAIL_PASSWORD variables

## 📱 Features Available After Deployment

✅ **Dashboard** - Real-time analytics and statistics
✅ **Chatbot** - AI-powered educational assistant
✅ **Student Management** - Comprehensive learner tracking
✅ **Coursework Analytics** - 7-course DBA program tracking
✅ **Dissertation Management** - Research phase monitoring
✅ **Email Campaigns** - Bulk email system
✅ **Session Reminders** - Automated reminder system
✅ **OTP Authentication** - Secure login system
✅ **Admin Panel** - User and system management

## 🌐 Your Deployment URLs

**GitHub Repository:** https://github.com/akshit-shetty/eduops360-2-.git
**Render App URL:** Will be provided after deployment

## 📞 Support

If you encounter any issues:
1. Check Render logs in the dashboard
2. Verify environment variables
3. Ensure all dependencies are in requirements.txt
4. Check the GitHub repository for latest updates

---

**Ready for Production! 🚀**
