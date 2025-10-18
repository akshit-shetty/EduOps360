# EduOps360 - Back4app Container Deployment Guide

## 🚀 Complete Docker Deployment for Back4app

### Prerequisites
- Back4app account (sign up at back4app.com)
- GitHub repository with your code
- Docker files created (✅ Already done)

---

## Step 1: Prepare Your Repository

### ✅ Files Already Created:
- `Dockerfile` - Container configuration
- `.dockerignore` - Exclude unnecessary files
- `requirements.txt` - Updated Python dependencies
- `BACK4APP_DEPLOYMENT.md` - This guide

### Environment Variables Needed:
```env
FLASK_SECRET_KEY=your-secret-key-here
FLASK_ENV=production
EMAIL_ADDRESS=your-office365-email@domain.com
EMAIL_PASSWORD=your-email-password
EMAIL_DISPLAY_NAME=GGU DBA ET Operations
PORT=5000
```

---

## Step 2: Push to GitHub

1. **Add all files to git:**
```bash
git add .
git commit -m "Add Docker configuration for Back4app deployment"
git push origin main
```

2. **Verify files are uploaded:**
- ✅ Dockerfile
- ✅ .dockerignore  
- ✅ requirements.txt
- ✅ All application files

---

## Step 3: Deploy on Back4app

### 3.1 Create New Container App
1. Login to **Back4app Dashboard**
2. Click **"New App"**
3. Select **"Containers as a Service"**
4. Click **"Import from GitHub"**

### 3.2 Configure Repository
1. **Search and select** your EduOps360 repository
2. **Branch**: `main` (or your default branch)
3. **App Name**: `eduops360` (or your preferred name)
4. Click **"Create App"**

### 3.3 Configure Environment Variables
In the Back4app dashboard, go to **Environment Variables** and add:

```
FLASK_SECRET_KEY=your-super-secure-secret-key-change-this
FLASK_ENV=production
EMAIL_ADDRESS=your-office365-email@domain.com
EMAIL_PASSWORD=your-email-password-or-app-password
EMAIL_DISPLAY_NAME=GGU DBA ET Operations
PORT=5000
```

### 3.4 Deploy Container
1. Click **"Deploy"** button
2. Wait for build process to complete
3. Monitor build logs for any errors

---

## Step 4: Verify Deployment

### 4.1 Check Application Status
1. **Build Status**: Should show "Success" ✅
2. **Container Status**: Should show "Running" ✅
3. **URL**: Your app will be available at provided URL

### 4.2 Test Core Features
1. **Access your app** at the provided URL
2. **Test login** with OTP functionality
3. **Test email sending** (OTP emails)
4. **Upload Excel file** to test database functionality
5. **Check dashboard** analytics and features

---

## Step 5: Post-Deployment Configuration

### 5.1 Custom Domain (Optional)
1. Go to **Settings** → **Domains**
2. Add your custom domain
3. Configure DNS records as instructed

### 5.2 Database Backup
1. Download your `eduops360.db` file regularly
2. Store backups securely
3. Consider setting up automated backups

---

## 🔧 Troubleshooting

### Common Issues:

**1. Build Fails:**
```bash
# Check Dockerfile syntax
# Verify requirements.txt dependencies
# Check build logs in Back4app dashboard
```

**2. Container Won't Start:**
```bash
# Check environment variables are set
# Verify PORT=5000 is configured
# Check application logs
```

**3. Email Not Working:**
```bash
# Verify EMAIL_ADDRESS and EMAIL_PASSWORD
# Check Office365 SMTP settings
# Test with app passwords if using 2FA
```

**4. Database Issues:**
```bash
# Ensure eduops360.db is included in repository
# Check file permissions
# Verify SQLite is working
```

### Debug Commands:
```bash
# View container logs
# Check environment variables
# Test database connection
# Monitor resource usage
```

---

## 📊 Expected Performance

### What Will Work:
- ✅ **Full Flask application**
- ✅ **Office365 email sending** (OTP, campaigns, reminders)
- ✅ **Database operations** (SQLite)
- ✅ **File uploads** (Excel processing)
- ✅ **All dashboard features**
- ✅ **Student management**
- ✅ **Analytics and reporting**

### Potential Limitations:
- ⚠️ **NVIDIA chatbot** - May need verification for external API access
- ⚠️ **Resource limits** on free tier
- ⚠️ **Container sleep** after inactivity

---

## 🎯 Production Checklist

- [ ] Repository pushed to GitHub with Docker files
- [ ] Back4app container app created and configured
- [ ] Environment variables set correctly
- [ ] Application builds successfully
- [ ] Container starts and runs
- [ ] Login/OTP functionality tested
- [ ] Email sending verified
- [ ] Database upload tested
- [ ] Dashboard features working
- [ ] Custom domain configured (optional)
- [ ] Backup strategy in place

---

## 🚀 Going Live

Once deployment is successful:

1. **Share your URL** with team members
2. **Upload production data** via Excel upload
3. **Create user accounts** for administrators
4. **Test all features** thoroughly
5. **Monitor performance** and logs

---

## 📞 Support Resources

- **Back4app Documentation**: https://docs.back4app.com/
- **Container Logs**: Available in Back4app dashboard
- **GitHub Issues**: For code-related problems
- **Email Testing**: Use your Office365 account

**Your EduOps360 application should now be fully deployed and functional on Back4app with Docker containers!**

---

## 🔄 Updates and Maintenance

To update your application:

1. **Make changes** to your code locally
2. **Commit and push** to GitHub:
```bash
git add .
git commit -m "Update application"
git push origin main
```
3. **Redeploy** in Back4app dashboard
4. **Test changes** on live deployment

**Back4app will automatically rebuild and redeploy your container when you push changes to GitHub.**
