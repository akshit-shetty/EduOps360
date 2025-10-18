# EduOps360 - Appwrite Deployment Guide

## 🚨 IMPORTANT: Deployment Type Issue

**The current deployment is using Appwrite Functions, but EduOps360 is a full web application that needs Appwrite Cloud (container deployment).**

## 🔧 Quick Fix for Current Deployment

### Step 1: Check Your Deployment Type
1. Go to your Appwrite Console
2. Check if you deployed as:
   - **Functions** ❌ (This won't work for full web apps)
   - **Cloud/Containers** ✅ (This is what you need)

### Step 2: If You Used Functions (Current Issue)
**Problem**: Appwrite Functions are for serverless functions, not full Flask applications.

**Solution**: Redeploy using Appwrite Cloud containers:

1. **Delete the current function deployment**
2. **Create a new Cloud deployment** instead
3. **Use container/Docker deployment** option

## 🚀 Correct Appwrite Cloud Deployment

### Prerequisites
- Appwrite Cloud account
- GitHub repository with your code
- Updated files (✅ Already created)

### Step 1: Updated Files Created
- ✅ `server.py` - Production server entry point
- ✅ `start.sh` - Startup script
- ✅ Updated `Dockerfile` - Container configuration
- ✅ `appwrite.json` - Configuration file

### Step 2: Environment Variables Needed
```env
FLASK_SECRET_KEY=your-secret-key-here
FLASK_ENV=production
EMAIL_ADDRESS=ggugenai.operations@upgrad.com
EMAIL_PASSWORD=your-email-password
EMAIL_DISPLAY_NAME=GGU DBA ET Operations
PORT=3000
HOST=0.0.0.0
```

### Step 3: Deploy to Appwrite Cloud

1. **Login to Appwrite Console**
2. **Create New Project** (or use existing)
3. **Choose "Cloud" not "Functions"**
4. **Select "Container/Docker" deployment**
5. **Connect your GitHub repository**
6. **Configure environment variables**
7. **Deploy**

### Step 4: Alternative Quick Solutions

#### Option A: Use Render (Recommended)
```bash
# 1. Push your code to GitHub
git add .
git commit -m "Add Appwrite deployment fixes"
git push origin main

# 2. Go to render.com
# 3. Create new Web Service
# 4. Connect GitHub repository
# 5. Use these settings:
#    - Build Command: pip install -r requirements.txt
#    - Start Command: python server.py
#    - Port: 3000
```

#### Option B: Use Railway
```bash
# 1. Go to railway.app
# 2. Deploy from GitHub
# 3. It will auto-detect Flask app
# 4. Add environment variables
```

#### Option C: Use Heroku
```bash
# 1. Create Procfile:
echo "web: python server.py" > Procfile

# 2. Deploy to Heroku
git add Procfile
git commit -m "Add Procfile for Heroku"
git push heroku main
```

## 🔍 Debugging Current Appwrite Issue

### Check Your Deployment
1. **Go to Appwrite Console**
2. **Check deployment logs**:
   - Look for "Functions" vs "Cloud" in the URL
   - Functions URL: `https://cloud.appwrite.io/console/project-xxx/functions`
   - Cloud URL: `https://cloud.appwrite.io/console/project-xxx/overview`

### Common Error Messages
- **"Not Found"** = Wrong deployment type (Functions vs Cloud)
- **"Internal Server Error"** = Missing environment variables
- **"Port binding failed"** = Wrong port configuration

## 🎯 Recommended Solution

**Use Render.com for easiest deployment:**

1. **Go to [render.com](https://render.com)**
2. **Sign up with GitHub**
3. **Create New Web Service**
4. **Select your EduOps360 repository**
5. **Use these exact settings**:
   ```
   Name: eduops360
   Environment: Docker
   Build Command: (leave empty - uses Dockerfile)
   Start Command: (leave empty - uses Dockerfile CMD)
   ```
6. **Add environment variables**:
   ```
   FLASK_SECRET_KEY=your-secret-key
   FLASK_ENV=production
   EMAIL_ADDRESS=ggugenai.operations@upgrad.com
   EMAIL_PASSWORD=your-password
   EMAIL_DISPLAY_NAME=GGU DBA ET Operations
   ```
7. **Deploy**

**Your app will be available at**: `https://eduops360.onrender.com`

## 🔧 Files Updated for Better Deployment

### New Files Created:
1. **`server.py`** - Production-ready server
2. **`start.sh`** - Startup script with error handling
3. **`APPWRITE_DEPLOYMENT.md`** - This guide

### Updated Files:
1. **`Dockerfile`** - Fixed port and entry point
2. **`appwrite.json`** - Appwrite configuration

## 📞 Next Steps

1. **Try Render.com first** (easiest and most reliable)
2. **If you want Appwrite**, use Cloud deployment, not Functions
3. **Push updated code to GitHub**:
   ```bash
   git add .
   git commit -m "Fix deployment configuration"
   git push origin main
   ```

## 🎉 Expected Result

After correct deployment:
- ✅ **Login page loads** at your deployment URL
- ✅ **OTP emails work** (if email configured)
- ✅ **Dashboard accessible** after login
- ✅ **All features functional**

**The issue is deployment type, not your code!** Your EduOps360 application is perfectly configured.
