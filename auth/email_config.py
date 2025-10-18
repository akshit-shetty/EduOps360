# email_config.py - Office365 SMTP email configuration
import os
from dataclasses import dataclass
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class EmailAccount:
    """Email account configuration"""
    name: str
    email: str
    password: str
    smtp_server: str = 'smtp-mail.outlook.com'
    smtp_port: int = 587
    use_tls: bool = True
    
    def __str__(self):
        return f"{self.name} ({self.email})"

class EmailAccountManager:
    """Manages Office365 email accounts for SMTP"""
    
    def __init__(self):
        self.accounts: Dict[str, EmailAccount] = {}
        self._load_accounts()
    
    def _get_smtp_config(self, email_address):
        """Office365 SMTP configuration with Render-optimized settings"""
        # Multiple Office 365 SMTP configurations for maximum compatibility
        return [
            # Primary Office 365 SMTP
            ('smtp-mail.outlook.com', 587, True),
            # Alternative Office 365 SMTP
            ('smtp.office365.com', 587, True),
            # Office 365 SSL (more reliable on some cloud platforms)
            ('smtp-mail.outlook.com', 465, False),  # SSL instead of TLS
            # Gmail fallback (if Office 365 fails)
            ('smtp.gmail.com', 587, True),
            ('smtp.gmail.com', 465, False)  # Gmail SSL
        ]

    def _load_accounts(self):
        """Load Office365 email accounts from environment variables"""
        # Primary Account: Office365 Email (Default for OTP)
        email_address = os.getenv('EMAIL_ADDRESS')
        email_password = os.getenv('EMAIL_PASSWORD')
        email_display_name = os.getenv('EMAIL_DISPLAY_NAME', 'EduOps360 System')
        
        if email_address and email_password:
            # Use primary Office365 SMTP settings
            smtp_configs = self._get_smtp_config(email_address)
            primary_config = smtp_configs[0]  # Use first configuration
            
            self.accounts['primary'] = EmailAccount(
                name=email_display_name,
                email=email_address,
                password=email_password,
                smtp_server=primary_config[0],
                smtp_port=primary_config[1],
                use_tls=primary_config[2]
            )
            print(f"✅ Primary Office365 account configured: {email_display_name} ({email_address})")
        else:
            print("⚠️  WARNING: EMAIL_ADDRESS and EMAIL_PASSWORD not found in environment variables")
            print("   Please configure your Office365 email settings in the .env file")
            print("   Required variables: EMAIL_ADDRESS, EMAIL_PASSWORD, EMAIL_DISPLAY_NAME")
        
        # Secondary Account: Office365 Email (Optional)
        email_address_secondary = os.getenv('EMAIL_ADDRESS_SECONDARY')
        email_password_secondary = os.getenv('EMAIL_PASSWORD_SECONDARY')
        email_display_name_secondary = os.getenv('EMAIL_DISPLAY_NAME_SECONDARY', 'EduOps360 Secondary')
        
        if email_address_secondary and email_password_secondary:
            # Use primary Office365 SMTP settings for secondary account too
            smtp_configs = self._get_smtp_config(email_address_secondary)
            secondary_config = smtp_configs[0]  # Use first configuration
            
            self.accounts['secondary'] = EmailAccount(
                name=email_display_name_secondary,
                email=email_address_secondary,
                password=email_password_secondary,
                smtp_server=secondary_config[0],
                smtp_port=secondary_config[1],
                use_tls=secondary_config[2]
            )
            print(f"✅ Secondary Office365 account configured: {email_display_name_secondary} ({email_address_secondary})")
        else:
            print("ℹ️  Secondary email account not configured (optional)")
            print("   Use EMAIL_ADDRESS_SECONDARY and EMAIL_PASSWORD_SECONDARY if needed")
    
    def get_account(self, account_key: str) -> Optional[EmailAccount]:
        """Get email account by key"""
        return self.accounts.get(account_key)
    
    def get_account_by_email(self, email: str) -> Optional[EmailAccount]:
        """Get email account by email address"""
        for account in self.accounts.values():
            if account.email.lower() == email.lower():
                return account
        return None
    
    def list_accounts(self) -> List[Dict[str, str]]:
        """List all available accounts for UI selection"""
        return [
            {
                'key': key,
                'name': account.name,
                'email': account.email
            }
            for key, account in self.accounts.items()
        ]
    
    def get_default_account(self) -> EmailAccount:
        """Get the default account (primary account for OTP)"""
        # Always return primary account as default for OTP
        return self.accounts.get('primary') or list(self.accounts.values())[0] if self.accounts else None
    
    def get_otp_account(self) -> EmailAccount:
        """Get the account to use for OTP emails (GGU DBA ET Operations)"""
        # Primary account is configured as GGU DBA ET Operations for OTP
        return self.accounts.get('primary')
    
    def validate_account(self, account_key: str) -> bool:
        """Validate if account exists and has required credentials"""
        account = self.get_account(account_key)
        if not account:
            return False
        return bool(account.email and account.password)

# Global instance
email_manager = EmailAccountManager()

# Convenience functions
def get_email_accounts() -> List[Dict[str, str]]:
    """Get list of email accounts for UI"""
    return email_manager.list_accounts()

def get_account_by_key(account_key: str) -> Optional[EmailAccount]:
    """Get email account by key"""
    return email_manager.get_account(account_key)

def get_default_account() -> EmailAccount:
    """Get default email account"""
    return email_manager.get_default_account()

def get_otp_account() -> EmailAccount:
    """Get the email account for OTP (GGU DBA ET Operations)"""
    return email_manager.get_otp_account()
