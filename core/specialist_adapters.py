"""
Specialist Agent Adapters - Phase 36 Integration
Wraps all specialist agents with a unified task interface for the Multi-Agent System.
"""

import json
import time
import traceback
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path

from core.ma_base import BaseAgent, registry, get_ma_connection
from core.context_engine import get_current_session, build_context_for_llm
from core.semantic_memory import add_memory, search_memory
# from core.context_provider import inject_context, get_task_context
# Lazy import to avoid circular dependency
def inject_context(payload: Dict, task_type: str = "") -> Dict:
    try:
        from core.context_provider import inject_context as _inject
        return _inject(payload, task_type)
    except:
        return payload

def get_task_context(task_payload: Dict, task_type: str = ""):
    try:
        from core.context_provider import get_task_context as _get
        return _get(task_payload, task_type)
    except:
        class DummyContext:
            pass
        return DummyContext()


# ============================================================
# UNIFIED TASK CONTRACT
# ============================================================

@dataclass
class TaskSpec:
    """Standardized task specification for all specialist agents."""
    task_id: str
    task_type: str
    capability: str
    payload: Dict[str, Any]
    context: Dict[str, Any] = field(default_factory=dict)
    priority: int = 3
    timeout: float = 300.0
    retry_count: int = 0
    max_retries: int = 3
    dependencies: List[str] = field(default_factory=list)
    correlation_id: str = ""
    created_at: float = field(default_factory=time.time)


@dataclass
class TaskResult:
    """Standardized task result from all specialist agents."""
    task_id: str
    success: bool
    output: Any = None
    evidence: List[Dict] = field(default_factory=list)
    artifacts: List[Dict] = field(default_factory=list)
    confidence: float = 1.0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    progress: float = 1.0
    agent_name: str = ""
    agent_type: str = ""
    started_at: float = 0
    completed_at: float = 0
    resource_usage: Dict = field(default_factory=dict)
    next_actions: List[Dict] = field(default_factory=list)


# ============================================================
# BASE SPECIALIST ADAPTER
# ============================================================

class BaseSpecialistAdapter(BaseAgent):
    """Base adapter wrapping a specialist agent with standard task interface."""

    def __init__(self, name: str, agent_type: str, capabilities: List[str],
                 specialist_instance: Any, max_concurrent_tasks: int = 1,
                 resource_profile: Dict = None):
        super().__init__(name, agent_type, capabilities, max_concurrent_tasks)
        self.specialist = specialist_instance
        self.resource_profile = resource_profile or {
            "gpu_memory_mb": 0,
            "cpu_cores": 1,
            "ram_mb": 512
        }
        self._method_map: Dict[str, Callable] = {}

    def register_method(self, task_type: str, method: Callable):
        """Map a task_type to a specialist method."""
        self._method_map[task_type] = method

    def execute(self, task: Dict) -> Any:
        """Execute a standardized task."""
        # Map queue task format to TaskSpec
        if isinstance(task, dict):
            task_spec = TaskSpec(
                task_id=task.get("id", ""),
                task_type=task.get("task_type", ""),
                capability=task.get("task_type", ""),
                payload=task.get("payload", {}),
                context=task.get("context", {}),
                priority=task.get("priority", 3)
            )
        else:
            task_spec = task
        started = time.time()

        method = self._method_map.get(task_spec.task_type)
        if not method:
            return TaskResult(
                task_id=task_spec.task_id,
                success=False,
                errors=[f"Unknown task_type: {task_spec.task_type}"],
                agent_name=self.name,
                agent_type=self.agent_type,
                started_at=started,
                completed_at=time.time()
            ).__dict__

        try:
            # Build and inject shared context automatically
            enriched_payload = inject_context(task_spec.payload, task_spec.task_type)

            # Call specialist method
            result = method(enriched_payload)

            # Build standardized result
            task_result = self._build_result(
                task_spec.task_id,
                success=True,
                output=result,
                started_at=started
            )

            # Store in shared memory if significant
            if task_result.confidence > 0.7 and task_result.output:
                self._store_in_memory(task_spec, task_result)

            return task_result.__dict__

        except Exception as e:
            return TaskResult(
                task_id=task_spec.task_id,
                success=False,
                errors=[str(e), traceback.format_exc()],
                agent_name=self.name,
                agent_type=self.agent_type,
                started_at=started,
                completed_at=time.time()
            ).__dict__

    def _build_result(self, task_id: str, success: bool, output: Any,
                      started_at: float, confidence: float = 1.0,
                      evidence: List = None, artifacts: List = None,
                      warnings: List = None) -> TaskResult:
        """Build standardized TaskResult."""
        return TaskResult(
            task_id=task_id,
            success=success,
            output=output,
            evidence=evidence or [],
            artifacts=artifacts or [],
            confidence=confidence,
            warnings=warnings or [],
            agent_name=self.name,
            agent_type=self.agent_type,
            started_at=started_at,
            completed_at=time.time()
        )

    def _store_in_memory(self, task_spec: TaskSpec, result: TaskResult):
        """Store significant results in shared memory."""
        try:
            key = f"{self.agent_type}.{task_spec.task_type}.{task_spec.task_id}"
            value = json.dumps({
                "task_type": task_spec.task_type,
                "payload": task_spec.payload,
                "output": result.output,
                "confidence": result.confidence,
                "timestamp": time.time()
            }, default=str)
            add_memory(key, value)
        except Exception:
            pass  # Silent fail for memory storage


# ============================================================
# SPECIALIST ADAPTERS
# ============================================================

class CodingAgentAdapter(BaseSpecialistAdapter):
    def __init__(self):
        from core.coding_agent import coding_agent
        super().__init__(
            "CodingAgent", "coding",
            ["code_generation", "code_explanation", "code_review", "code_fixing",
             "code_refactoring", "test_generation", "doc_generation", "code_analysis",
             "bug_finding", "code_optimization", "code_conversion"],
            coding_agent,
            max_concurrent_tasks=2,
            resource_profile={"gpu_memory_mb": 2048, "cpu_cores": 2, "ram_mb": 2048}
        )
        self._register_methods()

    def _register_methods(self):
        self.register_method("generate_code", self._generate_code)
        self.register_method("code_generation", self._generate_code)  # Alias
        self.register_method("explain_code", self._explain_code)
        self.register_method("code_explanation", self._explain_code)  # Alias
        self.register_method("review_code", self._review_code)
        self.register_method("code_review", self._review_code)  # Alias
        self.register_method("fix_code", self._fix_code)
        self.register_method("code_fixing", self._fix_code)  # Alias
        self.register_method("refactor_code", self._refactor_code)
        self.register_method("code_refactoring", self._refactor_code)  # Alias
        self.register_method("generate_tests", self._generate_tests)
        self.register_method("test_generation", self._generate_tests)  # Alias
        self.register_method("generate_docs", self._generate_docs)
        self.register_method("doc_generation", self._generate_docs)  # Alias
        self.register_method("analyze_file", self._analyze_file)
        self.register_method("code_analysis", self._analyze_file)  # Alias
        self.register_method("find_bugs", self._find_bugs)
        self.register_method("bug_finding", self._find_bugs)  # Alias
        self.register_method("optimize_code", self._optimize_code)
        self.register_method("code_optimization", self._optimize_code)  # Alias
        self.register_method("convert_code", self._convert_code)
        self.register_method("code_conversion", self._convert_code)  # Alias

    def _generate_code(self, payload: Dict) -> Dict:
        prompt = payload.get("prompt", "")
        language = payload.get("language", "python")
        context = payload.get("_context", "")
        return {"code": self.specialist.generate_code(prompt, language, context)}

    def _explain_code(self, payload: Dict) -> Dict:
        code = payload.get("code", "")
        language = payload.get("language", "python")
        return {"explanation": self.specialist.explain_code(code, language)}

    def _review_code(self, payload: Dict) -> Dict:
        code = payload.get("code", "")
        language = payload.get("language", "python")
        return {"review": self.specialist.review_code(code, language)}

    def _fix_code(self, payload: Dict) -> Dict:
        code = payload.get("code", "")
        error = payload.get("error", "")
        language = payload.get("language", "python")
        return {"fixed_code": self.specialist.fix_code(code, error, language)}

    def _refactor_code(self, payload: Dict) -> Dict:
        code = payload.get("code", "")
        instruction = payload.get("instruction", "")
        language = payload.get("language", "python")
        return {"refactored_code": self.specialist.refactor_code(code, instruction, language)}

    def _generate_tests(self, payload: Dict) -> Dict:
        code = payload.get("code", "")
        language = payload.get("language", "python")
        framework = payload.get("framework", "pytest")
        return {"tests": self.specialist.generate_tests(code, language, framework)}

    def _generate_docs(self, payload: Dict) -> Dict:
        code = payload.get("code", "")
        language = payload.get("language", "python")
        style = payload.get("style", "docstring")
        return {"documented_code": self.specialist.generate_docs(code, language, style)}

    def _analyze_file(self, payload: Dict) -> Dict:
        file_path = payload.get("file_path", "")
        return self.specialist.analyze_file(file_path)

    def _find_bugs(self, payload: Dict) -> Dict:
        code = payload.get("code", "")
        language = payload.get("language", "python")
        return {"bugs": self.specialist.find_bugs(code, language)}

    def _optimize_code(self, payload: Dict) -> Dict:
        code = payload.get("code", "")
        language = payload.get("language", "python")
        return {"optimized_code": self.specialist.optimize_code(code, language)}

    def _convert_code(self, payload: Dict) -> Dict:
        code = payload.get("code", "")
        from_lang = payload.get("from_lang", "python")
        to_lang = payload.get("to_lang", "python")
        return {"converted_code": self.specialist.convert_code(code, from_lang, to_lang)}


class ResearchAgentAdapter(BaseSpecialistAdapter):
    def __init__(self):
        from core.research_agent import research_agent
        super().__init__(
            "ResearchAgent", "research",
            ["web_research", "quick_fact", "comparison", "latest_news",
             "technical_research", "search_web", "synthesize"],
            research_agent,
            max_concurrent_tasks=3,
            resource_profile={"gpu_memory_mb": 0, "cpu_cores": 1, "ram_mb": 1024}
        )
        self._register_methods()

    def _register_methods(self):
        self.register_method("research", self._research)
        self.register_method("quick_fact", self._quick_fact)
        self.register_method("compare", self._compare)
        self.register_method("latest_news", self._latest_news)
        self.register_method("technical_research", self._technical_research)
        self.register_method("search_web", self._search_web)

    def _research(self, payload: Dict) -> Dict:
        query = payload.get("query", "")
        depth = payload.get("depth", "standard")
        result = self.specialist.research(query, depth)
        return {"summary": result.summary, "key_findings": result.key_findings,
                "sources": [{"title": s.title, "url": s.url} for s in result.sources]}

    def _quick_fact(self, payload: Dict) -> Dict:
        query = payload.get("query", "")
        return {"fact": self.specialist.quick_fact(query)}

    def _compare(self, payload: Dict) -> Dict:
        topic_a = payload.get("topic_a", "")
        topic_b = payload.get("topic_b", "")
        aspect = payload.get("aspect", "")
        result = self.specialist.compare(topic_a, topic_b, aspect)
        return {"summary": result.summary, "key_findings": result.key_findings}

    def _latest_news(self, payload: Dict) -> Dict:
        topic = payload.get("topic", "")
        result = self.specialist.latest_news(topic)
        return {"summary": result.summary, "key_findings": result.key_findings}

    def _technical_research(self, payload: Dict) -> Dict:
        topic = payload.get("topic", "")
        result = self.specialist.technical_research(topic)
        return {"summary": result.summary, "key_findings": result.key_findings}

    def _search_web(self, payload: Dict) -> Dict:
        query = payload.get("query", "")
        max_results = payload.get("max_results", 5)
        sources = self.specialist.search_and_extract(query, max_results)
        return {"sources": sources}


class WritingAgentAdapter(BaseSpecialistAdapter):
    def __init__(self):
        from core.writing_agent import writing_agent
        super().__init__(
            "WritingAgent", "writing",
            ["text_generation", "text_editing", "text_rewriting", "summarization",
             "text_expansion", "outlining", "grammar_fixing", "tone_change",
             "email_writing", "report_writing", "blog_writing", "readme_writing",
             "docstring_writing", "commit_writing", "pr_writing"],
            writing_agent,
            max_concurrent_tasks=2,
            resource_profile={"gpu_memory_mb": 1024, "cpu_cores": 1, "ram_mb": 1024}
        )
        self._register_methods()

    def _register_methods(self):
        self.register_method("generate", self._generate)
        self.register_method("edit", self._edit)
        self.register_method("rewrite", self._rewrite)
        self.register_method("summarize", self._summarize)
        self.register_method("expand", self._expand)
        self.register_method("outline", self._outline)
        self.register_method("fix_grammar", self._fix_grammar)
        self.register_method("change_tone", self._change_tone)
        self.register_method("write_email", self._write_email)
        self.register_method("write_report", self._write_report)
        self.register_method("write_blog", self._write_blog)
        self.register_method("write_readme", self._write_readme)
        self.register_method("write_docstring", self._write_docstring)
        self.register_method("write_commit", self._write_commit)
        self.register_method("write_pr", self._write_pr)

    def _generate(self, payload: Dict) -> Dict:
        prompt = payload.get("prompt", "")
        style = payload.get("style", "formal")
        length = payload.get("length", "medium")
        return {"text": self.specialist.generate(prompt, style, length)}

    def _edit(self, payload: Dict) -> Dict:
        import pyperclip
        content = pyperclip.paste()
        instruction = payload.get("instruction", "")
        return {"edited_text": self.specialist.edit(content, instruction)}

    def _rewrite(self, payload: Dict) -> Dict:
        import pyperclip
        content = pyperclip.paste()
        style = payload.get("style", "formal")
        return {"rewritten_text": self.specialist.rewrite(content, style)}

    def _summarize(self, payload: Dict) -> Dict:
        import pyperclip
        content = pyperclip.paste()
        length = payload.get("length", "short")
        return {"summary": self.specialist.summarize(content, length)}

    def _expand(self, payload: Dict) -> Dict:
        import pyperclip
        content = pyperclip.paste()
        return {"expanded_text": self.specialist.expand(content)}

    def _outline(self, payload: Dict) -> Dict:
        topic = payload.get("topic", "")
        return {"outline": self.specialist.outline(topic)}

    def _fix_grammar(self, payload: Dict) -> Dict:
        import pyperclip
        content = pyperclip.paste()
        return {"corrected_text": self.specialist.fix_grammar(content)}

    def _change_tone(self, payload: Dict) -> Dict:
        import pyperclip
        content = pyperclip.paste()
        tone = payload.get("tone", "formal")
        return {"retuned_text": self.specialist.change_tone(content, tone)}

    def _write_email(self, payload: Dict) -> Dict:
        prompt = payload.get("prompt", "")
        return {"email": self.specialist.write_email(prompt)}

    def _write_report(self, payload: Dict) -> Dict:
        prompt = payload.get("prompt", "")
        return {"report": self.specialist.write_report(prompt)}

    def _write_blog(self, payload: Dict) -> Dict:
        prompt = payload.get("prompt", "")
        return {"blog": self.specialist.write_blog(prompt)}

    def _write_readme(self, payload: Dict) -> Dict:
        prompt = payload.get("prompt", "")
        return {"readme": self.specialist.write_readme(prompt)}

    def _write_docstring(self, payload: Dict) -> Dict:
        import pyperclip
        content = pyperclip.paste()
        return {"docstring": self.specialist.write_docstring(content)}

    def _write_commit(self, payload: Dict) -> Dict:
        import pyperclip
        content = pyperclip.paste()
        return {"commit_message": self.specialist.write_commit(content)}

    def _write_pr(self, payload: Dict) -> Dict:
        import pyperclip
        content = pyperclip.paste()
        return {"pr_description": self.specialist.write_pr_description(content)}


class OfficeAgentAdapter(BaseSpecialistAdapter):
    def __init__(self):
        from core.office_agent import office_agent
        super().__init__(
            "OfficeAgent", "office",
            ["document_creation", "document_reading", "spreadsheet_creation",
             "presentation_creation", "format_conversion", "data_processing"],
            office_agent,
            max_concurrent_tasks=2,
            resource_profile={"gpu_memory_mb": 0, "cpu_cores": 1, "ram_mb": 512}
        )
        self._register_methods()

    def _register_methods(self):
        self.register_method("create_document", self._create_document)
        self.register_method("read_document", self._read_document)
        self.register_method("create_spreadsheet", self._create_spreadsheet)
        self.register_method("create_presentation", self._create_presentation)
        self.register_method("convert_format", self._convert_format)
        self.register_method("get_document_info", self._get_document_info)

    def _create_document(self, payload: Dict) -> Dict:
        doc_type = payload.get("doc_type", "word")
        file_path = payload.get("file_path", "")
        title = payload.get("title", "")
        return self.specialist.create_document(doc_type, file_path, title)

    def _read_document(self, payload: Dict) -> Dict:
        file_path = payload.get("file_path", "")
        return self.specialist.read_document(file_path)

    def _create_spreadsheet(self, payload: Dict) -> Dict:
        file_path = payload.get("file_path", "")
        return self.specialist.create_excel(file_path)

    def _create_presentation(self, payload: Dict) -> Dict:
        file_path = payload.get("file_path", "")
        return self.specialist.create_powerpoint(file_path)

    def _convert_format(self, payload: Dict) -> Dict:
        from_format = payload.get("from_format", "")
        to_format = payload.get("to_format", "")
        file_path = payload.get("file_path", "")
        if from_format == "excel" and to_format == "csv":
            return self.specialist.excel_to_csv(file_path)
        elif from_format == "csv" and to_format == "excel":
            return self.specialist.csv_to_excel(file_path)
        return {"error": "Unsupported conversion"}

    def _get_document_info(self, payload: Dict) -> Dict:
        file_path = payload.get("file_path", "")
        return self.specialist.get_document_info(file_path)


class SystemAgentAdapter(BaseSpecialistAdapter):
    def __init__(self):
        from core.system_agent import system_agent
        super().__init__(
            "SystemAgent", "system",
            ["system_monitoring", "process_management", "service_management",
             "automation_rules", "metrics_collection"],
            system_agent,
            max_concurrent_tasks=3,
            resource_profile={"gpu_memory_mb": 0, "cpu_cores": 1, "ram_mb": 256}
        )
        self._register_methods()

    def _register_methods(self):
        self.register_method("get_system_info", self._get_system_info)
        self.register_method("list_processes", self._list_processes)
        self.register_method("get_metrics", self._get_metrics)
        self.register_method("manage_service", self._manage_service)

    def _get_system_info(self, payload: Dict) -> Dict:
        return self.specialist.get_system_info()

    def _list_processes(self, payload: Dict) -> Dict:
        return self.specialist.list_processes()

    def _get_metrics(self, payload: Dict) -> Dict:
        return self.specialist.get_system_metrics()

    def _manage_service(self, payload: Dict) -> Dict:
        action = payload.get("action", "status")
        service = payload.get("service", "")
        return self.specialist.manage_service(service, action)


class CybersecurityAgentAdapter(BaseSpecialistAdapter):
    def __init__(self):
        from core.cybersecurity_agent import cybersecurity_agent
        super().__init__(
            "CybersecurityAgent", "cybersecurity",
            ["threat_intelligence", "vulnerability_scanning", "log_analysis",
             "security_monitoring", "incident_response"],
            cybersecurity_agent,
            max_concurrent_tasks=2,
            resource_profile={"gpu_memory_mb": 0, "cpu_cores": 2, "ram_mb": 1024}
        )
        self._register_methods()

    def _register_methods(self):
        self.register_method("scan_vulnerabilities", self._scan_vulnerabilities)
        self.register_method("analyze_logs", self._analyze_logs)
        self.register_method("check_threats", self._check_threats)

    def _scan_vulnerabilities(self, payload: Dict) -> Dict:
        target = payload.get("target", "local")
        return self.specialist.scan_vulnerabilities(target)

    def _analyze_logs(self, payload: Dict) -> Dict:
        log_path = payload.get("log_path", "")
        return self.specialist.analyze_logs(log_path)

    def _check_threats(self, payload: Dict) -> Dict:
        indicators = payload.get("indicators", [])
        return self.specialist.check_threats(indicators)


class FinanceAgentAdapter(BaseSpecialistAdapter):
    def __init__(self):
        from core.finance_agent import finance_agent
        super().__init__(
            "FinanceAgent", "finance",
            ["account_management", "transaction_tracking", "budgeting",
             "investment_tracking", "financial_reporting"],
            finance_agent,
            max_concurrent_tasks=2,
            resource_profile={"gpu_memory_mb": 0, "cpu_cores": 1, "ram_mb": 512}
        )
        self._register_methods()

    def _register_methods(self):
        self.register_method("add_account", self._add_account)
        self.register_method("add_transaction", self._add_transaction)
        self.register_method("get_balance", self._get_balance)
        self.register_method("create_budget", self._create_budget)
        self.register_method("generate_report", self._generate_report)

    def _add_account(self, payload: Dict) -> Dict:
        return self.specialist.add_account(payload)

    def _add_transaction(self, payload: Dict) -> Dict:
        return self.specialist.add_transaction(payload)

    def _get_balance(self, payload: Dict) -> Dict:
        return self.specialist.get_balances()

    def _create_budget(self, payload: Dict) -> Dict:
        return self.specialist.create_budget(payload)

    def _generate_report(self, payload: Dict) -> Dict:
        return self.specialist.generate_report(payload)


class AccountingAgentAdapter(BaseSpecialistAdapter):
    def __init__(self):
        from core.accounting_agent import accounting_agent
        super().__init__(
            "AccountingAgent", "accounting",
            ["chart_of_accounts", "journal_entries", "ledger_management",
             "reconciliation", "financial_statements"],
            accounting_agent,
            max_concurrent_tasks=2,
            resource_profile={"gpu_memory_mb": 0, "cpu_cores": 1, "ram_mb": 512}
        )
        self._register_methods()

    def _register_methods(self):
        self.register_method("create_account", self._create_account)
        self.register_method("create_journal_entry", self._create_journal_entry)
        self.register_method("reconcile", self._reconcile)
        self.register_method("generate_statements", self._generate_statements)

    def _create_account(self, payload: Dict) -> Dict:
        return self.specialist.create_account(payload)

    def _create_journal_entry(self, payload: Dict) -> Dict:
        return self.specialist.create_journal_entry(payload)

    def _reconcile(self, payload: Dict) -> Dict:
        return self.specialist.reconcile(payload)

    def _generate_statements(self, payload: Dict) -> Dict:
        return self.specialist.generate_financial_statements(payload)


class AuditAgentAdapter(BaseSpecialistAdapter):
    def __init__(self):
        import core.audit_agent as audit_module
        self.specialist = audit_module
        super().__init__(
            "AuditAgent", "audit",
            ["engagement_management", "audit_programs", "workpapers",
             "risk_assessment", "compliance_checking", "quality_review"],
            self.specialist,
            max_concurrent_tasks=2,
            resource_profile={"gpu_memory_mb": 0, "cpu_cores": 1, "ram_mb": 1024}
        )
        self._register_methods()

    def _register_methods(self):
        self.register_method("create_engagement", self._create_engagement)
        self.register_method("create_program", self._create_program)
        self.register_method("create_workpaper", self._create_workpaper)
        self.register_method("assess_risk", self._assess_risk)
        self.register_method("assess_compliance", self._assess_compliance)

    def _create_engagement(self, payload: Dict) -> Dict:
        return self.specialist.create_engagement(payload)

    def _create_program(self, payload: Dict) -> Dict:
        return self.specialist.create_audit_program(payload)

    def _create_workpaper(self, payload: Dict) -> Dict:
        return self.specialist.create_workpaper(payload)

    def _assess_risk(self, payload: Dict) -> Dict:
        return self.specialist.assess_risk(payload)

    def _assess_compliance(self, payload: Dict) -> Dict:
        return self.specialist.assess_compliance(payload)


class DataScienceAgentAdapter(BaseSpecialistAdapter):
    def __init__(self):
        import core.data_science_agent as ds_module
        # Find the agent instance
        for attr in dir(ds_module):
            obj = getattr(ds_module, attr)
            if hasattr(obj, '__class__') and 'DataScience' in obj.__class__.__name__:
                self.specialist = obj
                break
        else:
            self.specialist = None
        super().__init__(
            "DataScienceAgent", "data_science",
            ["data_analysis", "statistical_modeling", "machine_learning",
             "data_visualization", "data_cleaning", "feature_engineering"],
            self.specialist,
            max_concurrent_tasks=1,
            resource_profile={"gpu_memory_mb": 4096, "cpu_cores": 4, "ram_mb": 8192}
        )
        if self.specialist:
            self._register_methods()

    def _register_methods(self):
        if not self.specialist:
            return
        self.register_method("load_dataset", self._load_dataset)
        self.register_method("analyze", self._analyze)
        self.register_method("train_model", self._train_model)
        self.register_method("visualize", self._visualize)

    def _load_dataset(self, payload: Dict) -> Dict:
        if not self.specialist: return {"error": "Agent not initialized"}
        return self.specialist.load_dataset(payload.get("path", ""))

    def _analyze(self, payload: Dict) -> Dict:
        if not self.specialist: return {"error": "Agent not initialized"}
        return self.specialist.analyze(payload)

    def _train_model(self, payload: Dict) -> Dict:
        if not self.specialist: return {"error": "Agent not initialized"}
        return self.specialist.train_model(payload)

    def _visualize(self, payload: Dict) -> Dict:
        if not self.specialist: return {"error": "Agent not initialized"}
        return self.specialist.visualize(payload)


class VisionAgentAdapter(BaseSpecialistAdapter):
    def __init__(self):
        from core.vision.vision_manager import vision_manager
        from core.vision.vision_command import vision_commands
        self.vision_manager = vision_manager
        self.vision_commands = vision_commands
        super().__init__(
            "VisionAgent", "vision",
            ["screen_capture", "ocr", "screen_reading", "region_reading",
             "ai_vision", "screen_description", "code_analysis", "error_analysis",
             "ui_element_finding", "text_extraction"],
            vision_manager,
            max_concurrent_tasks=1,
            resource_profile={"gpu_memory_mb": 2048, "cpu_cores": 2, "ram_mb": 1024}
        )
        self._register_methods()

    def _register_methods(self):
        self.register_method("read_screen", self._read_screen)
        self.register_method("read_region", self._read_region)
        self.register_method("describe_screen", self._describe_screen)
        self.register_method("analyze_code", self._analyze_code)
        self.register_method("analyze_error", self._analyze_error)
        self.register_method("find_ui_element", self._find_ui_element)
        self.register_method("extract_text", self._extract_text)

    def _read_screen(self, payload: Dict) -> Dict:
        return {"text": self.vision_commands.read_screen()}

    def _read_region(self, payload: Dict) -> Dict:
        left = payload.get("left", 0)
        top = payload.get("top", 0)
        width = payload.get("width", 1920)
        height = payload.get("height", 1080)
        return {"text": self.vision_commands.read_region(left, top, width, height)}

    def _describe_screen(self, payload: Dict) -> Dict:
        detail = payload.get("detail", "")
        return {"description": self.vision_commands.describe_screen(detail)}

    def _analyze_code(self, payload: Dict) -> Dict:
        return {"analysis": self.vision_commands.analyze_code()}

    def _analyze_error(self, payload: Dict) -> Dict:
        return {"analysis": self.vision_commands.analyze_error()}

    def _find_ui_element(self, payload: Dict) -> Dict:
        description = payload.get("description", "")
        return {"element": self.vision_commands.find_on_screen(description)}

    def _extract_text(self, payload: Dict) -> Dict:
        return {"text": self.vision_commands.read_screen_text()}


class MemoryAgentAdapter(BaseSpecialistAdapter):
    def __init__(self):
        from memory import remember, recall, all_memory, search_memory_facts, forget
        self.remember = remember
        self.recall = recall
        self.all_memory = all_memory
        self.search_memory = search_memory_facts
        self.forget = forget
        super().__init__(
            "MemoryAgent", "memory",
            ["fact_storage", "fact_recall", "memory_search", "memory_listing", "memory_deletion"],
            self,
            max_concurrent_tasks=3,
            resource_profile={"gpu_memory_mb": 0, "cpu_cores": 1, "ram_mb": 256}
        )
        self._register_methods()

    def _register_methods(self):
        self.register_method("remember", self._remember)
        self.register_method("recall", self._recall)
        self.register_method("search", self._search)
        self.register_method("list_all", self._list_all)
        self.register_method("forget", self._forget)

    def _remember(self, payload: Dict) -> Dict:
        key = payload.get("key", "")
        value = payload.get("value", "")
        self.remember(key, value)
        return {"stored": True, "key": key}

    def _recall(self, payload: Dict) -> Dict:
        key = payload.get("key", "")
        value = self.recall(key)
        return {"value": value, "found": value is not None}

    def _search(self, payload: Dict) -> Dict:
        query = payload.get("query", "")
        n = payload.get("n_results", 5)
        results = self.search_memory(query, n)
        return {"results": results}

    def _list_all(self, payload: Dict) -> Dict:
        return {"memory": self.all_memory()}

    def _forget(self, payload: Dict) -> Dict:
        key = payload.get("key", "")
        self.forget(key)
        return {"deleted": True, "key": key}


class FileSearchAgentAdapter(BaseSpecialistAdapter):
    def __init__(self):
        from core.search_manager import search_manager
        self.search_manager = search_manager
        super().__init__(
            "FileSearchAgent", "file_search",
            ["file_search", "folder_search", "document_search", "universal_search", "recent_files"],
            search_manager,
            max_concurrent_tasks=3,
            resource_profile={"gpu_memory_mb": 0, "cpu_cores": 1, "ram_mb": 256}
        )
        self._register_methods()

    def _register_methods(self):
        self.register_method("search_files", self._search_files)
        self.register_method("search_folders", self._search_folders)
        self.register_method("search_documents", self._search_documents)
        self.register_method("search_universal", self._search_universal)
        self.register_method("recent_files", self._recent_files)

    def _search_files(self, payload: Dict) -> Dict:
        query = payload.get("query", "")
        limit = payload.get("limit", 20)
        results = self.search_manager.search_files(query, limit)
        return {"results": results, "count": len(results)}

    def _search_folders(self, payload: Dict) -> Dict:
        query = payload.get("query", "")
        limit = payload.get("limit", 20)
        results = self.search_manager.search_folders(query, limit)
        return {"results": results, "count": len(results)}

    def _search_documents(self, payload: Dict) -> Dict:
        query = payload.get("query", "")
        limit = payload.get("limit", 20)
        results = self.search_manager.search_documents(query, limit)
        return {"results": results, "count": len(results)}

    def _search_universal(self, payload: Dict) -> Dict:
        query = payload.get("query", "")
        limit = payload.get("limit", 20)
        results = self.search_manager.search(query, limit)
        return {"results": results, "count": len(results)}

    def _recent_files(self, payload: Dict) -> Dict:
        limit = payload.get("limit", 20)
        results = self.search_manager.search_recent(limit)
        return {"results": results, "count": len(results)}


# ============================================================
# ADDITIONAL SPECIALIST ADAPTERS
# ============================================================

class AITutorAdapter(BaseSpecialistAdapter):
    def __init__(self):
        import core.ai_tutor as ai_tutor_module
        # Find the tutor instance
        self.tutor = None
        for attr in dir(ai_tutor_module):
            obj = getattr(ai_tutor_module, attr)
            if hasattr(obj, '__class__') and 'Tutor' in obj.__class__.__name__:
                self.tutor = obj
                break
        super().__init__(
            "AITutor", "ai_tutor",
            ["topic_management", "lesson_generation", "quiz_creation", "progress_tracking", "learning_path"],
            self.tutor,
            max_concurrent_tasks=2,
            resource_profile={"gpu_memory_mb": 1024, "cpu_cores": 2, "ram_mb": 1024}
        )
        if self.tutor:
            self._register_methods()

    def _register_methods(self):
        self.register_method("create_topic", self._create_topic)
        self.register_method("generate_lesson", self._generate_lesson)
        self.register_method("create_quiz", self._create_quiz)
        self.register_method("get_progress", self._get_progress)

    def _create_topic(self, payload: Dict) -> Dict:
        if not self.tutor: return {"error": "Tutor not initialized"}
        return self.tutor.create_topic(payload)

    def _generate_lesson(self, payload: Dict) -> Dict:
        if not self.tutor: return {"error": "Tutor not initialized"}
        return self.tutor.generate_lesson(payload)

    def _create_quiz(self, payload: Dict) -> Dict:
        if not self.tutor: return {"error": "Tutor not initialized"}
        return self.tutor.create_quiz(payload)

    def _get_progress(self, payload: Dict) -> Dict:
        if not self.tutor: return {"error": "Tutor not initialized"}
        return self.tutor.get_user_progress(payload.get("topic_id", ""))


class LectureIntelligenceAdapter(BaseSpecialistAdapter):
    def __init__(self):
        self.lecture = None
        try:
            import core.lecture_intelligence as lecture_module
            self.lecture = lecture_module
        except ImportError:
            pass
        super().__init__(
            "LectureIntelligence", "lecture_intelligence",
            ["audio_capture", "transcription", "note_generation", "summarization", "action_extraction"],
            self.lecture,
            max_concurrent_tasks=1,
            resource_profile={"gpu_memory_mb": 2048, "cpu_cores": 2, "ram_mb": 2048}
        )
        if self.lecture:
            self._register_methods()

    def _register_methods(self):
        self.register_method("start_recording", self._start_recording)
        self.register_method("stop_recording", self._stop_recording)
        self.register_method("get_notes", self._get_notes)
        self.register_method("get_summary", self._get_summary)

    def _start_recording(self, payload: Dict) -> Dict:
        session = self.lecture.start_lecture(payload.get("title", "Lecture"))
        return {"session_id": session.id, "status": "recording"}

    def _stop_recording(self, payload: Dict) -> Dict:
        session_id = payload.get("session_id")
        self.lecture.stop_lecture(session_id)
        return {"status": "stopped"}

    def _get_notes(self, payload: Dict) -> Dict:
        session_id = payload.get("session_id")
        notes = self.lecture.get_lecture_notes(session_id)
        return {"notes": notes}

    def _get_summary(self, payload: Dict) -> Dict:
        session_id = payload.get("session_id")
        summary = self.lecture.get_lecture_summary(session_id)
        return {"summary": summary}


class PassiveMentorAdapter(BaseSpecialistAdapter):
    def __init__(self):
        import core.passive_mentor as mentor_module
        self.mentor = mentor_module.mentor if hasattr(mentor_module, 'mentor') else None
        super().__init__(
            "PassiveMentor", "passive_mentor",
            ["pattern_observation", "proactive_suggestions", "learning_insights", "anomaly_detection"],
            self.mentor,
            max_concurrent_tasks=2,
            resource_profile={"gpu_memory_mb": 512, "cpu_cores": 1, "ram_mb": 512}
        )
        if self.mentor:
            self._register_methods()

    def _register_methods(self):
        self.register_method("get_suggestions", self._get_suggestions)
        self.register_method("get_insights", self._get_insights)
        self.register_method("get_anomalies", self._get_anomalies)

    def _get_suggestions(self, payload: Dict) -> Dict:
        if not self.mentor: return {"error": "Mentor not initialized"}
        return self.mentor.get_proactive_suggestions(payload.get("context", {}))

    def _get_insights(self, payload: Dict) -> Dict:
        if not self.mentor: return {"error": "Mentor not initialized"}
        return self.mentor.get_learning_insights()

    def _get_anomalies(self, payload: Dict) -> Dict:
        if not self.mentor: return {"error": "Mentor not initialized"}
        return self.mentor.get_anomalies()


class ExplanationEngineAdapter(BaseSpecialistAdapter):
    def __init__(self):
        import core.explanation_engine as exp_module
        self.engine = exp_module.ReasoningEngine() if hasattr(exp_module, 'ReasoningEngine') else None
        super().__init__(
            "ExplanationEngine", "explanation_engine",
            ["step_by_step_reasoning", "decision_trace", "causal_chain", "counterfactual", "confidence_analysis"],
            self.engine,
            max_concurrent_tasks=2,
            resource_profile={"gpu_memory_mb": 1024, "cpu_cores": 2, "ram_mb": 1024}
        )
        if self.engine:
            self._register_methods()

    def _register_methods(self):
        self.register_method("reason_step_by_step", self._reason_step_by_step)
        self.register_method("trace_decision", self._trace_decision)

    def _reason_step_by_step(self, payload: Dict) -> Dict:
        if not self.engine: return {"error": "Engine not initialized"}
        question = payload.get("question", "")
        context = payload.get("context", {})
        return self.engine.reason_step_by_step(question, context)

    def _trace_decision(self, payload: Dict) -> Dict:
        if not self.engine: return {"error": "Engine not initialized"}
        decision = payload.get("decision", "")
        context = payload.get("context", {})
        options = payload.get("options", [])
        return self.engine.trace_decision(decision, context, options)


class ProjectAwarenessAdapter(BaseSpecialistAdapter):
    def __init__(self):
        import core.project_awareness as pa_module
        self.project_awareness = pa_module.project_awareness if hasattr(pa_module, 'project_awareness') else None
        super().__init__(
            "ProjectAwareness", "project_awareness",
            ["project_discovery", "git_integration", "dependency_tracking", "health_monitoring", "file_tracking"],
            self.project_awareness,
            max_concurrent_tasks=2,
            resource_profile={"gpu_memory_mb": 0, "cpu_cores": 1, "ram_mb": 512}
        )
        if self.project_awareness:
            self._register_methods()

    def _register_methods(self):
        self.register_method("discover_project", self._discover_project)
        self.register_method("get_project_context", self._get_project_context)
        self.register_method("track_dependencies", self._track_dependencies)

    def _discover_project(self, payload: Dict) -> Dict:
        if not self.project_awareness: return {"error": "Project awareness not initialized"}
        path = payload.get("path", ".")
        return self.project_awareness.discover_project(path)

    def _get_project_context(self, payload: Dict) -> Dict:
        if not self.project_awareness: return {"error": "Project awareness not initialized"}
        path = payload.get("path", ".")
        return self.project_awareness.get_project_context(path)

    def _track_dependencies(self, payload: Dict) -> Dict:
        if not self.project_awareness: return {"error": "Project awareness not initialized"}
        path = payload.get("path", ".")
        return self.project_awareness.analyze_dependencies(path)


class GoalAwarenessAdapter(BaseSpecialistAdapter):
    def __init__(self):
        import core.goal_awareness as ga_module
        self.goal_awareness = ga_module
        super().__init__(
            "GoalAwareness", "goal_awareness",
            ["goal_management", "milestone_tracking", "progress_monitoring", "alignment_checking"],
            ga_module,
            max_concurrent_tasks=3,
            resource_profile={"gpu_memory_mb": 0, "cpu_cores": 1, "ram_mb": 256}
        )
        self._register_methods()

    def _register_methods(self):
        self.register_method("create_goal", self._create_goal)
        self.register_method("get_active_goals", self._get_active_goals)
        self.register_method("update_progress", self._update_progress)
        self.register_method("get_goal_health", self._get_goal_health)

    def _create_goal(self, payload: Dict) -> Dict:
        return self.goal_awareness.create_goal(payload)

    def _get_active_goals(self, payload: Dict) -> Dict:
        summary = self.goal_awareness.get_active_goals_summary()
        return summary

    def _update_progress(self, payload: Dict) -> Dict:
        goal_id = payload.get("goal_id")
        progress = payload.get("progress")
        return self.goal_awareness.update_goal_progress(goal_id, progress)

    def _get_goal_health(self, payload: Dict) -> Dict:
        goal_id = payload.get("goal_id")
        return self.goal_awareness.get_goal_health(goal_id)


class PredictiveAIAdapter(BaseSpecialistAdapter):
    def __init__(self):
        import core.predictive_ai as pa_module
        self.predictive_ai = pa_module
        super().__init__(
            "PredictiveAI", "predictive_ai",
            ["time_series_forecasting", "anomaly_detection", "pattern_prediction", "trend_analysis"],
            pa_module,
            max_concurrent_tasks=1,
            resource_profile={"gpu_memory_mb": 2048, "cpu_cores": 2, "ram_mb": 2048}
        )
        self._register_methods()

    def _register_methods(self):
        self.register_method("create_forecast", self._create_forecast)
        self.register_method("detect_anomalies", self._detect_anomalies)
        self.register_method("analyze_trends", self._analyze_trends)

    def _create_forecast(self, payload: Dict) -> Dict:
        return self.predictive_ai.create_forecast(payload)

    def _detect_anomalies(self, payload: Dict) -> Dict:
        return self.predictive_ai.detect_anomalies(payload)

    def _analyze_trends(self, payload: Dict) -> Dict:
        return self.predictive_ai.analyze_trends(payload)


class ExecutiveAssistantAdapter(BaseSpecialistAdapter):
    def __init__(self):
        import core.executive_assistant as ea_module
        self.executive = ea_module.executive_assistant if hasattr(ea_module, 'executive_assistant') else None
        super().__init__(
            "ExecutiveAssistant", "executive_assistant",
            ["task_management", "calendar_management", "decision_support", "contact_management", "daily_planning"],
            self.executive,
            max_concurrent_tasks=3,
            resource_profile={"gpu_memory_mb": 0, "cpu_cores": 1, "ram_mb": 512}
        )
        if self.executive:
            self._register_methods()

    def _register_methods(self):
        self.register_method("create_task", self._create_task)
        self.register_method("get_dashboard", self._get_dashboard)
        self.register_method("morning_briefing", self._morning_briefing)
        self.register_method("suggest_schedule", self._suggest_schedule)

    def _create_task(self, payload: Dict) -> Dict:
        if not self.executive: return {"error": "Executive assistant not initialized"}
        return self.executive.task_mgr.create_task(payload)

    def _get_dashboard(self, payload: Dict) -> Dict:
        if not self.executive: return {"error": "Executive assistant not initialized"}
        return self.executive.get_dashboard()

    def _morning_briefing(self, payload: Dict) -> Dict:
        if not self.executive: return {"error": "Executive assistant not initialized"}
        return {"briefing": self.executive.morning_briefing()}

    def _suggest_schedule(self, payload: Dict) -> Dict:
        if not self.executive: return {"error": "Executive assistant not initialized"}
        date = payload.get("date")
        return self.executive.suggest_schedule(date)


class DigitalTwinAdapter(BaseSpecialistAdapter):
    def __init__(self):
        import core.digital_twin as dt_module
        self.digital_twin = dt_module.digital_twin if hasattr(dt_module, 'digital_twin') else None
        super().__init__(
            "DigitalTwin", "digital_twin",
            ["environment_snapshots", "activity_timeline", "session_tracking", "behavior_modeling", "workspace_reconstruction"],
            self.digital_twin,
            max_concurrent_tasks=1,
            resource_profile={"gpu_memory_mb": 1024, "cpu_cores": 2, "ram_mb": 1024}
        )
        if self.digital_twin:
            self._register_methods()

    def _register_methods(self):
        self.register_method("capture_snapshot", self._capture_snapshot)
        self.register_method("get_activity_timeline", self._get_activity_timeline)
        self.register_method("reconstruct_workspace", self._reconstruct_workspace)

    def _capture_snapshot(self, payload: Dict) -> Dict:
        if not self.digital_twin: return {"error": "Digital twin not initialized"}
        return self.digital_twin.capture_environment_snapshot()

    def _get_activity_timeline(self, payload: Dict) -> Dict:
        if not self.digital_twin: return {"error": "Digital twin not initialized"}
        hours = payload.get("hours", 24)
        return self.digital_twin.get_activity_timeline(hours)

    def _reconstruct_workspace(self, payload: Dict) -> Dict:
        if not self.digital_twin: return {"error": "Digital twin not initialized"}
        return self.digital_twin.reconstruct_workspace()


class OfflineIntelligenceAdapter(BaseSpecialistAdapter):
    def __init__(self):
        import core.offline_intelligence as oi_module
        self.offline = oi_module.offline_intelligence if hasattr(oi_module, 'offline_intelligence') else None
        super().__init__(
            "OfflineIntelligence", "offline_intelligence",
            ["model_management", "model_pulling", "benchmarking", "model_comparison", "local_inference"],
            self.offline,
            max_concurrent_tasks=1,
            resource_profile={"gpu_memory_mb": 4096, "cpu_cores": 4, "ram_mb": 8192}
        )
        if self.offline:
            self._register_methods()

    def _register_methods(self):
        self.register_method("list_models", self._list_models)
        self.register_method("pull_model", self._pull_model)
        self.register_method("benchmark_model", self._benchmark_model)

    def _list_models(self, payload: Dict) -> Dict:
        if not self.offline: return {"error": "Offline intelligence not initialized"}
        return self.offline.list_models()

    def _pull_model(self, payload: Dict) -> Dict:
        if not self.offline: return {"error": "Offline intelligence not initialized"}
        name = payload.get("name")
        return self.offline.pull_model(name)

    def _benchmark_model(self, payload: Dict) -> Dict:
        if not self.offline: return {"error": "Offline intelligence not initialized"}
        name = payload.get("name")
        return self.offline.benchmark_model(name)


class PersonalContextAdapter(BaseSpecialistAdapter):
    def __init__(self):
        import core.personal_context as pc_module
        self.personal_context = pc_module.personal_context if hasattr(pc_module, 'personal_context') else None
        super().__init__(
            "PersonalContext", "personal_context",
            ["preference_learning", "usage_patterns", "habit_tracking", "proactive_suggestions", "adaptive_config"],
            self.personal_context,
            max_concurrent_tasks=2,
            resource_profile={"gpu_memory_mb": 0, "cpu_cores": 1, "ram_mb": 256}
        )
        if self.personal_context:
            self._register_methods()

    def _register_methods(self):
        self.register_method("get_suggestions", self._get_suggestions)
        self.register_method("get_preferences", self._get_preferences)
        self.register_method("record_command", self._record_command)

    def _get_suggestions(self, payload: Dict) -> Dict:
        if not self.personal_context: return {"error": "Personal context not initialized"}
        limit = payload.get("limit", 5)
        return {"suggestions": self.personal_context.get_suggestions(limit)}

    def _get_preferences(self, payload: Dict) -> Dict:
        if not self.personal_context: return {"error": "Personal context not initialized"}
        return self.personal_context.get_user_preferences()

    def _record_command(self, payload: Dict) -> Dict:
        if not self.personal_context: return {"error": "Personal context not initialized"}
        return self.personal_context.record_command(payload)


class TimelineMemoryAdapter(BaseSpecialistAdapter):
    def __init__(self):
        import core.timeline_memory as tm_module
        self.timeline = tm_module.event_store if hasattr(tm_module, 'event_store') else None
        super().__init__(
            "TimelineMemory", "timeline_memory",
            ["event_logging", "daily_summaries", "temporal_queries", "activity_heatmap", "narrative_threads"],
            self.timeline,
            max_concurrent_tasks=2,
            resource_profile={"gpu_memory_mb": 0, "cpu_cores": 1, "ram_mb": 512}
        )
        if self.timeline:
            self._register_methods()

    def _register_methods(self):
        self.register_method("log_event", self._log_event)
        self.register_method("get_timeline", self._get_timeline)
        self.register_method("get_daily_summary", self._get_daily_summary)

    def _log_event(self, payload: Dict) -> Dict:
        if not self.timeline: return {"error": "Timeline memory not initialized"}
        return self.timeline.add_timeline_event(payload)

    def _get_timeline(self, payload: Dict) -> Dict:
        if not self.timeline: return {"error": "Timeline memory not initialized"}
        hours = payload.get("hours", 24)
        return {"events": self.timeline.get_timeline_events(hours)}

    def _get_daily_summary(self, payload: Dict) -> Dict:
        if not self.timeline: return {"error": "Timeline memory not initialized"}
        date = payload.get("date")
        return self.timeline.get_daily_summary(date)


class ContinuousAwarenessAdapter(BaseSpecialistAdapter):
    def __init__(self):
        import core.continuous_awareness as ca_module
        self.awareness = ca_module.continuous_awareness if hasattr(ca_module, 'continuous_awareness') else None
        super().__init__(
            "ContinuousAwareness", "continuous_awareness",
            ["context_snapshots", "activity_monitoring", "presence_detection", "proactive_suggestions"],
            self.awareness,
            max_concurrent_tasks=1,
            resource_profile={"gpu_memory_mb": 512, "cpu_cores": 1, "ram_mb": 512}
        )
        if self.awareness:
            self._register_methods()

    def _register_methods(self):
        self.register_method("get_current_context", self._get_current_context)
        self.register_method("get_suggestions", self._get_suggestions)

    def _get_current_context(self, payload: Dict) -> Dict:
        if not self.awareness: return {"error": "Continuous awareness not initialized"}
        return self.awareness.get_current_context()

    def _get_suggestions(self, payload: Dict) -> Dict:
        if not self.awareness: return {"error": "Continuous awareness not initialized"}
        return self.awareness.get_proactive_suggestions()


class SecondBrainAdapter(BaseSpecialistAdapter):
    def __init__(self):
        import core.second_brain as sb_module
        self.second_brain = sb_module.knowledge_graph if hasattr(sb_module, 'knowledge_graph') else None
        super().__init__(
            "SecondBrain", "second_brain",
            ["knowledge_graph", "bidirectional_links", "concept_mapping", "spaced_repetition", "review_scheduling"],
            self.second_brain,
            max_concurrent_tasks=2,
            resource_profile={"gpu_memory_mb": 0, "cpu_cores": 1, "ram_mb": 512}
        )
        if self.second_brain:
            self._register_methods()

    def _register_methods(self):
        self.register_method("create_node", self._create_node)
        self.register_method("link_nodes", self._link_nodes)
        self.register_method("search_nodes", self._search_nodes)
        self.register_method("get_review_schedule", self._get_review_schedule)

    def _create_node(self, payload: Dict) -> Dict:
        if not self.second_brain: return {"error": "Second brain not initialized"}
        return self.second_brain.create_node(payload)

    def _link_nodes(self, payload: Dict) -> Dict:
        if not self.second_brain: return {"error": "Second brain not initialized"}
        return self.second_brain.link_nodes(payload.get("source_id"), payload.get("target_id"), payload.get("relation_type"))

    def _search_nodes(self, payload: Dict) -> Dict:
        if not self.second_brain: return {"error": "Second brain not initialized"}
        query = payload.get("query", "")
        return {"nodes": self.second_brain.search_nodes(query)}

    def _get_review_schedule(self, payload: Dict) -> Dict:
        if not self.second_brain: return {"error": "Second brain not initialized"}
        return self.second_brain.get_review_schedule()


# ============================================================
# ADAPTER FACTORY & REGISTRATION
# ============================================================

def create_all_specialist_adapters() -> List[BaseSpecialistAdapter]:
    """Create all specialist agent adapters."""
    adapters = [
        CodingAgentAdapter(),
        ResearchAgentAdapter(),
        WritingAgentAdapter(),
        OfficeAgentAdapter(),
        SystemAgentAdapter(),
        CybersecurityAgentAdapter(),
        FinanceAgentAdapter(),
        AccountingAgentAdapter(),
        AuditAgentAdapter(),
        DataScienceAgentAdapter(),
        VisionAgentAdapter(),
        MemoryAgentAdapter(),
        FileSearchAgentAdapter(),
        AITutorAdapter(),
        LectureIntelligenceAdapter(),
        PassiveMentorAdapter(),
        ExplanationEngineAdapter(),
        ProjectAwarenessAdapter(),
        GoalAwarenessAdapter(),
        PredictiveAIAdapter(),
        ExecutiveAssistantAdapter(),
        DigitalTwinAdapter(),
        OfflineIntelligenceAdapter(),
        PersonalContextAdapter(),
        TimelineMemoryAdapter(),
        ContinuousAwarenessAdapter(),
        SecondBrainAdapter(),
    ]
    return adapters


def register_all_specialists():
    """Register all specialist agents in the global registry."""
    adapters = create_all_specialist_adapters()
    for adapter in adapters:
        registry.register_agent(adapter)
        adapter.start()
    return adapters


def get_specialist_capabilities() -> Dict[str, List[str]]:
    """Get capability map for all specialists."""
    adapters = create_all_specialist_adapters()
    cap_map = {}
    for adapter in adapters:
        cap_map[adapter.agent_type] = adapter.capabilities
    return cap_map


if __name__ == "__main__":
    print("Specialist Agent Adapters loaded.")
    adapters = create_all_specialist_adapters()
    for a in adapters:
        print(f"  {a.name} ({a.agent_type}): {a.capabilities}")