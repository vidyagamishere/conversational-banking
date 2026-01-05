"""Seed the database with sample data."""
from datetime import datetime, timedelta
from sqlmodel import Session, select
from database import engine
from models import (
    Customer, Account, Transaction, AccountType,
    OperationType, TransactionStatus, SQLModel
)
from auth import get_pin_hash


def seed_database():
    """Seed database with sample customers, accounts, and transactions."""
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # Check if data already exists
        existing = session.exec(select(Customer)).first()
        if existing:
            print("Database already seeded. Skipping...")
            return
        
        # Create Customer 1 (English)
        customer1 = Customer(
            name="John Doe",
            primary_email="john.doe@example.com",
            preferred_language="en"
        )
        session.add(customer1)
        session.commit()
        session.refresh(customer1)
        
        # Create Customer 2 (Spanish)
        customer2 = Customer(
            name="Maria Garcia",
            primary_email="maria.garcia@example.com",
            preferred_language="es"
        )
        session.add(customer2)
        session.commit()
        session.refresh(customer2)
        
        # Create accounts for Customer 1
        checking1 = Account(
            customer_id=customer1.id,
            type=AccountType.CHECKING,
            currency="USD",
            balance=2500.00,
            status="ACTIVE"
        )
        savings1 = Account(
            customer_id=customer1.id,
            type=AccountType.SAVINGS,
            currency="USD",
            balance=4200.00,
            status="ACTIVE"
        )
        session.add_all([checking1, savings1])
        session.commit()
        session.refresh(checking1)
        session.refresh(savings1)
        
        # Create accounts for Customer 2
        checking2 = Account(
            customer_id=customer2.id,
            type=AccountType.CHECKING,
            currency="USD",
            balance=1800.00,
            status="ACTIVE"
        )
        savings2 = Account(
            customer_id=customer2.id,
            type=AccountType.SAVINGS,
            currency="USD",
            balance=3600.00,
            status="ACTIVE"
        )
        session.add_all([checking2, savings2])
        session.commit()
        session.refresh(checking2)
        session.refresh(savings2)
        
        # Create historical transactions for Customer 1
        transactions1 = [
            Transaction(
                operation=OperationType.DEPOSIT,
                from_account_id=None,
                to_account_id=checking1.id,
                amount=1000.00,
                currency="USD",
                status=TransactionStatus.COMPLETED,
                timestamp=datetime.utcnow() - timedelta(days=10),
                details='{"description": "Payroll deposit"}'
            ),
            Transaction(
                operation=OperationType.WITHDRAW,
                from_account_id=checking1.id,
                to_account_id=None,
                amount=200.00,
                currency="USD",
                status=TransactionStatus.COMPLETED,
                timestamp=datetime.utcnow() - timedelta(days=8),
                details='{"description": "ATM withdrawal"}'
            ),
            Transaction(
                operation=OperationType.TRANSFER,
                from_account_id=checking1.id,
                to_account_id=savings1.id,
                amount=500.00,
                currency="USD",
                status=TransactionStatus.COMPLETED,
                timestamp=datetime.utcnow() - timedelta(days=5),
                details='{"description": "Transfer to savings"}'
            ),
            Transaction(
                operation=OperationType.PAYMENT,
                from_account_id=checking1.id,
                to_account_id=None,
                amount=150.00,
                currency="USD",
                status=TransactionStatus.COMPLETED,
                timestamp=datetime.utcnow() - timedelta(days=3),
                details='{"description": "Utility payment"}'
            ),
            Transaction(
                operation=OperationType.DEPOSIT,
                from_account_id=None,
                to_account_id=savings1.id,
                amount=300.00,
                currency="USD",
                status=TransactionStatus.COMPLETED,
                timestamp=datetime.utcnow() - timedelta(days=1),
                details='{"description": "Interest credit"}'
            )
        ]
        session.add_all(transactions1)
        
        # Create historical transactions for Customer 2
        transactions2 = [
            Transaction(
                operation=OperationType.DEPOSIT,
                from_account_id=None,
                to_account_id=checking2.id,
                amount=800.00,
                currency="USD",
                status=TransactionStatus.COMPLETED,
                timestamp=datetime.utcnow() - timedelta(days=12),
                details='{"description": "Payroll deposit"}'
            ),
            Transaction(
                operation=OperationType.WITHDRAW,
                from_account_id=checking2.id,
                to_account_id=None,
                amount=100.00,
                currency="USD",
                status=TransactionStatus.COMPLETED,
                timestamp=datetime.utcnow() - timedelta(days=9),
                details='{"description": "ATM withdrawal"}'
            ),
            Transaction(
                operation=OperationType.TRANSFER,
                from_account_id=savings2.id,
                to_account_id=checking2.id,
                amount=300.00,
                currency="USD",
                status=TransactionStatus.COMPLETED,
                timestamp=datetime.utcnow() - timedelta(days=6),
                details='{"description": "Transfer from savings"}'
            ),
            Transaction(
                operation=OperationType.PAYMENT,
                from_account_id=checking2.id,
                to_account_id=None,
                amount=120.00,
                currency="USD",
                status=TransactionStatus.COMPLETED,
                timestamp=datetime.utcnow() - timedelta(days=4),
                details='{"description": "Internet payment"}'
            ),
            Transaction(
                operation=OperationType.DEPOSIT,
                from_account_id=None,
                to_account_id=savings2.id,
                amount=250.00,
                currency="USD",
                status=TransactionStatus.COMPLETED,
                timestamp=datetime.utcnow() - timedelta(days=2),
                details='{"description": "Interest credit"}'
            )
        ]
        session.add_all(transactions2)
        
        session.commit()
        
        print("✅ Database seeded successfully!")
        print(f"Customer 1: {customer1.name} - Card: 4111111111111111, PIN: 1234")
        print(f"  Checking ({checking1.id}): ${checking1.balance}")
        print(f"  Savings ({savings1.id}): ${savings1.balance}")
        print(f"Customer 2: {customer2.name} - Card: 4222222222222222, PIN: 5678")
        print(f"  Checking ({checking2.id}): ${checking2.balance}")
        print(f"  Savings ({savings2.id}): ${savings2.balance}")


if __name__ == "__main__":
    seed_database()
