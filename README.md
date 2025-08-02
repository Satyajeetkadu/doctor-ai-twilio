# 🏥 Dr. Sunil Mishra's Derm & Hair AI Assistant

An AI-powered WhatsApp assistant for Dr. Sunil Mishra's Hair & Trichology clinic. It allows patients to get information on hair health conditions and book, reschedule, or cancel appointments through natural conversation.

## 🚀 Features

- **Specialized Hair Health Q&A**: Answers patient questions on hair symptoms, products, and lifestyle
- **Natural Language Appointment Management**: Book, reschedule, and cancel appointments with simple commands
- **WhatsApp Integration**: Communicate directly through WhatsApp for all your needs
- **AI-Powered**: Uses Google Gemini for natural language understanding and medical guidance
- **Real-time Booking**: Checks availability and books consultation slots instantly  
- **Google Calendar**: Automatically creates calendar events for consultations
- **Database Management**: Stores patient info and consultation history

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python)
- **AI**: Google Gemini 1.5 Flash
- **Database**: Supabase (PostgreSQL)
- **Messaging**: Twilio WhatsApp API
- **Calendar**: Google Calendar API
- **Deployment**: Render

## 📋 Prerequisites

Before starting, ensure you have:

1. **Twilio Account** with WhatsApp sandbox set up
2. **Supabase Account** and project
3. **Google Cloud Platform** account for Gemini and Calendar APIs
4. **Render Account** for deployment
5. **Python 3.12** installed locally

## ⚙️ Setup Instructions

### 1. Clone and Setup Environment

```bash
# Navigate to project directory
cd backend

# Create virtual environment
python3.12 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the `backend` directory:

```env
# Twilio Configuration
TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
TWILIO_PHONE_NUMBER=your_twilio_whatsapp_number_here

# Supabase Configuration (Get from your Supabase project)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_role_key

# Google Configuration
GEMINI_API_KEY=your_gemini_api_key

# Render Configuration
RENDER_API_KEY=rnd_bPsdBK0GNsh87IZtpauuUAdFAd7D
```

### 3. Database Setup

1. **Create Supabase Project**:
   - Go to [Supabase](https://supabase.com)
   - Create a new project named `doctor_ai`
   - Copy the project URL and API keys

2. **Run Database Setup**:
   - Open Supabase SQL Editor
   - Copy and paste the contents of `database_setup.sql`
   - Execute the script

3. **Update Environment Variables**:
   - Add your Supabase URL and keys to `.env`

### 4. Google Cloud Setup

1. **Create GCP Project**:
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project named `doctor-ai-clinic`

2. **Enable APIs**:
   - Enable Generative Language API (for Gemini)
   - Enable Google Calendar API

3. **Get API Keys**:
   - Create an API key for Gemini
   - For Calendar: Create OAuth 2.0 credentials and download `credentials.json`
   - Add Gemini API key to `.env`

### 5. Test the Application

```bash
# Run the test suite
python test_app.py
```

This will verify all connections and configurations.

### 6. Run Locally

```bash
# Start the FastAPI server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Visit `http://localhost:8000` to see the health check endpoint.

## 🚀 Deployment

### Using Render

1. **Initialize Git Repository**:
```bash
git init
git add .
git commit -m "Initial commit"
```

2. **Push to GitHub**:
```bash
# Create repository on GitHub, then:
git remote add origin https://github.com/yourusername/doctor-ai-whatsapp.git
git push -u origin main
```

3. **Deploy to Render**:
```bash
# The render.yaml file will automatically configure the deployment
# Just connect your GitHub repository to Render
```

4. **Configure Twilio Webhook**:
   - Go to Twilio Console > WhatsApp Sandbox
   - Set webhook URL to: `https://your-app-name.onrender.com/whatsapp-webhook`
   - Set HTTP method to POST

## 📱 Usage

### For Patients

1. **Join WhatsApp Sandbox**: Send the join code to the Twilio sandbox number
2. **Book Appointment**: Send messages like:
   - "I want to book an appointment"
   - "Book appointment"
   - "Schedule a visit"

3. **Select Slot**: Reply with the slot number (e.g., "1", "2", "3")
4. **Confirmation**: Receive confirmation with appointment details

### Sample Conversation

```
Patient: Hi, I need to book an appointment
Bot: Here are the available appointment slots:

1. Thursday, August 01 at 09:00 AM
2. Thursday, August 01 at 09:30 AM  
3. Thursday, August 01 at 10:00 AM
4. Friday, August 02 at 09:00 AM
5. Friday, August 02 at 09:30 AM

Reply with the number of your preferred slot (e.g., '1' for the first slot).

Patient: 2
Bot: ✅ Your appointment is confirmed!

📅 Date & Time: Thursday, August 01 at 09:30 AM
👨‍⚕️ Doctor: Dr. Sunil Mishra
📞 Phone: +1234567890

Please arrive 15 minutes early. If you need to reschedule, please contact us at least 24 hours in advance.
```

## 🧪 Testing

Run the test suite to verify everything is working:

```bash
python test_app.py
```

## 📁 Project Structure

```
backend/
├── main.py                 # FastAPI application entry point
├── requirements.txt        # Python dependencies
├── .env                   # Environment variables (create this)
├── database_setup.sql     # Database schema and initial data
├── render.yaml           # Render deployment configuration
├── test_app.py           # Test suite
├── README.md             # This file
└── services/
    ├── __init__.py       # Python package
    ├── gemini_service.py # AI intent analysis
    ├── supabase_service.py # Database operations
    ├── twilio_service.py # WhatsApp messaging
    └── gcal_service.py   # Google Calendar integration
```

## 🔧 API Endpoints

- `GET /` - Health check
- `POST /whatsapp-webhook` - Twilio WhatsApp webhook
- `GET /status` - Service status

## 🐛 Troubleshooting

### Common Issues

1. **Twilio Webhook Errors**:
   - Verify webhook URL is correct
   - Check that the server is accessible from the internet
   - Ensure endpoint returns valid TwiML

2. **Database Connection Issues**:
   - Verify Supabase credentials in `.env`
   - Check if database tables exist
   - Run `database_setup.sql` if tables are missing

3. **Gemini API Errors**:
   - Verify API key is correct
   - Check if Generative Language API is enabled
   - Monitor API quotas and usage

4. **Google Calendar Issues**:
   - Ensure OAuth credentials are set up correctly
   - Calendar API integration is optional for MVP

### Logs

Check application logs in Render dashboard or run locally with:

```bash
uvicorn main:app --log-level debug
```

## 🔮 Future Enhancements

- **Patient Intake Forms**: QR code-based intake questionnaires
- **Treatment Engine**: RAG-powered post-procedure care instructions
- **Multi-language Support**: Support for multiple languages
- **Advanced Scheduling**: Recurring appointments and reminders
- **Analytics Dashboard**: Appointment analytics and insights

## 📄 License

This project is for demonstration purposes. Please ensure compliance with healthcare regulations in your jurisdiction.

## 🤝 Support

For support or questions, please contact the development team or check the application logs for detailed error information. 