# EduOps360 - PythonAnywhere Deployment Guide

## 🚀 Complete Step-by-Step Deployment Instructions

### Prerequisites
- PythonAnywhere free account (sign up at pythonanywhere.com)
- Your Office365 email credentials
- Git repository access (optional)

---

## Step 1: Create PythonAnywhere Account

1. Go to **https://www.pythonanywhere.com/**
2. Click **"Pricing & signup"**
3. Choose **"Create a Beginner account"** (FREE)
4. Sign up with your email and create username
5. Verify your email address

---

## Step 2: Upload Your Code

### Option A: Using Git (Recommended)
1. Open **"Consoles"** tab in PythonAnywhere dashboard
2. Click **"Bash"** to open terminal
3. Run these commands:
```bash
cd ~
git clone https://github.com/akshit-shetty/EduOps360.git
cd EduOps360/Ver14
```

### Option B: Using File Upload
1. Go to **"Files"** tab in PythonAnywhere dashboard
2. Create folder: **EduOps360**
3. Upload all your project files to `/home/yourusername/EduOps360/`

---

## Step 3: Install Dependencies

1. In the **Bash console**, navigate to your project:
```bash
cd ~/EduOps360/Ver14
```

2. Install required packages:
```bash
pip3.10 install --user Flask==2.3.3
pip3.10 install --user pandas==2.1.4
pip3.10 install --user numpy==1.24.4
pip3.10 install --user Werkzeug==2.3.7
pip3.10 install --user openpyxl==3.1.2
pip3.10 install --user python-dotenv==1.0.0
pip3.10 install --user openai==1.50.0
pip3.10 install --user Flask-CORS==4.0.0
pip3.10 install --user requests==2.31.0
```

Or install all at once:
```bash
pip3.10 install --user -r requirements.txt
```

---

## Step 4: Configure Environment Variables

1. In **"Files"** tab, navigate to your project folder
2. Edit the **`.env`** file with your settings:

```env
# Flask Configuration
FLASK_SECRET_KEY=your-super-secure-secret-key-here-change-this
FLASK_ENV=production
FLASK_DEBUG=False

# Email Configuration (Your Office365 Settings)
EMAIL_ADDRESS=your-office365-email@domain.com
EMAIL_PASSWORD=your-email-password-or-app-password
EMAIL_DISPLAY_NAME=GGU DBA ET Operations

# Optional Secondary Email
EMAIL_ADDRESS_SECONDARY=secondary-email@domain.com
EMAIL_PASSWORD_SECONDARY=secondary-password
EMAIL_DISPLAY_NAME_SECONDARY=EduOps360 Secondary

# Database
DATABASE_URL=sqlite:///eduops360.db
SESSION_TIMEOUT_HOURS=24
```

**Important**: Replace the email settings with your actual Office365 credentials.

---

## Step 5: Set Up Web Application

1. Go to **"Web"** tab in PythonAnywhere dashboard
2. Click **"Add a new web app"**
3. Choose **"Manual configuration"**
4. Select **"Python 3.10"**
5. Click **"Next"**

---

## Step 6: Configure WSGI File

1. In the **Web** tab, find **"Code"** section
2. Click on **"WSGI configuration file"** link
3. **Replace ALL content** with this:

```python
import sys
import os

# Add your project directory to Python path
# Replace 'yourusername' with your actual PythonAnywhere username
project_home = '/home/yourusername/EduOps360/Ver14'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment variables
os.environ['FLASK_ENV'] = 'production'
os.environ['FLASK_DEBUG'] = 'False'

# Import your Flask application
from app import app as application

if __name__ == '__main__':
    application.run(debug=False)
```

4. **Replace `yourusername`** with your actual PythonAnywhere username
5. Click **"Save"**

---

## Step 7: Configure Static Files (Optional)

1. In **Web** tab, scroll to **"Static files"** section
2. Add static file mapping:
   - **URL**: `/static/`
   - **Directory**: `/home/yourusername/EduOps360/Ver14/static/`

---

## Step 8: Test Your Application

1. In **Web** tab, click **"Reload yourusername.pythonanywhere.com"**
2. Wait for reload to complete (green checkmark)
3. Click your domain link: **https://yourusername.pythonanywhere.com**
4. Your EduOps360 application should load!

---

## Step 9: Test Email Functionality

1. Try to login with an existing user email
2. Check if OTP is sent to your email
3. If email fails, OTP might be displayed in error logs

### Check Error Logs:
1. Go to **Web** tab
2. Click **"Error log"** link
3. Look for any email-related errors

---

## Step 10: Database Setup (If Needed)

If you need to upload fresh data:

1. In **Bash console**:
```bash
cd ~/EduOps360/Ver14
python3.10 db.py
```

2. Upload your Excel file through the web interface

---

## 🔧 Troubleshooting

### Common Issues:

**1. Import Errors:**
```bash
# Install missing packages
pip3.10 install --user package-name
```

**2. Database Errors:**
```bash
# Check database file permissions
ls -la eduops360.db
chmod 644 eduops360.db
```

**3. Email Not Working:**
- Check your `.env` file has correct email credentials
- Verify Office365 email settings
- Check error logs for SMTP errors

**4. Static Files Not Loading:**
- Verify static files mapping in Web tab
- Check file paths are correct

**5. Application Won't Start:**
- Check WSGI file configuration
- Verify Python path in WSGI file
- Check error logs for detailed errors

---

## 📊 Free Account Limitations

**What Works:**
- ✅ Full Flask application
- ✅ SQLite database
- ✅ File uploads
- ✅ Office365 email sending (~100 emails/day)
- ✅ All your core features

**Limitations:**
- ❌ NVIDIA chatbot (external API blocked)
- ⚠️ Limited CPU seconds per day
- ⚠️ Email rate limits

---

## 🎯 Success Checklist

- [ ] PythonAnywhere account created
- [ ] Code uploaded to `/home/yourusername/EduOps360/Ver14/`
- [ ] Dependencies installed with `pip3.10 install --user`
- [ ] `.env` file configured with your email settings
- [ ] WSGI file configured with correct username and path
- [ ] Web app created and configured
- [ ] Application reloaded successfully
- [ ] Website accessible at yourusername.pythonanywhere.com
- [ ] Login functionality tested
- [ ] Email/OTP functionality tested

---

## 🚀 Going Live

Once everything works:

1. **Test all features** thoroughly
2. **Upload your real data** via Excel upload
3. **Create user accounts** for your team
4. **Share the URL**: `https://yourusername.pythonanywhere.com`

---

## 📞 Support

If you encounter issues:
1. Check PythonAnywhere help documentation
2. Review error logs in Web tab
3. Test locally first to isolate PythonAnywhere-specific issues

**Your application should be fully functional on PythonAnywhere with your existing Office365 email configuration!**
