"""Email service for sending transaction receipts."""
import asyncio
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Any
from jinja2 import Template
from config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


# HTML Email Templates
WITHDRAWAL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><style>
body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
.container { max-width: 600px; margin: 0 auto; padding: 20px; }
.header { background: #667eea; color: white; padding: 20px; text-align: center; }
.content { padding: 20px; background: #f9f9f9; }
.details { background: white; padding: 15px; margin: 10px 0; border-radius: 5px; }
.row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; }
.label { font-weight: bold; }
.footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
</style></head>
<body>
<div class="container">
    <div class="header">
        <h2>ATM Withdrawal Receipt</h2>
    </div>
    <div class="content">
        <div class="details">
            <div class="row"><span class="label">Transaction ID:</span><span>{{transaction_id}}</span></div>
            <div class="row"><span class="label">Date:</span><span>{{date}}</span></div>
            <div class="row"><span class="label">Account:</span><span>{{account_number}}</span></div>
            <div class="row"><span class="label">Amount Withdrawn:</span><span>${{amount}}</span></div>
            <div class="row"><span class="label">New Balance:</span><span>${{new_balance}}</span></div>
            <div class="row"><span class="label">Location:</span><span>{{location}}</span></div>
        </div>
    </div>
    <div class="footer">
        <p>Thank you for banking with us!</p>
        <p>This is an automated email. Please do not reply.</p>
    </div>
</div>
</body>
</html>
"""

CASH_DEPOSIT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><style>
body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
.container { max-width: 600px; margin: 0 auto; padding: 20px; }
.header { background: #48bb78; color: white; padding: 20px; text-align: center; }
.content { padding: 20px; background: #f9f9f9; }
.details { background: white; padding: 15px; margin: 10px 0; border-radius: 5px; }
.row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; }
.denomination { background: #f0f0f0; padding: 10px; margin: 10px 0; }
.label { font-weight: bold; }
.footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
</style></head>
<body>
<div class="container">
    <div class="header">
        <h2>Cash Deposit Receipt</h2>
    </div>
    <div class="content">
        <div class="details">
            <div class="row"><span class="label">Transaction ID:</span><span>{{transaction_id}}</span></div>
            <div class="row"><span class="label">Date:</span><span>{{date}}</span></div>
            <div class="row"><span class="label">Account:</span><span>{{account_number}}</span></div>
            <div class="denomination">
                <h4>Denomination Breakdown:</h4>
                <div class="row"><span>$100 Bills:</span><span>{{bills_100}} × $100 = ${{bills_100_total}}</span></div>
                <div class="row"><span>$50 Bills:</span><span>{{bills_50}} × $50 = ${{bills_50_total}}</span></div>
                <div class="row"><span>$20 Bills:</span><span>{{bills_20}} × $20 = ${{bills_20_total}}</span></div>
                <div class="row"><span>$10 Bills:</span><span>{{bills_10}} × $10 = ${{bills_10_total}}</span></div>
                <div class="row"><span>$5 Bills:</span><span>{{bills_5}} × $5 = ${{bills_5_total}}</span></div>
                <div class="row"><span>$1 Bills:</span><span>{{bills_1}} × $1 = ${{bills_1_total}}</span></div>
                <div class="row"><span>Coins:</span><span>${{coins_amount}}</span></div>
            </div>
            <div class="row"><span class="label">Total Deposited:</span><span>${{total_amount}}</span></div>
            <div class="row"><span class="label">New Balance:</span><span>${{new_balance}}</span></div>
        </div>
    </div>
    <div class="footer">
        <p>Thank you for banking with us!</p>
    </div>
</div>
</body>
</html>
"""

CHECK_DEPOSIT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><style>
body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
.container { max-width: 600px; margin: 0 auto; padding: 20px; }
.header { background: #4299e1; color: white; padding: 20px; text-align: center; }
.content { padding: 20px; background: #f9f9f9; }
.details { background: white; padding: 15px; margin: 10px 0; border-radius: 5px; }
.warning { background: #fff3cd; padding: 10px; margin: 10px 0; border-left: 4px solid #ffc107; }
.row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; }
.label { font-weight: bold; }
.footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
</style></head>
<body>
<div class="container">
    <div class="header">
        <h2>Check Deposit Receipt</h2>
    </div>
    <div class="content">
        <div class="details">
            <div class="row"><span class="label">Transaction ID:</span><span>{{transaction_id}}</span></div>
            <div class="row"><span class="label">Date:</span><span>{{date}}</span></div>
            <div class="row"><span class="label">Account:</span><span>{{account_number}}</span></div>
            <div class="row"><span class="label">Check Number:</span><span>{{check_number}}</span></div>
            <div class="row"><span class="label">Check Date:</span><span>{{check_date}}</span></div>
            <div class="row"><span class="label">Payer:</span><span>{{payer_name}}</span></div>
            <div class="row"><span class="label">Amount:</span><span>${{amount}}</span></div>
            <div class="row"><span class="label">Status:</span><span>{{status}}</span></div>
        </div>
        {% if hold_until_date %}
        <div class="warning">
            <strong>Important:</strong> Funds will be available on {{hold_until_date}}
        </div>
        {% endif %}
        <div class="details">
            <div class="row"><span class="label">New Balance:</span><span>${{new_balance}}</span></div>
        </div>
    </div>
    <div class="footer">
        <p>Thank you for banking with us!</p>
    </div>
</div>
</body>
</html>
"""

BILL_PAYMENT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><style>
body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
.container { max-width: 600px; margin: 0 auto; padding: 20px; }
.header { background: #ed8936; color: white; padding: 20px; text-align: center; }
.content { padding: 20px; background: #f9f9f9; }
.details { background: white; padding: 15px; margin: 10px 0; border-radius: 5px; }
.row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; }
.label { font-weight: bold; }
.footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
</style></head>
<body>
<div class="container">
    <div class="header">
        <h2>Bill Payment Receipt</h2>
    </div>
    <div class="content">
        <div class="details">
            <div class="row"><span class="label">Transaction ID:</span><span>{{transaction_id}}</span></div>
            <div class="row"><span class="label">Confirmation Number:</span><span>{{confirmation_number}}</span></div>
            <div class="row"><span class="label">Date:</span><span>{{date}}</span></div>
            <div class="row"><span class="label">From Account:</span><span>{{account_number}}</span></div>
            <div class="row"><span class="label">Payee:</span><span>{{payee_name}}</span></div>
            <div class="row"><span class="label">Amount Paid:</span><span>${{amount}}</span></div>
            <div class="row"><span class="label">New Balance:</span><span>${{new_balance}}</span></div>
            {% if is_recurring %}
            <div class="row"><span class="label">Recurring:</span><span>{{frequency}}</span></div>
            {% endif %}
        </div>
    </div>
    <div class="footer">
        <p>Thank you for banking with us!</p>
    </div>
</div>
</body>
</html>
"""

TRANSFER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><style>
body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
.container { max-width: 600px; margin: 0 auto; padding: 20px; }
.header { background: #9f7aea; color: white; padding: 20px; text-align: center; }
.content { padding: 20px; background: #f9f9f9; }
.details { background: white; padding: 15px; margin: 10px 0; border-radius: 5px; }
.row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; }
.label { font-weight: bold; }
.footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
</style></head>
<body>
<div class="container">
    <div class="header">
        <h2>Transfer Receipt</h2>
    </div>
    <div class="content">
        <div class="details">
            <div class="row"><span class="label">Transaction ID:</span><span>{{transaction_id}}</span></div>
            <div class="row"><span class="label">Date:</span><span>{{date}}</span></div>
            <div class="row"><span class="label">From Account:</span><span>{{from_account}}</span></div>
            <div class="row"><span class="label">To Account:</span><span>{{to_account}}</span></div>
            <div class="row"><span class="label">Amount Transferred:</span><span>${{amount}}</span></div>
            <div class="row"><span class="label">New Balance:</span><span>${{new_balance}}</span></div>
            {% if memo %}
            <div class="row"><span class="label">Memo:</span><span>{{memo}}</span></div>
            {% endif %}
        </div>
    </div>
    <div class="footer">
        <p>Thank you for banking with us!</p>
    </div>
</div>
</body>
</html>
"""


async def send_receipt_email(
    recipient_email: str,
    transaction_type: str,
    details: Dict[str, Any]
) -> bool:
    """
    Send transaction receipt email to customer.
    
    Args:
        recipient_email: Customer's email address
        transaction_type: Type of transaction (withdrawal, cash_deposit, check_deposit, bill_payment, transfer)
        details: Dictionary containing transaction details for template
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Select template based on transaction type
        template_map = {
            "withdrawal": WITHDRAWAL_TEMPLATE,
            "cash_deposit": CASH_DEPOSIT_TEMPLATE,
            "check_deposit": CHECK_DEPOSIT_TEMPLATE,
            "bill_payment": BILL_PAYMENT_TEMPLATE,
            "transfer": TRANSFER_TEMPLATE,
        }
        
        template_str = template_map.get(transaction_type.lower())
        if not template_str:
            logger.error(f"Unknown transaction type: {transaction_type}")
            return False
        
        # Render HTML template
        template = Template(template_str)
        html_content = template.render(**details)
        
        # Create email message
        message = MIMEMultipart("alternative")
        message["From"] = f"{settings.sender_name} <{settings.sender_email}>"
        message["To"] = recipient_email
        message["Subject"] = f"ATM Transaction Receipt - {transaction_type.replace('_', ' ').title()}"
        
        html_part = MIMEText(html_content, "html")
        message.attach(html_part)
        
        # Send email via SMTP
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            use_tls=settings.smtp_use_tls,
        )
        
        logger.info(f"Receipt email sent successfully to {recipient_email} for {transaction_type}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send receipt email: {str(e)}")
        return False


def format_withdrawal_details(
    transaction_id: int,
    account_number: str,
    amount: float,
    new_balance: float
) -> Dict[str, Any]:
    """Format withdrawal transaction details for email template."""
    return {
        "transaction_id": transaction_id,
        "date": datetime.now().strftime("%B %d, %Y %I:%M %p"),
        "account_number": account_number,
        "amount": f"{amount:.2f}",
        "new_balance": f"{new_balance:.2f}",
        "location": "ATM Web Terminal"
    }


def format_cash_deposit_details(
    transaction_id: int,
    account_number: str,
    denomination: Dict[str, int],
    new_balance: float
) -> Dict[str, Any]:
    """Format cash deposit details for email template."""
    bills_100_total = denomination.get("bills_100", 0) * 100
    bills_50_total = denomination.get("bills_50", 0) * 50
    bills_20_total = denomination.get("bills_20", 0) * 20
    bills_10_total = denomination.get("bills_10", 0) * 10
    bills_5_total = denomination.get("bills_5", 0) * 5
    bills_1_total = denomination.get("bills_1", 0) * 1
    coins_amount = denomination.get("coins_amount", 0)
    
    total = bills_100_total + bills_50_total + bills_20_total + bills_10_total + bills_5_total + bills_1_total + coins_amount
    
    return {
        "transaction_id": transaction_id,
        "date": datetime.now().strftime("%B %d, %Y %I:%M %p"),
        "account_number": account_number,
        "bills_100": denomination.get("bills_100", 0),
        "bills_100_total": f"{bills_100_total:.2f}",
        "bills_50": denomination.get("bills_50", 0),
        "bills_50_total": f"{bills_50_total:.2f}",
        "bills_20": denomination.get("bills_20", 0),
        "bills_20_total": f"{bills_20_total:.2f}",
        "bills_10": denomination.get("bills_10", 0),
        "bills_10_total": f"{bills_10_total:.2f}",
        "bills_5": denomination.get("bills_5", 0),
        "bills_5_total": f"{bills_5_total:.2f}",
        "bills_1": denomination.get("bills_1", 0),
        "bills_1_total": f"{bills_1_total:.2f}",
        "coins_amount": f"{coins_amount:.2f}",
        "total_amount": f"{total:.2f}",
        "new_balance": f"{new_balance:.2f}"
    }


def format_check_deposit_details(
    transaction_id: int,
    account_number: str,
    check_number: str,
    check_date: str,
    payer_name: str,
    amount: float,
    status: str,
    new_balance: float,
    hold_until_date: str = None
) -> Dict[str, Any]:
    """Format check deposit details for email template."""
    return {
        "transaction_id": transaction_id,
        "date": datetime.now().strftime("%B %d, %Y %I:%M %p"),
        "account_number": account_number,
        "check_number": check_number,
        "check_date": check_date,
        "payer_name": payer_name,
        "amount": f"{amount:.2f}",
        "status": status,
        "new_balance": f"{new_balance:.2f}",
        "hold_until_date": hold_until_date
    }


def format_bill_payment_details(
    transaction_id: int,
    confirmation_number: str,
    account_number: str,
    payee_name: str,
    amount: float,
    new_balance: float,
    is_recurring: bool = False,
    frequency: str = None
) -> Dict[str, Any]:
    """Format bill payment details for email template."""
    return {
        "transaction_id": transaction_id,
        "confirmation_number": confirmation_number,
        "date": datetime.now().strftime("%B %d, %Y %I:%M %p"),
        "account_number": account_number,
        "payee_name": payee_name,
        "amount": f"{amount:.2f}",
        "new_balance": f"{new_balance:.2f}",
        "is_recurring": is_recurring,
        "frequency": frequency
    }


def format_transfer_details(
    transaction_id: int,
    from_account: str,
    to_account: str,
    amount: float,
    new_balance: float,
    memo: str = None
) -> Dict[str, Any]:
    """Format transfer details for email template."""
    return {
        "transaction_id": transaction_id,
        "date": datetime.now().strftime("%B %d, %Y %I:%M %p"),
        "from_account": from_account,
        "to_account": to_account,
        "amount": f"{amount:.2f}",
        "new_balance": f"{new_balance:.2f}",
        "memo": memo
    }