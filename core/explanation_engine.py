"""
Explanation Engine - Phase 17
Step-by-step reasoning, decision tracing, and explainable AI.
Fully local using Ollama, no cloud dependencies.
"""

import json
import time
import uuid
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict

from brain import ask_nova


class ExplanationType(Enum):
    STEP_BY_STEP = "step_by_step"
    DECISION_TRACE = "decision_trace"
    CAUSAL_CHAIN = "causal_chain"
    COUNTERFACTUAL = "counterfactual"
    CONFIDENCE = "confidence"
    ALTERNATIVE = "alternative"


class ReasoningStepType(Enum):
    OBSERVATION = "observation"
    INFERENCE = "inference"
    DECISION = "decision"
    ACTION = "action"
    VALIDATION = "validation"
    CORRECTION = "correction"


@dataclass
class ReasoningStep:
    step_id: str
    step_type: ReasoningStepType
    description: str
    input_data: Dict = field(default_factory=dict)
    output_data: Dict = field(default_factory=dict)
    confidence: float = 1.0
    dependencies: List[str] = field(default_factory=list)  # step_ids
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)


@dataclass
class Explanation:
    explanation_id: str
    explanation_type: ExplanationType
    question: str
    answer: str
    reasoning_chain: List[ReasoningStep] = field(default_factory=list)
    confidence: float = 0.0
    alternatives: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class DecisionTrace:
    trace_id: str
    decision: str
    context: Dict
    options_considered: List[Dict]
    chosen_option: Dict
    reasoning: List[ReasoningStep]
    confidence: float
    timestamp: float = field(default_factory=time.time)


class ReasoningEngine:
    """Core reasoning engine for step-by-step explanations."""

    def __init__(self):
        self.reasoning_chains = {}
        self.decision_traces = {}

    def reason_step_by_step(self, question: str, context: Dict = None) -> Explanation:
        """Generate step-by-step reasoning for a question."""
        explanation_id = str(uuid.uuid4())[:8]

        # Build reasoning prompt
        context_str = json.dumps(context or {}, indent=2)
        prompt = f"""Answer this question with explicit step-by-step reasoning.

Question: {question}
Context: {context_str}

Format your response as a JSON array of reasoning steps, where each step has:
- step_type: one of [observation, inference, decision, action, validation, correction]
- description: what happens in this step
- input: data used
- output: result produced
- confidence: 0.0-1.0
- depends_on: list of previous step_ids this step depends on

Then provide the final answer and overall confidence (0.0-1.0)."""

        try:
            response = ask_nova(prompt)
            # Parse the response
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            steps_data = []
            if json_match:
                steps_data = json.loads(json_match.group())

            reasoning_chain = []
            for i, step_data in enumerate(steps_data):
                step = ReasoningStep(
                    step_id=f"step_{i+1}",
                    step_type=ReasoningStepType(step_data.get("step_type", "inference")),
                    description=step_data.get("description", ""),
                    input_data=step_data.get("input", {}),
                    output_data=step_data.get("output", {}),
                    confidence=step_data.get("confidence", 0.8),
                    dependencies=step_data.get("depends_on", [])
                )
                reasoning_chain.append(step)

            # Extract final answer and confidence
            answer = self._extract_answer(response)
            confidence = self._extract_confidence(response, steps_data)

            explanation = Explanation(
                explanation_id=explanation_id,
                explanation_type=ExplanationType.STEP_BY_STEP,
                question=question,
                answer=answer,
                reasoning_chain=reasoning_chain,
                confidence=confidence,
                metadata={"context": context}
            )

            self.reasoning_chains[explanation_id] = explanation
            return explanation

        except Exception as e:
            return Explanation(
                explanation_id=explanation_id,
                explanation_type=ExplanationType.STEP_BY_STEP,
                question=question,
                answer=f"Reasoning failed: {e}",
                confidence=0.0,
                metadata={"error": str(e)}
            )

    def trace_decision(self, decision_question: str, options: List[Dict],
                       context: Dict = None) -> DecisionTrace:
        """Trace a decision-making process."""
        trace_id = str(uuid.uuid4())[:8]

        options_str = json.dumps(options, indent=2)
        context_str = json.dumps(context or {}, indent=2)

        prompt = f"""Trace the decision-making process for this question.

Decision: {decision_question}
Options: {options_str}
Context: {context_str}

For each option, evaluate pros/cons. Then explain the final choice.
Return JSON with:
- reasoning_steps: array of {{step_type, description, input, output, confidence, depends_on}}
- chosen_option: the selected option
- final_confidence: 0.0-1.0"""

        try:
            response = ask_nova(prompt)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            data = {}
            if json_match:
                data = json.loads(json_match.group())

            reasoning_chain = []
            for i, step_data in enumerate(data.get("reasoning_steps", [])):
                step = ReasoningStep(
                    step_id=f"step_{i+1}",
                    step_type=ReasoningStepType(step_data.get("step_type", "inference")),
                    description=step_data.get("description", ""),
                    input_data=step_data.get("input", {}),
                    output_data=step_data.get("output", {}),
                    confidence=step_data.get("confidence", 0.8),
                    dependencies=step_data.get("depends_on", [])
                )
                reasoning_chain.append(step)

            trace = DecisionTrace(
                trace_id=trace_id,
                decision=decision_question,
                context=context or {},
                options_considered=options,
                chosen_option=data.get("chosen_option", options[0] if options else {}),
                reasoning=reasoning_chain,
                confidence=data.get("final_confidence", 0.7),
                timestamp=time.time()
            )

            self.decision_traces[trace_id] = trace
            return trace

        except Exception as e:
            return DecisionTrace(
                trace_id=trace_id,
                decision=decision_question,
                context=context or {},
                options_considered=options,
                chosen_option={},
                reasoning=[],
                confidence=0.0,
                timestamp=time.time()
            )

    def generate_counterfactual(self, question: str, actual_outcome: str,
                                context: Dict = None) -> Explanation:
        """Generate counterfactual explanation."""
        explanation_id = str(uuid.uuid4())[:8]

        prompt = f"""Generate a counterfactual explanation.

Question: {question}
Actual outcome: {actual_outcome}
Context: {json.dumps(context or {}, indent=2)}

Explain what would have happened if key factors were different.
Identify 3-5 critical factors and their counterfactual impact.
Return JSON with:
- counterfactuals: array of {{factor, actual_value, alternative_value, predicted_outcome, confidence}}
- overall_confidence: 0.0-1.0"""

        try:
            response = ask_nova(prompt)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            data = {}
            if json_match:
                data = json.loads(json_match.group())

            alternatives = data.get("counterfactuals", [])
            confidence = data.get("overall_confidence", 0.6)

            return Explanation(
                explanation_id=str(uuid.uuid4())[:8],
                explanation_type=ExplanationType.COUNTERFACTUAL,
                question=question,
                answer=f"Counterfactual analysis of: {actual_outcome}",
                reasoning_chain=[],
                confidence=confidence,
                alternatives=alternatives,
                metadata={"actual_outcome": actual_outcome, "context": context}
            )
        except Exception as e:
            return Explanation(
                explanation_id=str(uuid.uuid4())[:8],
                explanation_type=ExplanationType.COUNTERFACTUAL,
                question=question,
                answer=f"Counterfactual generation failed: {e}",
                confidence=0.0
            )

    def explain_confidence(self, prediction: str, confidence: float,
                           factors: List[str] = None) -> Explanation:
        """Explain why a confidence score was assigned."""
        explanation_id = str(uuid.uuid4())[:8]

        factors_str = ", ".join(factors or ["model uncertainty", "data quality", "context ambiguity"])

        prompt = f"""Explain the confidence assessment for this prediction.

Prediction: {prediction}
Confidence: {confidence:.0%}
Factors: {factors_str}

Explain what contributes to this confidence level. Break down:
1. Supporting evidence
2. Sources of uncertainty
3. What would increase/decrease confidence
Return as structured explanation."""

        response = ask_nova(prompt)
        return Explanation(
            explanation_id=str(uuid.uuid4())[:8],
            explanation_type=ExplanationType.CONFIDENCE,
            question=f"Why confidence {confidence:.0%} for: {prediction}",
            answer=response,
            confidence=confidence,
            metadata={"factors": factors}
        )

    def suggest_alternatives(self, question: str, current_answer: str,
                             context: Dict = None) -> Explanation:
        """Suggest alternative approaches or answers."""
        explanation_id = str(uuid.uuid4())[:8]

        prompt = f"""Suggest alternative approaches to this question.

Question: {question}
Current answer: {current_answer}
Context: {json.dumps(context or {}, indent=2)}

Provide 3-5 alternatives with pros/cons.
Return JSON with:
- alternatives: array of {{approach, description, pros, cons, confidence}}
- recommendation: which alternative is best and why"""

        try:
            response = ask_nova(prompt)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            data = {}
            if json_match:
                data = json.loads(json_match.group())

            alternatives = data.get("alternatives", [])
            return Explanation(
                explanation_id=str(uuid.uuid4())[:8],
                explanation_type=ExplanationType.ALTERNATIVE,
                question=question,
                answer=current_answer,
                confidence=0.7,
                alternatives=alternatives,
                metadata={"recommendation": data.get("recommendation", "")}
            )
        except Exception as e:
            return Explanation(
                explanation_id=str(uuid.uuid4())[:8],
                explanation_type=ExplanationType.ALTERNATIVE,
                question=question,
                answer=f"Alternative generation failed: {e}",
                confidence=0.0
            )

    def _extract_answer(self, response: str) -> str:
        """Extract final answer from LLM response."""
        # Try to find answer after reasoning
        parts = response.split("final answer")
        if len(parts) > 1:
            return parts[-1].strip()
        # Try to find answer after conclusion
        parts = response.split("conclusion")
        if len(parts) > 1:
            return parts[-1].strip()
        return response[:500]  # Fallback

    def _extract_confidence(self, response: str, steps_data: List) -> float:
        """Extract overall confidence."""
        # Look for confidence in response
        import re
        conf_match = re.search(r'confidence["\s:]+([0-9.]+)', response, re.IGNORECASE)
        if conf_match:
            return float(conf_match.group(1))
        # Average step confidences
        if steps_data:
            confs = [s.get("confidence", 0.8) for s in steps_data]
            return sum(confs) / len(confs)
        return 0.7


class CausalAnalyzer:
    """Analyze causal relationships in reasoning."""

    def __init__(self):
        self.causal_graph = defaultdict(list)

    def build_causal_chain(self, events: List[Dict]) -> List[Dict]:
        """Build causal chain from events."""
        # Simple temporal + dependency analysis
        chain = []
        for event in events:
            causes = self._find_causes(event, events)
            chain.append({
                "event": event,
                "direct_causes": causes,
                "confidence": 0.7
            })
        return chain

    def _find_causes(self, event: Dict, all_events: List[Dict]) -> List[Dict]:
        """Find direct causes of an event."""
        causes = []
        event_time = event.get("timestamp", 0)

        for other in all_events:
            if other.get("timestamp", 0) < event_time:
                # Check if other could cause event
                if self._could_cause(other, event):
                    causes.append(other)
        return causes

    def _could_cause(self, cause: Dict, effect: Dict) -> bool:
        """Heuristic: could cause lead to effect?"""
        cause_type = cause.get("type", "")
        effect_type = effect.get("type", "")

        causal_rules = {
            "action": ["observation", "state_change"],
            "decision": ["action"],
            "observation": ["inference"],
            "inference": ["decision"],
            "state_change": ["observation"],
        }

        return effect_type in causal_rules.get(cause_type, [])


class ExplanationManager:
    """Manage explanations and provide querying."""

    def __init__(self):
        self.reasoning_engine = ReasoningEngine()
        self.causal_analyzer = CausalAnalyzer()
        self.explanations = {}
        self.explanation_history = []

    def explain(self, question: str, context: Dict = None,
                explanation_type: ExplanationType = ExplanationType.STEP_BY_STEP) -> Explanation:
        """Generate an explanation."""
        if explanation_type == ExplanationType.STEP_BY_STEP:
            explanation = self.reasoning_engine.reason_step_by_step(question, context)
        elif explanation_type == ExplanationType.COUNTERFACTUAL:
            explanation = self.reasoning_engine.generate_counterfactual(
                question, context.get("actual_outcome", ""), context
            )
        elif explanation_type == ExplanationType.CONFIDENCE:
            explanation = self.reasoning_engine.explain_confidence(
                context.get("prediction", ""), context.get("confidence", 0.5),
                context.get("factors")
            )
        elif explanation_type == ExplanationType.ALTERNATIVE:
            explanation = self.reasoning_engine.suggest_alternatives(
                question, context.get("current_answer", ""), context
            )
        else:
            explanation = self.reasoning_engine.reason_step_by_step(question, context)

        self.explanations[explanation.explanation_id] = explanation
        self.explanation_history.append({
            "id": explanation.explanation_id,
            "type": explanation.explanation_type.value,
            "question": question,
            "timestamp": explanation.timestamp
        })

        return explanation

    def trace_decision(self, decision: str, options: List[Dict],
                       context: Dict = None) -> DecisionTrace:
        return self.reasoning_engine.trace_decision(decision, options, context)

    def get_explanation(self, explanation_id: str) -> Optional[Explanation]:
        return self.explanations.get(explanation_id)

    def list_explanations(self, limit: int = 20) -> List[Dict]:
        return self.explanation_history[-limit:]

    def format_explanation(self, explanation: Explanation,
                           format: str = "text") -> str:
        """Format explanation for display."""
        if format == "json":
            return json.dumps(asdict(explanation), indent=2, default=str)

        lines = [
            f"Explanation: {explanation.explanation_id}",
            f"Type: {explanation.explanation_type.value}",
            f"Question: {explanation.question}",
            f"Confidence: {explanation.confidence:.0%}",
            f"",
            f"Answer: {explanation.answer}",
            f"",
        ]

        if explanation.reasoning_chain:
            lines.append("Reasoning Chain:")
            for step in explanation.reasoning_chain:
                deps = f" (depends on: {', '.join(step.dependencies)})" if step.dependencies else ""
                lines.append(f"  {step.step_id} [{step.step_type.value}]: {step.description}{deps}")
                if step.input_data:
                    lines.append(f"    Input: {step.input_data}")
                if step.output_data:
                    lines.append(f"    Output: {step.output_data}")
                lines.append(f"    Confidence: {step.confidence:.0%}")
            lines.append("")

        if explanation.alternatives:
            lines.append("Alternatives:")
            for alt in explanation.alternatives:
                lines.append(f"  - {alt.get('approach', 'N/A')}: {alt.get('description', '')}")
                if "pros" in alt:
                    lines.append(f"    Pros: {', '.join(alt['pros'])}")
                if "cons" in alt:
                    lines.append(f"    Cons: {', '.join(alt['cons'])}")
            lines.append("")

        return "\n".join(lines)

    def format_decision_trace(self, trace: DecisionTrace, format: str = "text") -> str:
        if format == "json":
            return json.dumps(asdict(trace), indent=2, default=str)

        lines = [
            f"Decision Trace: {trace.trace_id}",
            f"Decision: {trace.decision}",
            f"Confidence: {trace.confidence:.0%}",
            f"",
            f"Options Considered:",
        ]

        for i, opt in enumerate(trace.options_considered):
            chosen = " ✓ CHOSEN" if opt == trace.chosen_option else ""
            lines.append(f"  {i+1}. {opt}{chosen}")

        lines.append("")
        lines.append("Reasoning:")
        for step in trace.reasoning:
            lines.append(f"  {step.step_id} [{step.step_type.value}]: {step.description}")
            if step.output_data:
                lines.append(f"    → {step.output_data}")

        return "\n".join(lines)


# Global instance
explanation_manager = ExplanationManager()


# Convenience functions
def explain(question: str, context: Dict = None,
            explanation_type: ExplanationType = ExplanationType.STEP_BY_STEP) -> Explanation:
    return explanation_manager.explain(question, context, explanation_type)

def trace_decision(decision: str, options: List[Dict], context: Dict = None) -> DecisionTrace:
    return explanation_manager.trace_decision(decision, options, context)

def explain_confidence(prediction: str, confidence: float, factors: List[str] = None) -> Explanation:
    return explanation_manager.reasoning_engine.explain_confidence(prediction, confidence, factors)

def suggest_alternatives(question: str, current_answer: str, context: Dict = None) -> Explanation:
    return explanation_manager.reasoning_engine.suggest_alternatives(question, current_answer, context)

def counterfactual(question: str, actual_outcome: str, context: Dict = None) -> Explanation:
    return explanation_manager.reasoning_engine.generate_counterfactual(question, actual_outcome, context)

def format_explanation(explanation: Explanation, format: str = "text") -> str:
    return explanation_manager.format_explanation(explanation, format)

def format_decision_trace(trace: DecisionTrace, format: str = "text") -> str:
    return explanation_manager.format_decision_trace(trace, format)

def list_explanations(limit: int = 20) -> List[Dict]:
    return explanation_manager.list_explanations(limit)


# Voice command integration
def explanation_debug(question: str, exp_type: str = "step_by_step") -> str:
    """Debug explanation generation."""
    exp_type_map = {
        "step": ExplanationType.STEP_BY_STEP,
        "counterfactual": ExplanationType.COUNTERFACTUAL,
        "confidence": ExplanationType.CONFIDENCE,
        "alternative": ExplanationType.ALTERNATIVE,
    }
    exp_type = exp_type_map.get(exp_type, ExplanationType.STEP_BY_STEP)

    explanation = explain(question, explanation_type=exp_type)
    return format_explanation(explanation)


if __name__ == "__main__":
    # Test
    print("Explanation Engine loaded.")
    print("Available functions:")
    print("  explain(question, context, type)")
    print("  trace_decision(decision, options, context)")
    print("  explain_confidence(prediction, confidence, factors)")
    print("  suggest_alternatives(question, current_answer, context)")
    print("  counterfactual(question, actual_outcome, context)")
    print("  format_explanation(explanation, format)")