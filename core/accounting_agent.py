"""
Accounting Agent - Phase 26
Accounting automation, journal entries, financial statements, reconciliation.
Fully local, no cloud dependencies.
"""

import os
import json
import time
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from core.context_engine import get_connection
from core.finance_agent import finance_agent


DB_DIR = "database"
ACCOUNTING_DB = os.path.join(DB_DIR, "accounting.db")

os.makedirs(DB_DIR, exist_ok=True)


def init_accounting_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Chart of Accounts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            account_type TEXT NOT NULL,  -- 'asset', 'liability', 'equity', 'revenue', 'expense'
            parent_id TEXT,
            description TEXT,
            is_active BOOLEAN DEFAULT 1,
            normal_balance TEXT,  -- 'debit', 'credit'
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (parent_id) REFERENCES accounts(id)
        )
    """)

    # Journal Entries
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS journal_entries (
            id TEXT PRIMARY KEY,
            entry_number TEXT UNIQUE NOT NULL,
            date REAL NOT NULL,
            description TEXT,
            reference TEXT,
            source TEXT,  -- 'manual', 'import', 'recurring', 'reversing'
            status TEXT DEFAULT 'draft',  -- 'draft', 'posted', 'reversed', 'voided'
            total_debit REAL NOT NULL DEFAULT 0,
            total_credit REAL NOT NULL DEFAULT 0,
            created_by TEXT,
            posted_at REAL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Journal Entry Lines
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS journal_entry_lines (
            id TEXT PRIMARY KEY,
            entry_id TEXT NOT NULL,
            line_number INTEGER NOT NULL,
            account_id TEXT NOT NULL,
            description TEXT,
            debit REAL DEFAULT 0,
            credit REAL DEFAULT 0,
            memo TEXT,
            FOREIGN KEY (entry_id) REFERENCES journal_entries(id),
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)

    # Ledger balances
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ledger_balances (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            period_start REAL NOT NULL,
            period_end REAL NOT NULL,
            opening_balance REAL DEFAULT 0,
            total_debits REAL DEFAULT 0,
            total_credits REAL DEFAULT 0,
            closing_balance REAL DEFAULT 0,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)

    # Reconciliation
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reconciliations (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            statement_date REAL NOT NULL,
            statement_balance REAL NOT NULL,
            book_balance REAL NOT NULL,
            difference REAL NOT NULL DEFAULT 0,
            status TEXT DEFAULT 'pending',  -- 'pending', 'matched', 'investigating', 'resolved'
            reconciled_at REAL,
            reconciled_by TEXT,
            notes TEXT,
            created_at REAL NOT NULL
        )
    """)

    # Reconciliation items
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reconciliation_items (
            id TEXT PRIMARY KEY,
            reconciliation_id TEXT NOT NULL,
            transaction_id TEXT,
            matched BOOLEAN DEFAULT 0,
            matched_at REAL,
            notes TEXT,
            FOREIGN KEY (reconciliation_id) REFERENCES reconciliations(id)
        )
    """)

    # Financial Statements
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS financial_statements (
            id TEXT PRIMARY KEY,
            statement_type TEXT NOT NULL,  -- 'balance_sheet', 'income_statement', 'cash_flow', 'equity'
            period_start REAL NOT NULL,
            period_end REAL NOT NULL,
            data TEXT NOT NULL,  -- JSON
            generated_at REAL NOT NULL,
            generated_by TEXT,
            version INTEGER DEFAULT 1
        )
    """)

    # Tax calculations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tax_calculations (
            id TEXT PRIMARY KEY,
            tax_year INTEGER NOT NULL,
            tax_type TEXT,  -- 'income', 'sales', 'property', 'payroll'
            jurisdiction TEXT,
            taxable_income REAL,
            tax_owed REAL,
            tax_paid REAL,
            refund_due REAL,
            status TEXT DEFAULT 'pending',  -- 'pending', 'filed', 'paid', 'refunded'
            filed_date REAL,
            due_date REAL,
            notes TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Tax line items
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tax_line_items (
            id TEXT PRIMARY KEY,
            calculation_id TEXT NOT NULL,
            line_name TEXT NOT NULL,
            amount REAL NOT NULL,
            line_type TEXT,  -- 'income', 'deduction', 'credit', 'payment'
            description TEXT,
            FOREIGN KEY (calculation_id) REFERENCES tax_calculations(id)
        )
    """)

    # Fixed Assets
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fixed_assets (
            id TEXT PRIMARY KEY,
            asset_number TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT,
            purchase_date REAL NOT NULL,
            purchase_cost REAL NOT NULL,
            salvage_value REAL DEFAULT 0,
            useful_life_years INTEGER,
            depreciation_method TEXT DEFAULT 'straight_line',  -- 'straight_line', 'declining_balance', 'sum_of_years'
            depreciation_rate REAL,
            accumulated_depreciation REAL DEFAULT 0,
            book_value REAL,
            location TEXT,
            department TEXT,
            serial_number TEXT,
            status TEXT DEFAULT 'active',  -- 'active', 'disposed', 'sold', 'impaired'
            disposal_date REAL,
            disposal_value REAL,
            notes TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Depreciation schedule
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS depreciation_schedule (
            id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL,
            period_start REAL NOT NULL,
            period_end REAL NOT NULL,
            depreciation_expense REAL NOT NULL,
            accumulated_depreciation REAL NOT NULL,
            book_value REAL NOT NULL,
            is_posted BOOLEAN DEFAULT 0,
            posted_at REAL,
            FOREIGN KEY (asset_id) REFERENCES fixed_assets(id)
        )
    """)

    # Audit trail
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_trail (
            id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,  -- 'journal_entry', 'account', 'transaction', 'reconciliation'
            entity_id TEXT NOT NULL,
            action TEXT NOT NULL,  -- 'create', 'update', 'delete', 'post', 'reverse', 'void'
            old_values TEXT,  -- JSON
            new_values TEXT,  -- JSON
            user TEXT,
            timestamp REAL NOT NULL,
            ip_address TEXT
        )
    """)

    # Budgets vs Actuals
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budget_vs_actual (
            id TEXT PRIMARY KEY,
            budget_id TEXT NOT NULL,
            period_start REAL NOT NULL,
            period_end REAL NOT NULL,
            budgeted_amount REAL NOT NULL,
            actual_amount REAL NOT NULL,
            variance REAL NOT NULL,
            variance_percent REAL,
            FOREIGN KEY (budget_id) REFERENCES budgets(id)
        )
    """)

    conn.commit()
    conn.close()


init_accounting_db()


@dataclass
class Account:
    id: str
    code: str
    name: str
    account_type: str
    parent_id: Optional[str]
    description: str
    is_active: bool
    normal_balance: str
    created_at: float
    updated_at: float


@dataclass
class JournalEntry:
    id: str
    entry_number: str
    date: float
    description: str
    reference: str
    source: str
    status: str
    total_debit: float
    total_credit: float
    created_by: str
    posted_at: Optional[float]
    created_at: float
    updated_at: float


@dataclass
class JournalEntryLine:
    id: str
    entry_id: str
    line_number: int
    account_id: str
    description: str
    debit: float
    credit: float
    memo: str


class ChartOfAccounts:
    """Manages the chart of accounts."""

    def __init__(self):
        self._init_default_accounts()

    def _init_default_accounts(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM accounts")
        count = cursor.fetchone()[0]
        conn.close()

        if count > 0:
            return

        # Standard chart of accounts
        default_accounts = [
            # Assets
            ("1000", "Assets", "asset", None, "Total assets", "debit"),
            ("1100", "Current Assets", "asset", "1000", "Current assets", "debit"),
            ("1110", "Cash", "asset", "1100", "Cash and cash equivalents", "debit"),
            ("1120", "Checking Account", "asset", "1110", "Checking account", "debit"),
            ("1130", "Savings Account", "asset", "1110", "Savings account", "debit"),
            ("1140", "Petty Cash", "asset", "1110", "Petty cash fund", "debit"),
            ("1200", "Accounts Receivable", "asset", "1100", "Trade receivables", "debit"),
            ("1210", "Allowance for Doubtful Accounts", "asset", "1200", "Contra-asset", "credit"),
            ("1300", "Inventory", "asset", "1100", "Inventory", "debit"),
            ("1400", "Prepaid Expenses", "asset", "1100", "Prepaid expenses", "debit"),
            ("1500", "Fixed Assets", "asset", "1000", "Property, plant, equipment", "debit"),
            ("1510", "Equipment", "asset", "1500", "Equipment", "debit"),
            ("1520", "Vehicles", "asset", "1500", "Vehicles", "debit"),
            ("1530", "Furniture & Fixtures", "asset", "1500", "Furniture & fixtures", "debit"),
            ("1590", "Accumulated Depreciation", "asset", "1500", "Contra-asset", "credit"),
            ("1600", "Intangible Assets", "asset", "1000", "Intangible assets", "debit"),

            # Liabilities
            ("2000", "Liabilities", "liability", None, "Total liabilities", "credit"),
            ("2100", "Current Liabilities", "liability", "2000", "Current liabilities", "credit"),
            ("2110", "Accounts Payable", "liability", "2100", "Trade payables", "credit"),
            ("2120", "Accrued Expenses", "liability", "2100", "Accrued expenses", "credit"),
            ("2130", "Payroll Liabilities", "liability", "2100", "Payroll liabilities", "credit"),
            ("2140", "Taxes Payable", "liability", "2100", "Taxes payable", "credit"),
            ("2150", "Credit Cards", "liability", "2100", "Credit card balances", "credit"),
            ("2200", "Long-term Liabilities", "liability", "2000", "Long-term liabilities", "credit"),
            ("2210", "Long-term Debt", "liability", "2200", "Long-term debt", "credit"),

            # Equity
            ("3000", "Equity", "equity", None, "Total equity", "credit"),
            ("3100", "Owner's Equity", "equity", "3000", "Owner's equity", "credit"),
            ("3200", "Retained Earnings", "equity", "3000", "Retained earnings", "credit"),
            ("3300", "Current Year Earnings", "equity", "3000", "Current year earnings", "credit"),

            # Revenue
            ("4000", "Revenue", "revenue", None, "Total revenue", "credit"),
            ("4100", "Sales Revenue", "revenue", "4000", "Sales revenue", "credit"),
            ("4200", "Service Revenue", "revenue", "4000", "Service revenue", "credit"),
            ("4300", "Interest Income", "revenue", "4000", "Interest income", "credit"),
            ("4400", "Other Income", "revenue", "4000", "Other income", "credit"),

            # Expenses
            ("5000", "Expenses", "expense", None, "Total expenses", "debit"),
            ("5100", "Cost of Goods Sold", "expense", "5000", "COGS", "debit"),
            ("5200", "Payroll Expenses", "expense", "5000", "Payroll", "debit"),
            ("5300", "Rent Expense", "expense", "5000", "Rent", "debit"),
            ("5400", "Utilities", "expense", "5000", "Utilities", "debit"),
            ("5500", "Office Expenses", "expense", "5000", "Office expenses", "debit"),
            ("5600", "Marketing", "expense", "5000", "Marketing", "debit"),
            ("5700", "Travel", "expense", "5000", "Travel", "debit"),
            ("5800", "Professional Fees", "expense", "5000", "Professional fees", "debit"),
            ("5800", "Depreciation Expense", "expense", "5000", "Depreciation", "debit"),
            ("5900", "Interest Expense", "expense", "5000", "Interest", "debit"),
            ("5950", "Taxes", "expense", "5000", "Taxes", "debit"),
        ]

        conn = get_connection()
        cursor = conn.cursor()
        now = time.time()

        for code, name, acc_type, parent, desc, normal_balance in default_accounts:
            account_id = f"acct_{code}"
            parent_id = f"acct_{parent}" if parent else None

            cursor.execute("""
                INSERT OR IGNORE INTO accounts (id, code, name, account_type, parent_id, description, is_active, normal_balance, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """, (account_id, code, name, acc_type, parent_id, desc, normal_balance, time.time(), time.time()))

        conn.commit()
        conn.close()

    def get_account(self, account_id: str) -> Optional[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "code": row[1], "name": row[2], "account_type": row[3],
                "parent_id": row[4], "description": row[5], "is_active": bool(row[5]),
                "normal_balance": row[6], "created_at": row[6], "updated_at": row[7]
            }
        return None

    def get_account_by_code(self, code: str) -> Optional[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE code = ?", (code,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "code": row[1], "name": row[2], "account_type": row[3],
                "parent_id": row[4], "description": row[5], "is_active": bool(row[5]),
                "normal_balance": row[6], "created_at": row[6], "updated_at": row[7]
            }
        return None

    def list_accounts(self, account_type: str = None) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        if account_type:
            cursor.execute("SELECT * FROM accounts WHERE account_type = ? ORDER BY code", (account_type,))
        else:
            cursor.execute("SELECT * FROM accounts ORDER BY code")
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "code": r[1], "name": r[2], "account_type": r[3],
             "parent_id": r[4], "description": r[5], "is_active": bool(r[5]),
             "normal_balance": r[6], "created_at": r[6], "updated_at": r[7]}
            for r in rows
        ]

    def get_account_hierarchy(self) -> Dict:
        """Returns the full account hierarchy as a nested dict."""
        accounts = self.list_accounts()
        hierarchy = {}

        for acc in accounts:
            if not acc["parent_id"]:
                hierarchy[acc["id"]] = {**acc, "children": []}
            else:
                # Would need recursive building for full hierarchy
                pass

        return hierarchy


class JournalManager:
    """Manages journal entries and posting."""

    def __init__(self):
        pass

    def create_journal_entry(self, date: float, description: str, reference: str = "",
                             source: str = "manual", created_by: str = "system") -> str:
        entry_id = f"je_{int(time.time() * 1000) % 100000000:08d}"
        entry_number = f"JE-{datetime.fromtimestamp(time.time()).strftime('%Y%m%d')}-{int(time.time() * 1000) % 10000:04d}"

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO journal_entries (id, entry_number, date, description, reference, source, status, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?)
        """, (entry_id, entry_number, date, description, reference, source, created_by, time.time(), time.time()))
        conn.commit()
        conn.close()
        return entry_id

    def add_line(self, entry_id: str, account_id: str, description: str = "",
                 debit: float = 0, credit: float = 0, memo: str = "") -> str:
        line_id = f"jel_{int(time.time() * 1000) % 100000000:08d}"
        line_number = self._get_next_line_number(entry_id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO journal_entry_lines (id, entry_id, line_number, account_id, description, debit, credit, memo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (line_id, entry_id, line_number, account_id, description, debit, credit, memo))
        conn.commit()
        conn.close()

        # Update entry totals
        self._update_entry_totals(entry_id)
        return line_id

    def _get_next_line_number(self, entry_id: str) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(MAX(line_number), 0) + 1 FROM journal_entry_lines WHERE entry_id = ?", (entry_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 1

    def _update_entry_totals(self, entry_id: str):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0)
            FROM journal_entry_lines WHERE entry_id = ?
        """, (entry_id,))
        row = cursor.fetchone()
        total_debit = row[0] if row else 0
        total_credit = row[1] if row else 0

        cursor.execute("UPDATE journal_entries SET total_debit = ?, total_credit = ?, updated_at = ? WHERE id = ?",
                       (total_debit, total_credit, time.time(), entry_id))
        conn.commit()
        conn.close()

    def validate_entry(self, entry_id: str) -> Dict:
        """Validate that debits equal credits."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0)
            FROM journal_entry_lines WHERE entry_id = ?
        """, (entry_id,))
        row = cursor.fetchone()
        conn.close()

        total_debit = row[0] if row else 0
        total_credit = row[1] if row else 0

        return {
            "is_balanced": abs(total_debit - total_credit) < 0.01,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "difference": total_debit - total_credit
        }

    def post_entry(self, entry_id: str, posted_by: str = "system") -> bool:
        validation = self.validate_entry(entry_id)
        if not validation["is_balanced"]:
            return False

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE journal_entries SET status = 'posted', posted_at = ?, created_by = ?, updated_at = ?
            WHERE id = ? AND status = 'draft'
        """, (time.time(), "system", time.time(), entry_id))
        conn.commit()
        conn.close()
        return True

    def reverse_entry(self, entry_id: str, reversal_date: float = None, reason: str = "") -> str:
        """Create a reversing entry."""
        reversal_date = reversal_date or time.time()

        # Get original entry
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM journal_entries WHERE id = ?", (entry_id,))
        original = cursor.fetchone()
        conn.close()

        if not original:
            raise ValueError("Entry not found")

        # Create reversal entry
        reversal_id = self.create_journal_entry(
            date=reversal_date,
            description=f"Reversal of {original[3]}: {reason}",
            reference=f"REV-{original[1]}",
            source="reversing",
            created_by="system"
        )

        # Get original lines
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM journal_entry_lines WHERE entry_id = ?", (entry_id,))
        lines = cursor.fetchall()
        conn.close()

        # Add reversed lines (swap debit/credit)
        for line in lines:
            line_id, _, line_number, account_id, description, debit, credit, memo = row
            self.add_line(reversal_id, account_id, description,
                         credit=debit, debit=credit, memo=f"Reversal: {memo}")

        return reversal_id


class LedgerManager:
    """Manages general ledger and trial balance."""

    def __init__(self):
        pass

    def calculate_balances(self, period_start: float, period_end: float) -> Dict[str, Dict]:
        """Calculate account balances for a period."""
        conn = get_connection()
        cursor = conn.cursor()

        # Get all accounts
        cursor.execute("SELECT id, code, name, normal_balance FROM accounts WHERE is_active = 1")
        accounts = cursor.fetchall()
        conn.close()

        balances = {}
        for acc in accounts:
            acc_id, code, name, normal_balance = acc

            # Get opening balance (balance before period)
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0)
                FROM journal_entry_lines jel
                JOIN journal_entries je ON jel.entry_id = je.id
                WHERE jel.account_id = ? AND je.status = 'posted' AND je.date < ?
            """, (acc_id, period_start))
            row = cursor.fetchone()
            conn.close()

            opening_debit = row[0] if row else 0
            opening_credit = row[1] if row else 0
            opening_balance = opening_debit - opening_credit if normal_balance == 'debit' else opening_credit - opening_debit

            # Get period activity
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0)
                FROM journal_entry_lines jel
                JOIN journal_entries je ON jel.entry_id = je.id
                WHERE jel.account_id = ? AND je.status = 'posted' AND je.date >= ? AND je.date <= ?
            """, (acc_id, period_start, period_end))
            row = cursor.fetchone()
            conn.close()

            period_debit = row[0] if row else 0
            period_credit = row[1] if row else 0

            # Calculate closing balance
            if normal_balance == 'debit':
                closing_balance = opening_balance + period_debit - period_credit
            else:
                closing_balance = opening_balance + period_credit - period_debit

            return {
                "account_id": acc_id,
                "code": code,
                "name": name,
                "normal_balance": normal_balance,
                "opening_balance": opening_balance,
                "period_debit": period_debit,
                "period_credit": period_credit,
                "closing_balance": closing_balance
            }

    def get_trial_balance(self, period_start: float, period_end: float) -> Dict:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, code, name, normal_balance FROM accounts WHERE is_active = 1 ORDER BY code")
        accounts = cursor.fetchall()
        conn.close()

        trial_balance = []
        total_debits = 0
        total_credits = 0

        for acc in accounts:
            bal = self.calculate_balances(acc[0], period_start, period_end)
            if bal["closing_balance"] != 0 or bal["period_debit"] != 0 or bal["period_credit"] != 0:
                trial_balance.append(bal)
                total_debits += bal["period_debit"]
                total_credits += bal["period_credit"]

        return {
            "period_start": period_start,
            "period_end": period_end,
            "accounts": trial_balance,
            "total_debits": total_debits,
            "total_credits": total_credits,
            "is_balanced": abs(total_debits - total_credits) < 0.01
        }

    def get_account_balance(self, account_id: str, as_of: float = None) -> Dict:
        as_of = as_of or time.time()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT code, name, normal_balance FROM accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {}

        code, name, normal_balance = row

        # Get all posted transactions up to date
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0)
            FROM journal_entry_lines jel
            JOIN journal_entries je ON jel.entry_id = je.id
            WHERE jel.account_id = ? AND je.status = 'posted' AND je.date <= ?
        """, (account_id, as_of))
        row = cursor.fetchone()
        conn.close()

        total_debit = row[0] if row else 0
        total_credit = row[1] if row else 0

        balance = total_debit - total_credit if normal_balance == 'debit' else total_credit - total_debit

        return {
            "account_id": account_id,
            "code": code,
            "name": name,
            "balance": balance,
            "normal_balance": normal_balance,
            "as_of": as_of
        }


class ReconciliationManager:
    """Manages account reconciliation."""

    def __init__(self):
        pass

    def start_reconciliation(self, account_id: str, statement_date: float,
                             statement_balance: float) -> str:
        conn = get_connection()
        cursor = conn.cursor()

        # Get book balance
        book_balance = self._get_book_balance(account_id, statement_date)

        recon_id = f"rec_{int(time.time() * 1000) % 100000000:08d}"
        difference = statement_balance - book_balance

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO reconciliations (id, account_id, statement_date, statement_balance,
                                       book_balance, difference, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (recon_id, account_id, statement_date, statement_balance, book_balance, difference, time.time()))
        conn.commit()
        conn.close()

        return recon_id

    def _get_book_balance(self, account_id: str, as_of: float) -> float:
        ledger = LedgerManager()
        balance = ledger.get_account_balance(account_id, as_of)
        return balance.get("balance", 0)

    def add_reconciliation_item(self, reconciliation_id: str, transaction_id: str = None,
                                matched: bool = False, notes: str = "") -> str:
        item_id = f"ri_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO reconciliation_items (id, reconciliation_id, transaction_id, matched, matched_at, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (item_id, reconciliation_id, transaction_id, matched, time.time() if matched else None, notes))
        conn.commit()
        conn.close()
        return item_id

    def match_transactions(self, reconciliation_id: str, bank_transaction_id: str,
                           book_transaction_id: str) -> bool:
        conn = get_connection()
        cursor = conn.cursor()

        # Mark both as matched
        cursor.execute("""
            UPDATE reconciliation_items SET matched = 1, matched_at = ?
            WHERE reconciliation_id = ? AND (transaction_id = ? OR transaction_id = ?)
        """, (time.time(), reconciliation_id, bank_transaction_id, book_transaction_id))

        # Check if all items matched
        cursor.execute("""
            SELECT COUNT(*) FROM reconciliation_items
            WHERE reconciliation_id = ? AND matched = 0
        """, (reconciliation_id,))
        unmatched = cursor.fetchone()[0]

        if unmatched == 0:
            cursor.execute("""
                UPDATE reconciliations SET status = 'matched', reconciled_at = ?
                WHERE id = ?
            """, (time.time(), reconciliation_id))

        conn.commit()
        conn.close()
        return True

    def get_reconciliation_status(self, reconciliation_id: str) -> Dict:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reconciliations WHERE id = ?", (reconciliation_id,))
        row = cursor.fetchone()

        if not row:
            return {}

        cursor.execute("SELECT * FROM reconciliation_items WHERE reconciliation_id = ?", (reconciliation_id,))
        items = cursor.fetchall()
        conn.close()

        matched = sum(1 for item in items if item[3])
        total = len(items)

        return {
            "id": row[0], "account_id": row[1], "statement_date": row[2],
            "statement_balance": row[3], "book_balance": row[4], "difference": row[5],
            "status": row[6], "matched_items": matched, "total_items": total,
            "items": [
                {"id": i[0], "reconciliation_id": i[1], "transaction_id": i[2],
                 "matched": bool(i[3]), "matched_at": i[4], "notes": i[5]}
                for i in items
            ]
        }


class FinancialStatementGenerator:
    """Generates financial statements."""

    def __init__(self, ledger: LedgerManager):
        self.ledger = ledger

    def generate_balance_sheet(self, as_of: float = None) -> Dict:
        as_of = as_of or time.time()

        # Assets
        assets = self.ledger.get_trial_balance(0, as_of)
        asset_accounts = [a for a in assets["accounts"] if a["name"].startswith(("1",))]
        total_assets = sum(a["closing_balance"] for a in asset_accounts)

        # Liabilities
        liability_accounts = [a for a in assets["accounts"] if a["name"].startswith(("2",))]
        total_liabilities = sum(a["closing_balance"] for a in liability_accounts)

        # Equity
        equity_accounts = [a for a in assets["accounts"] if a["name"].startswith(("3",))]
        total_equity = sum(a["closing_balance"] for a in equity_accounts)

        return {
            "as_of": as_of,
            "assets": {"accounts": asset_accounts, "total": total_assets},
            "liabilities": {"accounts": liability_accounts, "total": total_liabilities},
            "equity": {"accounts": equity_accounts, "total": total_equity},
            "balanced": abs(total_assets - (total_liabilities + total_equity)) < 0.01
        }

    def generate_income_statement(self, period_start: float, period_end: float) -> Dict:
        tb = self.ledger.get_trial_balance(period_start, period_end)

        revenue_accounts = [a for a in tb["accounts"] if a["name"].startswith(("4",))]
        expense_accounts = [a for a in tb["accounts"] if a["name"].startswith(("5",))]

        total_revenue = sum(a["closing_balance"] for a in revenue_accounts)
        total_expenses = sum(a["closing_balance"] for a in expense_accounts)
        net_income = total_revenue - total_expenses

        return {
            "period_start": period_start,
            "period_end": period_end,
            "revenue": {"accounts": revenue_accounts, "total": total_revenue},
            "expenses": {"accounts": expense_accounts, "total": total_expenses},
            "net_income": net_income
        }

    def generate_cash_flow(self, period_start: float, period_end: float) -> Dict:
        # Simplified cash flow - would need more detailed tracking in practice
        tb = self.ledger.get_trial_balance(period_start, period_end)

        # Operating activities
        net_income = sum(a["closing_balance"] for a in tb["accounts"]
                         if a["name"].startswith(("4",))) - \
                     sum(a["closing_balance"] for a in tb["accounts"]
                         if a["name"].startswith(("5",)))

        # Simplified - real implementation would track changes in working capital
        operating = net_income
        investing = 0
        financing = 0

        return {
            "period_start": period_start,
            "period_end": period_end,
            "operating": operating,
            "investing": investing,
            "financing": financing,
            "net_change": operating + investing + financing
        }


class TaxCalculator:
    """Calculates taxes for various jurisdictions."""

    def __init__(self):
        self.tax_brackets = {
            "us_federal_2024": [
                (0, 11600, 0.10),
                (11600, 47150, 0.12),
                (47150, 100525, 0.22),
                (100525, 191950, 0.24),
                (191950, 243725, 0.32),
                (243725, 609350, 0.35),
                (609350, float('inf'), 0.37)
            ],
            "standard_deduction": {
                "single": 14600,
                "married_filing_jointly": 29200,
                "head_of_household": 21900
            }
        }

    def calculate_federal_tax(self, taxable_income: float, filing_status: str = "single") -> Dict:
        brackets = self.tax_brackets["us_federal_2024"]
        deduction = self.tax_brackets["standard_deduction"].get(filing_status, 14600)

        taxable = max(0, taxable_income - deduction)
        tax = 0
        remaining = taxable

        for lower, upper, rate in brackets:
            taxable_in_bracket = min(remaining, upper - lower)
            tax += taxable_in_bracket * rate
            remaining -= taxable_in_bracket
            if remaining <= 0:
                break

        return {
            "taxable_income": taxable_income,
            "standard_deduction": deduction,
            "taxable_after_deduction": taxable,
            "federal_tax": tax,
            "effective_rate": tax / taxable_income if taxable_income > 0 else 0,
            "marginal_rate": self._get_marginal_rate(taxable, brackets)
        }

    def _get_marginal_rate(self, taxable: float, brackets: List) -> float:
        for lower, upper, rate in brackets:
            if lower <= taxable < upper:
                return rate
        return brackets[-1][2]

    def calculate_sales_tax(self, amount: float, state: str = "CA") -> float:
        """Calculate sales tax for a given state."""
        rates = {
            "CA": 0.0725, "NY": 0.08, "TX": 0.0625, "FL": 0.06,
            "WA": 0.065, "IL": 0.0625, "PA": 0.06, "OH": 0.0575
        }
        rate = rates.get(state.upper(), 0)
        return amount * rate

    def calculate_payroll_tax(self, gross_pay: float, filing_status: str = "single",
                              allowances: int = 0) -> Dict:
        """Calculate federal payroll tax withholding."""
        # Simplified - real implementation would use IRS tables
        annual = gross_pay * 26  # Biweekly
        tax = self.calculate_federal_tax(annual, filing_status)["federal_tax"]
        per_period = tax / 26

        # Social Security (6.2% up to wage base)
        ss_wage_base = 168600
        ss_tax = min(gross_pay, ss_wage_base / 26) * 0.062

        # Medicare (1.45%)
        medicare_tax = gross_pay * 0.0145

        return {
            "federal_withholding": per_period,
            "social_security": ss_tax,
            "medicare": medicare_tax,
            "total_withholding": per_period + ss_tax + medicare_tax
        }


class AuditTrail:
    """Tracks all changes for audit compliance."""

    def __init__(self):
        pass

    def log_action(self, entity_type: str, entity_id: str, action: str,
                   old_values: Dict = None, new_values: Dict = None, user: str = "system"):
        audit_id = f"audit_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_trail (id, entity_type, entity_id, action, old_values, new_values, user, timestamp, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (audit_id, entity_type, entity_id, action,
              json.dumps(old_values) if old_values else None,
              json.dumps(new_values) if new_values else None,
              user, time.time(), "local"))
        conn.commit()
        conn.close()
        return audit_id

    def get_audit_trail(self, entity_type: str = None, entity_id: str = None,
                        start_date: float = None, end_date: float = None, limit: int = 100) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()

        sql = "SELECT * FROM audit_trail WHERE 1=1"
        params = []

        if entity_type:
            sql += " AND entity_type = ?"
            params.append(entity_type)
        if entity_id:
            sql += " AND entity_id = ?"
            params.append(entity_id)
        if start_date:
            sql += " AND timestamp >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND timestamp <= ?"
            params.append(end_date)

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        return [
            {"id": r[0], "entity_type": r[1], "entity_id": r[2], "action": r[3],
             "old_values": json.loads(r[4]) if r[4] else None,
             "new_values": json.loads(r[5]) if r[5] else None,
             "user": r[6], "timestamp": r[7], "ip": r[8]}
            for r in rows
        ]


class AccountingAgent:
    """Main Accounting Agent coordinator."""

    def __init__(self):
        self.chart_of_accounts = ChartOfAccounts()
        self.journal_manager = JournalManager()
        self.ledger_manager = LedgerManager()
        self.reconciliation_manager = ReconciliationManager()
        self.financial_statements = FinancialStatementGenerator(self.ledger_manager)
        self.tax_calculator = TaxCalculator()
        self.audit_trail = AuditTrail()

    def get_dashboard(self) -> Dict:
        trial_balance = self.ledger_manager.get_trial_balance(0, time.time())
        return {
            "trial_balance": trial_balance,
            "is_balanced": trial_balance["is_balanced"]
        }

    def create_journal_entry(self, date: float, description: str, lines: List[Dict],
                             reference: str = "", source: str = "manual") -> str:
        """Create a journal entry with multiple lines."""
        entry_id = self.journal_manager.create_journal_entry(
            date=time.time(), description="Manual entry", reference="",
            created_by="system"
        )

        for line in lines:
            self.journal_manager.add_line(entry_id, line["account_id"],
                                         line.get("description", ""),
                                         line.get("debit", 0), line.get("credit", 0),
                                         line.get("memo", ""))

        validation = self.journal_manager.validate_entry(entry_id)
        if not validation["is_balanced"]:
            raise ValueError(f"Entry not balanced: {validation['difference']}")

        self.journal_manager.post_entry(entry_id)
        return entry_id

    def post_journal_entry(self, entry_id: str) -> bool:
        return self.journal_manager.post_entry(entry_id)

    def reverse_journal_entry(self, entry_id: str, reason: str = "") -> str:
        return self.journal_manager.reverse_entry(entry_id, reason=reason)

    def get_trial_balance(self, period_start: float = 0, period_end: float = None) -> Dict:
        return self.ledger_manager.get_trial_balance(period_start, period_end or time.time())

    def generate_balance_sheet(self, as_of: float = None) -> Dict:
        return self.financial_statements.generate_balance_sheet(as_of)

    def generate_income_statement(self, period_start: float, period_end: float) -> Dict:
        return self.financial_statements.generate_income_statement(period_start, period_end)

    def generate_cash_flow(self, period_start: float, period_end: float) -> Dict:
        return self.financial_statements.generate_cash_flow(period_start, period_end)

    def reconcile_account(self, account_id: str, statement_date: float,
                          statement_balance: float) -> str:
        return self.reconciliation_manager.start_reconciliation(account_id, statement_date, statement_balance)

    def match_reconciliation(self, reconciliation_id: str, bank_txn_id: str, book_txn_id: str) -> bool:
        return self.reconciliation_manager.match_transactions(reconciliation_id, bank_txn_id, book_txn_id)

    def get_reconciliation_status(self, reconciliation_id: str) -> Dict:
        return self.reconciliation_manager.get_reconciliation_status(reconciliation_id)

    def calculate_tax(self, taxable_income: float, filing_status: str = "single") -> Dict:
        return self.tax_calculator.calculate_federal_tax(taxable_income, filing_status)

    def calculate_payroll_tax(self, gross_pay: float, filing_status: str = "single",
                              allowances: int = 0) -> Dict:
        return self.tax_calculator.calculate_payroll_tax(gross_pay, filing_status, allowances)

    def calculate_sales_tax(self, amount: float, state: str = "CA") -> float:
        return self.tax_calculator.calculate_sales_tax(amount, state)

    def create_budget(self, name: str, period: str, start_date: float, total_amount: float,
                      category_limits: Dict[str, float] = None) -> str:
        # Would need to add budget table and manager
        pass

    def record_audit(self, entity_type: str, entity_id: str, action: str,
                     old_values: Dict = None, new_values: Dict = None, user: str = "system"):
        return self.audit_trail.log_action(entity_type, entity_id, action, old_values, new_values, user)

    def get_audit_trail(self, entity_type: str = None, entity_id: str = None,
                        limit: int = 100) -> List[Dict]:
        return self.audit_trail.get_audit_trail(entity_type, entity_id, limit=limit)

    def add_fixed_asset(self, name: str, category: str, purchase_date: float,
                        purchase_cost: float, useful_life_years: int,
                        depreciation_method: str = "straight_line", **kwargs) -> str:
        asset_id = f"fa_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO fixed_assets (id, asset_number, name, category, purchase_date, purchase_cost,
                                    salvage_value, useful_life_years, depreciation_method,
                                    location, department, serial_number, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"fa_{int(time.time() * 1000) % 100000000:08d}", f"FA-{int(time.time())}", name, category,
              purchase_date, purchase_cost, kwargs.get("salvage_value", 0), useful_life_years,
              depreciation_method, kwargs.get("location", ""), kwargs.get("department", ""),
              kwargs.get("serial_number", ""), kwargs.get("notes", ""), time.time(), time.time()))
        conn.commit()
        conn.close()
        return asset_id

    def generate_depreciation_schedule(self, asset_id: str, year: int) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM fixed_assets WHERE id = ?", (asset_id,))
        asset = cursor.fetchone()
        conn.close()

        if not asset:
            return []

        # Calculate depreciation based on method
        # Simplified - would need full implementation
        return []

    def generate_financial_statements(self, period_start: float, period_end: float) -> Dict:
        return {
            "balance_sheet": self.financial_statements.generate_balance_sheet(period_end),
            "income_statement": self.financial_statements.generate_income_statement(period_start, period_end),
            "cash_flow": self.financial_statements.generate_cash_flow(period_start, period_end)
        }

    def run_trial_balance(self, as_of: float = None) -> Dict:
        return self.ledger_manager.get_trial_balance(0, as_of or time.time())

    def close_period(self, period_end: float) -> Dict:
        """Close accounting period."""
        # Generate financial statements
        statements = self.generate_financial_statements(0, period_end)

        # Create closing entries
        # This would involve creating entries to close revenue/expense to retained earnings

        return {
            "period_end": period_end,
            "statements": statements,
            "message": "Period closed successfully"
        }


# Global instance
accounting_agent = AccountingAgent()


# Convenience functions
def create_journal_entry(date: float, description: str, lines: List[Dict],
                         reference: str = "", source: str = "manual") -> str:
    return accounting_agent.create_journal_entry(date, description, lines, reference)

def post_journal_entry(entry_id: str) -> bool:
    return accounting_agent.post_journal_entry(entry_id)

def reverse_journal_entry(entry_id: str, reason: str = "") -> str:
    return accounting_agent.reverse_journal_entry(entry_id, reason)

def get_trial_balance(period_start: float = 0, period_end: float = None) -> Dict:
    return accounting_agent.get_trial_balance(period_start, period_end)

def generate_balance_sheet(as_of: float = None) -> Dict:
    return accounting_agent.generate_balance_sheet(as_of)

def generate_income_statement(period_start: float, period_end: float) -> Dict:
    return accounting_agent.generate_income_statement(period_start, period_end)

def generate_cash_flow(period_start: float, period_end: float) -> Dict:
    return accounting_agent.generate_cash_flow(period_start, period_end)

def reconcile_account(account_id: str, statement_date: float, statement_balance: float) -> str:
    return accounting_agent.reconcile_account(account_id, statement_date, statement_balance)

def match_reconciliation(reconciliation_id: str, bank_txn_id: str, book_txn_id: str) -> bool:
    return accounting_agent.match_reconciliation(reconciliation_id, bank_txn_id, book_txn_id)

def get_reconciliation_status(reconciliation_id: str) -> Dict:
    return accounting_agent.get_reconciliation_status(reconciliation_id)

def calculate_federal_tax(taxable_income: float, filing_status: str = "single") -> Dict:
    from core.accounting_agent import accounting_agent
    return accounting_agent.calculate_federal_tax(taxable_income, filing_status)

def calculate_payroll_tax(gross_pay: float, filing_status: str = "single", allowances: int = 0) -> Dict:
    from core.accounting_agent import accounting_agent
    return accounting_agent.calculate_payroll_tax(gross_pay, filing_status, allowances)

def calculate_sales_tax(amount: float, state: str = "CA") -> float:
    from core.accounting_agent import accounting_agent
    return accounting_agent.calculate_sales_tax(amount, state)

def create_asset(name: str, category: str, purchase_date: float, purchase_cost: float,
                 useful_life: int, depreciation_method: str = "straight_line", **kwargs) -> str:
    return accounting_agent.add_fixed_asset(name, category, purchase_date, purchase_cost, useful_life, depreciation_method, **kwargs)

def get_audit_trail(entity_type: str = None, entity_id: str = None, limit: int = 100) -> List[Dict]:
    from core.accounting_agent import accounting_agent
    return accounting_agent.get_audit_trail(entity_type, entity_id, limit)

def create_budget(name: str, period: str, start_date: float, total_amount: float,
                  category_limits: Dict[str, float] = None) -> str:
    # Would need budget table implementation
    pass

def get_budget_status(budget_id: str) -> Optional[Dict]:
    pass

def create_automation_rule(name: str, trigger_type: str, trigger_config: Dict,
                           action_type: str, action_config: Dict, cooldown: int = 60) -> str:
    # Would need automation rules table
    pass


# Voice command integration
def accounting_debug() -> str:
    tb = accounting_agent.run_trial_balance()
    return f"Accounting System:\nTrial Balance Balanced: {tb['is_balanced']}\nTotal Debits: ${tb['total_debits']:,.2f}\nTotal Credits: ${tb['total_credits']:,.2f}"


if __name__ == "__main__":
    print("Accounting Agent module loaded.")
    print("Available functions:")
    print("  create_journal_entry(date, description, lines, reference)")
    print("  post_journal_entry(entry_id)")
    print("  reverse_journal_entry(entry_id, reason)")
    print("  get_trial_balance(period_start, period_end)")
    print("  generate_balance_sheet(as_of)")
    print("  generate_income_statement(period_start, period_end)")
    print("  generate_cash_flow(period_start, period_end)")
    print("  reconcile_account(account_id, statement_date, statement_balance)")
    print("  match_reconciliation(reconciliation_id, bank_txn_id, book_txn_id)")
    print("  calculate_federal_tax(taxable_income, filing_status)")
    print("  calculate_payroll_tax(gross_pay, filing_status, allowances)")
    print("  calculate_sales_tax(amount, state)")
    print("  create_asset(name, category, purchase_date, purchase_cost, useful_life, depreciation_method)")
    print("  get_audit_trail(entity_type, entity_id, limit)")
    print("  create_budget(name, period, start_date, total_amount, category_limits)")
    print("  get_budget_status(budget_id)")
    print("  create_automation_rule(name, trigger_type, trigger_config, action_type, action_config, cooldown)")
    print("  get_automation_rules()")