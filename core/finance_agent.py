"""
Finance Agent - Phase 25
Personal finance management, budgeting, expense tracking, investment tracking.
Fully local, no cloud dependencies.
"""

import os
import json
import time
import threading
import sqlite3
import csv
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from core.context_engine import get_connection


DB_DIR = "database"
FINANCE_DB = os.path.join(DB_DIR, "finance.db")

os.makedirs(DB_DIR, exist_ok=True)


def init_finance_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Accounts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            account_type TEXT NOT NULL,  -- 'checking', 'savings', 'credit', 'investment', 'loan', 'crypto', 'cash'
            institution TEXT,
            currency TEXT DEFAULT 'USD',
            balance REAL DEFAULT 0.0,
            credit_limit REAL,
            interest_rate REAL,
            due_day INTEGER,
            is_active BOOLEAN DEFAULT 1,
            last_sync REAL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Transactions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            date REAL NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'USD',
            category TEXT,
            subcategory TEXT,
            description TEXT,
            notes TEXT,
            merchant TEXT,
            is_recurring BOOLEAN DEFAULT 0,
            recurring_rule TEXT,  -- JSON
            is_income BOOLEAN DEFAULT 0,
            is_transfer BOOLEAN DEFAULT 0,
            transfer_account_id TEXT,
            tags TEXT,  -- JSON array
            attachment_path TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_account_date
        ON transactions(account_id, date)
    """)

    # Budgets
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            period TEXT NOT NULL,  -- 'weekly', 'monthly', 'quarterly', 'yearly'
            start_date REAL NOT NULL,
            end_date REAL,
            total_amount REAL NOT NULL,
            currency TEXT DEFAULT 'USD',
            category_limits TEXT,  -- JSON: {"category": amount}
            alert_threshold REAL DEFAULT 0.8,
            is_active BOOLEAN DEFAULT 1,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Budget tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budget_spending (
            id TEXT PRIMARY KEY,
            budget_id TEXT NOT NULL,
            category TEXT NOT NULL,
            spent REAL DEFAULT 0.0,
            period_start REAL NOT NULL,
            period_end REAL NOT NULL,
            FOREIGN KEY (budget_id) REFERENCES budgets(id)
        )
    """)

    # Investment portfolio
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS investments (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            name TEXT,
            asset_type TEXT,  -- 'stock', 'etf', 'mutual_fund', 'crypto', 'bond', 'option'
            shares REAL NOT NULL,
            avg_cost_basis REAL,
            current_price REAL,
            currency TEXT DEFAULT 'USD',
            purchase_date REAL,
            account_id TEXT,
            notes TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)

    # Investment transactions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS investment_transactions (
            id TEXT PRIMARY KEY,
            investment_id TEXT NOT NULL,
            transaction_type TEXT NOT NULL,  -- 'buy', 'sell', 'dividend', 'split', 'dividend_reinvest'
            date REAL NOT NULL,
            shares REAL NOT NULL,
            price_per_share REAL NOT NULL,
            fees REAL DEFAULT 0.0,
            total_amount REAL NOT NULL,
            currency TEXT DEFAULT 'USD',
            notes TEXT,
            FOREIGN KEY (investment_id) REFERENCES investments(id)
        )
    """)

    # Recurring transactions/rules
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recurring_rules (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            account_id TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'USD',
            category TEXT,
            subcategory TEXT,
            description TEXT,
            merchant TEXT,
            frequency TEXT NOT NULL,  -- 'daily', 'weekly', 'biweekly', 'monthly', 'quarterly', 'yearly'
            day_of_month INTEGER,
            day_of_week INTEGER,  -- 0=Monday
            start_date REAL NOT NULL,
            end_date REAL,
            is_income BOOLEAN DEFAULT 0,
            category_id TEXT,
            tags TEXT,  -- JSON array
            is_active BOOLEAN DEFAULT 1,
            last_generated REAL,
            next_due REAL,
            created_at REAL NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)

    # Financial goals
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS financial_goals (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            goal_type TEXT NOT NULL,  -- 'savings', 'debt_payoff', 'investment', 'emergency_fund', 'purchase'
            target_amount REAL NOT NULL,
            current_amount REAL DEFAULT 0.0,
            currency TEXT DEFAULT 'USD',
            target_date REAL,
            account_id TEXT,
            auto_contribute REAL DEFAULT 0.0,
            contribute_frequency TEXT,  -- 'weekly', 'biweekly', 'monthly'
            priority INTEGER DEFAULT 1,
            status TEXT DEFAULT 'active',  -- 'active', 'paused', 'completed', 'cancelled'
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)

    # Bills/Subscriptions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            account_id TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'USD',
            due_day INTEGER NOT NULL,  -- Day of month
            frequency TEXT NOT NULL,  -- 'monthly', 'quarterly', 'yearly'
            category TEXT,
            description TEXT,
            is_active BOOLEAN DEFAULT 1,
            auto_pay BOOLEAN DEFAULT 0,
            payment_method TEXT,
            last_paid REAL,
            next_due REAL NOT NULL,
            reminder_days INTEGER DEFAULT 3,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)

    # Bill payments history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bill_payments (
            id TEXT PRIMARY KEY,
            bill_id TEXT NOT NULL,
            date REAL NOT NULL,
            amount REAL NOT NULL,
            payment_method TEXT,
            confirmation_number TEXT,
            notes TEXT,
            FOREIGN KEY (bill_id) REFERENCES bills(id)
        )
    """)

    # Categories
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            parent_id TEXT,
            icon TEXT,
            color TEXT,
            is_income BOOLEAN DEFAULT 0,
            is_system BOOLEAN DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (parent_id) REFERENCES categories(id)
        )
    """)

    # Import/Export history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS import_exports (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,  -- 'import', 'export'
            format TEXT,  -- 'csv', 'json', 'ofx', 'qif'
            file_path TEXT,
            account_id TEXT,
            records_count INTEGER,
            status TEXT,  -- 'pending', 'completed', 'failed'
            error_message TEXT,
            started_at REAL NOT NULL,
            completed_at REAL,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)

    # Exchange rates cache
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exchange_rates (
            id TEXT PRIMARY KEY,
            base_currency TEXT NOT NULL,
            target_currency TEXT NOT NULL,
            rate REAL NOT NULL,
            source TEXT,
            fetched_at REAL NOT NULL,
            expires_at REAL
        )
    """)

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_exchange_pair
        ON exchange_rates(base_currency, target_currency)
    """)

    conn.commit()
    conn.close()


init_finance_db()


class AccountManager:
    def __init__(self):
        pass

    def create_account(self, name: str, account_type: str, institution: str = "",
                       currency: str = "USD", balance: float = 0.0,
                       credit_limit: float = None, interest_rate: float = None,
                       due_day: int = None) -> str:
        account_id = f"acc_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_connection()
        cursor = conn.cursor()
        now = time.time()
        cursor.execute("""
            INSERT INTO accounts (id, name, account_type, institution, currency, balance,
                                credit_limit, interest_rate, due_day, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (account_id, name, account_type, institution, currency, balance,
              credit_limit, interest_rate, due_day, time.time(), time.time()))
        conn.commit()
        conn.close()
        return account_id

    def get_account(self, account_id: str) -> Optional[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "name": row[1], "account_type": row[2],
                "institution": row[3], "currency": row[4], "balance": row[5],
                "credit_limit": row[6], "interest_rate": row[7], "due_day": row[8],
                "is_active": bool(row[8]), "last_sync": row[9],
                "created_at": row[10], "updated_at": row[11]
            }
        return None

    def list_accounts(self, active_only: bool = True) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        if active_only:
            cursor.execute("SELECT * FROM accounts WHERE is_active = 1 ORDER BY name")
        else:
            cursor.execute("SELECT * FROM accounts ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "name": r[1], "account_type": r[2], "institution": r[3],
             "currency": r[4], "balance": r[5], "credit_limit": r[6],
             "interest_rate": r[7], "due_day": r[8], "is_active": bool(r[8]),
             "last_sync": r[9], "created_at": r[10], "updated_at": r[11]}
            for r in rows
        ]

    def update_balance(self, account_id: str, new_balance: float) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET balance = ?, updated_at = ? WHERE id = ?",
                       (new_balance, time.time(), account_id))
        conn.commit()
        conn.close()
        return True

    def update_account(self, account_id: str, **kwargs) -> bool:
        allowed = {"name", "institution", "currency", "credit_limit", "interest_rate",
                   "due_day", "is_active"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        updates["updated_at"] = time.time()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [account_id]
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE accounts SET {set_clause} WHERE id = ?", values)
        conn.commit()
        conn.close()
        return True

    def get_total_balance(self, currency: str = "USD") -> float:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(balance) FROM accounts WHERE currency = ? AND is_active = 1", (currency,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result and result[0] else 0.0


class TransactionManager:
    def __init__(self):
        pass

    def add_transaction(self, account_id: str, date: float, amount: float,
                        category: str = None, subcategory: str = None,
                        description: str = "", notes: str = "", merchant: str = "",
                        is_recurring: bool = False, recurring_rule: Dict = None,
                        is_income: bool = False, is_transfer: bool = False,
                        transfer_account_id: str = None, tags: List[str] = None,
                        currency: str = "USD") -> str:
        txn_id = f"txn_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO transactions (id, account_id, date, amount, currency, category, subcategory,
                                    description, notes, merchant, is_recurring, recurring_rule,
                                    is_income, is_transfer, transfer_account_id, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (txn_id, account_id, date, amount, currency, category, subcategory,
              description, notes, merchant, is_recurring,
              json.dumps(recurring_rule) if recurring_rule else None,
              is_income, is_transfer, transfer_account_id,
              json.dumps(tags or []), time.time(), time.time()))
        conn.commit()
        conn.close()
        return txn_id

    def get_transactions(self, account_id: str = None, start_date: float = None,
                         end_date: float = None, limit: int = 100) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()

        sql = "SELECT * FROM transactions WHERE 1=1"
        params = []

        if account_id:
            sql += " AND account_id = ?"
            params.append(account_id)
        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)

        sql += " ORDER BY date DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        return [
            {"id": r[0], "account_id": r[1], "date": r[2], "amount": r[3],
             "currency": r[4], "category": r[5], "subcategory": r[6],
             "description": r[6], "notes": r[7], "merchant": r[7],
             "is_recurring": bool(r[8]), "recurring_rule": json.loads(r[9]) if r[9] else None,
             "is_income": bool(r[9]), "is_transfer": bool(r[10]),
             "transfer_account_id": r[11], "tags": json.loads(r[12]) if r[12] else [],
             "attachment_path": r[13], "created_at": r[14], "updated_at": r[15]}
            for r in rows
        ]

    def update_transaction(self, txn_id: str, **kwargs) -> bool:
        allowed = {"date", "amount", "category", "subcategory", "description",
                   "notes", "merchant", "category", "subcategory", "tags",
                   "is_recurring", "recurring_rule", "is_income", "is_transfer"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        updates["updated_at"] = time.time()
        if "tags" in updates:
            updates["tags"] = json.dumps(updates["tags"])
        if "recurring_rule" in updates:
            updates["recurring_rule"] = json.dumps(updates["recurring_rule"])
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [txn_id]
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE transactions SET {set_clause} WHERE id = ?", values)
        conn.commit()
        conn.close()
        return True

    def delete_transaction(self, txn_id: str) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))
        conn.commit()
        conn.close()
        return True

    def get_spending_by_category(self, account_id: str = None,
                                 start_date: float = None, end_date: float = None) -> Dict[str, float]:
        conn = get_connection()
        cursor = conn.cursor()

        sql = "SELECT category, SUM(amount) FROM transactions WHERE is_income = 0"
        params = []

        if account_id:
            sql += " AND account_id = ?"
            params.append(account_id)
        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)

        sql += " GROUP BY category"
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        return {row[0] or "Uncategorized": row[1] for row in rows}

    def get_income_by_category(self, account_id: str = None,
                               start_date: float = None, end_date: float = None) -> Dict[str, float]:
        conn = get_connection()
        cursor = conn.cursor()

        sql = "SELECT category, SUM(amount) FROM transactions WHERE is_income = 1"
        params = []

        if account_id:
            sql += " AND account_id = ?"
            params.append(account_id)
        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)

        sql += " GROUP BY category"
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        return {row[0] or "Uncategorized": row[1] for row in rows}


class BudgetManager:
    def __init__(self):
        pass

    def create_budget(self, name: str, period: str, start_date: float,
                      total_amount: float, category_limits: Dict[str, float] = None,
                      alert_threshold: float = 0.8, currency: str = "USD") -> str:
        budget_id = f"bud_{int(time.time() * 1000) % 100000000:08d}"
        period_days = {"weekly": 7, "monthly": 30, "quarterly": 90, "yearly": 365}.get(period, 30)
        end_date = start_date + period_days * 86400

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO budgets (id, name, period, start_date, end_date, total_amount,
                               currency, category_limits, alert_threshold, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (budget_id, name, period, start_date, end_date, total_amount,
              currency, json.dumps(category_limits or {}), alert_threshold, time.time(), time.time()))
        conn.commit()
        conn.close()
        return budget_id

    def get_budget_status(self, budget_id: str) -> Optional[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM budgets WHERE id = ?", (budget_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        budget = {
            "id": row[0], "name": row[1], "period": row[2],
            "start_date": row[3], "end_date": row[3],
            "total_amount": row[5], "currency": row[6],
            "category_limits": json.loads(row[7]) if row[7] else {},
            "alert_threshold": row[8], "is_active": bool(row[9])
        }

        # Calculate spending per category
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT category, SUM(amount) as spent
            FROM transactions
            WHERE date >= ? AND date <= ? AND is_income = 0
            GROUP BY category
        """, (row[3], row[4]))
        spending = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()

        budget["spending_by_category"] = spending
        budget["total_spent"] = sum(spending.values())
        budget["remaining"] = budget["total_amount"] - budget["total_spent"]
        budget["percent_used"] = (budget["total_spent"] / budget["total_amount"]) if budget["total_amount"] > 0 else 0

        return budget

    def check_budget_alerts(self) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM budgets WHERE is_active = 1")
        rows = cursor.fetchall()
        conn.close()

        alerts = []
        for row in rows:
            budget = self.get_budget_status(row[0])
            if budget and budget["percent_used"] >= row[8]:  # alert_threshold
                alerts.append({
                    "budget_id": row[0],
                    "budget_name": row[1],
                    "percent_used": budget["percent_used"],
                    "threshold": row[8],
                    "message": f"Budget '{row[1]}' is at {budget['percent_used']:.0%} (threshold: {row[8]:.0%})"
                })
        return alerts


class InvestmentManager:
    def __init__(self):
        pass

    def add_investment(self, symbol: str, name: str, asset_type: str,
                       shares: float, avg_cost_basis: float, current_price: float = None,
                       account_id: str = None, currency: str = "USD", notes: str = "") -> str:
        inv_id = f"inv_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO investments (id, symbol, name, asset_type, shares, avg_cost_basis,
                                   current_price, currency, purchase_date, account_id, notes,
                                   created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (inv_id, symbol, name, asset_type, shares, avg_cost_basis,
              current_price, currency, time.time(), account_id, notes, time.time(), time.time()))
        conn.commit()
        conn.close()
        return inv_id

    def update_price(self, investment_id: str, new_price: float) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE investments SET current_price = ?, updated_at = ? WHERE id = ?",
                       (new_price, time.time(), investment_id))
        conn.commit()
        conn.close()
        return True

    def record_transaction(self, investment_id: str, transaction_type: str,
                           date: float, shares: float, price_per_share: float,
                           fees: float = 0.0, notes: str = "", currency: str = "USD") -> str:
        txn_id = f"itx_{int(time.time() * 1000) % 100000000:08d}"
        total_amount = shares * price_per_share + fees

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO investment_transactions (id, investment_id, transaction_type,
                                               date, shares, price_per_share, fees,
                                               total_amount, currency, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (txn_id, investment_id, transaction_type, date, shares,
              price_per_share, fees, total_amount, currency, notes))
        conn.commit()
        conn.close()
        return txn_id

    def get_portfolio_value(self, account_id: str = None) -> Dict:
        conn = get_connection()
        cursor = conn.cursor()

        if account_id:
            cursor.execute("SELECT * FROM investments WHERE account_id = ?", (account_id,))
        else:
            cursor.execute("SELECT * FROM investments")

        rows = cursor.fetchall()
        conn.close()

        total_value = 0.0
        total_cost = 0.0
        holdings = []

        for row in rows:
            inv = {
                "id": row[0], "symbol": row[1], "name": row[2], "asset_type": row[3],
                "shares": row[4], "avg_cost_basis": row[5], "current_price": row[6],
                "currency": row[7], "purchase_date": row[8], "account_id": row[9]
            }
            current_price = inv["current_price"] or inv["avg_cost_basis"]
            value = inv["shares"] * current_price
            cost = inv["shares"] * inv["avg_cost_basis"]
            gain_loss = value - cost
            gain_loss_pct = (gain_loss / cost * 100) if cost > 0 else 0

            total_value += value
            total_cost += cost
            holdings.append({**inv, "current_value": value, "gain_loss": gain_loss,
                           "gain_loss_pct": gain_loss_pct})

        return {
            "total_value": total_value,
            "total_cost": total_cost,
            "total_gain_loss": total_value - total_cost,
            "gain_loss_pct": ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0,
            "holdings": holdings
        }





class GoalManager:
    def __init__(self):
        pass

    def create_goal(self, name: str, goal_type: str, target_amount: float,
                    target_date: float = None, account_id: str = None,
                    auto_contribute: float = 0.0, contribute_frequency: str = "monthly",
                    priority: int = 1, currency: str = "USD") -> str:
        goal_id = f"goal_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO financial_goals (id, name, goal_type, target_amount, current_amount,
                                       currency, target_date, account_id, auto_contribute,
                                       contribute_frequency, priority, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 0.0, ?, ?, ?, ?, ?, 'active', ?, ?)
        """, (goal_id, name, goal_type, target_amount, currency, target_date,
              account_id, auto_contribute, contribute_frequency, priority,
              time.time(), time.time()))
        conn.commit()
        conn.close()
        return goal_id

    def update_progress(self, goal_id: str, amount: float) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE financial_goals
            SET current_amount = current_amount + ?, updated_at = ?
            WHERE id = ?
        """, (amount, time.time(), goal_id))
        conn.commit()
        conn.close()
        return True

    def get_goal(self, goal_id: str) -> Optional[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM financial_goals WHERE id = ?", (goal_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "name": row[1], "goal_type": row[2],
                "target_amount": row[3], "current_amount": row[4],
                "currency": row[5], "target_date": row[6],
                "account_id": row[7], "auto_contribute": row[8],
                "contribute_frequency": row[9], "priority": row[10],
                "status": row[10], "created_at": row[11], "updated_at": row[12]
            }
        return None

    def list_goals(self, status: str = None) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM financial_goals WHERE status = ? ORDER BY priority, target_date", (status,))
        else:
            cursor.execute("SELECT * FROM financial_goals ORDER BY priority, target_date")
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "name": r[1], "goal_type": r[2], "target_amount": r[3],
             "current_amount": r[4], "currency": r[5], "target_date": r[6],
             "account_id": r[7], "auto_contribute": r[8], "contribute_frequency": r[9],
             "priority": r[10], "status": r[10]}
            for r in rows
        ]


class BillManager:
    def __init__(self):
        pass

    def add_bill(self, name: str, account_id: str, amount: float, due_day: int,
                 frequency: str = "monthly", category: str = "", description: str = "",
                 is_active: bool = True, auto_pay: bool = False, payment_method: str = "",
                 reminder_days: int = 3, currency: str = "USD") -> str:
        bill_id = f"bill_{int(time.time() * 1000) % 100000000:08d}"
        now = time.time()
        next_due = self._calculate_next_due(due_day, frequency)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO bills (id, name, account_id, amount, currency, due_day,
                             frequency, category, description, is_active, auto_pay,
                             payment_method, reminder_days, next_due, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (bill_id, name, account_id, amount, currency, due_day,
              frequency, category, description, is_active, auto_pay,
              payment_method, reminder_days, next_due, time.time(), time.time()))
        conn.commit()
        conn.close()
        return bill_id

    def _calculate_next_due(self, due_day: int, frequency: str) -> float:
        now = datetime.now()
        if frequency == "monthly":
            next_due = now.replace(day=due_day)
            if next_due < now:
                next_due = (now.replace(day=1) + timedelta(days=32)).replace(day=due_day)
        elif frequency == "quarterly":
            # Next quarter
            next_due = now.replace(day=due_day)
            while next_due <= now:
                next_due = (next_due.replace(day=1) + timedelta(days=95)).replace(day=1)
        elif frequency == "yearly":
            next_due = now.replace(day=due_day, month=1)
            if next_due <= now:
                next_due = next_due.replace(year=now.year + 1)
        else:
            next_due = now.replace(day=due_day)
        return next_due.timestamp()

    def get_upcoming_bills(self, days: int = 30) -> List[Dict]:
        cutoff = time.time() + (days * 86400)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM bills WHERE is_active = 1 AND next_due <= ?
            ORDER BY next_due
        """, (time.time() + days * 86400,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "name": r[1], "account_id": r[2], "amount": r[3],
             "currency": r[4], "due_day": r[5], "frequency": r[6],
             "category": r[7], "description": r[8], "is_active": bool(r[9]),
             "auto_pay": bool(r[10]), "payment_method": r[11],
             "next_due": r[12], "reminder_days": r[13]}
            for r in rows
        ]

    def record_payment(self, bill_id: str, date: float = None, amount: float = None,
                       payment_method: str = "", confirmation_number: str = "",
                       notes: str = "") -> str:
        payment_id = f"pay_{int(time.time() * 1000) % 100000000:08d}"
        date = date or time.time()
        conn = get_connection()
        cursor = conn.cursor()

        # Record payment
        cursor.execute("""
            INSERT INTO bill_payments (id, bill_id, date, amount, payment_method,
                                     confirmation_number, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (payment_id, bill_id, date, amount, payment_method, confirmation_number, notes))

        # Update bill next due
        cursor.execute("SELECT frequency, due_day FROM bills WHERE id = ?", (bill_id,))
        bill = cursor.fetchone()
        if bill:
            next_due = self._calculate_next_due(bill[5], bill[4])
            cursor.execute("UPDATE bills SET last_paid = ?, next_due = ?, updated_at = ? WHERE id = ?",
                           (date, next_due, time.time(), bill_id))

        conn.commit()
        conn.close()
        return payment_id


class CategoryManager:
    def __init__(self):
        self._init_default_categories()

    def _init_default_categories(self):
        defaults = [
            # Expense categories
            ("Food & Dining", None, "🍽️", "#FF6B6B", False),
            ("Groceries", "Food & Dining", "🛒", "#FF8E8E", False),
            ("Restaurants", "Food & Dining", "🍽️", "#FF8E8E", False),
            ("Coffee", "Food & Dining", "☕", "#FF8E8E", False),
            ("Transportation", None, "🚌", "#4ECDC4", False),
            ("Gas", "Transportation", "⛽", "#4ECDC4", False),
            ("Public Transit", "Transportation", "🚌", "#4ECDC4", False),
            ("Rideshare", "Transportation", "🚗", "#4ECDC4", False),
            ("Shopping", None, "🛍️", "#45B7D1", False),
            ("Clothing", "Shopping", "👕", "#45B7D1", False),
            ("Electronics", "Shopping", "📱", "#45B7D1", False),
            ("Entertainment", None, "🎮", "#96CEB4", False),
            ("Streaming", "Entertainment", "📺", "#96CEB4", False),
            ("Games", "Entertainment", "🎮", "#96CEB4", False),
            ("Health & Fitness", None, "💪", "#FFBE0B", False),
            ("Medical", "Health & Fitness", "🏥", "#FFBE0B", False),
            ("Gym", "Health & Fitness", "💪", "#FFBE0B", False),
            ("Utilities", None, "💡", "#FF6B6B", False),
            ("Electric", "Utilities", "💡", "#FF6B6B", False),
            ("Water", "Utilities", "💧", "#FF6B6B", False),
            ("Internet", "Utilities", "🌐", "#FF6B6B", False),
            ("Phone", "Utilities", "📱", "#FF6B6B", False),
            ("Housing", None, "🏠", "#8E44AD", False),
            ("Rent/Mortgage", "Housing", "🏠", "#8E44AD", False),
            ("Insurance", "Housing", "🛡️", "#8E44AD", False),
            ("Income", None, "💰", "#2ECC71", True),
            ("Salary", "Income", "💰", "#2ECC71", True),
            ("Freelance", "Income", "💼", "#2ECC71", True),
            ("Investments", "Income", "📈", "#2ECC71", True),
            ("Gifts", "Income", "🎁", "#2ECC71", True),
            ("Transfers", None, "🔄", "#95A5A6", False),
        ]

        conn = get_connection()
        cursor = conn.cursor()
        for name, parent, icon, color, is_income in defaults:
            cursor.execute("""
                INSERT OR IGNORE INTO categories (id, name, parent_id, icon, color, is_income, is_system, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (f"cat_{name.lower().replace(' ', '_').replace('&', 'and').replace('/', '_')}",
                  name, parent, icon, color, is_income, True, 0))
        conn.commit()
        conn.close()


class RecurringTransactionManager:
    def __init__(self):
        pass

    def create_rule(self, name: str, account_id: str, amount: float, currency: str = "USD",
                    category: str = None, subcategory: str = None, description: str = "",
                    merchant: str = "", frequency: str = "monthly", day_of_month: int = 1,
                    day_of_week: int = None, start_date: float = None, end_date: float = None,
                    is_income: bool = False, tags: List[str] = None) -> str:
        rule_id = f"rec_{int(time.time() * 1000) % 100000000:08d}"
        start_date = start_date or time.time()
        next_due = self._calculate_next_due(start_date, frequency, day_of_month, day_of_week)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO recurring_rules (id, name, account_id, amount, currency, category,
                                       subcategory, description, merchant, frequency,
                                       day_of_month, day_of_week, start_date, end_date,
                                       is_income, tags, is_active, last_generated, next_due,
                                       created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
        """, (rule_id, name, account_id, amount, currency, category, subcategory,
              description, merchant, frequency, day_of_month, day_of_week,
              start_date, end_date, is_income, json.dumps(tags or []),
              next_due, time.time()))
        conn.commit()
        conn.close()
        return rule_id

    def _calculate_next_due(self, start_date: float, frequency: str,
                           day_of_month: int = 1, day_of_week: int = None) -> float:
        dt = datetime.fromtimestamp(start_date)
        if frequency == "daily":
            return (datetime.fromtimestamp(start_date) + timedelta(days=1)).timestamp()
        elif frequency == "weekly":
            days_ahead = (day_of_week - dt.weekday()) % 7
            if days_ahead <= 0:
                days_ahead += 7
            return (dt + timedelta(days=days_ahead)).timestamp()
        elif frequency == "biweekly":
            days_ahead = (day_of_week - dt.weekday()) % 7
            if days_ahead <= 0:
                days_ahead += 7
            return (dt + timedelta(days=days_ahead + 7)).timestamp()
        elif frequency == "monthly":
            next_month = dt.replace(day=1) + timedelta(days=32)
            next_month = next_month.replace(day=min(day_of_month, 28))
            return next_month.timestamp()
        elif frequency == "quarterly":
            month = ((dt.month - 1) // 3 + 1) * 3 + 1
            if month > 12:
                month = 1
                year = dt.year + 1
            else:
                year = dt.year
            return dt.replace(month=month, year=year, day=min(day_of_month, 28)).timestamp()
        elif frequency == "yearly":
            return dt.replace(year=dt.year + 1, day=min(day_of_month, 28)).timestamp()
        return start_date

    def process_due_rules(self) -> List[str]:
        """Process all due recurring rules and generate transactions."""
        generated = []
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM recurring_rules
            WHERE is_active = 1 AND next_due <= ?
        """, (time.time(),))
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            rule_id, name, account_id, amount, currency, category, subcategory, \
            description, merchant, frequency, day_of_month, day_of_week, \
            start_date, end_date, is_income, tags, is_active, \
            last_generated, next_due, created_at = row

            if end_date and time.time() > end_date:
                continue

            # Generate transaction
            txn_manager = TransactionManager()
            txn_id = TransactionManager().add_transaction(
                account_id=account_id,
                date=time.time(),
                amount=amount,
                category=category,
                subcategory=subcategory,
                description=description or name,
                merchant=merchant,
                is_recurring=True,
                recurring_rule={"rule_id": rule_id},
                is_income=bool(is_income),
                currency=currency,
                tags=json.loads(tags) if tags else []
            )

            # Update next due date
            next_due = self._calculate_next_due(next_due, frequency, day_of_month, day_of_week)
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE recurring_rules
                SET last_generated = ?, next_due = ?
                WHERE id = ?
            """, (time.time(), next_due, rule_id))
            conn.commit()
            conn.close()

            generated.append(txn_id)

        return generated


class FinanceAgent:
    def __init__(self):
        self.account_manager = AccountManager()
        self.transaction_manager = TransactionManager()
        self.budget_manager = BudgetManager()
        self.investment_manager = InvestmentManager()
        self.goal_manager = GoalManager()
        self.bill_manager = BillManager()
        self.category_manager = CategoryManager()
        self.recurring_manager = RecurringTransactionManager()

    def get_dashboard(self) -> Dict:
        accounts = self.account_manager.list_accounts()
        total_balance = sum(a["balance"] for a in accounts if a["is_active"])
        total_income = sum(a["balance"] for a in accounts if a["account_type"] == "income")
        total_expenses = sum(a["balance"] for a in accounts if a["account_type"] != "income")

        # Recent transactions
        recent = self.transaction_manager.get_transactions(limit=10)

        # Budget alerts
        budget_alerts = self.budget_manager.check_budget_alerts()

        # Upcoming bills
        upcoming_bills = self.bill_manager.get_upcoming_bills(7)

        return {
            "total_balance": total_balance,
            "total_income": total_income,
            "total_expenses": total_expenses,
            "net_worth": total_balance,
            "recent_transactions": recent,
            "budget_alerts": budget_alerts,
            "upcoming_bills": upcoming_bills,
            "accounts_count": len(accounts)
        }

    def get_account_summary(self) -> List[Dict]:
        return self.account_manager.list_accounts()

    def get_transaction_history(self, account_id: str = None, days: int = 30) -> List[Dict]:
        start = time.time() - (days * 86400)
        return self.transaction_manager.get_transactions(account_id, start_date=time.time() - days * 86400)

    def get_category_spending(self, account_id: str = None, days: int = 30) -> Dict[str, float]:
        start = time.time() - (days * 86400)
        return self.transaction_manager.get_spending_by_category(account_id, time.time() - days * 86400)

    def get_income_by_category(self, account_id: str = None, days: int = 30) -> Dict[str, float]:
        start = time.time() - (days * 86400)
        return self.transaction_manager.get_income_by_category(account_id, time.time() - days * 86400)


# Global instance
finance_agent = FinanceAgent()


# Convenience functions
def add_account(name: str, account_type: str, institution: str = "",
                currency: str = "USD", balance: float = 0.0) -> str:
    return finance_agent.account_manager.create_account(name, account_type, institution,
                                                         currency, balance)

def add_transaction(account_id: str, amount: float, category: str = "",
                    description: str = "", date: float = None, **kwargs) -> str:
    return finance_agent.transaction_manager.add_transaction(account_id, date or time.time(),
                                                              amount, category, **kwargs)

def get_transactions(account_id: str = None, days: int = 30) -> List[Dict]:
    return finance_agent.get_transaction_history(account_id, days)

def get_dashboard() -> Dict:
    return finance_agent.get_dashboard()

def add_budget(name: str, period: str, start_date: float, total_amount: float,
               category_limits: Dict[str, float] = None) -> str:
    return finance_agent.budget_manager.create_budget(name, period, start_date, total_amount,
                                                      category_limits, alert_threshold=0.8)

def get_budget_status(budget_id: str) -> Optional[Dict]:
    return finance_agent.budget_manager.get_budget_status(budget_id)

def add_bill(name: str, account_id: str, amount: float, due_day: int,
             frequency: str = "monthly", **kwargs) -> str:
    return finance_agent.bill_manager.add_bill(name, account_id, amount, due_day,
                                                frequency, **kwargs)

def get_upcoming_bills(days: int = 30) -> List[Dict]:
    return finance_agent.bill_manager.get_upcoming_bills(days)

def record_bill_payment(bill_id: str, date: float = None, amount: float = None, **kwargs) -> str:
    return finance_agent.bill_manager.record_payment(bill_id, date, amount, **kwargs)

def add_recurring_rule(name: str, account_id: str, amount: float, frequency: str,
                       **kwargs) -> str:
    return finance_agent.recurring_manager.create_rule(name, account_id, amount, **kwargs)

def process_recurring() -> List[str]:
    return finance_agent.recurring_manager.process_due_rules()

def add_category(name: str, parent: str = None, icon: str = "", color: str = "",
                 is_income: bool = False) -> str:
    cat_id = f"cat_{int(time.time() * 1000) % 100000000:08d}"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO categories (id, name, parent_id, icon, color, is_income, is_system, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (cat_id, name, parent, icon, color, is_income, False, 0))
    conn.commit()
    conn.close()
    return cat_id

def get_categories(income_only: bool = False) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    if income_only:
        cursor.execute("SELECT * FROM categories WHERE is_income = 1 ORDER BY name")
    else:
        cursor.execute("SELECT * FROM categories ORDER BY parent_id, sort_order, name")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "parent_id": r[2], "icon": r[3],
             "color": r[4], "is_income": bool(r[5])} for r in rows]


# Voice command integration
def finance_debug() -> str:
    dashboard = finance_agent.get_dashboard()
    output = f"Finance Dashboard:\n"
    output += f"  Net Worth: ${dashboard['net_worth']:,.2f}\n"
    output += f"  Total Balance: ${dashboard['total_balance']:,.2f}\n"
    output += f"  Monthly Income: ${dashboard['total_income']:,.2f}\n"
    output += f"  Monthly Expenses: ${dashboard['total_expenses']:,.2f}\n"
    output += f"  Accounts: {dashboard['accounts_count']}\n"
    if dashboard['budget_alerts']:
        output += f"  Budget Alerts: {len(dashboard['budget_alerts'])}\n"
    if dashboard['upcoming_bills']:
        output += f"  Upcoming Bills: {len(dashboard['upcoming_bills'])}\n"
    return output


def finance_dashboard() -> str:
    return finance_debug()


def finance_accounts() -> str:
    accounts = finance_agent.get_account_summary()
    if not accounts:
        return "No accounts configured."
    output = "Accounts:\n"
    for a in accounts:
        status = "✓" if a["is_active"] else "✗"
        output += f"{status} {a['name']} ({a['account_type']}): ${a['balance']:,.2f}\n"
    return output


def finance_transactions(account: str = None, days: int = 30) -> str:
    acc_id = None
    if account:
        acc = next((a for a in finance_agent.account_manager.list_accounts() if a["name"].lower() == account.lower()), None)
        if acc:
            acc_id = acc["id"]
    transactions = finance_agent.get_transaction_history(acc_id, days)
    if not transactions:
        return "No transactions found."
    output = f"Transactions ({len(transactions)}):\n"
    for t in transactions[:10]:
        sign = "+" if t.get("is_income") else "-"
        output += f"  {sign}${abs(t['amount']):.2f} | {t.get('category', 'Uncategorized')} | {t.get('description', 'No description')[:50]}\n"
    return output


def finance_budget(budget_name: str = None) -> str:
    if budget_name:
        # Get specific budget
        # Would need to search by name
        return f"Budget '{budget_name}' status: [implementation needed]"
    return "Budget overview: [implementation needed]"


def add_budget(name: str, period: str, start_date: str, total: float, **kwargs) -> str:
    # Parse start_date
    from datetime import datetime
    start_ts = datetime.strptime(start_date, "%Y-%m-%d").timestamp()
    budget_id = finance_agent.budget_manager.create_budget(name, period, start_ts, total_amount,
                                                            category_limits, alert_threshold=0.8)
    return f"Created budget: {budget_id}"


def add_transaction(account: str, amount: float, category: str = "",
                    description: str = "", date: str = None, **kwargs) -> str:
    # Find account
    accounts = finance_agent.account_manager.list_accounts()
    acc = next((a for a in accounts if a["name"].lower() == account.lower()), None)
    if not acc:
        return f"Account '{account}' not found."
    date_ts = datetime.strptime(date, "%Y-%m-%d").timestamp() if date else time.time()
    txn_id = finance_agent.transaction_manager.add_transaction(
        acc["id"], date_ts, amount, category, description=description, **kwargs)
    return f"Added transaction: {txn_id}"


def add_budget(name: str, period: str, start_date: str, total: float, **kwargs) -> str:
    # Similar to add_budget above
    pass


def add_bill(name: str, account: str, amount: float, due_day: int, frequency: str = "monthly") -> str:
    accounts = finance_agent.account_manager.list_accounts()
    acc = next((a for a in accounts if a["name"].lower() == account.lower()), None)
    if not acc:
        return f"Account '{account}' not found."
    bill_id = finance_agent.bill_manager.add_bill(name, acc["id"], amount, due_day, frequency, **kwargs)
    return f"Created bill: {bill_id}"


def get_upcoming_bills(days: int = 30) -> str:
    bills = finance_agent.bill_manager.get_upcoming_bills(days)
    if not bills:
        return "No upcoming bills."
    output = f"Upcoming Bills ({len(bills)}):\n"
    for b in bills:
        dt = datetime.fromtimestamp(b['next_due']).strftime('%Y-%m-%d')
        output += f"  • {b['name']}: ${b['amount']:.2f} due {dt} ({b['frequency']})\n"
    return output


def pay_bill(bill_id: str, amount: float = None, date: str = None) -> str:
    date_ts = datetime.strptime(date, "%Y-%m-%d").timestamp() if date else time.time()
    payment_id = finance_agent.bill_manager.record_payment(bill_id, date_ts, amount)
    return f"Recorded payment: {payment_id}"


def add_recurring(name: str, account: str, amount: float, frequency: str, **kwargs) -> str:
    accounts = finance_agent.account_manager.list_accounts()
    acc = next((a for a in accounts if a["name"].lower() == account.lower()), None)
    if not acc:
        return f"Account '{account}' not found."
    return finance_agent.recurring_manager.create_rule(name, acc["id"], amount, frequency, **kwargs)


def process_recurring() -> str:
    generated = finance_agent.recurring_manager.process_due_rules()
    return f"Generated {len(generated)} transactions from recurring rules."


def add_category(name: str, parent: str = None, icon: str = "", color: str = "", is_income: bool = False) -> str:
    return add_category(name, parent, icon, color, is_income)


def list_categories(income_only: bool = False) -> str:
    cats = get_categories(income_only)
    if not cats:
        return "No categories."
    output = "Categories:\n"
    for c in cats:
        prefix = "+" if c["is_income"] else "-"
        parent = f" > {c['parent_id']}" if c.get("parent_id") else ""
        output += f"  {prefix} {c['name']}{parent} ({c['icon']})\n"
    return output


def add_bill_cmd(name: str, account: str, amount: float, due_day: int, frequency: str = "monthly") -> str:
    accounts = finance_agent.account_manager.list_accounts()
    acc = next((a for a in accounts if a["name"].lower() == account.lower()), None)
    if not acc:
        return f"Account '{account}' not found."
    bill_id = finance_agent.bill_manager.add_bill(name, acc["id"], amount, due_day, frequency)
    return f"Created bill: {bill_id}"


def add_budget_cmd(name: str, period: str, start_date: str, total: float) -> str:
    from datetime import datetime
    start_ts = datetime.strptime(start_date, "%Y-%m-%d").timestamp()
    budget_id = finance_agent.budget_manager.create_budget(name, period, start_ts, total)
    return f"Created budget: {budget_id}"


if __name__ == "__main__":
    print("Finance Agent module loaded.")
    print("Available functions:")
    print("  add_account(name, type, institution, currency, balance)")
    print("  add_transaction(account, amount, category, description, date)")
    print("  get_transactions(account, days)")
    print("  get_dashboard()")
    print("  add_budget(name, period, start_date, total, category_limits)")
    print("  get_budget_status(budget_id)")
    print("  add_bill(name, account, amount, due_day, frequency)")
    print("  get_upcoming_bills(days)")
    print("  pay_bill(bill_id, amount, date)")
    print("  add_recurring(name, account, amount, frequency, ...)")
    print("  process_recurring()")
    print("  add_category(name, parent, icon, color, is_income)")
    print("  list_categories(income_only)")