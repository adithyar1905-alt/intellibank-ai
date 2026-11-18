import unittest
from decimal import Decimal

from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, configure_mappers

from app.database import check_database_connection, create_database_engine
from app.models import (
    AccountType,
    BankAccount,
    Base,
    Customer,
    KYCDocument,
    Permission,
    Role,
    Transaction,
    User,
)


class DatabaseArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configure_mappers()

    def setUp(self) -> None:
        self.engine = create_database_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_database_connection_executes_select_one(self) -> None:
        check_database_connection(self.engine)
        with self.engine.connect() as connection:
            self.assertEqual(
                connection.execute(text("PRAGMA foreign_keys")).scalar_one(), 1
            )

    def test_all_requested_tables_are_registered(self) -> None:
        expected = {
            "users",
            "roles",
            "permissions",
            "customers",
            "kyc_documents",
            "bank_accounts",
            "account_types",
            "transactions",
            "beneficiaries",
            "loans",
            "loan_applications",
            "loan_repayments",
            "cards",
            "notifications",
            "audit_logs",
            "fraud_alerts",
        }
        self.assertTrue(expected.issubset(inspect(self.engine).get_table_names()))

    def test_relationships_persist_and_password_is_hash_only(self) -> None:
        user = User(email="customer@example.test", password_hash="argon2id$example")
        role = Role(name="customer")
        permission = Permission(
            name="accounts:read", resource="accounts", action="read"
        )
        role.permissions.append(permission)
        user.roles.append(role)
        customer = Customer(
            customer_number="CUST-0001",
            first_name="Ada",
            last_name="Lovelace",
            user=user,
        )
        account_type = AccountType(code="checking", name="Checking")
        account = BankAccount(
            customer=customer,
            account_type=account_type,
            account_number="000123456789",
            currency="USD",
            current_balance=Decimal("100.2500"),
        )
        document = KYCDocument(
            customer=customer,
            document_type="identity",
            document_reference="private/customer/document",
        )

        self.session.add_all([user, account_type, account, document])
        self.session.commit()

        self.assertEqual(user.customer.customer_number, "CUST-0001")
        self.assertEqual(user.roles[0].permissions[0].action, "read")
        self.assertEqual(account.customer.user.email, "customer@example.test")
        self.assertEqual(account.current_balance, Decimal("100.2500"))
        self.assertEqual(document.customer_id, customer.id)
        self.assertIn("password_hash", User.__table__.columns)
        self.assertNotIn("password", User.__table__.columns)

    def test_transaction_amount_constraint_rejects_zero(self) -> None:
        user = User(email="valid@example.test", password_hash="argon2id$example")
        customer = Customer(
            customer_number="CUST-0002",
            first_name="Grace",
            last_name="Hopper",
            user=user,
        )
        account_type = AccountType(code="savings", name="Savings")
        account = BankAccount(
            customer=customer,
            account_type=account_type,
            account_number="000987654321",
        )
        self.session.add(account)
        self.session.flush()
        self.session.add(
            Transaction(
                reference="TXN-INVALID",
                account=account,
                transaction_type="deposit",
                amount=Decimal("0"),
            )
        )

        with self.assertRaises(IntegrityError):
            self.session.flush()
