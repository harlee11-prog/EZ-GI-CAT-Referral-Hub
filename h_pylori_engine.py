# H. PYLORI PRIMARY PATHWAY:
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# 0. Enums
class TreatmentLine(Enum):
    NAIVE       = 0
    SECOND_LINE = 1
    THIRD_LINE  = 2
    FOURTH_LINE = 3

class LastRegimen(Enum):
    NONE  = "none"
    PAMC  = "PAMC"
    PBMT  = "PBMT"

class ReferralUrgency(Enum):
    URGENT  = "URGENT"
    ROUTINE = "ROUTINE"
    NONE    = "NONE"

# 1. Patient Dataclass
@dataclass
class Patient:
    age: Optional[int] = None
    sex: Optional[str] = None
    pregnant_or_nursing: Optional[bool] = None
    dyspepsia_symptoms: Optional[bool] = None
    history_ulcer_or_gi_bleed: Optional[bool] = None
    personal_or_family_hx_gastric_cancer: Optional[bool] = None
    immigrant_high_prevalence: Optional[bool] = None
    h_pylori_test_positive: Optional[bool] = None
    off_antibiotics_4_weeks: Optional[bool] = None
    off_ppis_2_weeks: Optional[bool] = None
    off_bismuth_2_weeks: Optional[bool] = None
    penicillin_allergy: Optional[bool] = None
    treatment_line: TreatmentLine = TreatmentLine.NAIVE
    last_regimen_used: LastRegimen = LastRegimen.NONE
    all_regimens_tried: List[str] = field(default_factory=list)
    alarm_family_hx_esophageal_gastric_cancer: Optional[bool] = None
    alarm_personal_ulcer_history: Optional[bool] = None
    alarm_age_over_60_new_persistent_symptoms: Optional[bool] = None
    alarm_unintended_weight_loss: Optional[bool] = None
    alarm_progressive_dysphagia: Optional[bool] = None
    alarm_persistent_vomiting: Optional[bool] = None
    alarm_black_stool: Optional[bool] = None
    alarm_blood_in_vomit: Optional[bool] = None
    alarm_iron_deficiency_anemia: Optional[bool] = None

    @property
    def has_testing_indication(self) -> bool:
        return any([
            self.dyspepsia_symptoms,
            self.history_ulcer_or_gi_bleed,
            self.personal_or_family_hx_gastric_cancer,
            self.immigrant_high_prevalence,
        ])

    @property
    def has_alarm_features(self) -> bool:
        return any([
            self.alarm_family_hx_esophageal_gastric_cancer,
            self.alarm_personal_ulcer_history,
            self.alarm_age_over_60_new_persistent_symptoms,
            self.alarm_unintended_weight_loss,
            self.alarm_progressive_dysphagia,
            self.alarm_persistent_vomiting,
            self.alarm_black_stool,
            self.alarm_blood_in_vomit,
            self.alarm_iron_deficiency_anemia,
        ])

    @property
    def active_alarms(self) -> List[str]:
        alarms = []
        if self.alarm_family_hx_esophageal_gastric_cancer:
            alarms.append("Family history (first-degree relative) of esophageal or gastric cancer")
        if self.alarm_personal_ulcer_history:
            alarms.append("Personal history of peptic ulcer disease")
        if self.alarm_age_over_60_new_persistent_symptoms:
            alarms.append("Age >60 with new and persistent symptoms (>3 months)")
        if self.alarm_unintended_weight_loss:
            alarms.append("Unintended weight loss >5% over 6–12 months")
        if self.alarm_progressive_dysphagia:
            alarms.append("Progressive dysphagia")
        if self.alarm_persistent_vomiting:
            alarms.append("Persistent vomiting (not associated with cannabis use)")
        if self.alarm_black_stool:
            alarms.append("Black stool (see Primer on Black Stool)")
        if self.alarm_blood_in_vomit:
            alarms.append("Blood in vomit")
        if self.alarm_iron_deficiency_anemia:
            alarms.append("Iron deficiency anemia (see Iron Primer)")
        return alarms

    @property
    def needs_urgent_labs(self) -> bool:
        return bool(self.alarm_black_stool or self.alarm_blood_in_vomit)

    @property
    def test_prep_ready(self) -> bool:
        return (
            self.off_antibiotics_4_weeks is not False
            and self.off_ppis_2_weeks is not False
            and self.off_bismuth_2_weeks is not False
        )

# 2. Decision Audit Trail
@dataclass
class DecisionStep:
    rule: str
    inputs: Dict[str, Any]
    decision: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

class DecisionTracker:
    def __init__(self):
        self.steps: List[DecisionStep] = []

    def log(self, rule, inputs, decision):
        self.steps.append(DecisionStep(rule, inputs, decision))

    def summary(self):
        return [s.__dict__ for s in self.steps]

@dataclass
class ClinicalAction:
    category: str
    urgency: str
    description: str
    details: List[str] = field(default_factory=list)

# 3. Regimen Catalogue
REGIMENS: Dict[str, Dict[str, Any]] = {
    "PAMC": {
        "name": "CLAMET Quad (PAMC)",
        "duration_days": 14,
        "cost_approx": "$130",
        "penicillin_required": True,
        "components": [
            "PPI (standard dose) 1 pill BID",
            "Amoxicillin 1000 mg (2 capsules) BID",
            "Metronidazole 500 mg (1 tablet) BID",
            "Clarithromycin 500 mg (1 capsule) BID",
        ],
        "notes": "Recommend blister pack to improve adherence.",
    },
    "PBMT_NON_ALLERGIC": {
        "name": "BMT Quad (PBMT)",
        "duration_days": 14,
        "cost_approx": "$80",
        "penicillin_required": False,
        "components": [
            "PPI (standard dose) 1 pill BID",
            "Bismuth subsalicylate 524 mg (2 caplets) QID",
            "Metronidazole 500 mg (1 tablet) QID",
            "Tetracycline 500 mg (1 capsule) QID",
        ],
        "notes": "Recommend blister pack to improve adherence.",
    },
    "PAL": {
        "name": "Levo-Amox (PAL)",
        "duration_days": 14,
        "cost_approx": "$100",
        "penicillin_required": True,
        "components": [
            "PPI (standard dose) 1 pill BID",
            "Amoxicillin 1000 mg (2 capsules) BID",
            "Levofloxacin 500 mg (1 tablet) once daily",
        ],
        "notes": "Third-line for non-allergic patients. Recommend blister pack.",
    },
    "PAR": {
        "name": "Rif-Amox (PAR)",
        "duration_days": 10,
        "cost_approx": "$170",
        "penicillin_required": True,
        "components": [
            "PPI (standard dose) 1 pill BID",
            "Amoxicillin 1000 mg (2 capsules) BID",
            "Rifabutin 150 mg (1 tablet) BID",
        ],
        "notes": (
            "⚠ IMPORTANT: Rifabutin has rarely been associated with potentially "
            "serious myelotoxicity (low white cell or platelet count). Pros and cons "
            "of fourth-line therapy must be decided on a case-by-case basis. "
            "Rifabutin may require Special Authorization for Alberta Blue Cross patients."
        ),
    },
    "PBMT_ALLERGIC": {
        "name": "Bismuth Quadruple Regimen (PBMT)",
        "duration_days": 14,
        "cost_approx": "$80",
        "penicillin_required": False,
        "components": [
            "PPI (standard dose) 1 pill BID",
            "Bismuth subsalicylate 524 mg QID",
            "Metronidazole 500 mg QID",
            "Tetracycline 500 mg QID",
        ],
        "notes": "First-line for penicillin-allergic patients. Recommend blister pack.",
    },
    "PCM": {
        "name": "Modified Triple Therapy (PCM)",
        "duration_days": 14,
        "cost_approx": "$100",
        "penicillin_required": False,
        "components": [
            "Pantoprazole 40 mg BID",
            "Clarithromycin 500 mg BID",
            "Metronidazole 500 mg BID",
        ],
        "notes": (
            "Second-line for penicillin-allergic patients. "
            "Consider referral for formal allergy testing after failure."
        ),
    },
}

def _format_regimen(key: str) -> List[str]:
    r = REGIMENS[key]
    lines = [
        f"Regimen: {r['name']} for {r['duration_days']} days "
        f"(approx. {r['cost_approx']} with generics).",
        "Components:",
        *[f"  • {c}" for c in r["components"]],
    ]
    if r.get("notes"):
        lines.append(f"Note: {r['notes']}")
    return lines

# 4. Pathway Engine
class HPyloriPathwayEngine:
    def __init__(self):
        self.tracker = DecisionTracker()

    def evaluate(self, p: Patient) -> List[ClinicalAction]:
        actions: List[ClinicalAction] = []

        # 0. PEDIATRIC EXCLUSION
        if p.age is not None and p.age < 18:
            self.tracker.log("Pediatric Exclusion", {"age": p.age}, "Do Not Use This Pathway")
            return [ClinicalAction(
                category="EXCLUSION",
                urgency="URGENT",
                description="Pediatric Patient – Do Not Use This Pathway",
                details=[
                    "This pathway is intended for adults only.",
                    "Consult a Pediatric Gastroenterologist via eReferral Advice Request.",
                ]
            )]

        # 1. TESTING INDICATOR
        if p.h_pylori_test_positive is None:
            if not p.has_testing_indication:
                self.tracker.log("Testing Indications", {}, "No Testing Indication Found")
                return [ClinicalAction(
                    category="TESTING",
                    urgency="INFO",
                    description="No Indication for H. pylori Testing Found",
                    details=[
                        "Testing is indicated for:",
                        "  • Patients with dyspepsia symptoms (epigastric pain/discomfort, "
                        "bloating, early satiety, loss of appetite).",
                        "  • Current or past gastric/duodenal ulcers or upper GI bleed.",
                        "  • Personal or first-degree relative with history of gastric cancer "
                        "(test once in adulthood).",
                        "  • First-generation immigrants from high-prevalence areas "
                        "(Asia, Africa, Central and South America).",
                        "NOTE: Many H. pylori infected patients are asymptomatic.",
                    ]
                )]

            self.tracker.log(
                "Box 1 – Testing Indications",
                {
                    "dyspepsia": p.dyspepsia_symptoms,
                    "ulcer_bleed": p.history_ulcer_or_gi_bleed,
                    "family_gastric_ca": p.personal_or_family_hx_gastric_cancer,
                    "immigrant": p.immigrant_high_prevalence,
                },
                "Testing Indicated – Pre-test Instructions Issued"
            )
            actions.append(ClinicalAction(
                category="TESTING",
                urgency="ROUTINE",
                description="Order H. pylori Diagnostic Test",
                details=[
                    "Test using H. pylori Stool Antigen Test (HpSAT) or "
                    "Urea Breath Test (UBT), depending on local availability.",
                    "HpSAT is the primary test in Edmonton, Calgary, and South Zones, "
                    "and selected sites in North and Central Zones.",
                    "⚠ Pre-test washout requirements (false negatives if not followed):",
                    "  • Off ALL antibiotics for at least 4 weeks before the test.",
                    "  • Off bismuth preparations (e.g., Pepto-Bismol) for at least 2 weeks.",
                    "  • Off PPIs for at least 2 weeks before the test.",
                    "  • Antacids may be taken up to 24 hours before the test.",
                ]
            ))
            if p.has_alarm_features:
                self._add_alarm_referral(p, actions)
            return actions

        # 2. ALARM FEATURES CHECK
        if p.has_alarm_features:
            self._add_alarm_referral(p, actions)
            # Family hx only: test + treat while awaiting referral
            if (p.h_pylori_test_positive
                    and p.alarm_family_hx_esophageal_gastric_cancer
                    and not any([
                        p.alarm_unintended_weight_loss,
                        p.alarm_progressive_dysphagia,
                        p.alarm_persistent_vomiting,
                        p.alarm_black_stool,
                        p.alarm_blood_in_vomit,
                        p.alarm_iron_deficiency_anemia,
                        p.alarm_age_over_60_new_persistent_symptoms,
                    ])):
                actions.append(ClinicalAction(
                    category="CLINICAL_NOTE",
                    urgency="ROUTINE",
                    description="Treat H. pylori While Awaiting Referral",
                    details=[
                        "For patients referred due to family history of gastric/esophageal "
                        "cancer, it is appropriate to initiate treatment while waiting for "
                        "consultation/gastroscopy.",
                    ]
                ))
                actions.extend(self._build_treatment_actions(p))
            return actions

        # 3. DIAGNOSIS NEGATIVE
        if p.h_pylori_test_positive is False:
            self.tracker.log("Test Result", {"result": "Negative"}, "Route to Dyspepsia Pathway")
            return [ClinicalAction(
                category="ROUTING",
                urgency="INFO",
                description="H. pylori Negative – Route to Dyspepsia Pathway",
                details=[
                    "HpSAT or UBT result is negative.",
                    "False negatives may occur with recent antibiotic or PPI use – "
                    "confirm washout requirements were met.",
                    "If symptoms persist, refer to the Dyspepsia Primary Care Pathway.",
                ]
            )]

        # Positive test confirmed from here
        self.tracker.log("Test Result", {"result": "Positive"}, "Positive – Proceed to Treatment")

        # 4. PREGNANCY CONTRAINDICATION
        if p.pregnant_or_nursing:
            self.tracker.log("Pregnancy Screen", {"pregnant_or_nursing": True}, "Contraindication – Do Not Treat")
            return [ClinicalAction(
                category="CONTRAINDICATION",
                urgency="URGENT",
                description="Contraindication: Do Not Treat H. pylori During Pregnancy/Nursing",
                details=[
                    "All H. pylori treatment regimens are contraindicated in pregnancy "
                    "and breastfeeding.",
                    "Reassess and initiate treatment postpartum.",
                ]
            )]

        # 5. TEST PREP WARNING
        if not p.test_prep_ready:
            actions.append(ClinicalAction(
                category="CLINICAL_NOTE",
                urgency="ROUTINE",
                description="Test Washout Requirements May Not Have Been Met",
                details=[
                    "A positive test result is reliable; false positives are rare.",
                    "Ensure washout requirements were followed to avoid false negatives "
                    "on any future eradication test.",
                ]
            ))

        # 6. TREATMENT
        actions.extend(self._build_treatment_actions(p))

        # 7. ERADICATION CONFIRMATION
        if p.treatment_line != TreatmentLine.FOURTH_LINE:
            actions.append(ClinicalAction(
                category="FOLLOW_UP",
                urgency="ROUTINE",
                description="Mandatory Eradication Confirmation",
                details=[
                    "Retest with HpSAT or UBT NO SOONER than 4 weeks after "
                    "completing treatment. Retesting too soon risks a false negative.",
                    "⚠ Washout before eradication test:",
                    "  • Off ALL antibiotics (including H. pylori treatment) ≥4 weeks.",
                    "  • Off PPIs ≥2 weeks.",
                    "Once eradicated, re-infection rate is <2%.",
                    "If symptoms persist after confirmed eradication, refer to the "
                    "Dyspepsia Pathway.",
                    "If test remains POSITIVE → proceed to next treatment line.",
                ]
            ))
        return actions

    # ── PRIVATE METHODS – correctly indented inside the class ──────────

    def _add_alarm_referral(self, p: Patient, actions: List[ClinicalAction]) -> None:
        self.tracker.log(
            "Box 2 – Alarm Features",
            {"alarms": p.active_alarms},
            "Urgent Referral Triggered"
        )
        details = [
            "One or more alarm features identified:",
            *[f"  • {a}" for a in p.active_alarms],
            "Refer for consultation and/or endoscopy. Include ALL alarm features "
            "in the referral to ensure appropriate triage.",
        ]
        if p.needs_urgent_labs:
            details.append(
                "⚠ URGENT LABS: Order CBC, INR, and BUN as part of the referral "
                "(indicated by black stool and/or blood in vomit)."
            )
        actions.append(ClinicalAction(
            category="REFERRAL",
            urgency=ReferralUrgency.URGENT.value,
            description="Urgent Referral: Gastroenterology / Endoscopy",
            details=details,
        ))

    def _build_treatment_actions(self, p: Patient) -> List[ClinicalAction]:
        actions: List[ClinicalAction] = []
        line = p.treatment_line
        allergic = bool(p.penicillin_allergy)

        # FIRST LINE
        if line == TreatmentLine.NAIVE:
            if allergic:
                self.tracker.log("Box 4 – First Line (Penicillin Allergy)", {}, "PBMT (Bismuth Quadruple)")
                actions.append(ClinicalAction(
                    category="TREATMENT",
                    urgency="ROUTINE",
                    description="First-Line Treatment (Penicillin Allergy): Bismuth Quadruple Regimen (PBMT)",
                    details=_format_regimen("PBMT_ALLERGIC"),
                ))
            else:
                self.tracker.log("Box 4 – First Line", {}, "PAMC or PBMT (clinician choice)")
                actions.append(ClinicalAction(
                    category="TREATMENT",
                    urgency="ROUTINE",
                    description="First-Line Treatment: CLAMET Quad (PAMC) OR BMT Quad (PBMT) – clinician choice",
                    details=[
                        "Choose ONE of the following two regimens:",
                        "",
                        "OPTION A – CLAMET Quad (PAMC):",
                        *_format_regimen("PAMC"),
                        "",
                        "OPTION B – BMT Quad (PBMT):",
                        *_format_regimen("PBMT_NON_ALLERGIC"),
                        "",
                        "⚠ Standard triple therapy (PAC/PMC/PAM) is NO LONGER "
                        "recommended due to changing antibiotic resistance.",
                    ]
                ))

        # SECOND LINE
        elif line == TreatmentLine.SECOND_LINE:
            if allergic:
                self.tracker.log("Box 4 – Second Line (Penicillin Allergy)", {}, "PCM or Allergy Referral")
                actions.append(ClinicalAction(
                    category="TREATMENT",
                    urgency="ROUTINE",
                    description="Second-Line Treatment (Penicillin Allergy): Modified Triple Therapy (PCM) or Allergy Referral",
                    details=[
                        *_format_regimen("PCM"),
                        "Alternative: Refer for formal penicillin allergy testing, "
                        "which may allow use of amoxicillin-containing regimens.",
                    ]
                ))
            else:
                prev = p.last_regimen_used
                if prev == LastRegimen.PAMC:
                    next_key, decision_text = "PBMT_NON_ALLERGIC", "Failed PAMC → Switch to PBMT"
                elif prev == LastRegimen.PBMT:
                    next_key, decision_text = "PAMC", "Failed PBMT → Switch to PAMC (or consider PAL)"
                else:
                    next_key, decision_text = "PAMC", "Prior regimen unknown → Default to PAMC"
                self.tracker.log("Box 4 – Second Line", {"last_regimen": prev.value}, decision_text)
                details = _format_regimen(next_key)
                if prev == LastRegimen.PBMT:
                    details.append(
                        "Alternative to PAMC: Consider Levo-Amox (PAL) if clinically appropriate."
                    )
                actions.append(ClinicalAction(
                    category="TREATMENT",
                    urgency="ROUTINE",
                    description=f"Second-Line Treatment: {REGIMENS[next_key]['name']}",
                    details=details,
                ))

        # THIRD LINE
        elif line == TreatmentLine.THIRD_LINE:
            if allergic:
                self.tracker.log("Box 4 – Third Line (Penicillin Allergy)", {"failures": 2}, "Refer to GI")
                actions.append(ClinicalAction(
                    category="REFERRAL",
                    urgency=ReferralUrgency.ROUTINE.value,
                    description="Third Line (Penicillin Allergy): Refer to Gastroenterology",
                    details=[
                        "After two failed regimens in a penicillin-allergic patient, refer to GI "
                        "or consult via Specialist LINK, ConnectMD, or Alberta Netcare eReferral.",
                        "Include full documentation of all failed treatment attempts in the referral.",
                    ]
                ))
            else:
                self.tracker.log("Box 4 – Third Line", {"failures": 2}, "Levo-Amox PAL")
                actions.append(ClinicalAction(
                    category="TREATMENT",
                    urgency="ROUTINE",
                    description="Third-Line Treatment: Levo-Amox (PAL)",
                    details=_format_regimen("PAL"),
                ))

        # FOURTH LINE / REFRACTORY
        elif line == TreatmentLine.FOURTH_LINE:
            regimens_str = ", ".join(p.all_regimens_tried) if p.all_regimens_tried else "See chart"
            self.tracker.log(
                "Box 6 – Treatment Failure / Fourth Line",
                {"failures": 3, "regimens_tried": regimens_str},
                "Rif-Amox (PAR) or Refer to GI"
            )
            actions.append(ClinicalAction(
                category="REFERRAL",
                urgency=ReferralUrgency.ROUTINE.value,
                description="Box 7 – Refer to Gastroenterology (Three Failed Rounds)",
                details=[
                    "H. pylori has not been eradicated after three rounds of treatment.",
                    f"Regimens trialed: {regimens_str}.",
                    "Options:",
                    "  OPTION A: Refer to GI or consult via Specialist LINK, ConnectMD, "
                    "or Alberta Netcare eReferral Advice Request.",
                    "  OPTION B (non-allergic, if FP comfortable): Rif-Amox (PAR) – see below.",
                    "",
                    *(_format_regimen("PAR") if not allergic else [
                        "(Rif-Amox is not appropriate for penicillin-allergic patients.)"
                    ]),
                ]
            ))

        # General treatment note (all lines)
        actions.append(ClinicalAction(
            category="CLINICAL_NOTE",
            urgency="INFO",
            description="General Treatment Notes",
            details=[
                "Treatment failure may be due to antibiotic resistance; however, "
                "explore non-adherence and intolerance with the patient.",
                "Do NOT retry the same treatment regimen after failure.",
            ]
        ))
        return actions


# 5. Clinical Report
def generate_clinical_report(
    patient: Patient,
    actions: List[ClinicalAction],
    engine: HPyloriPathwayEngine,
    *,
    width: int = 80
) -> str:
    SEP  = "=" * width
    DSEP = "-" * width
    lines: List[str] = []

    def line(text: str = "") -> None:
        lines.append(text)

    line(SEP)
    line("  CLINICAL DECISION SUPPORT – H. PYLORI PRIMARY CARE PATHWAY")
    line("  Alberta Health Services / Primary Care Networks  |  October 2021")
    line(SEP)
    line()
    line("[1]  PATIENT CONTEXT")
    line(DSEP)
    line(f"     Age / Sex              : {patient.age or 'Not provided'} / {(patient.sex or 'Not provided').capitalize()}")
    line(f"     Pregnant / Nursing     : {'Yes – CONTRAINDICATION' if patient.pregnant_or_nursing else 'No'}")
    line(f"     Allergy Status         : {'Penicillin Allergy' if patient.penicillin_allergy else 'No known allergy'}")
    test_str = "Not yet tested" if patient.h_pylori_test_positive is None else ("POSITIVE (+)" if patient.h_pylori_test_positive else "Negative (–)")
    line(f"     H. pylori Test         : {test_str}")
    line(f"     Testing Indication     : {'Yes' if patient.has_testing_indication else 'No'}")
    line(f"     Alarm Features         : {', '.join(patient.active_alarms) if patient.has_alarm_features else 'None'}")
    line_labels = {
        TreatmentLine.NAIVE:       "Treatment Naive",
        TreatmentLine.SECOND_LINE: "Second Line (1 prior failure)",
        TreatmentLine.THIRD_LINE:  "Third Line (2 prior failures)",
        TreatmentLine.FOURTH_LINE: "Fourth Line / Refractory (3 failures)",
    }
    line(f"     Treatment Line         : {line_labels[patient.treatment_line]}")
    if patient.all_regimens_tried:
        line(f"     Regimens Tried         : {', '.join(patient.all_regimens_tried)}")

    line()
    line("[2]  RECOMMENDED ACTIONS")
    line(DSEP)
    for i, action in enumerate(actions, 1):
        urgency_badge = f"[{action.urgency}]" if action.urgency != "INFO" else ""
        line(f"     {i}.  {urgency_badge}  {action.category}: {action.description}")
        for detail in action.details:
            line(f"          {detail}")
        line()

    line("[3]  DECISION AUDIT LOG")
    line(DSEP)
    for step in engine.tracker.steps:
        try:
            ts = datetime.fromisoformat(step.timestamp).strftime("%H:%M:%S")
        except Exception:
            ts = "??:??:??"
        line(f"     [{ts}]  {step.rule}")
        line(f"              → {step.decision}")
        if step.inputs:
            line(f"              inputs: {', '.join(f'{k}={v}' for k, v in step.inputs.items())}")
        line()

    line(SEP)
    line("  ⚠  This tool supports clinical decision-making and does not replace")
    line("     professional judgment. Always apply individual patient context.")
    line(SEP)
    return "\n".join(lines)


# Example usage
patient_c = Patient(
    age=63,
    sex="male",
    dyspepsia_symptoms=True,
    h_pylori_test_positive=True,
    alarm_black_stool=True,
    alarm_unintended_weight_loss=True,
    alarm_age_over_60_new_persistent_symptoms=True,
    penicillin_allergy=False,
    treatment_line=TreatmentLine.NAIVE,
)
engine_c = HPyloriPathwayEngine()
actions_c = engine_c.evaluate(patient_c)
print(generate_clinical_report(patient_c, actions_c, engine_c))
