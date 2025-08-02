# 🗓️ Google Calendar Setup Guide for Email Invitations

This guide will help you set up Google Calendar integration with **email invitation support** for your Doctor AI WhatsApp Assistant.

## 📧 **Problem**: Calendar Events Created But No Email Invitations

Currently, your system creates calendar events successfully but can't send email invitations because Google Calendar service accounts need **Domain-Wide Delegation** to invite attendees.

## 🎯 **Solutions Available**

### **Option 1: Enable Domain-Wide Delegation (Recommended)**
✅ **Best solution** - Enables automatic email invitations  
✅ **Professional setup** - Works like a real clinic calendar  
✅ **Full integration** - Patients get proper calendar invites  

### **Option 2: Email Notification Fallback**
✅ **Alternative solution** - Custom email notifications  
✅ **No Google Workspace required** - Works with any email service  
✅ **Add-to-calendar links** - Patients can manually add events  

---

## 🚀 **Option 1: Domain-Wide Delegation Setup**

### **Prerequisites**
- Google Workspace account (not personal Gmail)
- Domain administrator access
- Existing service account (you already have this)

### **Step 1: Enable Domain-Wide Delegation**

1. **Go to Google Cloud Console**
   ```
   https://console.cloud.google.com/
   ```

2. **Navigate to IAM & Admin > Service Accounts**
   - Find your existing service account
   - Click on it to open details

3. **Enable Domain-Wide Delegation**
   - Click "Enable Google Workspace Domain-wide Delegation"
   - Add a product name: "Doctor AI Calendar Integration"
   - Save the changes

4. **Note the Client ID**
   - Copy the "Unique ID" (Client ID) - you'll need this

### **Step 2: Configure Google Workspace Admin Console**

1. **Go to Google Workspace Admin Console**
   ```
   https://admin.google.com/
   ```

2. **Navigate to Security > API Controls**

3. **Add Domain-Wide Delegation**
   - Click "Add new" in the Domain-wide delegation section
   - **Client ID**: [Paste the Client ID from Step 1]
   - **OAuth Scopes**: 
     ```
     https://www.googleapis.com/auth/calendar,
     https://www.googleapis.com/auth/calendar.events
     ```
   - Click "Authorize"

### **Step 3: Update Environment Variables**

Add these to your `.env` file:

```bash
# Existing variables (keep these)
GOOGLE_SERVICE_ACCOUNT_JSON={"your":"existing","service":"account","json":"here"}

# New variables for Domain-Wide Delegation
GOOGLE_DOMAIN_WIDE_DELEGATION=true
GOOGLE_CALENDAR_ORGANIZER_EMAIL=doctor@yourdomain.com

# Optional: Specific calendar ID (leave empty to use primary)
GOOGLE_CALENDAR_ID=primary
```

### **Step 4: Test the Setup**

Restart your server and book a test appointment. You should see:

```
INFO:services.gcal_service:Using domain-wide delegation with organizer: doctor@yourdomain.com
INFO:services.gcal_service:Calendar event created successfully with email invitation: [event_id]
```

---

## 📧 **Option 2: Email Notification Fallback**

If you can't set up Domain-Wide Delegation, enable email notifications:

### **Step 1: Choose Email Provider**

**Option A: SendGrid** (Recommended)
```bash
pip install sendgrid
```

**Option B: SMTP** (Use your existing email)
```bash
# Uses built-in smtplib
```

### **Step 2: Update Environment Variables**

```bash
# Enable email notifications
EMAIL_SERVICE_ENABLED=true
EMAIL_PROVIDER=sendgrid  # or 'smtp'

# SendGrid configuration
SENDGRID_API_KEY=your_sendgrid_api_key
SENDGRID_FROM_EMAIL=noreply@yourdomain.com

# OR SMTP configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=your_email@gmail.com

# Organizer email (appears in notifications)
GOOGLE_CALENDAR_ORGANIZER_EMAIL=doctor@yourdomain.com
```

### **Step 3: Implement Email Service** (if using SendGrid)

Install and configure SendGrid:

```bash
pip install sendgrid
```

The system will automatically use email notifications when calendar invitations fail.

---

## 🔧 **Quick Setup Script**

Run this to enable the most basic setup:

```bash
# Navigate to your backend directory
cd /path/to/your/backend

# Add basic email fallback (no external dependencies)
echo "EMAIL_SERVICE_ENABLED=false" >> .env
echo "GOOGLE_DOMAIN_WIDE_DELEGATION=false" >> .env
echo "GOOGLE_CALENDAR_ORGANIZER_EMAIL=doctor@example.com" >> .env

# Restart your server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## ✅ **Testing Your Setup**

### **Test 1: Check Calendar Service**
```bash
curl http://localhost:8000/status
```

### **Test 2: Book Test Appointment**
Send WhatsApp messages:
1. "Hello" 
2. "book appointment"
3. Follow the flow...

### **Test 3: Check Logs**

**Domain-Wide Delegation Working:**
```
INFO:services.gcal_service:Using domain-wide delegation with organizer: doctor@yourdomain.com
INFO:services.gcal_service:Calendar event created successfully with email invitation
```

**Email Fallback Working:**
```
INFO:services.gcal_service:Calendar event created with email notification fallback
INFO:services.gcal_service:Appointment confirmation email sent to patient@email.com
```

---

## 🎯 **Expected Results**

### **With Domain-Wide Delegation:**
✅ Calendar event created in doctor's calendar  
✅ **Patient receives Google Calendar invitation email**  
✅ Patient can RSVP directly in Gmail/Calendar  
✅ Automatic reminders from Google Calendar  

### **With Email Notifications:**
✅ Calendar event created in service account calendar  
✅ **Patient receives custom email notification**  
✅ Patient gets "Add to Calendar" links  
✅ Professional appointment confirmation  

---

## 🚨 **Troubleshooting**

### **Issue: Still no email invitations**
```bash
# Check if Domain-Wide Delegation is enabled
grep -i "domain" your.log

# Verify environment variables
echo $GOOGLE_DOMAIN_WIDE_DELEGATION
echo $GOOGLE_CALENDAR_ORGANIZER_EMAIL
```

### **Issue: "forbiddenForServiceAccounts" error**
This means Domain-Wide Delegation is not properly configured. Check:
1. Client ID is correct in Google Workspace Admin
2. Scopes are exactly as specified
3. Service account has delegation enabled

### **Issue: No email notifications**
```bash
# Check email service configuration
echo $EMAIL_SERVICE_ENABLED
echo $EMAIL_PROVIDER
```

---

## 💡 **Which Option Should You Choose?**

| Scenario | Recommendation |
|----------|----------------|
| **You have Google Workspace** | Use Domain-Wide Delegation |
| **You use personal Gmail** | Use Email Notifications |
| **You want professional integration** | Use Domain-Wide Delegation |
| **Quick setup needed** | Use Email Notifications |

---

## 🆘 **Need Help?**

If you're having issues:

1. **Check the logs** for specific error messages
2. **Test with a simple appointment booking**
3. **Verify all environment variables are set**
4. **Make sure your Google Calendar credentials are valid**

The system will work either way - the choice is between Google's native invitations vs. custom email notifications! 