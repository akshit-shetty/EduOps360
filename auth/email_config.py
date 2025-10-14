# email_config.py - Multi-account SMTP email configuration
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
    smtp_server: str = 'smtp.gmail.com'
    smtp_port: int = 587
    use_tls: bool = True
    
    def __str__(self):
        return f"{self.name} ({self.email})"

class EmailAccountManager:
    """Manages multiple email accounts for SMTP"""
    
    def __init__(self):
        self.accounts: Dict[str, EmailAccount] = {}
        self._load_accounts()
    
    def _load_accounts(self):
        """Load email accounts from environment variables"""
        # Primary Account: GGU DBA ET Operations (Default for OTP)
        email_address = os.getenv('EMAIL_ADDRESS')
        email_password = os.getenv('EMAIL_PASSWORD')
        email_display_name = os.getenv('EMAIL_DISPLAY_NAME', 'GGU DBA ET Operations')
        
        if email_address and email_password:
            self.accounts['primary'] = EmailAccount(
                name=email_display_name,
                email=email_address,
                password=email_password,
                smtp_server=os.getenv('EMAIL_SMTP_SERVER', 'smtp-mail.outlook.com'),
                smtp_port=int(os.getenv('EMAIL_SMTP_PORT', '587')),
                use_tls=os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
            )
        else:
            print("⚠️  WARNING: EMAIL_ADDRESS and EMAIL_PASSWORD not found in environment variables")
            print("   Please configure your primary email settings in the .env file")
        
        # Secondary Account: GGU Gen AI Queries
        email_address_secondary = os.getenv('EMAIL_ADDRESS_SECONDARY')
        email_password_secondary = os.getenv('EMAIL_PASSWORD_SECONDARY')
        email_display_name_secondary = os.getenv('EMAIL_DISPLAY_NAME_SECONDARY', 'GGU Gen AI Queries')
        
        if email_address_secondary and email_password_secondary:
            self.accounts['secondary'] = EmailAccount(
                name=email_display_name_secondary,
                email=email_address_secondary,
                password=email_password_secondary,
                smtp_server=os.getenv('EMAIL_SMTP_SERVER', 'smtp-mail.outlook.com'),
                smtp_port=int(os.getenv('EMAIL_SMTP_PORT', '587')),
                use_tls=os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
            )
        else:
            print("⚠️  WARNING: EMAIL_ADDRESS_SECONDARY and EMAIL_PASSWORD_SECONDARY not found in environment variables")
            print("   Secondary email account (GGU Gen AI Queries) will not be available")
    
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
