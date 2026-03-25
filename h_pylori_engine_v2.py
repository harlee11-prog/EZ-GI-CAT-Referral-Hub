from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timezone

try:
    from dyspepsia_engine import run_dyspepsia_pathway
    DYSPEPSIA_ENGINE_AVAILABLE = True
except Exception:
    DYSPEPSIA_ENGINE_AVAILABLE = False


# =========================================================
# MEDICATION REFERENCE TABLES (from AHS pathway PDF)
# =========================================================

REGIMEN_DETAILS = {
    "PAMC": {
        "name": "CLAMET Quad (PAMC)",
        "duration": "14 days",
        "approx_cost": "~$130 (generic)",
        "medications": [
            {"drug": "PPI (e.g. omeprazole/pantoprazole)", "dose": "Standard dose", "frequency": "BID"},
            {"drug": "Amoxicillin",                         "dose": "1000 mg (2 capsules)", "frequency": "BID"},
            {"drug": "Metronidazole",                       "dose": "500 mg (1 tablet)",   "frequency": "BID"},
            {"drug": "Clarithromycin",                      "dose": "500 mg (1 capsule)",  "frequency": "BID"},
        ],
        "notes": "Blister/bubble pack recommended for adherence.",
    },
    "PBMT": {
        "name": "BMT Quad (PBMT)",
        "duration": "14 days",
        "approx_cost": "~$80 (generic)",
        "medications": [
            {"drug": "PPI (e.g. omeprazole/pantoprazole)",         "dose": "Standard dose",          "frequency": "BID"},
            {"drug": "Bismuth subsalicylate (Pepto-Bismol®)", "dose": "524 mg (2 caplets)", "frequency": "QID"},
            {"drug": "Metronidazole",                              "dose": "500 mg (1 tablet)",  "frequency": "QID"},
            {"drug": "Tetracycline",                               "dose": "500 mg (1 capsule)", "frequency": "QID"},
        ],
        "notes": "Blister/bubble pack recommended. Also used as first-line for penicillin-allergic patients.",
    },
    "PAL": {
        "name": "Levo-Amox (PAL)",
        "duration": "14 days",
        "approx_cost": "~$100 (generic)",
        "medications": [
            {"drug": "PPI (e.g. omeprazole/pantoprazole)", "dose": "Standard dose",          "frequency": "BID"},
            {"drug": "Amoxicillin",                         "dose": "1000 mg (2 capsules)", "frequency": "BID"},
            {"drug": "Levofloxacin",                        "dose": "500 mg (1 tablet)",    "frequency": "Once daily"},
        ],
        "notes": "Blister/bubble pack recommended.",
    },
    "PAR": {
        "name": "Rif-Amox (PAR)",
        "duration": "10 days",
        "approx_cost": "~$170 (generic)",
        "medications": [
            {"drug": "PPI (e.g. omeprazole/pantoprazole)", "dose": "Standard dose",          "frequency": "BID"},
            {"drug": "Amoxicillin",                         "dose": "1000 mg (2 capsules)", "frequency": "BID"},
            {"drug": "Rifabutin",                           "dose": "150 mg (1 tablet)",    "frequency": "BID"},
        ],
        "notes": (
            "⚠️  SAFETY: Rifabutin has rarely been associated with potentially serious myelotoxicity "
            "(low WBC or platelet count). Pros/cons must be assessed case-by-case. "
            "May require special authorization for Alberta Blue Cross patients. "
            "Blister/bubble pack recommended."
        ),
    },
    "PCM": {
        "name": "Modified Triple (PCM) — Penicillin-Allergic",
        "duration": "14 days",
        "approx_cost": "~$100 (generic)",
        "medications": [
            {"drug": "Pantoprazole",    "dose": "40 mg",            "frequency": "BID"},
            {"drug": "Clarithromycin", "dose": "500 mg (1 capsule)", "frequency": "BID"},
            {"drug": "Metronidazole",  "dose": "500 mg (1 tablet)",  "frequency": "BID"},
        ],
        "notes": "Second-line for penicillin-allergic patients only. Consider referral for allergy testing.",
    },
}


def _format_regimen(key: str) -> str:
    """Returns a nurse-friendly multiline summary of a regimen."""
    r = REGIMEN_DETAILS[key]
    lines = [
        f"📋 Regimen: {r['name']}",
        f"⏱  Duration: {r['duration']}   |   💊 Approx. cost: {r['approx_cost']}",
        "Medications:",
    ]
    for m in r["medications"]:
        lines.append(f"  • {m['drug']} — {m['dose']} — {m['frequency']}")
    if r.get("notes"):
        lines.append(f"📝 Note: {r['notes']}")
    return "\n".join(lines)


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
# OUTPUT FORMATTER  (nurse-facing display)
# =========================================================

_URGENCY_BADGE = {
    "urgent": "🔴 URGENT",
    "semi-urgent": "🟡 SEMI-URGENT",
    None: "",
}

_ROLE_ICON = {
    "primary_decision": "➡️ ",
    "advisory": "⚠️  ",
    "support": "ℹ️  ",
}


def format_outputs_for_nurse(outputs: List[Output]) -> str:
    """
    Renders pathway outputs as a readable, structured clinical summary
    suitable for display on a nurse-facing UI or printed handout.
    """
    sections: List[str] = []
    sections.append("=" * 60)
    sections.append("  H. PYLORI PATHWAY — CLINICAL DECISION SUMMARY")
    sections.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    sections.append("=" * 60)

    for o in outputs:

        # ---- Stop ----
        if isinstance(o, Stop):
            badge = _URGENCY_BADGE.get(o.urgency, "")
            sections.append("")
            if badge:
                sections.append(f"┌─ {badge} ──────────────────────────────────────")
            else:
                sections.append("┌─ PATHWAY STOP ──────────────────────────────────────")
            sections.append(f"│  {o.reason}")
            sections.append("└─────────────────────────────────────────────────────────")
            for a in o.actions:
                sections.append(_render_action(a))

        # ---- DataRequest ----
        elif isinstance(o, DataRequest):
            sections.append("")
            sections.append("┌─ 📥 DATA NEEDED ──────────────────────────────────────")
            sections.append(f"│  Node     : {o.blocking_node}")
            sections.append(f"│  Missing  : {', '.join(o.missing_fields)}")
            sections.append(f"│  Message  : {o.message}")
            if o.urgency_context:
                sections.append(f"│  Context  : {o.urgency_context}")
            sections.append("└─────────────────────────────────────────────────────────")
            for a in o.suggested_actions:
                sections.append(_render_action(a))

        # ---- Action ----
        elif isinstance(o, Action):
            sections.append(_render_action(o))

    sections.append("")
    sections.append("=" * 60)
    sections.append("  END OF PATHWAY OUTPUT")
    sections.append("=" * 60)
    return "\n".join(sections)


def _render_action(a: Action) -> str:
    role = a.display.get("role", "support")
    icon = _ROLE_ICON.get(role, "   ")
    badge = _URGENCY_BADGE.get(a.urgency, "")
    header = f"{icon}[{a.code}]"
    if badge:
        header += f"  {badge}"

    lines = ["", header, f"   {a.label}"]

    # Inline medication table when details contain a regimen_key
    if "regimen_key" in a.details:
        lines.append("")
        for med_line in _format_regimen(a.details["regimen_key"]).split("\n"):
            lines.append(f"   {med_line}")

    # Generic extra details (non-regimen)
    if a.details and "regimen_key" not in a.details:
        for k, v in a.details.items():
            if k not in ("supported_by",):
                lines.append(f"   • {k}: {v}")
        if "supported_by" in a.details:
            for note in a.details["supported_by"]:
                lines.append(f"   📌 {note}")

    if a.override_options:
        lines.append(f"   🔒 Override allowed — reason required")

    return "\n".join(lines)


# =========================================================
# H. PYLORI PATHWAY IMPLEMENTATION
# =========================================================

def h_pylori_build_engine() -> PathwayEngine:
    nodes: Dict[str, Node] = {}

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _entry_indication(ctx: Context) -> Dict[str, Any]:
        dyspepsia                       = bool(ctx.get("dyspepsia_symptoms"))
        ulcer_or_upper_gi_bleed         = bool(ctx.get("current_or_past_gastric_or_duodenal_ulcer_or_upper_gi_bleed"))
        fh_gastric_cancer               = bool(ctx.get("personal_or_first_degree_relative_history_gastric_cancer"))
        first_gen_immigrant             = bool(ctx.get("first_generation_immigrant_high_prevalence_region"))

        indicated = any([dyspepsia, ulcer_or_upper_gi_bleed, fh_gastric_cancer, first_gen_immigrant])
        return {
            "indicated": indicated,
            "dyspepsia_symptoms": dyspepsia,
            "current_or_past_gastric_or_duodenal_ulcer_or_upper_gi_bleed": ulcer_or_upper_gi_bleed,
            "personal_or_first_degree_relative_history_gastric_cancer": fh_gastric_cancer,
            "first_generation_immigrant_high_prevalence_region": first_gen_immigrant,
        }

    # ------------------------------------------------------------------
    # Node 1 – Who should be tested
    # ------------------------------------------------------------------

    def node_entry(ctx: Context):
        node_id = "Who_Should_Be_Tested"
        info = _entry_indication(ctx)
        indicated = ctx.apply_override(node_id, "testing_indicated", info["indicated"])
        ctx.set("testing_indicated", indicated)

        if not indicated:
            actions = [Action(
                code="TESTING_NOT_INDICATED_WARNING",
                label=(
                    "H. pylori testing is not clearly indicated based on pathway entry criteria.\n"
                    "   Indications: dyspepsia; current/past gastric or duodenal ulcer or upper GI bleed;\n"
                    "   personal or 1st-degree relative history of gastric cancer;\n"
                    "   first-generation immigrant from Asia, Africa, Central/South America."
                ),
                details=info,
                override_options={"node": node_id, "field": "testing_indicated",
                                  "allowed": [True, False], "reason_required": True},
                display={"role": "advisory", "badge": "warning",
                         "show_as_standalone": True, "sort_priority": 10},
            )]
        else:
            actions = [Action(
                code="TESTING_INDICATED",
                label="H. pylori testing is indicated.",
                details=info,
                override_options={"node": node_id, "field": "testing_indicated",
                                  "allowed": [True, False], "reason_required": True},
                display={"role": "support", "badge": "info",
                         "show_as_standalone": True, "sort_priority": 10},
            )]

        ctx.log(node_id, "ENTRY_ASSESSED", info, actions)
        return NodeResult(actions, next_node="Alarm_Features")

    nodes["Who_Should_Be_Tested"] = Node("Who_Should_Be_Tested", node_entry)

    # ------------------------------------------------------------------
    # Node 2 – Alarm features
    # ------------------------------------------------------------------

    def node_alarm(ctx: Context):
        node_id = "Alarm_Features"

        fh_esophageal_or_gastric_cancer     = bool(ctx.get("family_history_esophageal_or_gastric_cancer_first_degree"))
        personal_history_peptic_ulcer       = bool(ctx.get("personal_history_peptic_ulcer_disease"))
        age_over_60_new_persistent          = bool(ctx.get("age_over_60_new_persistent_symptoms_over_3_months"))
        unintended_weight_loss              = bool(ctx.get("unintended_weight_loss"))          # >5% over 6-12 months
        progressive_dysphagia               = bool(ctx.get("progressive_dysphagia"))
        persistent_vomiting                 = bool(ctx.get("persistent_vomiting_not_cannabis_related"))
        black_stool_or_blood_in_vomit       = bool(ctx.get("black_stool_or_blood_in_vomit"))
        iron_deficiency_anemia              = bool(ctx.get("iron_deficiency_anemia_present"))
        clinician_concern                   = bool(ctx.get("clinician_concern_serious_pathology"))

        alarm_present = any([
            fh_esophageal_or_gastric_cancer, personal_history_peptic_ulcer,
            age_over_60_new_persistent, unintended_weight_loss, progressive_dysphagia,
            persistent_vomiting, black_stool_or_blood_in_vomit,
            iron_deficiency_anemia, clinician_concern,
        ])
        alarm_present = ctx.apply_override(node_id, "alarm_features_present", alarm_present)
        ctx.set("alarm_features_present", alarm_present)

        if alarm_present:
            triggered = []
            if fh_esophageal_or_gastric_cancer:
                triggered.append("Family history (1st-degree) esophageal/gastric cancer — note: may still test/treat H. pylori while awaiting endoscopy")
            if personal_history_peptic_ulcer:
                triggered.append("Personal history of peptic ulcer disease")
            if age_over_60_new_persistent:
                triggered.append("Age >60 with new persistent symptoms (>3 months)")
            if unintended_weight_loss:
                triggered.append("Unintended weight loss (>5% over 6–12 months)")
            if progressive_dysphagia:
                triggered.append("Progressive dysphagia")
            if persistent_vomiting:
                triggered.append("Persistent vomiting (not cannabis-related)")
            if black_stool_or_blood_in_vomit:
                triggered.append("Black stool or blood in vomit")
            if iron_deficiency_anemia:
                triggered.append("Iron deficiency anemia")
            if clinician_concern:
                triggered.append('Clinician concern re: serious pathology (gut feeling)')

            actions = [Action(
                code="URGENT_ENDOSCOPY_REFERRAL",
                label=(
                    "Refer urgently for specialist consultation / endoscopy.\n"
                    "   Include ALL identified alarm features in the referral for appropriate triage."
                ),
                urgency="urgent",
                details={"alarm_features_triggered": triggered},
                override_options={"node": node_id, "field": "alarm_features_present",
                                  "allowed": [True, False], "reason_required": True},
                display={"role": "primary_decision", "show_as_standalone": True, "sort_priority": 20},
            )]

            if black_stool_or_blood_in_vomit:
                actions.append(Action(
                    code="BLEEDING_REFERRAL_LABS",
                    label=(
                        "Black stool / blood in vomit present → ORDER: CBC, INR, and BUN as part of referral.\n"
                        "   If patient is actively bleeding, consider calling GI on call and/or ED."
                    ),
                    display={"role": "advisory", "badge": "warning",
                             "show_as_standalone": True, "sort_priority": 21},
                ))

            stop = Stop(
                reason="⛔ Alarm feature(s) present — urgent referral required.",
                urgency="urgent",
                actions=actions,
            )
            ctx.log(node_id, "ALARM_FEATURES_PRESENT", {"triggered": triggered}, [stop])
            return NodeResult([stop])

        out = [Action(
            code="NO_ALARM_FEATURES",
            label="No alarm features identified. Proceeding to diagnosis.",
            display={"role": "support", "badge": "info",
                     "show_as_standalone": True, "sort_priority": 22},
        )]
        ctx.log(node_id, "NO_ALARM_FEATURES", {}, out)
        return NodeResult(out, next_node="Diagnosis")

    nodes["Alarm_Features"] = Node("Alarm_Features", node_alarm)

    # ------------------------------------------------------------------
    # Node 3 – Diagnosis
    # ------------------------------------------------------------------

    def node_diagnosis(ctx: Context):
        node_id = "Diagnosis"

        test_type   = ctx.get("hp_test_type")
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
                message=(
                    "Enter H. pylori test type (HpSAT or UBT) and result (positive/negative).\n"
                    "   HpSAT is primary test in Edmonton, Calgary, and South Zones."
                ),
                suggested_actions=[Action(
                    code="CAPTURE_HP_TEST",
                    label="Capture HpSAT or UBT result",
                    display={"role": "support", "badge": "info",
                             "show_as_standalone": True, "sort_priority": 30},
                )],
            )
            ctx.log(node_id, "BLOCKED_MISSING_DATA", {"missing": missing}, [dr])
            return NodeResult([dr])

        actions: List[Output] = []

        # Test-type advisory
        if test_type not in ["HpSAT", "UBT"]:
            actions.append(Action(
                code="HP_TEST_TYPE_WARNING",
                label=(
                    f"Test type '{test_type}' is not a preferred H. pylori test.\n"
                    "   Preferred tests: HpSAT (primary in Edmonton/Calgary/South Zone) or UBT."
                ),
                details={"hp_test_type": test_type},
                display={"role": "advisory", "badge": "warning",
                         "show_as_standalone": True, "sort_priority": 31},
            ))

        # Pre-test prep warnings
        if ctx.get("off_antibiotics_4_weeks_before_test") is False:
            actions.append(Action(
                code="TEST_PREP_ANTIBIOTIC_WARNING",
                label="⚠️  Patient must be OFF antibiotics ≥4 weeks before testing to avoid false negatives.",
                display={"role": "advisory", "badge": "warning",
                         "show_as_standalone": True, "sort_priority": 31},
            ))

        if ctx.get("off_ppi_2_weeks_before_test") is False:
            actions.append(Action(
                code="TEST_PREP_PPI_WARNING",
                label="⚠️  Patient must be OFF PPIs ≥2 weeks before testing to avoid false negatives.",
                display={"role": "advisory", "badge": "warning",
                         "show_as_standalone": True, "sort_priority": 31},
            ))

        if ctx.get("off_bismuth_2_weeks_before_test") is False:
            actions.append(Action(
                code="TEST_PREP_BISMUTH_WARNING",
                label="⚠️  Patient must avoid bismuth preparations (e.g. Pepto-Bismol®) ≥2 weeks before testing.",
                display={"role": "advisory", "badge": "warning",
                         "show_as_standalone": True, "sort_priority": 31},
            ))

        # ---- NEGATIVE result ----
        if test_result == "negative":
            actions.append(Action(
                code="HP_NEGATIVE",
                label="H. pylori test is NEGATIVE.",
                display={"role": "support", "badge": "info",
                         "show_as_standalone": True, "sort_priority": 32},
            ))

            # Dyspepsia chaining
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
                        elif hasattr(o, "reason") and hasattr(o, "actions"):
                            actions.append(Action(
                                code="DYSP_STOP", label=f"Dyspepsia stop: {o.reason}",
                                urgency=getattr(o, "urgency", None),
                                display={"role": "support", "badge": "info",
                                         "show_as_standalone": True, "sort_priority": 33},
                            ))
                            for a in getattr(o, "actions", []):
                                if hasattr(a, "code") and hasattr(a, "label"):
                                    actions.append(Action(
                                        code=f"DYSP_{a.code}", label=f"Dyspepsia: {a.label}",
                                        urgency=getattr(a, "urgency", None),
                                        details=getattr(a, "details", {}),
                                        display={"role": "support", "badge": "info",
                                                 "show_as_standalone": True, "sort_priority": 33},
                                    ))
                        elif hasattr(o, "blocking_node") and hasattr(o, "missing_fields"):
                            actions.append(Action(
                                code="DYSP_DATA_REQUEST",
                                label=f"Dyspepsia pathway needs more data at node: {o.blocking_node}",
                                details={"blocking_node": o.blocking_node,
                                         "missing_fields": o.missing_fields},
                                display={"role": "advisory", "badge": "warning",
                                         "show_as_standalone": True, "sort_priority": 33},
                            ))
                except Exception as e:
                    actions.append(Action(
                        code="DYSPEPSIA_CHAIN_FAILED",
                        label="Dyspepsia engine chaining failed — review Dyspepsia pathway separately.",
                        details={"error": str(e)},
                        display={"role": "advisory", "badge": "warning",
                                 "show_as_standalone": True, "sort_priority": 33},
                    ))
                else:
                    actions.append(Action(
                        code="ROUTE_DYSPEPSIA_PATHWAY",
                        label="Follow Dyspepsia pathway.",
                        display={"role": "primary_decision",
                                 "show_as_standalone": True, "sort_priority": 33},
                    ))
            elif ctx.get("dyspepsia_symptoms"):
                actions.append(Action(
                    code="ROUTE_DYSPEPSIA_PATHWAY",
                    label="H. pylori negative but dyspepsia symptoms present — follow Dyspepsia pathway.",
                    display={"role": "primary_decision",
                             "show_as_standalone": True, "sort_priority": 33},
                ))

            stop = Stop(
                reason="H. pylori test is negative — pathway ends here.",
                actions=actions,
            )
            ctx.log(node_id, "HP_NEGATIVE", {"hp_test_type": test_type}, [stop])
            return NodeResult([stop])

        # ---- POSITIVE result ----
        actions.append(Action(
            code="HP_POSITIVE",
            label="H. pylori test is POSITIVE — proceed to treatment.",
            display={"role": "support", "badge": "info",
                     "show_as_standalone": True, "sort_priority": 34},
        ))
        ctx.log(node_id, "HP_POSITIVE", {"hp_test_type": test_type}, actions)
        return NodeResult(actions, next_node="Treatment")

    nodes["Diagnosis"] = Node("Diagnosis", node_diagnosis)

    # ------------------------------------------------------------------
    # Node 4 – Treatment
    # ------------------------------------------------------------------

    def node_treatment(ctx: Context):
        node_id = "Treatment"

        # Pregnancy / breastfeeding — hard stop
        if bool(ctx.get("pregnant")) or bool(ctx.get("breastfeeding")):
            stop = Stop(
                reason="⛔ Pregnant / breastfeeding — H. pylori treatment is contraindicated.",
                actions=[Action(
                    code="DO_NOT_TREAT_PREGNANCY_BREASTFEEDING",
                    label=(
                        "Do NOT treat H. pylori during pregnancy or breastfeeding.\n"
                        "   All treatment regimens (PAMC, PBMT, PAL, PAR, PCM) are contraindicated."
                    ),
                    display={"role": "primary_decision",
                             "show_as_standalone": True, "sort_priority": 40},
                )],
            )
            ctx.log(node_id, "PREGNANCY_BREASTFEEDING_STOP",
                    {"pregnant": ctx.get("pregnant"), "breastfeeding": ctx.get("breastfeeding")}, [stop])
            return NodeResult([stop])

        treatment_line = ctx.get("treatment_line")
        if treatment_line is None:
            dr = DataRequest(
                blocking_node=node_id,
                missing_fields=["treatment_line"],
                message="Enter current H. pylori treatment line (1, 2, 3, or 4).",
                suggested_actions=[Action(
                    code="CAPTURE_TREATMENT_LINE",
                    label="Capture current treatment line (1–4)",
                    display={"role": "support", "badge": "info",
                             "show_as_standalone": True, "sort_priority": 41},
                )],
            )
            ctx.log(node_id, "BLOCKED_MISSING_DATA", {"missing": ["treatment_line"]}, [dr])
            return NodeResult([dr])

        penicillin_allergy = bool(ctx.get("penicillin_allergy"))
        actions: List[Output] = []

        if treatment_line == 1:
            if penicillin_allergy:
                actions.append(Action(
                    code="TREAT_LINE_1_PBMT",
                    label="First line (penicillin-allergic): Bismuth Quadruple Regimen (PBMT) — 14 days",
                    details={"regimen_key": "PBMT"},
                    display={"role": "primary_decision",
                             "show_as_standalone": True, "sort_priority": 42},
                ))
            else:
                actions.append(Action(
                    code="TREAT_LINE_1_PAMC",
                    label="First line – Option A: CLAMET Quad (PAMC) — 14 days",
                    details={"regimen_key": "PAMC"},
                    display={"role": "primary_decision",
                             "show_as_standalone": True, "sort_priority": 42},
                ))
                actions.append(Action(
                    code="TREAT_LINE_1_PBMT",
                    label="First line – Option B: BMT Quad (PBMT) — 14 days",
                    details={"regimen_key": "PBMT"},
                    display={"role": "primary_decision",
                             "show_as_standalone": True, "sort_priority": 42},
                ))

        elif treatment_line == 2:
            if penicillin_allergy:
                actions.append(Action(
                    code="TREAT_LINE_2_PCM",
                    label="Second line (penicillin-allergic): Modified Triple (PCM) — 14 days",
                    details={"regimen_key": "PCM"},
                    display={"role": "primary_decision",
                             "show_as_standalone": True, "sort_priority": 43},
                ))
                actions.append(Action(
                    code="TREAT_LINE_2_ALLERGY_REFERRAL_OPTION",
                    label="Alternative: consider referral for formal allergy testing before proceeding.",
                    display={"role": "advisory", "badge": "info",
                             "show_as_standalone": True, "sort_priority": 43},
                ))
            else:
                actions.append(Action(
                    code="TREAT_LINE_2_SWITCH",
                    label=(
                        "Second line: switch to the regimen NOT used in first line.\n"
                        "   If PAMC was used → use PBMT.\n"
                        "   If PBMT was used → use PAMC, or consider PAL (Levo-Amox)."
                    ),
                    details={
                        "PAMC_details": _format_regimen("PAMC"),
                        "PBMT_details": _format_regimen("PBMT"),
                    },
                    display={"role": "primary_decision",
                             "show_as_standalone": True, "sort_priority": 43},
                ))

        elif treatment_line == 3:
            if penicillin_allergy:
                actions.append(Action(
                    code="TREAT_LINE_3_GI_REFERRAL",
                    label="Third line (penicillin-allergic): consider GI referral after two allergy-regimen failures.",
                    display={"role": "primary_decision",
                             "show_as_standalone": True, "sort_priority": 44},
                ))
            else:
                actions.append(Action(
                    code="TREAT_LINE_3_PAL",
                    label="Third line: Levo-Amox (PAL) — 14 days",
                    details={"regimen_key": "PAL"},
                    display={"role": "primary_decision",
                             "show_as_standalone": True, "sort_priority": 44},
                ))

        elif treatment_line == 4:
            if penicillin_allergy:
                actions.append(Action(
                    code="TREAT_LINE_4_GI_REFERRAL",
                    label="Fourth line (penicillin-allergic): refer to GI / allergy for specialist management.",
                    display={"role": "primary_decision",
                             "show_as_standalone": True, "sort_priority": 45},
                ))
            else:
                actions.append(Action(
                    code="TREAT_LINE_4_PAR_OR_REFER",
                    label=(
                        "Fourth line options (physician discretion):\n"
                        "   A) Prescribe Rif-Amox (PAR) — 10 days (see medication details below)\n"
                        "   B) Consult GI via Specialist LINK / ConnectMD / eReferral Advice Request\n"
                        "   C) Refer to GI"
                    ),
                    details={
                        "regimen_key": "PAR",
                        "supported_by": [
                            "Rifabutin may rarely cause serious myelotoxicity — assess case-by-case.",
                            "Rifabutin may require special authorization for Alberta Blue Cross.",
                        ],
                    },
                    display={"role": "primary_decision",
                             "show_as_standalone": True, "sort_priority": 45},
                ))
        else:
            stop = Stop(
                reason="Invalid treatment line value.",
                actions=[Action(
                    code="INVALID_TREATMENT_LINE",
                    label="Treatment line must be 1, 2, 3, or 4.",
                    display={"role": "support", "badge": "warning",
                             "show_as_standalone": True, "sort_priority": 46},
                )],
            )
            ctx.log(node_id, "INVALID_TREATMENT_LINE", {"treatment_line": treatment_line}, [stop])
            return NodeResult([stop])

        # Adherence note
        if ctx.get("bubble_pack_used") is False:
            actions.append(Action(
                code="BUBBLE_PACK_ADHERENCE_NOTE",
                label=(
                    "📦 Bubble/blister pack NOT in use — recommend asking pharmacist to dispense in a blister pack.\n"
                    "   All H. pylori regimens are recommended to be dispensed in a blister pack to improve adherence."
                ),
                display={"role": "advisory", "badge": "warning",
                         "show_as_standalone": True, "sort_priority": 47},
            ))

        ctx.log(node_id, "TREATMENT_RECOMMENDED",
                {"treatment_line": treatment_line, "penicillin_allergy": penicillin_allergy}, actions)
        return NodeResult(actions, next_node="Confirm_Eradication")

    nodes["Treatment"] = Node("Treatment", node_treatment)

    # ------------------------------------------------------------------
    # Node 5 – Confirm eradication
    # ------------------------------------------------------------------

    def node_confirm_eradication(ctx: Context):
        node_id = "Confirm_Eradication"

        actions: List[Output] = [Action(
            code="RETEST_FOR_ERADICATION",
            label=(
                "Retest with HpSAT or UBT — no sooner than 4 weeks after completing treatment.\n"
                "   Retesting too early risks a false negative result.\n"
                "   Patient must be: OFF antibiotics ≥4 weeks AND off PPIs ≥2 weeks before retest.\n"
                "   Note: once cured, H. pylori re-infection rate is <2%."
            ),
            display={"role": "support", "badge": "info",
                     "show_as_standalone": True, "sort_priority": 50},
        )]

        if ctx.get("off_antibiotics_4_weeks_before_retest") is False:
            actions.append(Action(
                code="RETEST_PREP_ANTIBIOTIC_WARNING",
                label="⚠️  Patient has not been off antibiotics ≥4 weeks — retesting now may give a false negative.",
                display={"role": "advisory", "badge": "warning",
                         "show_as_standalone": True, "sort_priority": 51},
            ))

        if ctx.get("off_ppi_2_weeks_before_retest") is False:
            actions.append(Action(
                code="RETEST_PREP_PPI_WARNING",
                label="⚠️  Patient has not been off PPIs ≥2 weeks — retesting now may give a false negative.",
                display={"role": "advisory", "badge": "warning",
                         "show_as_standalone": True, "sort_priority": 51},
            ))

        eradication_test_result = ctx.get("eradication_test_result")
        symptoms_persist        = ctx.get("symptoms_persist")

        missing = []
        if eradication_test_result is None:
            missing.append("eradication_test_result")
        if symptoms_persist is None:
            missing.append("symptoms_persist")

        if missing:
            dr = DataRequest(
                blocking_node=node_id,
                missing_fields=missing,
                message=(
                    "Enter eradication test result (positive/negative) and whether symptoms persist (True/False)."
                ),
                suggested_actions=[Action(
                    code="CAPTURE_ERADICATION_STATUS",
                    label="Capture eradication result and current symptom status",
                    display={"role": "support", "badge": "info",
                             "show_as_standalone": True, "sort_priority": 52},
                )],
            )
            ctx.log(node_id, "BLOCKED_MISSING_DATA", {"missing": missing}, actions + [dr])
            return NodeResult(actions + [dr])

        # ✅ Eradication confirmed, no symptoms
        if eradication_test_result == "negative" and not symptoms_persist:
            stop = Stop(
                reason="✅ Eradication confirmed. Symptoms resolved. Pathway care complete.",
                actions=actions + [Action(
                    code="PATHWAY_COMPLETE",
                    label="H. pylori pathway care is complete. No further action required.",
                    display={"role": "primary_decision",
                             "show_as_standalone": True, "sort_priority": 53},
                )],
            )
            ctx.log(node_id, "ERADICATION_CONFIRMED_PATHWAY_COMPLETE",
                    {"eradication_test_result": eradication_test_result,
                     "symptoms_persist": symptoms_persist}, [stop])
            return NodeResult([stop])

        # ✅ Eradication confirmed, but symptoms persist
        if eradication_test_result == "negative" and symptoms_persist:
            actions.append(Action(
                code="POST_ERADICATION_SYMPTOMS_ROUTE_DYSPEPSIA",
                label=(
                    "H. pylori eradicated, but symptoms persist.\n"
                    "   → Follow Dyspepsia pathway and/or reassess diagnosis."
                ),
                display={"role": "primary_decision",
                         "show_as_standalone": True, "sort_priority": 54},
            ))
            stop = Stop(
                reason="Eradication confirmed but symptoms persist — further assessment needed.",
                actions=actions,
            )
            ctx.log(node_id, "ERADICATION_CONFIRMED_SYMPTOMS_PERSIST",
                    {"eradication_test_result": eradication_test_result,
                     "symptoms_persist": symptoms_persist}, [stop])
            return NodeResult([stop])

        # ❌ Eradication failed (test still positive)
        ctx.log(node_id, "ERADICATION_FAILED",
                {"eradication_test_result": eradication_test_result,
                 "symptoms_persist": symptoms_persist}, actions)
        return NodeResult(actions, next_node="Treatment_Failure")

    nodes["Confirm_Eradication"] = Node("Confirm_Eradication", node_confirm_eradication)

    # ------------------------------------------------------------------
    # Node 6 – Treatment failure
    # ------------------------------------------------------------------

    def node_treatment_failure(ctx: Context):
        node_id = "Treatment_Failure"

        treatment_line = ctx.get("treatment_line")
        actions: List[Output] = []

        if bool(ctx.get("nonadherence_suspected")):
            actions.append(Action(
                code="EXPLORE_NONADHERENCE",
                label=(
                    "Non-adherence or intolerance suspected — explore with patient before escalating.\n"
                    "   Treatment failure may be due to antibiotic resistance, intolerance, or non-adherence.\n"
                    "   Consider blister pack if not already used."
                ),
                display={"role": "advisory", "badge": "warning",
                         "show_as_standalone": True, "sort_priority": 60},
            ))

        if treatment_line is None:
            dr = DataRequest(
                blocking_node=node_id,
                missing_fields=["treatment_line"],
                message="Enter the treatment line that just failed (1, 2, or 3) to determine next steps.",
                suggested_actions=[Action(
                    code="CAPTURE_TREATMENT_LINE",
                    label="Capture failed treatment line",
                    display={"role": "support", "badge": "info",
                             "show_as_standalone": True, "sort_priority": 60},
                )],
            )
            ctx.log(node_id, "BLOCKED_MISSING_DATA", {"missing": ["treatment_line"]}, actions + [dr])
            return NodeResult(actions + [dr])

        failed_three_rounds = treatment_line >= 3
        failed_three_rounds = ctx.apply_override(node_id, "failed_three_rounds", failed_three_rounds)
        ctx.set("failed_three_rounds", failed_three_rounds)

        if failed_three_rounds:
            stop = Stop(
                reason="H. pylori not eradicated after ≥3 treatment attempts.",
                actions=actions + [Action(
                    code="REFER_AFTER_THREE_FAILURES",
                    label=(
                        "Three failed treatment attempts — refer to GI specialist.\n"
                        "   Include full testing and treatment history in the referral.\n"
                        "   Options: eReferral Advice Request | Specialist LINK (Calgary) | ConnectMD (Edmonton/North)"
                    ),
                    override_options={"node": node_id, "field": "failed_three_rounds",
                                      "allowed": [True, False], "reason_required": True},
                    display={"role": "primary_decision",
                             "show_as_standalone": True, "sort_priority": 61},
                )],
            )
            ctx.log(node_id, "REFER_AFTER_THREE_FAILURES", {"treatment_line": treatment_line}, [stop])
            return NodeResult([stop])

        next_line = treatment_line + 1
        actions.append(Action(
            code="PROCEED_TO_NEXT_TREATMENT_LINE",
            label=(
                f"Proceed to Line {next_line} of treatment — do NOT repeat the same regimen.\n"
                "   Return to Treatment node with updated treatment_line."
            ),
            details={"supported_by": [f"Failed treatment line: {treatment_line}"]},
            display={"role": "primary_decision",
                     "show_as_standalone": True, "sort_priority": 62},
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
