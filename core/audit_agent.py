"""
Audit Agent - Phase 27
Audit automation, compliance checking, risk assessment, internal controls.
Fully local, no cloud dependencies.
"""

import os
import json
import time
import threading
import re
import hashlib
import random
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import namedtuple

Engagement = namedtuple('Engagement', ['id', 'engagement_number', 'client_name', 'client_id',
                                        'audit_type', 'scope', 'start_date', 'end_date',
                                        'planned_start', 'planned_end', 'status', 'lead_auditor',
                                        'team_members', 'materiality', 'risk_assessment',
                                        'planning_notes', 'created_at', 'updated_at'])
from datetime import datetime, timedelta
from pathlib import Path

from core.accounting_agent import accounting_agent
from core.finance_agent import finance_agent
from core.cybersecurity_agent import cybersecurity_agent


DB_DIR = "database"
AUDIT_DB = os.path.join(DB_DIR, "audit.db")

os.makedirs(DB_DIR, exist_ok=True)


def get_audit_connection():
    import sqlite3
    conn = sqlite3.connect(AUDIT_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")
    return conn


def init_audit_db():
    conn = get_audit_connection()
    cursor = conn.cursor()

    # Audit engagements
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_engagements (
            id TEXT PRIMARY KEY,
            engagement_number TEXT UNIQUE NOT NULL,
            client_name TEXT NOT NULL,
            client_id TEXT,
            audit_type TEXT NOT NULL,
            scope TEXT,
            start_date REAL NOT NULL,
            end_date REAL,
            planned_start REAL,
            planned_end REAL,
            status TEXT DEFAULT 'planning',
            lead_auditor TEXT,
            team_members TEXT,
            materiality REAL,
            risk_assessment TEXT,
            planning_notes TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Audit programs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_programs (
            id TEXT PRIMARY KEY,
            engagement_id TEXT NOT NULL,
            area TEXT NOT NULL,
            objective TEXT NOT NULL,
            procedures TEXT NOT NULL,
            risk_level TEXT,
            assigned_to TEXT,
            status TEXT DEFAULT 'not_started',
            started_at REAL,
            completed_at REAL,
            reviewer TEXT,
            reviewed_at REAL,
            findings_count INTEGER DEFAULT 0,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (engagement_id) REFERENCES audit_engagements(id)
        )
    """)

    # Workpapers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workpapers (
            id TEXT PRIMARY KEY,
            engagement_id TEXT NOT NULL,
            program_id TEXT,
            reference TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            preparer TEXT,
            prepared_at REAL,
            reviewer TEXT,
            reviewed_at REAL,
            status TEXT DEFAULT 'draft',
            content TEXT,
            source_documents TEXT,
            cross_references TEXT,
            tickmarks TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (engagement_id) REFERENCES audit_engagements(id)
        )
    """)

    # Findings/Issues
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_findings (
            id TEXT PRIMARY KEY,
            engagement_id TEXT NOT NULL,
            workpaper_id TEXT,
            finding_number TEXT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            severity TEXT,
            category TEXT,
            root_cause TEXT,
            impact TEXT,
            recommendation TEXT,
            management_response TEXT,
            status TEXT DEFAULT 'open',
            assigned_to TEXT,
            target_date REAL,
            resolved_at REAL,
            mitre_techniques TEXT,
            cwe_ids TEXT,
            cve_ids TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (engagement_id) REFERENCES audit_engagements(id)
        )
    """)

    # Evidence
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_evidence (
            id TEXT PRIMARY KEY,
            engagement_id TEXT NOT NULL,
            workpaper_id TEXT,
            finding_id TEXT,
            evidence_type TEXT,
            description TEXT NOT NULL,
            source TEXT,
            file_path TEXT,
            hash_value TEXT,
            collected_by TEXT,
            collected_at REAL,
            relevance TEXT,
            reliability TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY (engagement_id) REFERENCES audit_engagements(id)
        )
    """)

    # Risk assessments
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS risk_assessments (
            id TEXT PRIMARY KEY,
            engagement_id TEXT NOT NULL,
            area TEXT NOT NULL,
            risk_description TEXT NOT NULL,
            likelihood TEXT,
            impact TEXT,
            risk_rating TEXT,
            inherent_risk TEXT,
            control_risk TEXT,
            detection_risk TEXT,
            mitigation_plan TEXT,
            owner TEXT,
            target_date REAL,
            status TEXT DEFAULT 'identified',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (engagement_id) REFERENCES audit_engagements(id)
        )
    """)

    # Sampling
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_samples (
            id TEXT PRIMARY KEY,
            engagement_id TEXT NOT NULL,
            area TEXT NOT NULL,
            population_size INTEGER,
            sample_size INTEGER,
            sampling_method TEXT,
            confidence_level REAL,
            tolerable_error REAL,
            expected_error REAL,
            selected_items TEXT,
            tested_items TEXT,
            exceptions_found INTEGER DEFAULT 0,
            projected_error REAL,
            upper_error_limit REAL,
            conclusion TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (engagement_id) REFERENCES audit_engagements(id)
        )
    """)

    # Compliance frameworks
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compliance_frameworks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            version TEXT,
            description TEXT,
            category TEXT,
            jurisdiction TEXT,
            effective_date REAL,
            expiry_date REAL,
            is_active BOOLEAN DEFAULT 1,
            requirements TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Compliance assessments
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compliance_assessments (
            id TEXT PRIMARY KEY,
            engagement_id TEXT NOT NULL,
            framework_id TEXT NOT NULL,
            requirement_id TEXT NOT NULL,
            requirement_text TEXT NOT NULL,
            status TEXT DEFAULT 'not_assessed',
            evidence TEXT,
            notes TEXT,
            assessed_by TEXT,
            assessed_at REAL,
            remediation_plan TEXT,
            remediation_deadline REAL,
            remediation_status TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (engagement_id) REFERENCES audit_engagements(id)
        )
    """)

    # Management letters / reports
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_reports (
            id TEXT PRIMARY KEY,
            engagement_id TEXT NOT NULL,
            report_type TEXT,
            title TEXT NOT NULL,
            executive_summary TEXT,
            body TEXT,
            conclusions TEXT,
            recommendations TEXT,
            management_response TEXT,
            issued_at REAL,
            issued_by TEXT,
            version INTEGER DEFAULT 1,
            status TEXT DEFAULT 'draft',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (engagement_id) REFERENCES audit_engagements(id)
        )
    """)

    # Quality control / peer review
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quality_reviews (
            id TEXT PRIMARY KEY,
            engagement_id TEXT NOT NULL,
            workpaper_id TEXT,
            reviewer TEXT NOT NULL,
            review_type TEXT,
            status TEXT DEFAULT 'pending',
            questions TEXT,
            findings TEXT,
            cleared_at REAL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (engagement_id) REFERENCES audit_engagements(id)
        )
    """)

    # Time tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS time_entries (
            id TEXT PRIMARY KEY,
            engagement_id TEXT NOT NULL,
            staff_id TEXT NOT NULL,
            date REAL NOT NULL,
            hours REAL NOT NULL,
            activity TEXT,
            description TEXT,
            billable BOOLEAN DEFAULT 1,
            rate REAL,
            created_at REAL NOT NULL
        )
    """)

    # Engagement budgets
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS engagement_budgets (
            id TEXT PRIMARY KEY,
            engagement_id TEXT NOT NULL,
            total_hours REAL,
            total_fee REAL,
            spent_hours REAL DEFAULT 0,
            spent_fee REAL DEFAULT 0,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    conn.commit()
    conn.close()


init_audit_db()


@dataclass
class AuditEngagement:
    id: str
    engagement_number: str
    client_name: str
    client_id: str
    audit_type: str
    scope: str
    start_date: float
    end_date: Optional[float]
    planned_start: float
    planned_end: float
    status: str
    lead_auditor: str
    team_members: List[str]
    materiality: float
    risk_assessment: Dict
    planning_notes: str
    created_at: float
    updated_at: float


@dataclass
class AuditProgram:
    id: str
    engagement_id: str
    area: str
    objective: str
    procedures: List[Dict]
    risk_level: str
    assigned_to: str
    status: str
    started_at: Optional[float]
    completed_at: Optional[float]
    reviewer: Optional[str]
    reviewed_at: Optional[float]
    findings_count: int
    created_at: float
    updated_at: float


@dataclass
class Workpaper:
    id: str
    engagement_id: str
    program_id: Optional[str]
    reference: str
    title: str
    description: str
    preparer: str
    prepared_at: float
    reviewer: Optional[str]
    reviewed_at: Optional[float]
    status: str
    content: str
    source_documents: List[str]
    cross_references: List[str]
    tickmarks: List[str]
    created_at: float
    updated_at: float


@dataclass
class AuditFinding:
    id: str
    engagement_id: str
    workpaper_id: Optional[str]
    finding_number: str
    title: str
    description: str
    severity: str
    category: str
    root_cause: str
    impact: str
    recommendation: str
    management_response: str
    status: str
    assigned_to: str
    target_date: Optional[float]
    resolved_at: Optional[float]
    mitre_techniques: List[str]
    cwe_ids: List[str]
    cve_ids: List[str]
    created_at: float
    updated_at: float


@dataclass
class AuditEvidence:
    id: str
    engagement_id: str
    workpaper_id: Optional[str]
    finding_id: Optional[str]
    evidence_type: str
    description: str
    source: str
    file_path: str
    hash_value: str
    collected_by: str
    collected_at: float
    relevance: str
    reliability: str
    created_at: float


@dataclass
class RiskAssessment:
    id: str
    engagement_id: str
    area: str
    risk_description: str
    likelihood: str
    impact: str
    risk_rating: str
    inherent_risk: str
    control_risk: str
    detection_risk: str
    mitigation_plan: str
    owner: str
    target_date: float
    status: str
    created_at: float
    updated_at: float


@dataclass
class AuditSample:
    id: str
    engagement_id: str
    area: str
    population_size: int
    sample_size: int
    sampling_method: str
    confidence_level: float
    tolerable_error: float
    expected_error: float
    selected_items: List[str]
    tested_items: List[str]
    exceptions_found: int
    projected_error: float
    upper_error_limit: float
    conclusion: str
    created_at: float
    updated_at: float


class AuditEngagementManager:
    def __init__(self):
        self._seed_engagements()

    def _seed_engagements(self):
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM audit_engagements")
        count = cursor.fetchone()[0]
        conn.close()

        if count > 0:
            return

        # Seed with example engagement
        self.create_engagement(
            client_name="Acme Corporation",
            client_id="client_001",
            audit_type="financial",
            scope="Full financial statement audit for FY2024",
            planned_start=time.time(),
            planned_end=time.time() + 86400 * 90,
            lead_auditor="John Smith",
            team_members=["Jane Doe", "Bob Wilson"],
            materiality=50000.0,
            planning_notes="First year audit. High risk in revenue recognition."
        )

    def create_engagement(self, client_name: str, client_id: str, audit_type: str,
                          scope: str, planned_start: float, planned_end: float,
                          lead_auditor: str, team_members: List[str],
                          materiality: float, planning_notes: str = "") -> str:
        engagement_id = f"eng_{int(time.time() * 1000) % 100000000:08d}"
        engagement_number = f"ENG-{datetime.now().strftime('%Y%m%d')}-{int(time.time() * 1000) % 10000:04d}"

        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_engagements (id, engagement_number, client_name, client_id, audit_type, scope,
                                          start_date, end_date, planned_start, planned_end, status, lead_auditor,
                                          team_members, materiality, risk_assessment, planning_notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (engagement_id, engagement_number, client_name, client_id, audit_type, scope,
              time.time(), None, planned_start, planned_end, 'planning', lead_auditor,
              json.dumps(team_members), materiality, '{}', planning_notes, time.time(), time.time()))
        conn.commit()
        conn.close()
        return self.get_engagement(engagement_id)

    def get_engagement(self, engagement_id: str) -> Optional[Dict]:
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, engagement_number, client_name, client_id, audit_type, scope,
                   start_date, end_date, planned_start, planned_end, status, lead_auditor,
                   team_members, materiality, risk_assessment, planning_notes, created_at, updated_at
            FROM audit_engagements WHERE id = ?
        """, (engagement_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            # Safely parse team_members
            team_members = []
            if row[12] and isinstance(row[12], str):
                try:
                    team_members = json.loads(row[12]) if row[12].strip() else []
                except (json.JSONDecodeError, AttributeError):
                    team_members = []
            else:
                team_members = []

            # Safely parse risk_assessment
            risk_assessment = {}
            if row[14] and isinstance(row[14], str):
                try:
                    risk_assessment = json.loads(row[14]) if row[14].strip() else {}
                except (json.JSONDecodeError, AttributeError):
                    risk_assessment = {}
            else:
                risk_assessment = {}

            return {
                "id": row[0], "engagement_number": row[1], "client_name": row[2],
                "client_id": row[3], "audit_type": row[4], "scope": row[5],
                "start_date": row[6], "end_date": row[7], "planned_start": row[8],
                "planned_end": row[9], "status": row[10], "lead_auditor": row[11],
                "team_members": team_members,
                "materiality": row[13], "risk_assessment": risk_assessment,
                "planning_notes": row[15], "created_at": row[16], "updated_at": row[17]
            }
        return None

    def list_engagements(self, status: str = None) -> List[Dict]:
        conn = get_audit_connection()
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM audit_engagements WHERE status = ? ORDER BY created_at DESC", (status,))
        else:
            cursor.execute("SELECT * FROM audit_engagements ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "engagement_number": r[1], "client_name": r[2],
             "audit_type": r[4], "status": r[10], "lead_auditor": r[11],
             "materiality": r[13]}
            for r in rows
        ]

    def update_status(self, engagement_id: str, status: str) -> bool:
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE audit_engagements SET status = ?, updated_at = ? WHERE id = ?",
                       (status, time.time(), engagement_id))
        conn.commit()
        conn.close()
        return True


class AuditProgramManager:
    def create_program(self, engagement_id: str, area: str, objective: str,
                       procedures: List[Dict], risk_level: str = "medium",
                       assigned_to: str = "") -> str:
        program_id = f"prog_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_programs (id, engagement_id, area, objective, procedures,
                                       risk_level, assigned_to, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'not_started', ?, ?)
        """, (program_id, engagement_id, area, objective, json.dumps(procedures),
              risk_level, assigned_to, time.time(), time.time()))
        conn.commit()
        conn.close()
        return program_id

    def get_program(self, program_id: str) -> Optional[Dict]:
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_programs WHERE id = ?", (program_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "engagement_id": row[1], "area": row[2],
                "objective": row[3], "procedures": json.loads(row[4]) if row[4] else [],
                "risk_level": row[5], "assigned_to": row[6], "status": row[7],
                "started_at": row[8], "completed_at": row[9], "reviewer": row[10],
                "reviewed_at": row[11], "findings_count": row[12],
                "created_at": row[13], "updated_at": row[14]
            }
        return None

    def list_programs(self, engagement_id: str) -> List[Dict]:
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_programs WHERE engagement_id = ? ORDER BY created_at", (engagement_id,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "area": r[2], "objective": r[3], "risk_level": r[5],
             "assigned_to": r[6], "status": r[7], "findings_count": r[12]}
            for r in rows
        ]

    def update_status(self, program_id: str, status: str) -> bool:
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE audit_programs SET status = ?, updated_at = ? WHERE id = ?",
                       (status, time.time(), program_id))
        conn.commit()
        conn.close()
        return True


class WorkpaperManager:
    def create_workpaper(self, engagement_id: str, reference: str, title: str,
                         description: str = "", program_id: str = None,
                         preparer: str = "") -> str:
        wp_id = f"wp_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO workpapers (id, engagement_id, program_id, reference, title, description,
                                   preparer, prepared_at, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?)
        """, (wp_id, engagement_id, program_id, reference, title, description,
              preparer, time.time(), time.time(), time.time()))
        conn.commit()
        conn.close()
        return wp_id

    def get_workpaper(self, wp_id: str) -> Optional[Dict]:
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workpapers WHERE id = ?", (wp_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "engagement_id": row[1], "program_id": row[2],
                "reference": row[3], "title": row[4], "description": row[5],
                "preparer": row[6], "prepared_at": row[7], "reviewer": row[8],
                "reviewed_at": row[9], "status": row[10], "content": row[11],
                "source_documents": json.loads(row[12]) if row[12] else [],
                "cross_references": json.loads(row[13]) if row[13] else [],
                "tickmarks": json.loads(row[14]) if row[14] else [],
                "created_at": row[15], "updated_at": row[16]
            }
        return None

    def list_workpapers(self, engagement_id: str, program_id: str = None) -> List[Dict]:
        conn = get_audit_connection()
        cursor = conn.cursor()
        if program_id:
            cursor.execute("SELECT * FROM workpapers WHERE engagement_id = ? AND program_id = ? ORDER BY reference",
                           (engagement_id, program_id))
        else:
            cursor.execute("SELECT * FROM workpapers WHERE engagement_id = ? ORDER BY reference", (engagement_id,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "reference": r[3], "title": r[4], "status": r[10],
             "preparer": r[6], "reviewer": r[8]}
            for r in rows
        ]

    def update_content(self, wp_id: str, content: str, status: str = None) -> bool:
        conn = get_audit_connection()
        cursor = conn.cursor()
        if status:
            cursor.execute("UPDATE workpapers SET content = ?, status = ?, updated_at = ? WHERE id = ?",
                           (content, status, time.time(), wp_id))
        else:
            cursor.execute("UPDATE workpapers SET content = ?, updated_at = ? WHERE id = ?",
                           (content, time.time(), wp_id))
        conn.commit()
        conn.close()
        return True


class FindingManager:
    def create_finding(self, engagement_id: str, title: str, description: str,
                       severity: str = "medium", category: str = "",
                       workpaper_id: str = None, finding_number: str = None) -> str:
        finding_id = f"fnd_{int(time.time() * 1000) % 100000000:08d}"
        if not finding_number:
            finding_number = f"F-{int(time.time()) % 10000:04d}"
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_findings (id, engagement_id, workpaper_id, finding_number, title, description,
                                       severity, category, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
        """, (finding_id, engagement_id, workpaper_id, finding_number, title, description,
              severity, category, time.time(), time.time()))
        conn.commit()
        conn.close()
        return finding_id

    def get_finding(self, finding_id: str) -> Optional[Dict]:
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_findings WHERE id = ?", (finding_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "engagement_id": row[1], "workpaper_id": row[2],
                "finding_number": row[3], "title": row[4], "description": row[5],
                "severity": row[6], "category": row[7], "root_cause": row[8],
                "impact": row[9], "recommendation": row[10], "management_response": row[11],
                "status": row[12], "assigned_to": row[13], "target_date": row[14],
                "resolved_at": row[15], "mitre_techniques": json.loads(row[16]) if row[16] else [],
                "cwe_ids": json.loads(row[17]) if row[17] else [],
                "cve_ids": json.loads(row[18]) if row[18] else [],
                "created_at": row[19], "updated_at": row[20]
            }
        return None

    def list_findings(self, engagement_id: str, status: str = None, severity: str = None) -> List[Dict]:
        conn = get_audit_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM audit_findings WHERE engagement_id = ?"
        params = [engagement_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "finding_number": r[3], "title": r[4], "severity": r[6],
             "category": r[7], "status": r[12], "assigned_to": r[13]}
            for r in rows
        ]

    def update_finding(self, finding_id: str, **kwargs) -> bool:
        conn = get_audit_connection()
        cursor = conn.cursor()
        updates = []
        params = []
        for key, value in kwargs.items():
            if key in ["title", "description", "severity", "category", "root_cause",
                       "impact", "recommendation", "management_response", "status",
                       "assigned_to", "target_date", "resolved_at"]:
                updates.append(f"{key} = ?")
                params.append(value)
        if updates:
            updates.append("updated_at = ?")
            params.append(time.time())
            params.append(finding_id)
            cursor.execute(f"UPDATE audit_findings SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
        conn.close()
        return True


class EvidenceManager:
    def add_evidence(self, engagement_id: str, description: str, evidence_type: str = "document",
                     workpaper_id: str = None, finding_id: str = None,
                     source: str = "", file_path: str = "", collected_by: str = "",
                     relevance: str = "", reliability: str = "") -> str:
        evidence_id = f"evd_{int(time.time() * 1000) % 100000000:08d}"
        hash_value = hashlib.sha256(file_path.encode()).hexdigest() if file_path else ""
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_evidence (id, engagement_id, workpaper_id, finding_id,
                                       evidence_type, description, source, file_path,
                                       hash_value, collected_by, collected_at, relevance, reliability, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (evidence_id, engagement_id, workpaper_id, finding_id,
              evidence_type, description, source, file_path,
              hash_value, collected_by, time.time(), relevance, reliability, time.time()))
        conn.commit()
        conn.close()
        return evidence_id

    def get_evidence(self, evidence_id: str) -> Optional[Dict]:
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_evidence WHERE id = ?", (evidence_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "engagement_id": row[1], "workpaper_id": row[2],
                "finding_id": row[3], "evidence_type": row[4], "description": row[5],
                "source": row[6], "file_path": row[7], "hash_value": row[8],
                "collected_by": row[9], "collected_at": row[10], "relevance": row[11],
                "reliability": row[12], "created_at": row[13]
            }
        return None

    def list_evidence(self, engagement_id: str, workpaper_id: str = None, finding_id: str = None) -> List[Dict]:
        conn = get_audit_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM audit_evidence WHERE engagement_id = ?"
        params = [engagement_id]
        if workpaper_id:
            query += " AND workpaper_id = ?"
            params.append(workpaper_id)
        if finding_id:
            query += " AND finding_id = ?"
            params.append(finding_id)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "evidence_type": r[4], "description": r[5],
             "source": r[6], "file_path": r[7], "collected_by": r[9]}
            for r in rows
        ]


class RiskAssessmentManager:
    def assess_risk(self, engagement_id: str, area: str, risk_description: str,
                    likelihood: str, impact: str, inherent_risk: str = "",
                    control_risk: str = "", detection_risk: str = "",
                    mitigation_plan: str = "", owner: str = "",
                    target_date: float = None) -> str:
        risk_id = f"risk_{int(time.time() * 1000) % 100000000:08d}"
        risk_rating = self._calculate_rating(likelihood, impact)
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO risk_assessments (id, engagement_id, area, risk_description,
                                         likelihood, impact, risk_rating, inherent_risk,
                                         control_risk, detection_risk, mitigation_plan,
                                         owner, target_date, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'identified', ?, ?)
        """, (risk_id, engagement_id, area, risk_description,
              likelihood, impact, risk_rating, inherent_risk,
              control_risk, detection_risk, mitigation_plan,
              owner, target_date, time.time(), time.time()))
        conn.commit()
        conn.close()
        return risk_id

    def _calculate_rating(self, likelihood: str, impact: str) -> str:
        likelihood_map = {"very_low": 1, "low": 2, "medium": 3, "high": 4, "very_high": 5}
        impact_map = {"very_low": 1, "low": 2, "medium": 3, "high": 4, "very_high": 5}
        score = likelihood_map.get(likelihood.lower(), 3) * impact_map.get(impact.lower(), 3)
        if score >= 16: return "critical"
        elif score >= 12: return "high"
        elif score >= 6: return "medium"
        elif score >= 3: return "low"
        return "very_low"

    def get_risk(self, risk_id: str) -> Optional[Dict]:
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM risk_assessments WHERE id = ?", (risk_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "engagement_id": row[1], "area": row[2],
                "risk_description": row[3], "likelihood": row[4], "impact": row[5],
                "risk_rating": row[6], "inherent_risk": row[7], "control_risk": row[8],
                "detection_risk": row[9], "mitigation_plan": row[10], "owner": row[11],
                "target_date": row[12], "status": row[13],
                "created_at": row[14], "updated_at": row[15]
            }
        return None

    def list_risks(self, engagement_id: str, status: str = None) -> List[Dict]:
        conn = get_audit_connection()
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM risk_assessments WHERE engagement_id = ? AND status = ? ORDER BY risk_rating DESC",
                           (engagement_id, status))
        else:
            cursor.execute("SELECT * FROM risk_assessments WHERE engagement_id = ? ORDER BY risk_rating DESC", (engagement_id,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "area": r[2], "risk_description": r[3],
             "likelihood": r[4], "impact": r[5], "risk_rating": r[6],
             "status": r[13], "owner": r[11]}
            for r in rows
        ]


class SamplingManager:
    def create_sample(self, engagement_id: str, area: str, population_size: int,
                      sample_size: int, sampling_method: str = "random",
                      confidence_level: float = 0.95, tolerable_error: float = 0.05,
                      expected_error: float = 0.01) -> str:
        sample_id = f"smpl_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_samples (id, engagement_id, area, population_size, sample_size,
                                      sampling_method, confidence_level, tolerable_error,
                                      expected_error, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sample_id, engagement_id, area, population_size, sample_size,
              sampling_method, confidence_level, tolerable_error, expected_error,
              time.time(), time.time()))
        conn.commit()
        conn.close()
        return sample_id

    def select_items(self, sample_id: str, items: List[str]) -> bool:
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE audit_samples SET selected_items = ?, updated_at = ? WHERE id = ?",
                       (json.dumps(items), time.time(), sample_id))
        conn.commit()
        conn.close()
        return True

    def record_results(self, sample_id: str, tested_items: List[str],
                       exceptions_found: int, projected_error: float = 0,
                       upper_error_limit: float = 0, conclusion: str = "") -> bool:
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE audit_samples SET tested_items = ?, exceptions_found = ?,
                                    projected_error = ?, upper_error_limit = ?,
                                    conclusion = ?, updated_at = ?
            WHERE id = ?
        """, (json.dumps(tested_items), exceptions_found, projected_error,
              upper_error_limit, conclusion, time.time(), sample_id))
        conn.commit()
        conn.close()
        return True


class ComplianceManager:
    def add_framework(self, name: str, version: str = "", description: str = "",
                      category: str = "", jurisdiction: str = "",
                      effective_date: float = None, requirements: List[Dict] = None) -> str:
        fw_id = f"fw_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO compliance_frameworks (id, name, version, description, category,
                                              jurisdiction, effective_date, requirements, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (fw_id, name, version, description, category, jurisdiction,
              effective_date, json.dumps(requirements or []), time.time(), time.time()))
        conn.commit()
        conn.close()
        return fw_id

    def assess_compliance(self, engagement_id: str, framework_id: str,
                          requirement_id: str, requirement_text: str,
                          assessed_by: str = "") -> str:
        assess_id = f"comp_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO compliance_assessments (id, engagement_id, framework_id, requirement_id,
                                               requirement_text, assessed_by, assessed_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (assess_id, engagement_id, framework_id, requirement_id,
              requirement_text, assessed_by, time.time(), time.time(), time.time()))
        conn.commit()
        conn.close()
        return assess_id

    def update_assessment(self, assessment_id: str, status: str = None,
                          evidence: str = None, notes: str = None,
                          remediation_plan: str = None, remediation_deadline: float = None) -> bool:
        conn = get_audit_connection()
        cursor = conn.cursor()
        updates = []
        params = []
        for key, value in [("status", status), ("evidence", evidence), ("notes", notes),
                          ("remediation_plan", remediation_plan), ("remediation_deadline", remediation_deadline)]:
            if value is not None:
                updates.append(f"{key} = ?")
                params.append(value)
        if updates:
            updates.append("updated_at = ?")
            params.append(time.time())
            params.append(assessment_id)
            cursor.execute(f"UPDATE compliance_assessments SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
        conn.close()
        return True


class AuditReportGenerator:
    def generate_report(self, engagement_id: str, report_type: str,
                        title: str, executive_summary: str = "",
                        body: str = "", conclusions: str = "",
                        recommendations: str = "") -> str:
        report_id = f"rpt_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_reports (id, engagement_id, report_type, title,
                                      executive_summary, body, conclusions, recommendations,
                                      status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?)
        """, (report_id, engagement_id, report_type, title, executive_summary,
              body, conclusions, recommendations, time.time(), time.time()))
        conn.commit()
        conn.close()
        return report_id

    def get_report(self, report_id: str) -> Optional[Dict]:
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_reports WHERE id = ?", (report_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "engagement_id": row[1], "report_type": row[2],
                "title": row[3], "executive_summary": row[4], "body": row[5],
                "conclusions": row[6], "recommendations": row[7],
                "management_response": row[8], "issued_at": row[9],
                "issued_by": row[10], "version": row[11], "status": row[12],
                "created_at": row[13], "updated_at": row[14]
            }
        return None


class QualityControl:
    def create_review(self, engagement_id: str, reviewer: str, review_type: str,
                      workpaper_id: str = None) -> str:
        review_id = f"qc_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO quality_reviews (id, engagement_id, workpaper_id, reviewer,
                                        review_type, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
        """, (review_id, engagement_id, workpaper_id, reviewer, review_type,
              time.time(), time.time()))
        conn.commit()
        conn.close()
        return review_id

    def complete_review(self, review_id: str, questions: List[str] = None,
                        findings: List[str] = None) -> bool:
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE quality_reviews SET status = 'completed', questions = ?,
                                      findings = ?, cleared_at = ?, updated_at = ?
            WHERE id = ?
        """, (json.dumps(questions or []), json.dumps(findings or []),
              time.time(), time.time(), review_id))
        conn.commit()
        conn.close()
        return True


class TimeTracking:
    def log_time(self, engagement_id: str, staff_id: str, hours: float,
                 activity: str = "", description: str = "", billable: bool = True,
                 rate: float = 0) -> str:
        entry_id = f"time_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO time_entries (id, engagement_id, staff_id, date, hours,
                                     activity, description, billable, rate, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (entry_id, engagement_id, staff_id, time.time(), hours,
              activity, description, billable, rate, time.time()))
        conn.commit()
        conn.close()
        return entry_id

    def get_time_summary(self, engagement_id: str) -> Dict:
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT staff_id, SUM(hours), SUM(hours * rate)
            FROM time_entries WHERE engagement_id = ? GROUP BY staff_id
        """, (engagement_id,))
        rows = cursor.fetchall()
        conn.close()
        total_hours = sum(r[1] for r in rows)
        total_fee = sum(r[2] for r in rows)
        return {
            "total_hours": total_hours, "total_fee": total_fee,
            "by_staff": {r[0]: {"hours": r[1], "fee": r[2]} for r in rows}
        }


# Module-level helper functions for voice commands
engagement_mgr = AuditEngagementManager()
program_mgr = AuditProgramManager()
workpaper_mgr = WorkpaperManager()
finding_mgr = FindingManager()
evidence_mgr = EvidenceManager()
risk_mgr = RiskAssessmentManager()
sampling_mgr = SamplingManager()
compliance_mgr = ComplianceManager()
report_mgr = AuditReportGenerator()
qc_mgr = QualityControl()
time_mgr = TimeTracking()


def audit_debug() -> str:
    """Debug info for audit agent."""
    conn = get_audit_connection()
    cursor = conn.cursor()
    tables = ["audit_engagements", "audit_programs", "workpapers", "audit_findings",
              "audit_evidence", "risk_assessments", "audit_samples",
              "compliance_frameworks", "compliance_assessments", "audit_reports",
              "quality_reviews", "time_entries", "engagement_budgets"]
    output = "Audit Agent Debug:\n"
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        count = cursor.fetchone()[0]
        output += f"  {t}: {count} records\n"
    conn.close()
    return output


def list_engagements() -> List[Dict]:
    return engagement_mgr.list_engagements()


def create_audit_engagement(client_name: str, client_id: str, audit_type: str,
                            scope: str, planned_start: float, planned_end: float,
                            lead_auditor: str, team: List[str],
                            materiality: float = 0, planning: str = ""):
    eng = engagement_mgr.create_engagement(
        client_name, client_id, audit_type, scope,
        planned_start, planned_end, lead_auditor, team, materiality, planning
    )
    return Engagement(**eng)


def start_audit(engagement_id: str) -> bool:
    return engagement_mgr.update_status(engagement_id, "fieldwork")


def complete_audit(engagement_id: str) -> bool:
    return engagement_mgr.update_status(engagement_id, "completed")


def create_audit_program(engagement_id: str, area: str, objective: str,
                         procedures: List[str], risk: str, assigned: str) -> str:
    proc_list = [{"step": i+1, "desc": p} for i, p in enumerate(procedures)]
    return program_mgr.create_program(engagement_id, area, objective, proc_list, risk, assigned)


def create_workpaper(engagement_id: str, reference: str, title: str,
                     description: str = "", program_id: str = None,
                     preparer: str = "system") -> str:
    return workpaper_mgr.create_workpaper(engagement_id, reference, title, description, program_id, preparer)


def update_workpaper(wp_id: str, content: str, status: str = "draft") -> bool:
    return workpaper_mgr.update_content(wp_id, content, status)


def create_finding(engagement_id: str, title: str, description: str,
                   severity: str, category: str, workpaper_id: str = None,
                   root_cause: str = "", impact: str = "", recommendation: str = "",
                   assigned_to: str = "", target_date: str = None,
                   mitre_techniques: List[str] = None) -> str:
    finding_number = f"F-{int(time.time()) % 10000:04d}"
    # Store additional fields in the description or use a custom approach
    # For now, just create the basic finding
    return finding_mgr.create_finding(
        engagement_id, title, description, severity, category, workpaper_id, finding_number
    )


def add_evidence(engagement_id: str, evidence_type: str, description: str,
                 source: str, file_path: str = None, collected_by: str = "system",
                 workpaper_id: str = None, finding_id: str = None,
                 relevance: str = "supports", reliability: str = "high") -> str:
    return evidence_mgr.add_evidence(
        engagement_id, description, evidence_type,
        workpaper_id, finding_id, source, file_path or "",
        collected_by, relevance, reliability
    )


def assess_risk(engagement_id: str, area: str, risk_description: str,
                likelihood: str, impact: str) -> str:
    return risk_mgr.assess_risk(engagement_id, area, risk_description, likelihood, impact)


def create_audit_sample(engagement_id: str, area: str, population: int,
                        confidence: float, tolerable_error: float,
                        expected_error: float) -> str:
    # Calculate sample size using attribute sampling formula
    # n = (Z^2 * p * (1-p)) / E^2, simplified for attribute sampling
    z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
    z = z_scores.get(confidence, 1.96)
    p = expected_error if expected_error > 0 else 0.5
    e = tolerable_error
    sample_size = int((z**2 * p * (1-p)) / (e**2))
    sample_size = min(sample_size, population)
    return sampling_mgr.create_sample(
        engagement_id, area, population, sample_size,
        "random", confidence, tolerable_error, expected_error
    )


def register_framework(name: str, version: str, description: str,
                       category: str, jurisdiction: str,
                       requirements: List[Dict]) -> str:
    return compliance_mgr.add_framework(name, version, description, category, jurisdiction, time.time(), requirements)


def assess_compliance(engagement_id: str, framework_id: str) -> str:
    conn = get_audit_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT requirements FROM compliance_frameworks WHERE id = ?", (framework_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return "Framework not found."
    reqs = json.loads(row[0]) if row[0] else []
    results = []
    for req in reqs:
        aid = compliance_mgr.assess_compliance(engagement_id, framework_id, req.get("id", ""), req.get("text", ""))
        results.append(f"  {req.get('id', 'N/A')}: {req.get('text', '')[:50]}... -> assessed")
    return f"Compliance assessment for {framework_id}:\n" + "\n".join(results)


def generate_audit_report(engagement_id: str, report_type: str) -> str:
    report_id = report_mgr.generate_report(
        engagement_id, report_type, f"{report_type.title()} Report",
        "", "", "", ""
    )
    return f"Generated {report_type} report: {report_id}"


def create_quality_review(engagement_id: str, workpaper_id: str,
                          reviewer: str, review_type: str) -> str:
    return qc_mgr.create_review(engagement_id, reviewer, review_type, workpaper_id)


def log_audit_time(engagement_id: str, staff: str, hours: float,
                   activity: str, description: str = "",
                   billable: bool = True, rate: float = 0) -> str:
    return time_mgr.log_time(engagement_id, staff, hours, activity, description, billable, rate)


def create_engagement_budget(engagement_id: str, total_hours: float,
                             total_fee: float) -> str:
    conn = get_audit_connection()
    cursor = conn.cursor()
    bid = f"bud_{int(time.time() * 1000) % 100000000:08d}"
    cursor.execute("""
        INSERT INTO engagement_budgets (id, engagement_id, total_hours, total_fee, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (bid, engagement_id, total_hours, total_fee, time.time(), time.time()))
    conn.commit()
    conn.close()
    return bid


def get_engagement_budget(budget_id: str) -> Optional[Dict]:
    conn = get_audit_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM engagement_budgets WHERE id = ?", (budget_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0], "engagement_id": row[1], "total_hours": row[2],
            "total_fee": row[3], "spent_hours": row[4], "spent_fee": row[5]
        }
    return None


# ==========================================
# ADVANCED AUDIT FEATURES
# ==========================================

class EngagementLetterGenerator:
    @staticmethod
    def generate(engagement_id: str, template: str = "standard") -> str:
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_engagements WHERE id = ?", (engagement_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return "Engagement not found."
        
        eng = {
            "engagement_number": row[1], "client_name": row[2], "client_id": row[3],
            "audit_type": row[4], "scope": row[5], "planned_start": row[8],
            "planned_end": row[9], "lead_auditor": row[11], "materiality": row[13],
        }
        
        if template == "standard":
            return f"""
ENGAGEMENT LETTER
{eng['engagement_number']}

Date: {datetime.fromtimestamp(time.time()).strftime('%B %d, %Y')}

To the Board of Directors and Management of {eng['client_name']}

Dear Sir/Madam,

We are pleased to confirm our understanding of the terms and objectives of our engagement
and the nature and limitations of the services we will provide.

1. ENGAGEMENT OBJECTIVES
We will audit the financial statements of {eng['client_name']} as of and for the year
ending {datetime.fromtimestamp(eng['planned_end']).strftime('%B %d, %Y')}.

2. SCOPE OF SERVICES
{eng['scope']}

3. MATERIALITY
Our materiality threshold for this engagement is ${eng['materiality']:,.2f}.

4. ENGAGEMENT TEAM
Lead Auditor: {eng['lead_auditor']}

5. FEES
Our fees will be based on time expended at standard billing rates.

6. CONFIDENTIALITY
All information obtained during the engagement will be kept confidential.

We look forward to a successful engagement.

Sincerely,
{eng['lead_auditor']}
Lead Auditor
            """.strip()


class ManagementRepLetter:
    @staticmethod
    def generate(engagement_id: str) -> str:
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_engagements WHERE id = ?", (engagement_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return "Engagement not found."
        
        return f"""
MANAGEMENT REPRESENTATION LETTER
{row[1]}

Date: {datetime.fromtimestamp(time.time()).strftime('%B %d, %Y')}

To the Audit Team

We are providing this letter in connection with your audit of the financial statements
of {row[2]} as of and for the year ended {datetime.fromtimestamp(row[9]).strftime('%B %d, %Y')}.

We confirm, to the best of our knowledge and belief, as of the date of this letter, the
following representations:

1. We have fulfilled our responsibilities for the preparation and fair presentation of
   the financial statements in accordance with the applicable financial reporting framework.

2. We have provided you with all relevant information and access to all records and
   documentation requested.

3. All transactions have been recorded and are reflected in the financial statements.

4. There are no known instances of fraud or suspected fraud affecting the entity.

5. We have disclosed all known contingent liabilities and commitments.

6. The financial statements are free of material misstatements.

7. There have been no subsequent events requiring adjustment or disclosure.

Signed: ___________________________
Title: ____________________________
Date: ____________________________
        """.strip()


class GoingConcernAssessment:
    @staticmethod
    def assess(engagement_id: str, factors: Dict) -> Dict:
        """Assess going concern risk based on financial and non-financial factors."""
        risk_score = 0
        indicators = []
        
        # Financial indicators
        if factors.get("negative_cash_flow"): 
            risk_score += 3; indicators.append("Negative operating cash flows")
        if factors.get("negative_working_capital"): 
            risk_score += 2; indicators.append("Negative working capital")
        if factors.get("loan_defaults"): 
            risk_score += 3; indicators.append("Loan defaults or covenant breaches")
        if factors.get("supplier_issues"): 
            risk_score += 2; indicators.append("Suppliers demanding cash on delivery")
        if factors.get("key_personnel_loss"): 
            risk_score += 1; indicators.append("Loss of key personnel")
        if factors.get("legal_issues"): 
            risk_score += 2; indicators.append("Significant litigation")
        if factors.get("regulatory_issues"): 
            risk_score += 2; indicators.append("Regulatory non-compliance")
        if factors.get("mitigating_factors"): 
            risk_score -= 2; indicators.append("Mitigating factors present")
        
        if risk_score >= 6: rating = "high"
        elif risk_score >= 3: rating = "moderate"
        else: rating = "low"
        
        return {
            "risk_score": risk_score, "rating": rating, "indicators": indicators,
            "conclusion": "Substantial doubt exists" if rating == "high" else 
                         "Moderate risk - additional procedures needed" if rating == "moderate" else
                         "No substantial doubt",
            "assessed_at": time.time()
        }


class FraudRiskAssessment:
    @staticmethod
    def assess(engagement_id: str) -> Dict:
        """Assess fraud risk per ISA 240 / AU-C 240."""
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_engagements WHERE id = ?", (engagement_id,))
        row = cursor.fetchone()
        conn.close()
        
        # Fraud risk factors
        incentive_pressure = [
            "Financial stability threatened",
            "Aggressive accounting policies",
            "High turnover in CFO/controller",
            "Significant related-party transactions"
        ]
        
        opportunity = [
            "Complex organizational structure",
            "Weak internal controls",
            "Dominant management",
            "Inadequate monitoring"
        ]
        
        rationalization = [
            "History of violations",
            "Unreasonable demands on staff",
            "Weak ethical culture"
        ]
        
        return {
            "engagement_id": engagement_id,
            "incentive_pressure_factors": incentive_pressure,
            "opportunity_factors": opportunity,
            "rationalization_factors": rationalization,
            "presumed_risks": ["Revenue recognition", "Management override of controls"],
            "assessed_at": time.time()
        }


class ITGCManager:
    @staticmethod
    def create_itgc_program(engagement_id: str) -> List[str]:
        """Create standard IT General Controls testing program."""
        itgc_areas = [
            {"area": "Access Controls", "procedures": [
                "Test user access provisioning/deprovisioning",
                "Review privileged access management",
                "Test segregation of duties in IT",
                "Review password policies and MFA"
            ]},
            {"area": "Change Management", "procedures": [
                "Test change request authorization",
                "Review emergency change procedures",
                "Test development vs production separation",
                "Review rollback procedures"
            ]},
            {"area": "Computer Operations", "procedures": [
                "Test backup and recovery procedures",
                "Review job scheduling and monitoring",
                "Test incident management",
                "Review system availability metrics"
            ]},
            {"area": "Program Development", "procedures": [
                "Test SDLC controls",
                "Review code review procedures",
                "Test data migration controls",
                "Review vendor management for IT"
            ]},
            {"area": "Network Security", "procedures": [
                "Test firewall rule review",
                "Review network segmentation",
                "Test intrusion detection",
                "Review VPN/remote access controls"
            ]},
        ]
        
        created = []
        for area in itgc_areas:
            proc_list = [{"step": i+1, "desc": p} for i, p in enumerate(area["procedures"])]
            pid = program_mgr.create_program(
                engagement_id, f"ITGC - {area['area']}", 
                f"Test IT General Controls for {area['area']}",
                proc_list, "high", "IT Audit Specialist"
            )
            created.append(pid)
        
        return created


class SampleSizeCalculator:
    @staticmethod
    def attribute_sampling(population: int, confidence: float, tolerable_rate: float,
                           expected_rate: float = 0.0) -> Dict:
        """Calculate attribute sample size per AICPA Audit Guide."""
        z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
        z = z_scores.get(confidence, 1.96)
        p = expected_rate if expected_rate > 0 else 0.5
        n0 = (z**2 * p * (1-p)) / (tolerable_rate**2)
        n = n0 / (1 + (n0 - 1) / population)
        n = int(n) + 1
        return {
            "sample_size": min(n, population),
            "population": population,
            "confidence": confidence,
            "tolerable_rate": tolerable_rate,
            "expected_rate": expected_rate,
            "method": "attribute"
        }
    
    @staticmethod
    def variable_sampling(population: int, confidence: float, tolerable_error: float,
                          expected_error: float, std_dev: float) -> Dict:
        """Calculate variable sample size."""
        z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
        z = z_scores.get(confidence, 1.96)
        n = (z * std_dev / tolerable_error)**2
        n = int(n) + 1
        return {
            "sample_size": min(n, population),
            "population": population,
            "confidence": confidence,
            "tolerable_error": tolerable_error,
            "expected_error": expected_error,
            "std_dev": std_dev,
            "method": "variable"
        }
    
    @staticmethod
    def mus_sampling(population_value: float, confidence: float, tolerable_error: float,
                     expected_error: float, population_items: int = None) -> Dict:
        """Monetary Unit Sampling (MUS) sample size.
        population_value: Total book value of population (e.g., total AR balance)
        tolerable_error: Maximum tolerable misstatement (absolute $)
        expected_error: Expected misstatement (absolute $)
        population_items: Number of items in population (optional, for item-based calc)
        """
        z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
        z = z_scores.get(confidence, 1.96)
        
        # Convert to rates
        tolerable_rate = tolerable_error / population_value if population_value > 0 else 0.05
        expected_rate = expected_error / population_value if population_value > 0 else 0.01
        
        # Cap rates
        tolerable_rate = min(max(tolerable_rate, 0.001), 0.5)
        expected_rate = min(max(expected_rate, 0.0001), tolerable_rate * 0.5)
        
        # MUS formula: n = (Z^2 * ExpRate * (1-ExpRate)) / TolRate^2
        n = (z**2 * expected_rate * (1 - expected_rate)) / (tolerable_rate**2)
        n = int(n) + 1
        
        # If population_items provided, cap at that
        if population_items:
            n = min(n, population_items)
        
        return {
            "sample_size": n,
            "population_value": population_value,
            "population_items": population_items,
            "confidence": confidence,
            "tolerable_error": tolerable_error,
            "tolerable_rate": tolerable_rate,
            "expected_error": expected_error,
            "expected_rate": expected_rate,
            "method": "MUS"
        }


class AnalyticalProcedures:
    @staticmethod
    def trend_analysis(engagement_id: str, account: str, years: int = 5) -> Dict:
        """Generate trend analysis framework for analytical procedures."""
        return {
            "account": account,
            "periods": years,
            "metrics": [
                "Year-over-year change %",
                "Compound annual growth rate (CAGR)",
                "Common-size percentages",
                "Ratio analysis (liquidity, profitability, leverage, efficiency)",
                "Regression analysis",
                "Benchmark comparison"
            ],
            "thresholds": {
                "material": "±10% or materiality threshold",
                "significant": "±5%",
                "investigate": "Any unexpected fluctuation"
            },
            "created_at": time.time()
        }
    
    @staticmethod
    def ratio_analysis(engagement_id: str) -> List[Dict]:
        """Standard financial ratios for analytical procedures."""
        return [
            {"name": "Current Ratio", "formula": "Current Assets / Current Liabilities", "category": "Liquidity"},
            {"name": "Quick Ratio", "formula": "(Cash + Receivables) / Current Liabilities", "category": "Liquidity"},
            {"name": "Gross Margin %", "formula": "(Revenue - COGS) / Revenue", "category": "Profitability"},
            {"name": "Net Profit Margin", "formula": "Net Income / Revenue", "category": "Profitability"},
            {"name": "ROA", "formula": "Net Income / Total Assets", "category": "Profitability"},
            {"name": "ROE", "formula": "Net Income / Equity", "category": "Profitability"},
            {"name": "Debt to Equity", "formula": "Total Debt / Total Equity", "category": "Leverage"},
            {"name": "Interest Coverage", "formula": "EBIT / Interest Expense", "category": "Leverage"},
            {"name": "Asset Turnover", "formula": "Revenue / Total Assets", "category": "Efficiency"},
            {"name": "Receivables Turnover", "formula": "Revenue / Avg Receivables", "category": "Efficiency"},
            {"name": "Inventory Turnover", "formula": "COGS / Avg Inventory", "category": "Efficiency"},
            {"name": "Days Sales Outstanding", "formula": "365 / Receivables Turnover", "category": "Efficiency"},
        ]


class JournalEntryTesting:
    @staticmethod
    def create_jet_program(engagement_id: str) -> List[str]:
        """Create Journal Entry Testing program."""
        jet_procedures = [
            {"area": "Non-standard JEs", "procedures": [
                "Extract all non-standard journal entries",
                "Filter by user (non-recurring, manual entries)",
                "Filter by amount (above threshold)",
                "Filter by date (period-end, weekends/holidays)",
                "Filter by account combinations (unusual)",
                "Test sample for validity and authorization"
            ]},
            {"area": "Recurring JEs", "procedures": [
                "Identify all recurring journal entries",
                "Verify authorization for recurring entries",
                "Test sample for continued validity"
            ]},
            {"area": "Top-side Adjustments", "procedures": [
                "Identify all top-side/consolidation entries",
                "Test for management override indicators",
                "Verify supporting documentation"
            ]},
        ]
        
        created = []
        for area in jet_procedures:
            proc_list = [{"step": i+1, "desc": p} for i, p in enumerate(area["procedures"])]
            pid = program_mgr.create_program(
                engagement_id, f"JET - {area['area']}",
                f"Journal Entry Testing for {area['area']}",
                proc_list, "high", "Senior Auditor"
            )
            created.append(pid)
        
        return created


class ConfirmationManager:
    @staticmethod
    def create_confirmation(engagement_id: str, confirmation_type: str,
                           counterparty: str, amount: float, details: str) -> str:
        """Create confirmation request."""
        conf_id = f"conf_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_evidence (id, engagement_id, evidence_type, description,
                                       source, collected_by, collected_at, relevance, reliability, created_at)
            VALUES (?, ?, 'confirmation', ?, ?, ?, ?, 'direct', 'high', ?)
        """, (conf_id, engagement_id, 
              f"{confirmation_type} confirmation - {details}", counterparty,
              "system", time.time(), time.time()))
        conn.commit()
        conn.close()
        return conf_id
    
    @staticmethod
    def track_responses(engagement_id: str) -> Dict:
        """Track confirmation responses."""
        conn = get_audit_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM audit_evidence 
            WHERE engagement_id = ? AND evidence_type = 'confirmation'
        """, (engagement_id,))
        rows = cursor.fetchall()
        conn.close()
        
        sent = len(rows)
        # In practice, would track responses separately
        return {"sent": sent, "received": 0, "outstanding": sent, "exceptions": 0}


class SubsequentEventsReview:
    @staticmethod
    def review(engagement_id: str, procedures: List[str] = None) -> Dict:
        """Document subsequent events review procedures."""
        default_procedures = [
            "Review minutes of meetings through report date",
            "Review latest interim financial statements",
            "Inquire of management about subsequent events",
            "Review legal letters through report date",
            "Analyze cash receipts/disbursements after year-end",
            "Review subsequent sales and purchases",
            "Check for new commitments or contingencies",
            "Review subsequent journal entries"
        ]
        
        return {
            "engagement_id": engagement_id,
            "procedures": procedures or default_procedures,
            "period_end": time.time(),
            "report_date": time.time() + 86400 * 30,  # 30 days
            "created_at": time.time()
        }


class RelatedPartyManager:
    @staticmethod
    def identify_related_parties(engagement_id: str) -> Dict:
        """Framework for related party identification."""
        return {
            "engagement_id": engagement_id,
            "categories": [
                "Entities with control/joint control/significant influence",
                "Key management personnel and close family",
                "Post-employment benefit plans",
                "Entities controlled by key management"
            ],
            "procedures": [
                "Review shareholder registers",
                "Inquire of management",
                "Review board minutes for related party transactions",
                "Analyze unusual transactions",
                "Check for transactions not at arm's length",
                "Review disclosures in financial statements"
            ],
            "created_at": time.time()
        }


class AuditChecklist:
    @staticmethod
    def planning_checklist(engagement_id: str) -> List[Dict]:
        """ISA 300 / AU-C 300 planning checklist."""
        return [
            {"area": "Engagement Acceptance", "items": [
                "Client integrity assessment",
                "Competence and resources evaluation",
                "Independence confirmation",
                "Engagement letter signed"
            ]},
            {"area": "Planning", "items": [
                "Understand entity and environment",
                "Assess fraud risk (ISA 240)",
                "Assess risk of material misstatement",
                "Determine materiality",
                "Identify significant risks",
                "Develop overall audit strategy",
                "Prepare detailed audit plan"
            ]},
            {"area": "Team", "items": [
                "Assign engagement team",
                "Engagement quality control reviewer assigned",
                "Specialists identified (IT, tax, valuation)",
                "Team briefing completed"
            ]},
        ]
    
    @staticmethod
    def completion_checklist(engagement_id: str) -> List[Dict]:
        """ISA 450/500/560/570/580/700/705/706 completion checklist."""
        return [
            {"area": "Evidence Evaluation", "items": [
                "Sufficient appropriate evidence obtained",
                "Uncorrected misstatements evaluated",
                "Materiality reconsidered",
                "Fraud risk responses evaluated"
            ]},
            {"area": "Subsequent Events", "items": [
                "Subsequent events review to report date",
                "Adjusting vs non-adjusting events"
            ]},
            {"area": "Going Concern", "items": [
                "Going concern assessment completed",
                "Management plans evaluated",
                "Disclosures adequate"
            ]},
            {"area": "Representations", "items": [
                "Management representation letter obtained",
                "All requested representations received"
            ]},
            {"area": "Reporting", "items": [
                "Auditor's report drafted",
                "Key audit matters communicated",
                "Emphasis of matter/other matter paragraphs",
                "Report reviewed by EQCR"
            ]},
            {"area": "Documentation", "items": [
                "Audit file assembly completed",
                "File review by engagement partner",
                "EQCR completed",
                "Documentation retention policy followed"
            ]},
        ]


class QualityControlChecklist:
    @staticmethod
    def isqc1_checklist() -> List[Dict]:
        """ISQC 1 / ISQM 1 quality control elements."""
        return [
            {"element": "Leadership Responsibilities", "items": [
                "Quality culture established",
                "Quality objectives set",
                "Resource allocation for quality"
            ]},
            {"element": "Ethical Requirements", "items": [
                "Independence policies",
                "Confidentiality policies",
                "Breach reporting procedures"
            ]},
            {"element": "Acceptance/Continuance", "items": [
                "Client evaluation procedures",
                "Engagement acceptance criteria",
                "Continuance evaluation"
            ]},
            {"element": "Human Resources", "items": [
                "Competence requirements",
                "Training and development",
                "Performance evaluation"
            ]},
            {"element": "Engagement Performance", "items": [
                "Supervision and review",
                "Consultation policies",
                "Engagement quality control review",
                "Differences of opinion resolution"
            ]},
            {"element": "Monitoring", "items": [
                "Ongoing monitoring activities",
                "Periodic inspections",
                "Corrective actions",
                "Root cause analysis"
            ]},
        ]


# Pre-built framework templates
FRAMEWORK_TEMPLATES = {
    "SOX": {
        "name": "Sarbanes-Oxley Act Section 404",
        "version": "2024",
        "category": "financial_reporting",
        "jurisdiction": "US",
        "requirements": [
            {"id": "404.a", "text": "Management assessment of ICFR effectiveness"},
            {"id": "404.b", "text": "Auditor attestation on ICFR"},
            {"id": "302", "text": "CEO/CFO certifications"},
            {"id": "409", "text": "Real-time issuer disclosures"},
            {"id": "802", "text": "Criminal penalties for document destruction"},
        ]
    },
    "ISO27001": {
        "name": "ISO/IEC 27001:2022",
        "version": "2022",
        "category": "information_security",
        "jurisdiction": "International",
        "requirements": [
            {"id": "A.5.1", "text": "Policies for information security"},
            {"id": "A.5.2", "text": "Information security roles and responsibilities"},
            {"id": "A.6.1", "text": "Screening of personnel"},
            {"id": "A.7.1", "text": "Asset inventory and ownership"},
            {"id": "A.8.1", "text": "User access management"},
            {"id": "A.8.2", "text": "Privileged access rights"},
            {"id": "A.8.3", "text": "Authentication"},
            {"id": "A.9.1", "text": "Physical security perimeters"},
            {"id": "A.12.1", "text": "Operational procedures and responsibilities"},
            {"id": "A.12.2", "text": "Protection from malware"},
            {"id": "A.12.3", "text": "Backup and recovery"},
            {"id": "A.13.1", "text": "Network controls"},
            {"id": "A.14.1", "text": "Security requirements in development"},
            {"id": "A.16.1", "text": "Incident management"},
            {"id": "A.17.1", "text": "Information security continuity"},
        ]
    },
    "NIST_CSF": {
        "name": "NIST Cybersecurity Framework",
        "version": "2.0",
        "category": "cybersecurity",
        "jurisdiction": "US",
        "requirements": [
            {"id": "ID.AM", "text": "Asset Management"},
            {"id": "ID.BE", "text": "Business Environment"},
            {"id": "ID.GV", "text": "Governance"},
            {"id": "ID.RA", "text": "Risk Assessment"},
            {"id": "ID.RM", "text": "Risk Management Strategy"},
            {"id": "ID.SC", "text": "Supply Chain Risk Management"},
            {"id": "PR.AC", "text": "Identity Management and Access Control"},
            {"id": "PR.AT", "text": "Awareness and Training"},
            {"id": "PR.DS", "text": "Data Security"},
            {"id": "PR.IP", "text": "Information Protection Processes"},
            {"id": "PR.MA", "text": "Maintenance"},
            {"id": "PR.PT", "text": "Protective Technology"},
            {"id": "DE.AE", "text": "Anomalies and Events"},
            {"id": "DE.CM", "text": "Security Continuous Monitoring"},
            {"id": "DE.DP", "text": "Detection Processes"},
            {"id": "RS.RP", "text": "Response Planning"},
            {"id": "RS.CO", "text": "Communications"},
            {"id": "RS.AN", "text": "Analysis"},
            {"id": "RS.MI", "text": "Mitigation"},
            {"id": "RS.IM", "text": "Improvements"},
            {"id": "RC.RP", "text": "Recovery Planning"},
            {"id": "RC.CO", "text": "Communications"},
            {"id": "RC.IM", "text": "Improvements"},
        ]
    },
    "GDPR": {
        "name": "General Data Protection Regulation",
        "version": "2016/679",
        "category": "data_privacy",
        "jurisdiction": "EU",
        "requirements": [
            {"id": "Art.5", "text": "Principles of data processing"},
            {"id": "Art.6", "text": "Lawfulness of processing"},
            {"id": "Art.7", "text": "Conditions for consent"},
            {"id": "Art.12", "text": "Transparent information to data subjects"},
            {"id": "Art.15", "text": "Right of access"},
            {"id": "Art.17", "text": "Right to erasure"},
            {"id": "Art.25", "text": "Data protection by design and by default"},
            {"id": "Art.30", "text": "Records of processing activities"},
            {"id": "Art.32", "text": "Security of processing"},
            {"id": "Art.33", "text": "Notification of data breach to supervisory authority"},
            {"id": "Art.35", "text": "Data protection impact assessment"},
            {"id": "Art.37", "text": "Data protection officer"},
        ]
    },
    "PCI_DSS": {
        "name": "PCI DSS v4.0",
        "version": "4.0",
        "category": "payment_security",
        "jurisdiction": "Global",
        "requirements": [
            {"id": "1", "text": "Install and maintain network security controls"},
            {"id": "2", "text": "Apply secure configurations to all system components"},
            {"id": "3", "text": "Protect stored account data"},
            {"id": "4", "text": "Protect cardholder data with strong cryptography during transmission"},
            {"id": "5", "text": "Protect all systems and networks from malicious software"},
            {"id": "6", "text": "Develop and maintain secure systems and software"},
            {"id": "7", "text": "Restrict access to system components and cardholder data by business need to know"},
            {"id": "8", "text": "Identify users and authenticate access to system components"},
            {"id": "9", "text": "Restrict physical access to cardholder data"},
            {"id": "10", "text": "Log and monitor all access to system components and cardholder data"},
            {"id": "11", "text": "Test security of systems and networks regularly"},
            {"id": "12", "text": "Support information security with organizational policies and programs"},
        ]
    },
}


def load_framework_template(template_name: str) -> Optional[str]:
    """Load a pre-built framework template."""
    template = FRAMEWORK_TEMPLATES.get(template_name.upper())
    if not template:
        return None
    return register_framework(
        template["name"], template["version"], "",
        template["category"], template["jurisdiction"], template["requirements"]
    )


def list_framework_templates() -> List[str]:
    """List available framework templates."""
    return list(FRAMEWORK_TEMPLATES.keys())