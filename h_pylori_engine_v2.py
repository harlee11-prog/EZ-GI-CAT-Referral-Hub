from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timezone

try:
    from dyspepsia_engine import run_dyspepsia_pathway
    DYSPEPSIA_ENGINE_AVAILABLE = True
except Exception:
    DYSPEPSIA_ENGINE_AVAILABLE = False


# =========================================================
# MEDICATION REFERENCE TABLES
# =========================================================

REGIMEN_DETAILS = {
    "PAMC": {
        "name": "CLAMET Quad (PAMC)",
        "duration": "14 days",
        "approx_cost": "~$130 (generic)",
        "medications": [
            {"drug": "PPI (e.g. omeprazole/pantoprazole)", "dose": "Standard dose", "frequency": "BID"},
            {"drug": "Amoxicillin",                        "dose": "1000 mg (2 capsules)", "frequency": "BID"},
            {"drug": "Metronidazole",                      "dose": "500 mg (1 tablet)",    "frequency": "BID"},
            {"drug": "Clarithromycin",                     "dose": "500 mg (1 capsule)",   "frequency": "BID"},
        ],
        "notes": "Dispense in blister/bubble pack to improve adherence.",
    },
    "PBMT": {
        "name": "BMT Quad (PBMT)",
        "duration": "14 days",
        "approx_cost": "~$80 (generic)",
        "medications": [
            {"drug": "PPI (e.g. omeprazole/pantoprazole)",  "dose": "Standard dose",        "frequency": "BID"},
            {"drug": "Bismuth subsalicylate (Pepto-Bismol®)", "dose": "524 mg (2 caplets)", "frequency": "QID"},
            {"drug": "Metronidazole",                        "dose": "500 mg (1 tablet)",   "frequency": "QID"},
            {"drug": "Tetracycline",                         "dose": "500 mg (1 capsule)",  "frequency": "QID"},
        ],
        "notes": "Dispense in blister/bubble pack. Used as first-line for penicillin-allergic patients.",
    },
    "PAL": {
        "name": "Levo-Amox (PAL)",
        "duration": "14 days",
        "approx_cost": "~$100 (generic)",
        "medications": [
            {"drug": "PPI (e.g. omeprazole/pantoprazole)", "dose": "Standard dose",        "frequency": "BID"},
            {"drug": "Amoxicillin",                        "dose": "1000 mg (2 capsules)", "frequency": "BID"},
            {"drug": "Levofloxacin",                       "dose": "500 mg (1 tablet)",    "frequency": "Once daily"},
        ],
        "notes": "Dispense in blister/bubble pack.",
    },
    "PAR": {
        "name": "Rif-Amox (PAR)",
        "duration": "10 days",
        "approx_cost": "~$170 (generic)",
        "medications": [
            {"drug": "PPI (e.g. omeprazole/pantoprazole)", "dose": "Standard dose",        "frequency": "BID"},
            {"drug": "Amoxicillin",                        "dose": "1000 mg (2 capsules)", "frequency": "BID"},
            {"drug": "Rifabutin",                          "dose": "150 mg (1 tablet)",    "frequency": "BID"},
        ],
        "notes": (
            "SAFETY: Rifabutin has rarely been associated with serious myelotoxicity "
            "(low WBC/platelet count). Pros/cons must be assessed case-by-case. "
            "May require special authorization for Alberta Blue Cross. "
            "Dispense in blister/bubble pack."
        ),
    },
    "PCM": {
        "name": "Modified Triple (PCM)",
        "duration": "14 days",
        "approx_cost": "~$100 (generic)",
        "medications": [
            {"drug": "Pantoprazole",    "dose": "40 mg",             "frequency": "BID"},
            {"drug": "Clarithromycin",  "dose": "500 mg (1 capsule)", "frequency": "BID"},
            {"drug": "Metronidazole",   "dose": "500 mg (1 tablet)",  "frequency": "BID"},
        ],
        "notes": "Penicillin-allergic patients only. Consider referral for allergy testing.",
    },
}


# =========================================================
# OUTPUT TYPES
# =========================================================

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
        self.logs.append(DecisionLog(
            node=node, decision=decision, used_inputs=inputs,
            outputs=[{"type": type(o).__name__} for o in outputs],
        ))


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
# HELPER: clean Action factory
# =========================================================

def _action(
    code: str,
    label: str,
    *,
    urgency: Optional[str] = None,
    bullets: Optional[List[str]] = None,
    notes: Optional[List[str]] = None,
    regimen_key: Optional[str] = None,
    supported_by: Optional[List[str]] = None,
    override_options: Optional[Dict[str, Any]] = None,
    role: str = "support",
    sort_priority: int = 50,
    badge: str = "info",
) -> Action:
    """
    Structured action factory.
    - label   : short card title (shown as <h4>)
    - bullets : key clinical points shown as bullet list
    - notes   : advisory notes shown below bullets
    - regimen_key : triggers inline medication table
    - supported_by: evidence / source notes
    """
    details: Dict[str, Any] = {}
    if bullets:
        details["bullets"] = bullets
    if notes:
        details["notes"] = notes
    if regimen_key:
        details["regimen_key"] = regimen_key
    if supported_by:
        details["supported_by"] = supported_by

    return Action(
        code=code,
        label=label,
        urgency=urgency,
        details=details,
        override_options=override_options,
        display={"role": role, "badge": badge,
                 "show_as_standalone": True, "sort_priority": sort_priority},
    )


# =========================================================
# H. PYLORI PATHWAY NODES
# =========================================================

def h_pylori_build_engine() -> PathwayEngine:
    nodes: Dict[str, Node] = {}

    # ----------------------------------------------------------
    # Node 1 – Who Should Be Tested
    # ----------------------------------------------------------

    def node_entry(ctx: Context):
        node_id = "Who_Should_Be_Tested"

        dyspepsia      = bool(ctx.get("dyspepsia_symptoms"))
        ulcer_gi_bleed = bool(ctx.get("current_or_past_gastric_or_duodenal_ulcer_or_upper_gi_bleed"))
        fh_gastric     = bool(ctx.get("personal_or_first_degree_relative_history_gastric_cancer"))
        immigrant      = bool(ctx.get("first_generation_immigrant_high_prevalence_region"))
        indicated      = any([dyspepsia, ulcer_gi_bleed, fh_gastric, immigrant])
        indicated      = ctx.apply_override(node_id, "testing_indicated", indicated)
        ctx.set("testing_indicated", indicated)

        if not indicated:
            a = _action(
                "TESTING_NOT_INDICATED",
                "No Indication for H. pylori Testing Found",
                bullets=[
                    "Testing is indicated for:",
                    "• Patients with dyspepsia symptoms (epigastric pain/discomfort, bloating, early satiety, loss of appetite).",
                    "• Current or past gastric/duodenal ulcers or upper GI bleed.",
                    "• Personal or first-degree relative with history of gastric cancer (test once in adulthood).",
                    "• First-generation immigrants from high-prevalence areas (Asia, Africa, Central and South America).",
                    "NOTE: Many H. pylori infected patients are asymptomatic.",
                ],
                role="advisory", badge="warning", sort_priority=10,
                override_options={"node": node_id, "field": "testing_indicated",
                                  "allowed": [True, False], "reason_required": True},
            )
        else:
            active = []
            if dyspepsia:      active.append("Dyspepsia symptoms")
            if ulcer_gi_bleed: active.append("History of gastric/duodenal ulcer or upper GI bleed")
            if fh_gastric:     active.append("Personal or family history of gastric cancer")
            if immigrant:      active.append("First-generation immigrant from high-prevalence region")
            a = _action(
                "TESTING_INDICATED",
                "H. pylori Testing Indicated",
                bullets=["Testing indicated based on:"] + [f"• {i}" for i in active],
                role="support", badge="info", sort_priority=10,
                override_options={"node": node_id, "field": "testing_indicated",
                                  "allowed": [True, False], "reason_required": True},
            )

        ctx.log(node_id, "ENTRY_ASSESSED", {}, [a])
        return NodeResult([a], next_node="Alarm_Features")

    nodes["Who_Should_Be_Tested"] = Node("Who_Should_Be_Tested", node_entry)

    # ----------------------------------------------------------
    # Node 2 – Alarm Features
    # ----------------------------------------------------------

    def node_alarm(ctx: Context):
        node_id = "Alarm_Features"

        checks = {
            "Family history (1st-degree) of esophageal or gastric cancer":
                bool(ctx.get("family_history_esophageal_or_gastric_cancer_first_degree")),
            "Personal history of peptic ulcer disease":
                bool(ctx.get("personal_history_peptic_ulcer_disease")),
            "Age >60 with new and persistent symptoms (>3 months)":
                bool(ctx.get("age_over_60_new_persistent_symptoms_over_3_months")),
            "Unintended weight loss (>5% over 6–12 months)":
                bool(ctx.get("unintended_weight_loss")),
            "Progressive dysphagia":
                bool(ctx.get("progressive_dysphagia")),
            "Persistent vomiting (not associated with cannabis use)":
                bool(ctx.get("persistent_vomiting_not_cannabis_related")),
            "Black stool or blood in vomit":
                bool(ctx.get("black_stool_or_blood_in_vomit")),
            "Iron deficiency anemia":
                bool(ctx.get("iron_deficiency_anemia_present")),
            "Clinician concern — serious pathology":
                bool(ctx.get("clinician_concern_serious_pathology")),
        }
        gi_bleed = checks["Black stool or blood in vomit"]
        alarm_present = any(checks.values())
        alarm_present = ctx.apply_override(node_id, "alarm_features_present", alarm_present)
        ctx.set("alarm_features_present", alarm_present)

        if alarm_present:
            triggered = [f"• {k}" for k, v in checks.items() if v]
            bullets = (
                ["One or more alarm features identified:"]
                + triggered
                + ["Refer for consultation and/or endoscopy. Include ALL alarm features in the referral to ensure appropriate triage."]
            )
            if gi_bleed:
                bullets.append("⚠ URGENT LABS: Order CBC, INR, and BUN as part of the referral (indicated by black stool and/or blood in vomit).")

            referral = _action(
                "URGENT_ENDOSCOPY_REFERRAL",
                "Urgent Referral: Gastroenterology / Endoscopy",
                urgency="urgent",
                bullets=bullets,
                role="primary_decision", sort_priority=20,
                override_options={"node": node_id, "field": "alarm_features_present",
                                  "allowed": [True, False], "reason_required": True},
            )
            stop = Stop(
                reason="Alarm feature(s) present — urgent referral required.",
                urgency="urgent",
                actions=[referral],
            )
            ctx.log(node_id, "ALARM_FEATURES_PRESENT", {}, [stop])
            return NodeResult([stop])

        a = _action(
            "NO_ALARM_FEATURES",
            "No Alarm Features Identified",
            bullets=["Proceed to H. pylori testing and diagnosis."],
            role="support", badge="info", sort_priority=22,
        )
        ctx.log(node_id, "NO_ALARM_FEATURES", {}, [a])
        return NodeResult([a], next_node="Diagnosis")

    nodes["Alarm_Features"] = Node("Alarm_Features", node_alarm)

    # ----------------------------------------------------------
    # Node 3 – Diagnosis
    # ----------------------------------------------------------

    def node_diagnosis(ctx: Context):
        node_id = "Diagnosis"

        test_type   = ctx.get("hp_test_type")
        test_result = ctx.get("hp_test_result")

        missing = []
        if test_type is None:   missing.append("hp_test_type")
        if test_result is None: missing.append("hp_test_result")

        if missing:
            return NodeResult([DataRequest(
                blocking_node=node_id,
                missing_fields=missing,
                message="H. pylori Test Required",
                urgency_context=(
                    "Order HpSAT (primary in Edmonton, Calgary, South Zone) or UBT. Ensure patient washout: off antibiotics ≥4 weeks, off PPIs ≥2 weeks, off bismuth ≥2 weeks."
                ),
                suggested_actions=[_action(
                    "CAPTURE_HP_TEST", "Enter test type and result to proceed.",
                    role="support", badge="info", sort_priority=30,
                )],
            )])

        actions: List[Output] = []

        # Washout warnings
        prep_issues = []
        if ctx.get("off_antibiotics_4_weeks_before_test") is False:
            prep_issues.append("• Patient has NOT been off antibiotics ≥4 weeks — false negative risk.")
        if ctx.get("off_ppi_2_weeks_before_test") is False:
            prep_issues.append("• Patient has NOT been off PPIs ≥2 weeks — false negative risk.")
        if ctx.get("off_bismuth_2_weeks_before_test") is False:
            prep_issues.append("• Patient has NOT avoided bismuth preparations ≥2 weeks — false negative risk.")
        if test_type not in ["HpSAT", "UBT"]:
            prep_issues.append(f"• Test type '{test_type}' is non-standard. Preferred: HpSAT or UBT.")

        if prep_issues:
            actions.append(_action(
                "TEST_PREP_WARNING",
                "Test Preparation Warning",
                bullets=["Review the following before accepting the test result:"] + prep_issues,
                role="advisory", badge="warning", sort_priority=31,
            ))

        if test_result == "negative":
            neg_bullets = [
                f"H. pylori test ({test_type}) is NEGATIVE.",
                "False negatives may occur with recent antibiotic or PPI use.",
            ]
            if ctx.get("dyspepsia_symptoms"):
                neg_bullets.append("Patient has dyspepsia symptoms — follow the Dyspepsia Pathway for further management.")
            actions.append(_action(
                "HP_NEGATIVE", "H. pylori Test: Negative",
                bullets=neg_bullets,
                role="support", badge="info", sort_priority=32,
            ))

            # Dyspepsia engine chaining (unchanged logic)
            if DYSPEPSIA_ENGINE_AVAILABLE and isinstance(ctx.get("dyspepsia_patient_data"), dict):
                try:
                    dys_outputs, _, _ = run_dyspepsia_pathway(ctx.get("dyspepsia_patient_data"))
                    for o in dys_outputs:
                        if hasattr(o, "code") and hasattr(o, "label"):
                            actions.append(Action(
                                code=f"DYSP_{o.code}", label=f"Dyspepsia: {o.label}",
                                urgency=getattr(o, "urgency", None),
                                details=getattr(o, "details", {}),
                                display={"role": "support", "badge": "info",
                                         "show_as_standalone": True, "sort_priority": 33},
                            ))
                except Exception as e:
                    actions.append(_action(
                        "DYSPEPSIA_CHAIN_FAILED",
                        "Dyspepsia Engine Unavailable",
                        bullets=["Review Dyspepsia pathway separately.", f"Error: {e}"],
                        role="advisory", badge="warning", sort_priority=33,
                    ))

            stop = Stop(reason="H. pylori test negative — pathway ends here.", actions=actions)
            ctx.log(node_id, "HP_NEGATIVE", {"hp_test_type": test_type}, [stop])
            return NodeResult([stop])

        # Positive
        actions.append(_action(
            "HP_POSITIVE", "H. pylori Test: Positive",
            bullets=[
                f"H. pylori test ({test_type}) is POSITIVE.",
                "Proceed to treatment selection below.",
                "Standard triple therapy (PAC/PMC/PAM) is no longer recommended due to antibiotic resistance.",
            ],
            role="support", badge="info", sort_priority=34,
        ))
        ctx.log(node_id, "HP_POSITIVE", {"hp_test_type": test_type}, actions)
        return NodeResult(actions, next_node="Treatment")

    nodes["Diagnosis"] = Node("Diagnosis", node_diagnosis)

    # ----------------------------------------------------------
    # Node 4 – Treatment
    # ----------------------------------------------------------

    def node_treatment(ctx: Context):
        node_id = "Treatment"

        # Pregnancy / breastfeeding
        is_pregnant = bool(ctx.get("pregnant")) or bool(ctx.get("breastfeeding"))
        is_pregnant = ctx.apply_override(node_id, "pregnancy_contraindication", is_pregnant)

        if is_pregnant:
            stop = Stop(
                reason="Pregnancy / breastfeeding — H. pylori treatment contraindicated.",
                actions=[_action(
                    "DO_NOT_TREAT_PREGNANCY",
                    "Do Not Treat: Pregnancy or Breastfeeding",
                    bullets=[
                        "All H. pylori treatment regimens are contraindicated during pregnancy and breastfeeding.",
                        "Reassess and initiate treatment postpartum when safe to do so.",
                    ],
                    role="primary_decision", sort_priority=40,
                    override_options={
                        "node": node_id,
                        "field": "pregnancy_contraindication",
                        "allowed": [True, False],
                        "reason_required": True,
                    },
                )],
            )
            ctx.log(node_id, "PREGNANCY_STOP", {}, [stop])
            return NodeResult([stop])

        treatment_line = ctx.get("treatment_line")
        if treatment_line is None:
            return NodeResult([DataRequest(
                blocking_node=node_id,
                missing_fields=["treatment_line"],
                message="Select Treatment Line",
                urgency_context="Enter current treatment line (1–4) to select the appropriate regimen.",
                suggested_actions=[_action(
                    "CAPTURE_TREATMENT_LINE", "Enter treatment line (1, 2, 3, or 4) to proceed.",
                    role="support", badge="info", sort_priority=41,
                )],
            )])

        penicillin_allergy = bool(ctx.get("penicillin_allergy"))
        actions: List[Output] = []

        # General treatment note (always shown)
        actions.append(_action(
            "GENERAL_TREATMENT_NOTES",
            "General Treatment Notes",
            bullets=[
                "Treatment failure may be due to antibiotic resistance; however, explore non-adherence and intolerance with the patient.",
                "Do NOT retry the same treatment regimen after failure.",
            ],
            role="support", badge="info", sort_priority=41,
        ))

        if treatment_line == 1:
            if penicillin_allergy:
                actions.append(_action(
                    "TREAT_LINE_1_PBMT",
                    "First-Line Treatment (Penicillin Allergy): Bismuth Quadruple Regimen (PBMT)",
                    bullets=[
                        f"Regimen: Bismuth Quadruple Regimen (PBMT) for 14 days (approx. $80 with generics).",
                        "Components:",
                        "• PPI (standard dose) 1 pill BID",
                        "• Bismuth subsalicylate 524 mg QID",
                        "• Metronidazole 500 mg QID",
                        "• Tetracycline 500 mg QID",
                        "Note: First-line for penicillin-allergic patients. Recommend blister pack.",
                    ],
                    regimen_key="PBMT",
                    role="primary_decision", sort_priority=42,
                ))
            else:
                actions.append(_action(
                    "TREAT_LINE_1_PAMC",
                    "First-Line Treatment — Option A: CLAMET Quad (PAMC)",
                    bullets=[
                        "Regimen: CLAMET Quad (PAMC) for 14 days (approx. $130 with generics).",
                        "Components:",
                        "• PPI (standard dose) 1 pill BID",
                        "• Amoxicillin 1000 mg BID",
                        "• Metronidazole 500 mg BID",
                        "• Clarithromycin 500 mg BID",
                        "Recommend dispensing in blister/bubble pack.",
                    ],
                    regimen_key="PAMC",
                    role="primary_decision", sort_priority=42,
                ))
                actions.append(_action(
                    "TREAT_LINE_1_PBMT",
                    "First-Line Treatment — Option B: BMT Quad (PBMT)",
                    bullets=[
                        "Regimen: BMT Quad (PBMT) for 14 days (approx. $80 with generics).",
                        "Components:",
                        "• PPI (standard dose) 1 pill BID",
                        "• Bismuth subsalicylate 524 mg QID",
                        "• Metronidazole 500 mg QID",
                        "• Tetracycline 500 mg QID",
                        "Recommend dispensing in blister/bubble pack.",
                    ],
                    regimen_key="PBMT",
                    role="primary_decision", sort_priority=43,
                ))

        elif treatment_line == 2:
            if penicillin_allergy:
                actions.append(_action(
                    "TREAT_LINE_2_PCM",
                    "Second-Line Treatment (Penicillin Allergy): Modified Triple (PCM)",
                    bullets=[
                        "Regimen: Modified Triple (PCM) for 14 days (approx. $100 with generics).",
                        "Components:",
                        "• Pantoprazole 40 mg BID",
                        "• Clarithromycin 500 mg BID",
                        "• Metronidazole 500 mg BID",
                        "Consider referral for formal allergy testing before proceeding.",
                    ],
                    regimen_key="PCM",
                    role="primary_decision", sort_priority=43,
                ))
            else:
                actions.append(_action(
                    "TREAT_LINE_2_SWITCH",
                    "Second-Line Treatment: Switch Regimen",
                    bullets=[
                        "Use the regimen NOT used in the first line:",
                        "• If CLAMET Quad (PAMC) was used → switch to BMT Quad (PBMT).",
                        "• If BMT Quad (PBMT) was used → switch to CLAMET Quad (PAMC), or consider Levo-Amox (PAL).",
                        "Do NOT repeat the same regimen that failed.",
                    ],
                    role="primary_decision", sort_priority=43,
                ))

        elif treatment_line == 3:
            if penicillin_allergy:
                actions.append(_action(
                    "TREAT_LINE_3_GI_REFERRAL",
                    "Third-Line (Penicillin Allergy): Consider GI Referral",
                    bullets=[
                        "After two failed allergy-appropriate regimens, consider referral to Gastroenterology.",
                        "Outline all testing and treatments provided to date in the referral.",
                    ],
                    role="primary_decision", sort_priority=44,
                ))
            else:
                actions.append(_action(
                    "TREAT_LINE_3_PAL",
                    "Third-Line Treatment: Levo-Amox (PAL)",
                    bullets=[
                        "Regimen: Levo-Amox (PAL) for 14 days (approx. $100 with generics).",
                        "Components:",
                        "• PPI (standard dose) 1 pill BID",
                        "• Amoxicillin 1000 mg BID",
                        "• Levofloxacin 500 mg once daily",
                        "Recommend dispensing in blister/bubble pack.",
                    ],
                    regimen_key="PAL",
                    role="primary_decision", sort_priority=44,
                ))

        elif treatment_line == 4:
            if penicillin_allergy:
                actions.append(_action(
                    "TREAT_LINE_4_GI_REFERRAL",
                    "Fourth-Line (Penicillin Allergy): GI / Allergy Referral",
                    bullets=[
                        "Refer to Gastroenterology and/or Allergy for specialist management.",
                        "Outline all testing and treatment history in the referral.",
                        "Options: eReferral Advice Request | Specialist LINK (Calgary) | ConnectMD (Edmonton/North).",
                    ],
                    role="primary_decision", sort_priority=45,
                ))
            else:
                actions.append(_action(
                    "TREAT_LINE_4_PAR",
                    "Fourth-Line Treatment: Rif-Amox (PAR) or Refer to GI",
                    bullets=[
                        "Regimen: Rif-Amox (PAR) for 10 days (approx. $170 with generics).",
                        "Components:",
                        "• PPI (standard dose) 1 pill BID",
                        "• Amoxicillin 1000 mg BID",
                        "• Rifabutin 150 mg BID",
                        "⚠ SAFETY: Rifabutin rarely associated with serious myelotoxicity (low WBC/platelet). Assess case-by-case.",
                        "⚠ May require special authorization for Alberta Blue Cross patients.",
                        "Alternative: Consult GI via Specialist LINK / ConnectMD / eReferral Advice Request, or refer directly.",
                    ],
                    regimen_key="PAR",
                    supported_by=["Rifabutin myelotoxicity risk — pros/cons must be assessed individually."],
                    role="primary_decision", sort_priority=45,
                ))
        else:
            stop = Stop(
                reason="Invalid treatment line.",
                actions=[_action(
                    "INVALID_TREATMENT_LINE", "Treatment Line Must Be 1, 2, 3, or 4.",
                    bullets=["Please re-enter a valid treatment line value (1–4)."],
                    role="support", sort_priority=46,
                )],
            )
            ctx.log(node_id, "INVALID_TREATMENT_LINE", {"treatment_line": treatment_line}, [stop])
            return NodeResult([stop])

        if ctx.get("bubble_pack_used") is False:
            actions.append(_action(
                "BUBBLE_PACK_REMINDER",
                "Adherence Reminder: Blister Pack Not in Use",
                bullets=[
                    "All H. pylori treatment regimens should be dispensed in a blister/bubble pack.",
                    "Ask the pharmacist to package the prescription in a bubble pack to improve adherence.",
                ],
                role="advisory", badge="warning", sort_priority=47,
            ))

        ctx.log(node_id, "TREATMENT_RECOMMENDED",
                {"treatment_line": treatment_line, "penicillin_allergy": penicillin_allergy}, actions)
        return NodeResult(actions, next_node="Confirm_Eradication")

    nodes["Treatment"] = Node("Treatment", node_treatment)

    # ----------------------------------------------------------
    # Node 5 – Confirm Eradication
    # ----------------------------------------------------------

    def node_confirm_eradication(ctx: Context):
        node_id = "Confirm_Eradication"

        retest = _action(
            "RETEST_FOR_ERADICATION",
            "Mandatory Eradication Confirmation",
            bullets=[
                "Retest with HpSAT or UBT NO SOONER than 4 weeks after completing treatment. Retesting too soon risks a false negative.",
                "⚠ Washout before eradication test:",
                "• Off ALL antibiotics (including H. pylori treatment) ≥4 weeks.",
                "• Off PPIs ≥2 weeks.",
                "Once eradicated, re-infection rate is <2%.",
                "If symptoms persist after confirmed eradication, refer to the Dyspepsia Pathway.",
                "If test remains POSITIVE → proceed to next treatment line.",
            ],
            role="support", badge="info", sort_priority=50,
        )

        prep_warnings = []
        if ctx.get("off_antibiotics_4_weeks_before_retest") is False:
            prep_warnings.append("Patient NOT off antibiotics ≥4 weeks — retesting now risks a false negative result.")
        if ctx.get("off_ppi_2_weeks_before_retest") is False:
            prep_warnings.append("Patient NOT off PPIs ≥2 weeks — retesting now risks a false negative result.")

        actions: List[Output] = [retest]

        if prep_warnings:
            actions.append(_action(
                "RETEST_PREP_WARNING",
                "Eradication Retest — Washout Not Complete",
                bullets=["Address the following before retesting:"] + [f"• {w}" for w in prep_warnings],
                role="advisory", badge="warning", sort_priority=51,
            ))

        eradication_result = ctx.get("eradication_test_result")
        symptoms_persist   = ctx.get("symptoms_persist")

        missing = []
        if eradication_result is None: missing.append("eradication_test_result")
        if symptoms_persist is None:   missing.append("symptoms_persist")

        if missing:
            dr = DataRequest(
                blocking_node=node_id,
                missing_fields=missing,
                message="Enter Eradication Test Result",
                urgency_context="Enter eradication test result (positive/negative) and whether symptoms persist (Yes/No).",
                suggested_actions=[_action(
                    "CAPTURE_ERADICATION_STATUS",
                    "Enter eradication test result and current symptom status.",
                    role="support", badge="info", sort_priority=52,
                )],
            )
            ctx.log(node_id, "BLOCKED_MISSING_DATA", {"missing": missing}, actions + [dr])
            return NodeResult(actions + [dr])

        if eradication_result == "negative" and not symptoms_persist:
            stop = Stop(
                reason="Eradication confirmed. Symptoms resolved. Pathway care complete.",
                actions=actions + [_action(
                    "PATHWAY_COMPLETE",
                    "Pathway Care Complete",
                    bullets=[
                        "H. pylori has been successfully eradicated.",
                        "Symptoms have resolved — no further action required.",
                        "Re-infection rate is <2%. No routine follow-up testing needed.",
                    ],
                    role="primary_decision", sort_priority=53,
                )],
            )
            ctx.log(node_id, "ERADICATION_CONFIRMED_COMPLETE", {}, [stop])
            return NodeResult([stop])

        if eradication_result == "negative" and symptoms_persist:
            stop = Stop(
                reason="Eradication confirmed, but symptoms persist.",
                actions=actions + [_action(
                    "POST_ERADICATION_SYMPTOMS",
                    "Eradication Confirmed — Symptoms Persist",
                    bullets=[
                        "H. pylori has been eradicated, but symptoms continue.",
                        "Follow the Dyspepsia Pathway for further management.",
                        "Reassess diagnosis — consider other causes of symptoms.",
                    ],
                    role="primary_decision", sort_priority=54,
                )],
            )
            ctx.log(node_id, "ERADICATION_CONFIRMED_SYMPTOMS_PERSIST", {}, [stop])
            return NodeResult([stop])

        ctx.log(node_id, "ERADICATION_FAILED",
                {"eradication_test_result": eradication_result, "symptoms_persist": symptoms_persist}, actions)
        return NodeResult(actions, next_node="Treatment_Failure")

    nodes["Confirm_Eradication"] = Node("Confirm_Eradication", node_confirm_eradication)

    # ----------------------------------------------------------
    # Node 6 – Treatment Failure
    # ----------------------------------------------------------

    def node_treatment_failure(ctx: Context):
        node_id = "Treatment_Failure"

        treatment_line = ctx.get("treatment_line")
        actions: List[Output] = []

        if bool(ctx.get("nonadherence_suspected")):
            actions.append(_action(
                "EXPLORE_NONADHERENCE",
                "Explore Non-Adherence Before Escalating",
                bullets=[
                    "Treatment failure may be due to antibiotic resistance, but also explore:",
                    "• Non-adherence — was the full course completed?",
                    "• Intolerance — did the patient experience side effects that led to stopping?",
                    "Consider dispensing next regimen in blister pack if not already done.",
                ],
                role="advisory", badge="warning", sort_priority=60,
            ))

        if treatment_line is None:
            return NodeResult(actions + [DataRequest(
                blocking_node=node_id,
                missing_fields=["treatment_line"],
                message="Enter Failed Treatment Line",
                urgency_context="Enter the treatment line that just failed (1, 2, or 3) to determine next steps.",
                suggested_actions=[_action(
                    "CAPTURE_TREATMENT_LINE", "Enter failed treatment line (1–3).",
                    role="support", badge="info", sort_priority=60,
                )],
            )])

        failed_three = treatment_line >= 3
        failed_three = ctx.apply_override(node_id, "failed_three_rounds", failed_three)
        ctx.set("failed_three_rounds", failed_three)

        if failed_three:
            stop = Stop(
                reason="H. pylori not eradicated after 3 or more treatment attempts.",
                actions=actions + [_action(
                    "REFER_AFTER_THREE_FAILURES",
                    "Refer to Gastroenterology After 3 Failed Attempts",
                    bullets=[
                        "H. pylori has not been eradicated after three rounds of treatment.",
                        "Refer to GI or seek specialist advice before proceeding.",
                        "Include full testing and treatment history in the referral.",
                        "Options: eReferral Advice Request | Specialist LINK (Calgary: 403-910-2551) | ConnectMD (Edmonton/North: 1-844-633-2263).",
                    ],
                    override_options={"node": node_id, "field": "failed_three_rounds",
                                      "allowed": [True, False], "reason_required": True},
                    role="primary_decision", sort_priority=61,
                )],
            )
            ctx.log(node_id, "REFER_AFTER_THREE_FAILURES", {"treatment_line": treatment_line}, [stop])
            return NodeResult([stop])

        next_line = treatment_line + 1
        actions.append(_action(
            "NEXT_TREATMENT_LINE",
            f"Proceed to Line {next_line} Treatment",
            bullets=[
                f"Current treatment line {treatment_line} has failed.",
                f"Proceed to Line {next_line} — do NOT repeat the same regimen.",
                "Return to the Treatment step and select the next line.",
            ],
            supported_by=[f"Failed treatment line: {treatment_line}"],
            role="primary_decision", sort_priority=62,
        ))
        ctx.log(node_id, "NEXT_TREATMENT_LINE", {"treatment_line": treatment_line}, actions)
        return NodeResult(actions)

    nodes["Treatment_Failure"] = Node("Treatment_Failure", node_treatment_failure)

    return PathwayEngine(nodes=nodes, start_node="Who_Should_Be_Tested")


# =========================================================
# RUNNER
# =========================================================

def run_h_pylori_pathway(patient_data: Dict[str, Any], overrides=None):
    engine = h_pylori_build_engine()
    ctx = Context(data=dict(patient_data), overrides=overrides or [])
    outputs = engine.run(ctx)
    return outputs, ctx.logs, ctx.overrides
