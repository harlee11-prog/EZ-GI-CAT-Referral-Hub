from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timezone

# Optional chained dyspepsia engine import
try:
    from dyspepsia_engine import run_dyspepsia_pathway
    DYSPEPSIA_ENGINE_AVAILABLE = True
except Exception:
    DYSPEPSIA_ENGINE_AVAILABLE = False


@dataclass
class Action:
    code: str
    label: str
    urgency: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    override_options: Optional[Dict[str, Any]] = None
    display: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataRequest:
    blocking_node: str
    missing_fields: List[str]
    message: str
    urgency_context: Optional[str] = None
    suggested_actions: List[Action] = field(default_factory=list)


@dataclass
class Stop:
    reason: str
    actions: List[Action] = field(default_factory=list)
    urgency: Optional[str] = None


Output = Action | DataRequest | Stop


# =========================================================
# DECISION LOG
# =========================================================

@dataclass
class DecisionLog:
    node: str
    decision: str
    used_inputs: Dict[str, Any]
    outputs: List[Dict[str, Any]]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Override:
    target_node: str
    field: str
    old_value: Any
    new_value: Any
    reason: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# =========================================================
# CONTEXT
# =========================================================

@dataclass
class Context:
    data: Dict[str, Any]
    logs: List[DecisionLog] = field(default_factory=list)
    overrides: List[Override] = field(default_factory=list)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def apply_override(self, node, field, value):
        for o in reversed(self.overrides):
            if o.target_node == node and o.field == field:
                return o.new_value
        return value

    def log(self, node, decision, inputs, outputs):
        self.logs.append(
            DecisionLog(
                node=node,
                decision=decision,
                used_inputs=inputs,
                outputs=[{"type": type(o).__name__} for o in outputs],
            )
        )


# =========================================================
# ENGINE CORE
# =========================================================

@dataclass
class NodeResult:
    outputs: List[Output]
    next_node: Optional[str] = None


NodeFn = Callable[[Context], NodeResult]


@dataclass
class Node:
    node_id: str
    fn: NodeFn


class PathwayEngine:
    def __init__(self, nodes: Dict[str, Node], start_node: str):
        self.nodes = nodes
        self.start_node = start_node

    def run(self, ctx: Context) -> List[Output]:
        outputs: List[Output] = []
        current = self.start_node
        guard = 0

        while current:
            guard += 1
            if guard > 250:
                outputs.append(Stop(reason="Safety stop: possible infinite loop"))
                break

            result = self.nodes[current].fn(ctx)
            outputs.extend(result.outputs)

            if any(isinstance(o, (Stop, DataRequest)) for o in result.outputs):
                break

            current = result.next_node

        return outputs


# =========================================================
# H. PYLORI PATHWAY IMPLEMENTATION
# =========================================================

def h_pylori_build_engine() -> PathwayEngine:
    nodes: Dict[str, Node] = {}

    # -----------------------------------------------------
    # Helper
    # -----------------------------------------------------

    def _entry_indication(ctx: Context) -> Dict[str, Any]:
        dyspepsia = bool(ctx.get("dyspepsia_symptoms"))
        ulcer_or_upper_gi_bleed = bool(ctx.get("current_or_past_gastric_or_duodenal_ulcer_or_upper_gi_bleed"))
        fh_gastric_cancer = bool(ctx.get("personal_or_first_degree_relative_history_gastric_cancer"))
        first_gen_immigrant_high_prevalence = bool(ctx.get("first_generation_immigrant_high_prevalence_region"))

        indicated = any([
            dyspepsia,
            ulcer_or_upper_gi_bleed,
            fh_gastric_cancer,
            first_gen_immigrant_high_prevalence,
        ])

        return {
            "indicated": indicated,
            "dyspepsia_symptoms": dyspepsia,
            "current_or_past_gastric_or_duodenal_ulcer_or_upper_gi_bleed": ulcer_or_upper_gi_bleed,
            "personal_or_first_degree_relative_history_gastric_cancer": fh_gastric_cancer,
            "first_generation_immigrant_high_prevalence_region": first_gen_immigrant_high_prevalence,
        }

    # -----------------------------------------------------
    # Node 1 – Who should be tested
    # -----------------------------------------------------

    def node_entry(ctx: Context):
        node_id = "Who_Should_Be_Tested"

        info = _entry_indication(ctx)
        indicated = info["indicated"]
        indicated = ctx.apply_override(node_id, "testing_indicated", indicated)
        ctx.set("testing_indicated", indicated)

        actions: List[Output] = []

        if not indicated:
            actions.append(Action(
                code="TESTING_NOT_INDICATED_WARNING",
                label="H. pylori testing is not clearly indicated based on pathway entry criteria.",
                details=info,
                override_options={
                    "node": node_id,
                    "field": "testing_indicated",
                    "allowed": [True, False],
                    "reason_required": True,
                },
                display={"role": "advisory", "badge": "warning", "show_as_standalone": True, "sort_priority": 10},
            ))
        else:
            actions.append(Action(
                code="TESTING_INDICATED",
                label="H. pylori testing is indicated.",
                details=info,
                override_options={
                    "node": node_id,
                    "field": "testing_indicated",
                    "allowed": [True, False],
                    "reason_required": True,
                },
                display={"role": "support", "badge": "info", "show_as_standalone": True, "sort_priority": 10},
            ))

        ctx.log(node_id, "ENTRY_ASSESSED", info, actions)
        return NodeResult(actions, next_node="Alarm_Features")

    nodes["Who_Should_Be_Tested"] = Node("Who_Should_Be_Tested", node_entry)

    # -----------------------------------------------------
    # Node 2 – Alarm features
    # -----------------------------------------------------

    def node_alarm(ctx: Context):
        node_id = "Alarm_Features"

        fh_esophageal_or_gastric_cancer = bool(ctx.get("family_history_esophageal_or_gastric_cancer_first_degree"))
        personal_history_peptic_ulcer_disease = bool(ctx.get("personal_history_peptic_ulcer_disease"))
        age_over_60_new_persistent_symptoms = bool(ctx.get("age_over_60_new_persistent_symptoms_over_3_months"))
        unintended_weight_loss = bool(ctx.get("unintended_weight_loss"))
        progressive_dysphagia = bool(ctx.get("progressive_dysphagia"))
        persistent_vomiting = bool(ctx.get("persistent_vomiting_not_cannabis_related"))
        black_stool_or_blood_in_vomit = bool(ctx.get("black_stool_or_blood_in_vomit"))
        iron_deficiency_anemia = bool(ctx.get("iron_deficiency_anemia_present"))
        clinician_concern = bool(ctx.get("clinician_concern_serious_pathology"))

        alarm_present = any([
            fh_esophageal_or_gastric_cancer,
            personal_history_peptic_ulcer_disease,
            age_over_60_new_persistent_symptoms,
            unintended_weight_loss,
            progressive_dysphagia,
            persistent_vomiting,
            black_stool_or_blood_in_vomit,
            iron_deficiency_anemia,
            clinician_concern,
        ])
        alarm_present = ctx.apply_override(node_id, "alarm_features_present", alarm_present)
        ctx.set("alarm_features_present", alarm_present)

        if alarm_present:
            actions = [
                Action(
                    code="URGENT_ENDOSCOPY_REFERRAL",
                    label="Refer for consultation/endoscopy.",
                    urgency="urgent",
                    details={
                        "supported_by": ["At least one H. pylori alarm feature is present"],
                        "family_history_esophageal_or_gastric_cancer_first_degree": fh_esophageal_or_gastric_cancer,
                        "personal_history_peptic_ulcer_disease": personal_history_peptic_ulcer_disease,
                        "age_over_60_new_persistent_symptoms_over_3_months": age_over_60_new_persistent_symptoms,
                        "unintended_weight_loss": unintended_weight_loss,
                        "progressive_dysphagia": progressive_dysphagia,
                        "persistent_vomiting_not_cannabis_related": persistent_vomiting,
                        "black_stool_or_blood_in_vomit": black_stool_or_blood_in_vomit,
                        "iron_deficiency_anemia_present": iron_deficiency_anemia,
                        "clinician_concern_serious_pathology": clinician_concern,
                    },
                    override_options={
                        "node": node_id,
                        "field": "alarm_features_present",
                        "allowed": [True, False],
                        "reason_required": True,
                    },
                    display={"role": "primary_decision", "show_as_standalone": True, "sort_priority": 20},
                )
            ]

            if black_stool_or_blood_in_vomit:
                actions.append(Action(
                    code="BLEEDING_REFERRAL_LABS",
                    label="If black stool or blood in vomit is present, include CBC, INR, and BUN as part of referral.",
                    display={"role": "support", "badge": "info", "show_as_standalone": True, "sort_priority": 21},
                ))

            stop = Stop(
                reason="Alarm features present – urgent referral for consultation/endoscopy.",
                urgency="urgent",
                actions=actions,
            )
            ctx.log(node_id, "ALARM_FEATURES_PRESENT", {}, [stop])
            return NodeResult([stop])

        out = [
            Action(
                code="NO_ALARM_FEATURES",
                label="No alarm features present.",
                display={"role": "support", "badge": "info", "show_as_standalone": True, "sort_priority": 22},
            )
        ]
        ctx.log(node_id, "NO_ALARM_FEATURES", {}, out)
        return NodeResult(out, next_node="Diagnosis")

    nodes["Alarm_Features"] = Node("Alarm_Features", node_alarm)

    # -----------------------------------------------------
    # Node 3 – Diagnosis
    # -----------------------------------------------------

    def node_diagnosis(ctx: Context):
        node_id = "Diagnosis"

        test_type = ctx.get("hp_test_type")
        test_result = ctx.get("hp_test_result")

        missing = []
        if test_type is None:
            missing.append("hp_test_type")
        if test_result is None:
            missing.append("hp_test_result")

        if missing:
            dr = DataRequest(
                blocking_node=node_id,
                missing_fields=missing,
                message="Need H. pylori test type and result.",
                suggested_actions=[
                    Action(
                        code="CAPTURE_HP_TEST",
                        label="Capture HpSAT or UBT result",
                        display={"role": "support", "badge": "info", "show_as_standalone": True, "sort_priority": 30},
                    )
                ],
            )
            ctx.log(node_id, "BLOCKED_MISSING_DATA", {"missing": missing}, [dr])
            return NodeResult([dr])

        actions: List[Output] = []

        if test_type not in ["HpSAT", "UBT"]:
            actions.append(Action(
                code="HP_TEST_TYPE_WARNING",
                label="Preferred H. pylori tests are HpSAT or UBT.",
                details={"hp_test_type": test_type},
                display={"role": "advisory", "badge": "warning", "show_as_standalone": True, "sort_priority": 31},
            ))

        if ctx.get("off_antibiotics_4_weeks_before_test") is False:
            actions.append(Action(
                code="TEST_PREP_ANTIBIOTIC_WARNING",
                label="Accurate H. pylori testing requires being off antibiotics for at least 4 weeks.",
                display={"role": "advisory", "badge": "warning", "show_as_standalone": True, "sort_priority": 31},
            ))

        if ctx.get("off_ppi_2_weeks_before_test") is False:
            actions.append(Action(
                code="TEST_PREP_PPI_WARNING",
                label="Accurate H. pylori testing requires being off PPIs for at least 2 weeks.",
                display={"role": "advisory", "badge": "warning", "show_as_standalone": True, "sort_priority": 31},
            ))

        if ctx.get("off_bismuth_2_weeks_before_test") is False:
            actions.append(Action(
                code="TEST_PREP_BISMUTH_WARNING",
                label="Accurate H. pylori testing requires avoiding bismuth for 2 weeks before testing.",
                display={"role": "advisory", "badge": "warning", "show_as_standalone": True, "sort_priority": 31},
            ))

        if test_result == "negative":
            actions.append(Action(
                code="HP_NEGATIVE",
                label="H. pylori test is negative.",
                display={"role": "support", "badge": "info", "show_as_standalone": True, "sort_priority": 32},
            ))

        if DYSPEPSIA_ENGINE_AVAILABLE and isinstance(ctx.get("dyspepsia_patient_data"), dict):
            try:
                dys_outputs, _, _ = run_dyspepsia_pathway(ctx.get("dyspepsia_patient_data"))

                for o in dys_outputs:
                    # Action-like objects from dyspepsia engine
                    if hasattr(o, "code") and hasattr(o, "label"):
                        actions.append(Action(
                            code=f"DYSP_{o.code}",
                            label=f"Dyspepsia: {o.label}",
                            urgency=getattr(o, "urgency", None),
                            details=getattr(o, "details", {}),
                            display={"role": "support", "badge": "info", "show_as_standalone": True, "sort_priority": 33},
                        ))

                    # Stop-like objects from dyspepsia engine
                    elif hasattr(o, "reason") and hasattr(o, "actions"):
                        actions.append(Action(
                            code="DYSP_STOP",
                            label=f"Dyspepsia stop: {o.reason}",
                            urgency=getattr(o, "urgency", None),
                            details={},
                            display={"role": "support", "badge": "info", "show_as_standalone": True, "sort_priority": 33},
                        ))

                        for a in getattr(o, "actions", []):
                            if hasattr(a, "code") and hasattr(a, "label"):
                                actions.append(Action(
                                    code=f"DYSP_{a.code}",
                                    label=f"Dyspepsia: {a.label}",
                                    urgency=getattr(a, "urgency", None),
                                    details=getattr(a, "details", {}),
                                    display={"role": "support", "badge": "info", "show_as_standalone": True, "sort_priority": 33},
                                ))

                    # DataRequest-like objects from dyspepsia engine
                    elif hasattr(o, "blocking_node") and hasattr(o, "missing_fields"):
                        actions.append(Action(
                            code="DYSP_DATA_REQUEST",
                            label=f"Dyspepsia needs more data at {o.blocking_node}",
                            details={
                                "blocking_node": o.blocking_node,
                                "missing_fields": o.missing_fields,
                            },
                            display={"role": "support", "badge": "warning", "show_as_standalone": True, "sort_priority": 33},
                        ))

            except Exception as e:
                actions.append(Action(
                    code="DYSPEPSIA_CHAIN_FAILED",
                    label="Dyspepsia engine chaining unavailable at runtime; review dyspepsia pathway separately.",
                    details={"error": str(e)},
                    display={"role": "advisory", "badge": "warning", "show_as_standalone": True, "sort_priority": 33},
                ))
            else:
                actions.append(Action(
                    code="ROUTE_DYSPEPSIA_PATHWAY",
                    label="Follow Dyspepsia pathway.",
                    display={"role": "primary_decision", "show_as_standalone": True, "sort_priority": 33},
                ))

            stop = Stop(
                reason="H. pylori test negative.",
                actions=actions,
            )
            ctx.log(node_id, "HP_NEGATIVE", {"hp_test_type": test_type}, [stop])
            return NodeResult([stop])

        actions.append(Action(
            code="HP_POSITIVE",
            label="H. pylori test is positive.",
            display={"role": "support", "badge": "info", "show_as_standalone": True, "sort_priority": 34},
        ))
        ctx.log(node_id, "HP_POSITIVE", {"hp_test_type": test_type}, actions)
        return NodeResult(actions, next_node="Treatment")

    nodes["Diagnosis"] = Node("Diagnosis", node_diagnosis)

    # -----------------------------------------------------
    # Node 4 – Treatment
    # -----------------------------------------------------

    def node_treatment(ctx: Context):
        node_id = "Treatment"

        if bool(ctx.get("pregnant")) or bool(ctx.get("breastfeeding")):
            stop = Stop(
                reason="Pregnant and nursing women should not be treated for H. pylori.",
                actions=[
                    Action(
                        code="DO_NOT_TREAT_PREGNANCY_BREASTFEEDING",
                        label="Do not treat H. pylori during pregnancy/breastfeeding.",
                        display={"role": "primary_decision", "show_as_standalone": True, "sort_priority": 40},
                    )
                ],
            )
            ctx.log(node_id, "PREGNANCY_BREASTFEEDING_STOP", {
                "pregnant": ctx.get("pregnant"),
                "breastfeeding": ctx.get("breastfeeding"),
            }, [stop])
            return NodeResult([stop])

        treatment_line = ctx.get("treatment_line")
        if treatment_line is None:
            dr = DataRequest(
                blocking_node=node_id,
                missing_fields=["treatment_line"],
                message="Need current H. pylori treatment line (1-4).",
                suggested_actions=[
                    Action(
                        code="CAPTURE_TREATMENT_LINE",
                        label="Capture current treatment line",
                        display={"role": "support", "badge": "info", "show_as_standalone": True, "sort_priority": 41},
                    )
                ],
            )
            ctx.log(node_id, "BLOCKED_MISSING_DATA", {"missing": ["treatment_line"]}, [dr])
            return NodeResult([dr])

        penicillin_allergy = bool(ctx.get("penicillin_allergy"))
        actions: List[Output] = []

        if treatment_line == 1:
            if penicillin_allergy:
                actions.append(Action(
                    code="TREAT_LINE_1_PBMT",
                    label="First line (penicillin allergy): Bismuth Quadruple Regimen (PBMT) for 14 days.",
                    display={"role": "primary_decision", "show_as_standalone": True, "sort_priority": 42},
                ))
            else:
                actions.append(Action(
                    code="TREAT_LINE_1_PAMC_OR_PBMT",
                    label="First line: CLAMET Quad (PAMC) or BMT Quad (PBMT) for 14 days.",
                    display={"role": "primary_decision", "show_as_standalone": True, "sort_priority": 42},
                ))

        elif treatment_line == 2:
            if penicillin_allergy:
                actions.append(Action(
                    code="TREAT_LINE_2_PCM_OR_ALLERGY_REFERRAL",
                    label="Second line (penicillin allergy): Modified Triple (PCM) or consider referral for allergy testing.",
                    display={"role": "primary_decision", "show_as_standalone": True, "sort_priority": 43},
                ))
            else:
                actions.append(Action(
                    code="TREAT_LINE_2_NEXT_OPTION",
                    label="Second line: use an alternative regimen not previously used (e.g. PAMC vs PBMT).",
                    display={"role": "primary_decision", "show_as_standalone": True, "sort_priority": 43},
                ))

        elif treatment_line == 3:
            if penicillin_allergy:
                actions.append(Action(
                    code="TREAT_LINE_3_GI_REFERRAL_CONSIDER",
                    label="After allergy-regimen failures, consider GI referral.",
                    display={"role": "primary_decision", "show_as_standalone": True, "sort_priority": 44},
                ))
            else:
                actions.append(Action(
                    code="TREAT_LINE_3_PAL",
                    label="Third line: Levo-Amox (PAL) for 14 days.",
                    display={"role": "primary_decision", "show_as_standalone": True, "sort_priority": 44},
                ))

        elif treatment_line == 4:
            if penicillin_allergy:
                actions.append(Action(
                    code="TREAT_LINE_4_GI_REFERRAL",
                    label="Fourth-line management for penicillin-allergic patient should involve GI/allergy support.",
                    display={"role": "primary_decision", "show_as_standalone": True, "sort_priority": 45},
                ))
            else:
                actions.append(Action(
                    code="TREAT_LINE_4_PAR_OR_REFER",
                    label="Fourth line: Rif-Amox (PAR) or refer to GI.",
                    details={"supported_by": ["Rifabutin may rarely cause potentially serious myelotoxicity"]},
                    display={"role": "primary_decision", "show_as_standalone": True, "sort_priority": 45},
                ))
        else:
            stop = Stop(
                reason="Invalid treatment line. Use values 1-4.",
                actions=[
                    Action(
                        code="INVALID_TREATMENT_LINE",
                        label="Treatment line must be 1, 2, 3, or 4.",
                        display={"role": "support", "badge": "info", "show_as_standalone": True, "sort_priority": 46},
                    )
                ],
            )
            ctx.log(node_id, "INVALID_TREATMENT_LINE", {"treatment_line": treatment_line}, [stop])
            return NodeResult([stop])

        if ctx.get("bubble_pack_used") is False:
            actions.append(Action(
                code="BUBBLE_PACK_ADHERENCE_NOTE",
                label="Consider blister/bubble pack to improve adherence.",
                display={"role": "support", "badge": "info", "show_as_standalone": True, "sort_priority": 47},
            ))

        ctx.log(node_id, "TREATMENT_RECOMMENDED", {
            "treatment_line": treatment_line,
            "penicillin_allergy": penicillin_allergy,
        }, actions)
        return NodeResult(actions, next_node="Confirm_Eradication")

    nodes["Treatment"] = Node("Treatment", node_treatment)

    # -----------------------------------------------------
    # Node 5 – Confirm eradication
    # -----------------------------------------------------

    def node_confirm_eradication(ctx: Context):
        node_id = "Confirm_Eradication"

        actions: List[Output] = [
            Action(
                code="RETEST_FOR_ERADICATION",
                label="Retest with HpSAT or UBT at least 4 weeks after completing treatment.",
                display={"role": "support", "badge": "info", "show_as_standalone": True, "sort_priority": 50},
            )
        ]

        if ctx.get("off_antibiotics_4_weeks_before_retest") is False:
            actions.append(Action(
                code="RETEST_PREP_ANTIBIOTIC_WARNING",
                label="Retesting requires being off antibiotics for at least 4 weeks.",
                display={"role": "advisory", "badge": "warning", "show_as_standalone": True, "sort_priority": 51},
            ))

        if ctx.get("off_ppi_2_weeks_before_retest") is False:
            actions.append(Action(
                code="RETEST_PREP_PPI_WARNING",
                label="Retesting requires being off PPIs for at least 2 weeks.",
                display={"role": "advisory", "badge": "warning", "show_as_standalone": True, "sort_priority": 51},
            ))

        eradication_test_result = ctx.get("eradication_test_result")
        symptoms_persist = ctx.get("symptoms_persist")

        missing = []
        if eradication_test_result is None:
            missing.append("eradication_test_result")
        if symptoms_persist is None:
            missing.append("symptoms_persist")

        if missing:
            dr = DataRequest(
                blocking_node=node_id,
                missing_fields=missing,
                message="Need eradication test result and symptom status after treatment.",
                suggested_actions=[
                    Action(
                        code="CAPTURE_ERADICATION_STATUS",
                        label="Capture eradication test result and whether symptoms persist",
                        display={"role": "support", "badge": "info", "show_as_standalone": True, "sort_priority": 52},
                    )
                ],
            )
            ctx.log(node_id, "BLOCKED_MISSING_DATA", {"missing": missing}, actions + [dr])
            return NodeResult(actions + [dr])

        if eradication_test_result == "negative" and symptoms_persist is False:
            stop = Stop(
                reason="Eradication confirmed and symptoms do not persist. Pathway care complete.",
                actions=actions + [
                    Action(
                        code="PATHWAY_COMPLETE",
                        label="Pathway care complete.",
                        display={"role": "primary_decision", "show_as_standalone": True, "sort_priority": 53},
                    )
                ],
            )
            ctx.log(node_id, "ERADICATION_CONFIRMED_PATHWAY_COMPLETE", {
                "eradication_test_result": eradication_test_result,
                "symptoms_persist": symptoms_persist,
            }, [stop])
            return NodeResult([stop])

        if eradication_test_result == "negative" and symptoms_persist is True:
            actions.append(Action(
                code="POST_ERADICATION_SYMPTOMS_ROUTE_DYSPEPSIA",
                label="If symptoms persist after eradication, follow Dyspepsia pathway and/or reassess diagnosis.",
                display={"role": "primary_decision", "show_as_standalone": True, "sort_priority": 54},
            ))
            stop = Stop(
                reason="Eradication confirmed, but symptoms persist.",
                actions=actions,
            )
            ctx.log(node_id, "ERADICATION_CONFIRMED_SYMPTOMS_PERSIST", {
                "eradication_test_result": eradication_test_result,
                "symptoms_persist": symptoms_persist,
            }, [stop])
            return NodeResult([stop])

        ctx.log(node_id, "ERADICATION_FAILED", {
            "eradication_test_result": eradication_test_result,
            "symptoms_persist": symptoms_persist,
        }, actions)
        return NodeResult(actions, next_node="Treatment_Failure")

    nodes["Confirm_Eradication"] = Node("Confirm_Eradication", node_confirm_eradication)

    # -----------------------------------------------------
    # Node 6 – Treatment failure
    # -----------------------------------------------------

    def node_treatment_failure(ctx: Context):
        node_id = "Treatment_Failure"

        treatment_line = ctx.get("treatment_line")
        actions: List[Output] = []

        if bool(ctx.get("nonadherence_suspected")):
            actions.append(Action(
                code="EXPLORE_NONADHERENCE",
                label="Explore non-adherence or intolerance as contributors to treatment failure.",
                display={"role": "support", "badge": "info", "show_as_standalone": True, "sort_priority": 60},
            ))

        if treatment_line is None:
            dr = DataRequest(
                blocking_node=node_id,
                missing_fields=["treatment_line"],
                message="Need treatment line to determine next step after treatment failure.",
                suggested_actions=[
                    Action(
                        code="CAPTURE_TREATMENT_LINE",
                        label="Capture current treatment line",
                        display={"role": "support", "badge": "info", "show_as_standalone": True, "sort_priority": 60},
                    )
                ],
            )
            ctx.log(node_id, "BLOCKED_MISSING_DATA", {"missing": ["treatment_line"]}, actions + [dr])
            return NodeResult(actions + [dr])

        failed_three_rounds = treatment_line >= 3
        failed_three_rounds = ctx.apply_override(node_id, "failed_three_rounds", failed_three_rounds)
        ctx.set("failed_three_rounds", failed_three_rounds)

        if failed_three_rounds:
            stop = Stop(
                reason="H. pylori has not been eradicated after three treatment attempts.",
                actions=actions + [
                    Action(
                        code="REFER_AFTER_THREE_FAILURES",
                        label="Option to refer to GI after 3 failed treatment attempts.",
                        override_options={
                            "node": node_id,
                            "field": "failed_three_rounds",
                            "allowed": [True, False],
                            "reason_required": True,
                        },
                        display={"role": "primary_decision", "show_as_standalone": True, "sort_priority": 61},
                    )
                ],
            )
            ctx.log(node_id, "REFER_AFTER_THREE_FAILURES", {"treatment_line": treatment_line}, [stop])
            return NodeResult([stop])

        actions.append(Action(
            code="PROCEED_TO_NEXT_TREATMENT_LINE",
            label="Proceed to the next line of treatment; do not repeat the same regimen.",
            details={"supported_by": [f"Current treatment line: {treatment_line}"]},
            display={"role": "primary_decision", "show_as_standalone": True, "sort_priority": 62},
        ))
        ctx.log(node_id, "NEXT_TREATMENT_LINE", {"treatment_line": treatment_line}, actions)
        return NodeResult(actions)

    nodes["Treatment_Failure"] = Node("Treatment_Failure", node_treatment_failure)

    return PathwayEngine(
        nodes=nodes,
        start_node="Who_Should_Be_Tested"
    )


# =========================================================
# RUNNER
# =========================================================

def run_h_pylori_pathway(patient_data: Dict[str, Any], overrides=None):
    engine = h_pylori_build_engine()

    ctx = Context(
        data=dict(patient_data),
        overrides=overrides or []
    )

    outputs = engine.run(ctx)
    return outputs, ctx.logs, ctx.overrides
