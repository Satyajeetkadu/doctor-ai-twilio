#!/usr/bin/env python3
"""
Quick Setup Script for Google Calendar Email Invitations
Configures the basic environment variables needed for calendar invitations.
"""

import os
from pathlib import Path

def setup_calendar_invitations():
    """Configure calendar invitation settings."""
    
    print("🗓️ Doctor AI - Calendar Invitation Setup")
    print("=" * 50)
    
    # Find .env file
    env_file = Path('.env')
    if not env_file.exists():
        print("❌ .env file not found. Creating a new one...")
        env_file.touch()
    
    # Read existing .env content
    existing_env = {}
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    existing_env[key] = value
    
    print(f"📁 Found .env file: {env_file.absolute()}")
    print()
    
    # Configuration options
    print("🎯 Choose your setup option:")
    print("1. 🚀 Domain-Wide Delegation (Google Workspace required)")
    print("2. 📧 Email Notifications (Works with any email service)")
    print("3. 🔧 Basic Setup (Calendar only, no invitations)")
    print()
    
    choice = input("Enter your choice (1-3): ").strip()
    
    new_vars = {}
    
    if choice == "1":
        print("\n🚀 Setting up Domain-Wide Delegation...")
        print("Prerequisites: Google Workspace account with admin access")
        print()
        
        # Get organizer email
        organizer_email = input("Enter the doctor/clinic email address: ").strip()
        if not organizer_email:
            organizer_email = "doctor@example.com"
        
        new_vars.update({
            'GOOGLE_DOMAIN_WIDE_DELEGATION': 'true',
            'GOOGLE_CALENDAR_ORGANIZER_EMAIL': organizer_email,
            'EMAIL_SERVICE_ENABLED': 'false'
        })
        
        print(f"✅ Configured for Domain-Wide Delegation with organizer: {organizer_email}")
        print()
        print("🔧 Next Steps:")
        print("1. Follow the guide in GOOGLE_CALENDAR_SETUP.md")
        print("2. Enable Domain-Wide Delegation in Google Cloud Console")
        print("3. Configure scopes in Google Workspace Admin Console")
        
    elif choice == "2":
        print("\n📧 Setting up Email Notifications...")
        
        # Get organizer email
        organizer_email = input("Enter the doctor/clinic email address: ").strip()
        if not organizer_email:
            organizer_email = "doctor@example.com"
        
        # Choose email provider
        print("\nChoose email provider:")
        print("1. SendGrid (Recommended)")
        print("2. SMTP (Use existing email)")
        email_choice = input("Enter choice (1-2): ").strip()
        
        if email_choice == "1":
            print("\n📮 SendGrid Setup:")
            sendgrid_key = input("Enter SendGrid API key (or leave empty): ").strip()
            sendgrid_from = input(f"Enter 'from' email address [{organizer_email}]: ").strip()
            if not sendgrid_from:
                sendgrid_from = organizer_email
            
            new_vars.update({
                'EMAIL_SERVICE_ENABLED': 'true',
                'EMAIL_PROVIDER': 'sendgrid',
                'SENDGRID_API_KEY': sendgrid_key or 'your_sendgrid_api_key_here',
                'SENDGRID_FROM_EMAIL': sendgrid_from,
                'GOOGLE_CALENDAR_ORGANIZER_EMAIL': organizer_email,
                'GOOGLE_DOMAIN_WIDE_DELEGATION': 'false'
            })
            
            if not sendgrid_key:
                print("⚠️  Remember to set your actual SendGrid API key later!")
        
        else:
            print("\n📨 SMTP Setup:")
            smtp_host = input("SMTP host [smtp.gmail.com]: ").strip() or "smtp.gmail.com"
            smtp_port = input("SMTP port [587]: ").strip() or "587"
            smtp_user = input(f"SMTP username [{organizer_email}]: ").strip() or organizer_email
            smtp_pass = input("SMTP password (app password recommended): ").strip()
            
            new_vars.update({
                'EMAIL_SERVICE_ENABLED': 'true',
                'EMAIL_PROVIDER': 'smtp',
                'SMTP_HOST': smtp_host,
                'SMTP_PORT': smtp_port,
                'SMTP_USERNAME': smtp_user,
                'SMTP_PASSWORD': smtp_pass or 'your_smtp_password_here',
                'SMTP_FROM_EMAIL': smtp_user,
                'GOOGLE_CALENDAR_ORGANIZER_EMAIL': organizer_email,
                'GOOGLE_DOMAIN_WIDE_DELEGATION': 'false'
            })
            
            if not smtp_pass:
                print("⚠️  Remember to set your actual SMTP password later!")
        
        print(f"✅ Configured for email notifications with organizer: {organizer_email}")
    
    else:
        print("\n🔧 Basic Setup (Calendar events only)...")
        
        organizer_email = input("Enter the doctor/clinic email address: ").strip()
        if not organizer_email:
            organizer_email = "doctor@example.com"
        
        new_vars.update({
            'GOOGLE_DOMAIN_WIDE_DELEGATION': 'false',
            'EMAIL_SERVICE_ENABLED': 'false',
            'GOOGLE_CALENDAR_ORGANIZER_EMAIL': organizer_email
        })
        
        print(f"✅ Basic setup complete with organizer: {organizer_email}")
        print("📝 Calendar events will be created but no automatic invitations will be sent")
    
    # Update .env file
    print(f"\n📝 Updating {env_file}...")
    
    # Merge with existing variables
    existing_env.update(new_vars)
    
    # Write updated .env file
    with open(env_file, 'w') as f:
        for key, value in existing_env.items():
            f.write(f"{key}={value}\n")
    
    print("✅ Environment variables updated!")
    print()
    print("🎯 Summary of changes:")
    for key, value in new_vars.items():
        # Mask sensitive values
        display_value = value
        if 'password' in key.lower() or 'key' in key.lower():
            display_value = '***' if value and value != f'your_{key.lower()}_here' else value
        print(f"  {key}={display_value}")
    
    print()
    print("🚀 Next Steps:")
    print("1. Restart your server:")
    print("   uvicorn main:app --host 0.0.0.0 --port 8000 --reload")
    print()
    print("2. Test appointment booking:")
    print("   Send 'Hello' to your WhatsApp number")
    print()
    print("3. Check logs for invitation status:")
    print("   Look for 'invitation_sent' and 'email_notification_sent' in logs")
    print()
    print("📖 For detailed setup instructions, see: GOOGLE_CALENDAR_SETUP.md")

if __name__ == "__main__":
    try:
        setup_calendar_invitations()
    except KeyboardInterrupt:
        print("\n👋 Setup cancelled by user")
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        print("Please check the error and try again") 