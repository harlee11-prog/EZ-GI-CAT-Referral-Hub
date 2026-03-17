# ============================================================
# CHRONIC CONSTIPATION PATHWAY
# Based on: Alberta Health Services / Primary Care Networks
# Chronic Constipation Primary Care Pathway (Oct 2021)
# Integrated with: MasterClinicalRecord schema
# ============================================================

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from enum import Enum, auto


# ============================================================
# 0. ENUMS
# ============================================================

class TreatmentTier(Enum):
    """Tracks which treatment tier patient is currently at."""
    NAIVE           = 0   # No prior treatment
    FAILED_LIFESTYLE = 1   # Failed dietary/lifestyle modification
    FAILED_BULK_OSMOTIC = 2   # Failed bulk-forming + osmotic laxatives
    FAILED_STIMULANT    = 3   # Failed stimulant laxatives (short-term)
    FAILED_ADVANCED     = 4   # Failed Linaclotide or Prucalopride → Refer


class ReferralUrgency(Enum):
    URGENT   = "URGENT"    # Alarm features present
    ROUTINE  = "ROUTINE"   # Unsatisfactory response after adequate therapy
    NONE     = "NONE"


# ============================================================
# 1. PATIENT DATACLASS
# Extends Constipation from MasterClinicalRecord; adds
# pathway-specific fields not in the shared schema.
# ============================================================

@dataclass
class ChronicConstipationPatient:
    """
    Full clinical representation for the Chronic Constipation
    Primary Care Pathway.

    Rome IV diagnostic criteria require ≥2 symptoms present
    for AT LEAST 3 of the last 6 months.
    """

    # ----- Demographics (from Demographics dataclass) -----
    age: Optional[int] = None
    sex: Optional[str] = None          # "male" / "female" / "other"
    crcl_ml_min: Optional[float] = None  # Creatinine clearance (Prucalopride dosing)
    severe_hepatic_impairment: Optional[bool] = None  # Prucalopride dosing

    # ----- Rome IV Diagnostic Criteria -----
    # Requires ≥2 of the following present for ≥3 of the last 6 months
    symptom_months_in_last_6: int = 0          # How many of past 6 months symptomatic
    bowel_movements_per_week: Optional[int] = None  # Criteria: ≤3 / week
    hard_lumpy_stool: Optional[bool] = None    # Bristol type 1-2 for >25% defecations
    straining: Optional[bool] = None           # >25% of defecations
    incomplete_evacuation: Optional[bool] = None   # >25% of defecations
    anorectal_blockage: Optional[bool] = None  # >25% of defecations
    manual_maneuvers: Optional[bool] = None    # Needed >25% of defecations

    # ----- IBS-C Exclusion -----
    # If predominant abdominal pain AND/OR bloating → IBS-C pathway
    abdominal_pain_predominant: Optional[bool] = None
    bloating_predominant: Optional[bool] = None

    # ----- Defecatory Dysfunction Signals -----
    traumatic_perineal_injury: Optional[bool] = None   # e.g., traumatic delivery, tear
    outlet_blockage_sensation: Optional[bool] = None   # Persistent sense of outlet blockage
    needs_wiggle_to_defecate: Optional[bool] = None    # Has to rotate/wiggle on toilet

    # ----- Alarm Features (Box 5 of pathway) -----
    alarm_family_hx_colorectal_cancer: Optional[bool] = None  # First-degree relative
    alarm_unintended_weight_loss: Optional[bool] = None        # >5% over 6–12 months
    alarm_sudden_change_bowel_habit: Optional[bool] = None     # Sudden or progressive
    alarm_blood_in_stool: Optional[bool] = None                # Visible blood
    alarm_iron_deficiency_anemia: Optional[bool] = None        # (see Iron Primer)
    alarm_anal_mass_or_irregularity: Optional[bool] = None     # On digital anorectal exam

    # ----- Baseline Investigations (Box 7) -----
    cbc_done: Optional[bool] = None
    positive_celiac_screen: Optional[bool] = None
    # Consider: glucose, creatinine, calcium/albumin, TSH
    tsh_abnormal: Optional[bool] = None
    calcium_abnormal: Optional[bool] = None
    glucose_abnormal: Optional[bool] = None
    creatinine_abnormal: Optional[bool] = None

    # ----- Secondary Causes Optimized? -----
    secondary_causes_reviewed: Optional[bool] = None
    # Includes: medications (OTC + Rx), comorbidities, activity, diet/fluids

    # ----- Treatment History -----
    treatment_tier: TreatmentTier = TreatmentTier.NAIVE
    months_on_current_therapy: Optional[float] = None
    unsatisfactory_response: Optional[bool] = None   # Patient/clinician assessment
    # Used at Level 2+ to determine Linaclotide vs Prucalopride
    failed_laxative_classes_count: int = 0   # Number of distinct laxative classes tried
    advice_service_consulted: Optional[bool] = None  # Pathway recommends before referring

    # ---- Computed Properties ----

    @property
    def meets_duration_criteria(self) -> bool:
        """Rome IV: symptoms present in at least 3 of the last 6 months."""
        return self.symptom_months_in_last_6 >= 3

    @property
    def symptom_count(self) -> int:
        """Count how many of the 6 Rome IV symptoms are positive."""
        count = 0
        if self.bowel_movements_per_week is not None and self.bowel_movements_per_week <= 3:
            count += 1
        if self.hard_lumpy_stool:   count += 1
        if self.straining:          count += 1
        if self.incomplete_evacuation: count += 1
        if self.anorectal_blockage: count += 1
        if self.manual_maneuvers:   count += 1
        return count

    @property
    def meets_symptom_criteria(self) -> bool:
        """Rome IV: at least 2 of the 6 symptoms must be positive."""
        return self.symptom_count >= 2

    @property
    def meets_diagnostic_criteria(self) -> bool:
        """Full Rome IV criteria: ≥2 symptoms AND ≥3 of last 6 months."""
        return self.meets_symptom_criteria and self.meets_duration_criteria

    @property
    def has_ibs_c_features(self) -> bool:
        """Predominant pain AND/OR bloating → route to IBS pathway."""
        return bool(self.abdominal_pain_predominant or self.bloating_predominant)

    @property
    def has_defecatory_dysfunction_signals(self) -> bool:
        return any([
            self.traumatic_perineal_injury,
            self.outlet_blockage_sensation,
            self.manual_maneuvers,
            self.needs_wiggle_to_defecate,
        ])

    @property
    def has_alarm_features(self) -> bool:
        return any([
            self.alarm_family_hx_colorectal_cancer,
            self.alarm_unintended_weight_loss,
            self.alarm_sudden_change_bowel_habit,
            self.alarm_blood_in_stool,
            self.alarm_iron_deficiency_anemia,
            self.alarm_anal_mass_or_irregularity,
        ])

    @property
    def active_alarms(self) -> List[str]:
        alarms = []
        if self.alarm_family_hx_colorectal_cancer:
            alarms.append("Family history (first-degree relative) of colorectal cancer")
        if self.alarm_unintended_weight_loss:
            alarms.append("Unintended weight loss >5% over 6–12 months")
        if self.alarm_sudden_change_bowel_habit:
            alarms.append("Sudden or progressive change in bowel habits")
        if self.alarm_blood_in_stool:
            alarms.append("Visible blood in stool")
        if self.alarm_iron_deficiency_anemia:
            alarms.append("Iron deficiency anemia")
        if self.alarm_anal_mass_or_irregularity:
            alarms.append("Suspicious mass or irregularity of anal canal on exam")
        return alarms

    @property
    def prucalopride_dose_mg(self) -> float:
        """
        Dose-reduce Prucalopride to 1 mg daily if:
        - Age > 65
        - CrCl < 30 mL/min
        - Severe hepatic impairment
        Otherwise standard dose is 2 mg daily.
        Has not been studied for use in men; note this flag.
        """
        reduce = (
            (self.age is not None and self.age > 65)
            or (self.crcl_ml_min is not None and self.crcl_ml_min < 30)
            or bool(self.severe_hepatic_impairment)
        )
        return 1.0 if reduce else 2.0

    @property
    def prucalopride_dose_note(self) -> Optional[str]:
        reasons = []
        if self.age is not None and self.age > 65:
            reasons.append("age >65")
        if self.crcl_ml_min is not None and self.crcl_ml_min < 30:
            reasons.append(f"CrCl {self.crcl_ml_min} mL/min (<30)")
        if self.severe_hepatic_impairment:
            reasons.append("severe hepatic impairment")
        if reasons:
            return f"Dose reduced to 1 mg (reason: {', '.join(reasons)})"
        return None


# ============================================================
# 2. DECISION AUDIT TRAIL
# ============================================================

@dataclass
class DecisionStep:
    rule: str
    inputs: Dict[str, Any]
    decision: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class DecisionTracker:
    def __init__(self):
        self.steps: List[DecisionStep] = []

    def log(self, rule: str, inputs: Dict[str, Any], decision: str) -> None:
        self.steps.append(DecisionStep(rule=rule, inputs=inputs, decision=decision))

    def summary(self) -> List[Dict[str, Any]]:
        return [s.__dict__ for s in self.steps]


# ============================================================
# 3. CLINICAL ACTIONS (Structured Output)
# ============================================================

@dataclass
class ClinicalAction:
    category: str           # e.g., "REFERRAL", "INVESTIGATION", "TREATMENT"
    urgency: str            # "URGENT", "ROUTINE", "INFO"
    description: str
    details: List[str] = field(default_factory=list)


# ============================================================
# 4. PATHWAY ENGINE
# ============================================================

class ChronicConstipationPathwayEngine:
    """
    Implements the Alberta Health Services Chronic Constipation
    Primary Care Pathway (October 2021), Boxes 1–9.
    """

    def __init__(self):
        self.tracker = DecisionTracker()

    def evaluate(self, p: ChronicConstipationPatient) -> List[ClinicalAction]:
        actions: List[ClinicalAction] = []

        # ── BOX 3: IBS-C EXCLUSION ──────────────────────────────────────
        if p.has_ibs_c_features:
            self.tracker.log(
                "Box 3 – IBS-C Screen",
                {"pain_predominant": p.abdominal_pain_predominant,
                 "bloating_predominant": p.bloating_predominant},
                "Route to IBS Pathway"
            )
            return [ClinicalAction(
                category="ROUTING",
                urgency="INFO",
                description="Route to IBS Pathway",
                details=[
                    "Patient has predominant abdominal pain and/or bloating.",
                    "This is more consistent with IBS-C (Irritable Bowel Syndrome – "
                    "Constipation predominant).",
                    "Please follow the IBS Primary Care Pathway instead.",
                ]
            )]

        # ── BOX 1: DIAGNOSTIC CRITERIA ──────────────────────────────────
        if not p.meets_symptom_criteria:
            self.tracker.log(
                "Box 1 – Symptom Count",
                {"symptom_count": p.symptom_count},
                "Does Not Meet Rome IV Symptom Criteria"
            )
            return [ClinicalAction(
                category="DIAGNOSTIC",
                urgency="INFO",
                description="Does Not Meet Rome IV Diagnostic Criteria",
                details=[
                    f"Only {p.symptom_count} of 6 Rome IV symptoms present; "
                    "≥2 are required.",
                    "Symptoms checked: ≤3 BM/week, hard/lumpy stool, straining, "
                    "incomplete evacuation, anorectal blockage, manual maneuvers.",
                ]
            )]

        if not p.meets_duration_criteria:
            self.tracker.log(
                "Box 1 – Duration",
                {"symptom_months_in_last_6": p.symptom_months_in_last_6},
                "Does Not Meet Rome IV Duration Criteria"
            )
            return [ClinicalAction(
                category="DIAGNOSTIC",
                urgency="INFO",
                description="Does Not Yet Meet Rome IV Duration Criteria",
                details=[
                    f"Symptoms present in {p.symptom_months_in_last_6} of last 6 months; "
                    "≥3 months required.",
                    "Continue monitoring; reassess when duration criterion is met.",
                ]
            )]

        self.tracker.log(
            "Box 1 – Diagnostic Criteria",
            {"symptom_count": p.symptom_count,
             "months_in_last_6": p.symptom_months_in_last_6},
            "Meets Rome IV Criteria for Chronic Constipation"
        )

        # ── BOX 4: PHYSICAL EXAM REMINDER ───────────────────────────────
        actions.append(ClinicalAction(
            category="EXAMINATION",
            urgency="INFO",
            description="Ensure Physical Examination is Complete",
            details=[
                "Abdominal exam: distention, focal discomfort, palpable mass, "
                "inguinal lymphadenopathy.",
                "Digital anorectal exam: stricture, rectal mass, irregularity "
                "of anal canal, prolapse.",
            ]
        ))

        # ── BOX 5: ALARM FEATURES ────────────────────────────────────────
        if p.has_alarm_features:
            self.tracker.log(
                "Box 5 – Alarm Features",
                {"alarms": p.active_alarms},
                "Urgent Referral Triggered"
            )
            return [ClinicalAction(
                category="REFERRAL",
                urgency=ReferralUrgency.URGENT.value,
                description="Urgent Referral: Gastroenterology / Endoscopy",
                details=[
                    "One or more alarm features identified:",
                    *[f"  • {a}" for a in p.active_alarms],
                    "Include ALL identified alarm features in the referral "
                    "form to ensure appropriate triage.",
                ]
            )]

        self.tracker.log(
            "Box 5 – Alarm Features",
            {},
            "No Alarm Features – Continue Pathway"
        )

        # ── BOX 6: SECONDARY CAUSES ──────────────────────────────────────
        actions.append(ClinicalAction(
            category="SECONDARY_CAUSES",
            urgency="ROUTINE",
            description="Optimize Management of Secondary Causes",
            details=[
                "Review full medication history including OTCs and supplements "
                "(antacids, anticholinergics, opioids, iron/calcium supplements, "
                "CCBs, antipsychotics, anticonvulsants, etc.).",
                "Assess and address underlying medical conditions "
                "(hypothyroidism, diabetes, Parkinson's, renal dysfunction, etc.).",
                "Counsel on limited physical activity, diet/fluid intake, "
                "bowel regimen (especially in elderly patients).",
            ]
        ))

        # ── DEFECATORY DYSFUNCTION FLAG ──────────────────────────────────
        if p.has_defecatory_dysfunction_signals:
            self.tracker.log(
                "Defecatory Dysfunction Screen",
                {
                    "perineal_injury": p.traumatic_perineal_injury,
                    "outlet_blockage": p.outlet_blockage_sensation,
                    "manual_maneuvers": p.manual_maneuvers,
                    "wiggle_to_defecate": p.needs_wiggle_to_defecate,
                },
                "Defecatory Dysfunction Signals Present"
            )
            actions.append(ClinicalAction(
                category="CLINICAL_NOTE",
                urgency="ROUTINE",
                description="Possible Defecatory Dysfunction (Pelvic Floor Dyssynergia)",
                details=[
                    "Signals present: traumatic perineal injury, outlet blockage "
                    "sensation, manual maneuvers, or wiggling to defecate.",
                    "Patients with defecatory dysfunction and slow-transit constipation "
                    "may respond poorly to fibre supplementation.",
                    "Complete evaluation may require specialty input: anal manometry, "
                    "defecography.",
                ]
            ))

        # ── BOX 7: BASELINE INVESTIGATIONS ──────────────────────────────
        investigation_details = [
            "There is little evidence to support routine investigations.",
            "CBC: order if not done recently.",
            "Consider: glucose, creatinine, calcium/albumin, TSH, celiac disease screen.",
        ]
        if p.age is not None and p.age >= 65:
            investigation_details.append(
                "Abdominal radiograph: may be useful in elderly patients with "
                "episodic diarrhea/fecal incontinence to rule out overflow constipation."
            )
        if p.alarm_iron_deficiency_anemia:
            investigation_details.append(
                "Order ferritin and transferrin saturation to evaluate iron stores "
                "(see Iron Primer)."
            )

        actions.append(ClinicalAction(
            category="INVESTIGATIONS",
            urgency="ROUTINE",
            description="Baseline Investigations",
            details=investigation_details
        ))

        # Celiac screen positive → refer
        if p.positive_celiac_screen:
            self.tracker.log(
                "Box 7 – Celiac Screen",
                {"positive_celiac_screen": True},
                "Referral for Positive Celiac Screen"
            )
            return actions + [ClinicalAction(
                category="REFERRAL",
                urgency=ReferralUrgency.ROUTINE.value,
                description="Referral: Positive Celiac Disease Screen",
                details=[
                    "Positive celiac disease screen identified on baseline investigations.",
                    "Refer to gastroenterology for further evaluation.",
                ]
            )]

        # ── BOX 8: MANAGEMENT – TIERED TREATMENT LADDER ─────────────────
        self.tracker.log(
            "Box 8 – Treatment Tier",
            {"tier": p.treatment_tier.name,
             "months_on_therapy": p.months_on_current_therapy},
            f"Applying Treatment Tier: {p.treatment_tier.name}"
        )

        treatment_actions = self._build_treatment_actions(p)
        actions.extend(treatment_actions)

        # ── FOLLOW-UP / MANAGEMENT FAILURE ───────────────────────────────
        if p.unsatisfactory_response:
            self.tracker.log(
                "Management Response",
                {"unsatisfactory": True,
                 "advice_consulted": p.advice_service_consulted},
                "Unsatisfactory Response – Escalation Considered"
            )
            if not p.advice_service_consulted:
                actions.append(ClinicalAction(
                    category="ADVICE",
                    urgency="ROUTINE",
                    description="Consider Specialist Advice Service Before Referring",
                    details=[
                        "Unsatisfactory response to management noted.",
                        "Pathway recommends using an advice service before formal "
                        "referral to gastroenterology.",
                        "Calgary Zone: specialistlink.ca or 403-910-2551 "
                        "(Mon–Fri 08:00–17:00; response within 1 hour).",
                        "Edmonton/North Zones: 1-844-633-2263 or pcnconnectmd.com "
                        "(Mon–Thu 09:00–18:00, Fri 09:00–16:00; response within 2 business days).",
                        "Alberta-wide: Alberta Netcare eReferral Advice Request "
                        "(response within 5 calendar days).",
                    ]
                ))
            else:
                actions.append(ClinicalAction(
                    category="REFERRAL",
                    urgency=ReferralUrgency.ROUTINE.value,
                    description="Referral: Gastroenterology (Refractory / Unsatisfactory Response)",
                    details=[
                        "Recommended strategies have not led to satisfactory symptom management.",
                        "Include in referral: all identified alarm features, important findings, "
                        "and treatment/management strategies trialed.",
                        "Management 'failure' is subjective – suggest at least 3–6 months of "
                        "titrated, multi-pronged therapy before referring.",
                    ]
                ))
        else:
            actions.append(ClinicalAction(
                category="FOLLOW_UP",
                urgency="INFO",
                description="Follow-Up: Reassess in 3–6 Months",
                details=[
                    "Management 'failure' is subjective. Suggest at least 3–6 months of "
                    "titrated, multi-pronged therapy mixing various approaches.",
                    "Patient adherence to constipation treatment tends to be low; "
                    "frequent monitoring, reinforcement, and encouragement are important.",
                    "Colonoscopy rarely explains motility disorders; avoid in the absence "
                    "of alarm features.",
                ]
            ))

        return actions

    # ── PRIVATE: TREATMENT LADDER ────────────────────────────────────

    def _build_treatment_actions(
        self, p: ChronicConstipationPatient
    ) -> List[ClinicalAction]:
        """
        Builds treatment recommendations according to tier.
        All tiers retain lifestyle advice; pharmacotherapy layers are additive.
        """
        tier = p.treatment_tier
        actions: List[ClinicalAction] = []

        # ---- TIER 0 (Naive) OR ALL TIERS: Lifestyle is always first -----
        actions.append(ClinicalAction(
            category="TREATMENT",
            urgency="ROUTINE",
            description="Step 1 – Non-Pharmacological (Lifestyle Modification)",
            details=[
                "PATIENT EDUCATION: Reassure that normal bowel frequency ranges "
                "from 3x/day to once every 2–3 days. Variability is expected.",
                "FIBRE: Target 21–38 g/day for most adults (14 g/1000 kcal). "
                "Increase slowly to avoid gas/bloating. Start at one-third dose "
                "and titrate up.",
                "  • Soluble fibre target: 5–10 g/day (psyllium, oats, barley, "
                "fruit, seeds). Soluble fibre absorbs water to form a gel that "
                "stimulates peristalsis.",
                "  • Insoluble fibre adds bulk but offers less therapeutic benefit "
                "than soluble fibre.",
                "FLUIDS: 2 L/day (females), 3 L/day (males). "
                "Fibre without adequate fluid can worsen constipation.",
                "PHYSICAL ACTIVITY: ≥20 minutes/day; aim for 150 min/week "
                "(improves defecation patterns and colonic transit time).",
                "BOWEL ROUTINE: Encourage scheduled toilet time; do not ignore "
                "the urge to defecate.",
            ]
        ))

        if tier == TreatmentTier.NAIVE:
            return actions   # Lifestyle only at this stage

        # ---- TIER 1: Add Bulk-Forming + Osmotic Laxatives ---------------
        if tier.value >= TreatmentTier.FAILED_LIFESTYLE.value:
            actions.append(ClinicalAction(
                category="TREATMENT",
                urgency="ROUTINE",
                description="Step 2 – Pharmacological: Bulk-Forming Laxatives",
                details=[
                    "First-line pharmacological option; safe for long-term use "
                    "if taken with adequate fluids (≥250 mL per dose).",
                    "NOTE: Patients with pelvic floor dysfunction or slow-transit "
                    "constipation may respond poorly to fibre supplementation.",
                    "Recommended options (take ≥2 hours apart from other medications):",
                    "  • Psyllium (Metamucil®): start low, titrate to effect "
                    "(~$20/month; not typically covered by insurance).",
                    "  • Methylcellulose (Citrucel®): 2 caplets QID – less bloating "
                    "and flatulence ($10–40/month).",
                    "  • Calcium Polycarbophil (Prodiem®): 2 caplets QID "
                    "($5–20/month).",
                    "  • Inulin (Benefibre®): 1–2 tsp TID; onset 24–48 h "
                    "($10–20/month).",
                ]
            ))
            actions.append(ClinicalAction(
                category="TREATMENT",
                urgency="ROUTINE",
                description="Step 2 – Pharmacological: Osmotic Laxatives (First-Line among Rx)",
                details=[
                    "PEG 3350 is first-line osmotic agent. Superior to lactulose for "
                    "stool frequency, form, and abdominal pain relief.",
                    "  • Polyethylene glycol (PEG 3350 / Restoralax®, Lax-A-Day®): "
                    "17 g dissolved in 250 mL liquid at night; titrate to effect "
                    "(max 34 g/day); onset 48–96 h; safe long-term ($25–50/month).",
                    "  • Lactulose: 15–30 mL daily–TID; onset 24–48 h ($10–20/month).",
                    "  • Milk of Magnesia: follow product instructions; onset 30 min–3 h. "
                    "AVOID in renal failure (risk of hypermagnesemia). Separate from "
                    "quinolones and tetracyclines ($10–20/month).",
                ]
            ))

        # ---- TIER 2: Add Stimulant Laxatives (Short-Term / Rescue) ------
        if tier.value >= TreatmentTier.FAILED_BULK_OSMOTIC.value:
            actions.append(ClinicalAction(
                category="TREATMENT",
                urgency="ROUTINE",
                description="Step 3 – Pharmacological: Stimulant Laxatives (Short-Term / Rescue)",
                details=[
                    "Second-line; appropriate for opioid-induced constipation or "
                    "short-term rescue. Prescribe for a LIMITED duration only "
                    "(long-term safety not established; risk of electrolyte disturbances).",
                    "Adverse effects: abdominal cramping, diarrhea; habituation possible.",
                    "  • Bisacodyl (Dulcolax®): 5–10 mg PO daily or PRN (onset 6–12 h); "
                    "10 mg PR daily or PRN (onset 15 min–1 h).",
                    "  • Sennosides (Senokot®): 2–4 tablets PO at bedtime "
                    "(max 8 tabs/day); onset 6–12 h. Note: discolours urine/feces.",
                ]
            ))

        # ---- TIER 3: Advanced Therapy (after ≥2 laxative classes fail) --
        if tier.value >= TreatmentTier.FAILED_STIMULANT.value:
            # Linaclotide
            actions.append(ClinicalAction(
                category="TREATMENT",
                urgency="ROUTINE",
                description="Step 4a – Advanced: Linaclotide (Constella®)",
                details=[
                    "Use when PEG and bisacodyl (traditional laxatives) have failed.",
                    "Mechanism: guanylate cyclase agonist; increases chloride/bicarbonate "
                    "secretion and intestinal transit; may reduce visceral pain.",
                    "Dose: 72–145 mcg daily, 30 minutes BEFORE first meal of day.",
                    "Adverse effects: diarrhea, upper abdominal pain.",
                    "Cost: ~$40–80/month.",
                ]
            ))
            # Prucalopride (with dose adjustment)
            dose = p.prucalopride_dose_mg
            dose_note = p.prucalopride_dose_note or "Standard dosing applies."
            gender_note = (
                "NOTE: Prucalopride has not been studied for use in men."
                if p.sex == "male" else ""
            )
            actions.append(ClinicalAction(
                category="TREATMENT",
                urgency="ROUTINE",
                description="Step 4b – Advanced: Prucalopride (Resotran®)",
                details=[
                    "Reserve for clinician with experience in chronic constipation "
                    f"when ≥2 laxative classes have failed ({p.failed_laxative_classes_count} "
                    "classes documented).",
                    "Mechanism: 5-HT₄ receptor agonist → prokinetic activity.",
                    "Less evidence for IBS-C vs. idiopathic constipation.",
                    f"Dose: {dose} mg PO daily. {dose_note}",
                    "Reduce to 1 mg daily if: age >65, CrCl <30 mL/min, or severe "
                    "hepatic impairment.",
                    "Adverse effects: nausea, diarrhea, abdominal pain, headache.",
                    "Discontinue if no benefit after 4 weeks of treatment.",
                    f"Cost: ~$120/month.",
                    *([] if not gender_note else [gender_note]),
                ]
            ))

            # Probiotics (adjunct)
            actions.append(ClinicalAction(
                category="TREATMENT",
                urgency="INFO",
                description="Adjunct: Probiotics (Limited Evidence)",
                details=[
                    "Evidence for clinical effectiveness in chronic constipation is limited "
                    "and costs may be prohibitive. Decision should be shared with patient.",
                    "Select Health Canada–licensed products. Strains with most evidence:",
                    "  • Activia®: 1 serving/day (~$64/month).",
                    "  • BioGaia® Protectis Chew Tab: 1 tablet twice/day (~$60/month).",
                    "  • Visbiome®: 1–4 sachets/day (~$99–396/month).",
                    "A one-month trial is reasonable. Probiotics have NOT been conclusively "
                    "shown to improve IBS symptoms.",
                ]
            ))

        # ---- TIER 4: Refer (Refractory) ---------------------------------
        if tier == TreatmentTier.FAILED_ADVANCED:
            return [ClinicalAction(
                category="REFERRAL",
                urgency=ReferralUrgency.ROUTINE.value,
                description="Referral: Gastroenterology (Refractory Constipation)",
                details=[
                    "Patient has failed advanced therapy (Linaclotide and/or Prucalopride).",
                    "Document in referral: failed trials of lifestyle modification, "
                    "bulk-forming laxatives, osmotic laxatives, stimulant laxatives, "
                    "and advanced agents.",
                    "Include details of duration and doses trialed.",
                ]
            )]

        return actions


# ============================================================
# 5. REPORTING / CLINICAL SUMMARY
# ============================================================

def generate_clinical_report(
    patient: ChronicConstipationPatient,
    actions: List[ClinicalAction],
    engine: ChronicConstipationPathwayEngine,
    *,
    width: int = 80
) -> str:
    """
    Returns a formatted clinical summary string for display or logging.
    """
    SEP  = "=" * width
    DSEP = "-" * width
    lines: List[str] = []

    def line(text: str = "") -> None:
        lines.append(text)

    line(SEP)
    line("  CLINICAL DECISION SUPPORT – CHRONIC CONSTIPATION PRIMARY CARE PATHWAY")
    line("  Alberta Health Services / Primary Care Networks  |  October 2021")
    line(SEP)

    # --- 1. Patient Context ---
    line()
    line("[1]  PATIENT CONTEXT")
    line(DSEP)

    age_str = str(patient.age) if patient.age is not None else "Not provided"
    sex_str = (patient.sex or "Not provided").capitalize()
    line(f"     Age / Sex            : {age_str} / {sex_str}")

    criteria_str = "MET ✓" if patient.meets_diagnostic_criteria else "NOT MET ✗"
    line(f"     Diagnostic Criteria  : {criteria_str}  "
         f"({patient.symptom_count}/6 symptoms; "
         f"{patient.symptom_months_in_last_6}/6 months)")

    ibs_str = "YES → IBS Pathway" if patient.has_ibs_c_features else "No"
    line(f"     IBS-C Features       : {ibs_str}")

    dd_str = "Signals Present" if patient.has_defecatory_dysfunction_signals else "None noted"
    line(f"     Defecatory Dysfx     : {dd_str}")

    alarm_str = (", ".join(patient.active_alarms)
                 if patient.has_alarm_features else "None")
    line(f"     Alarm Features       : {alarm_str}")

    tier_labels = {
        TreatmentTier.NAIVE:               "0 – Treatment Naive",
        TreatmentTier.FAILED_LIFESTYLE:    "1 – Failed Lifestyle/Fibre",
        TreatmentTier.FAILED_BULK_OSMOTIC: "2 – Failed Bulk/Osmotic Laxatives",
        TreatmentTier.FAILED_STIMULANT:    "3 – Failed Stimulant Laxatives",
        TreatmentTier.FAILED_ADVANCED:     "4 – Failed Advanced Therapy",
    }
    line(f"     Treatment Tier       : {tier_labels[patient.treatment_tier]}")

    months_str = (f"{patient.months_on_current_therapy} months"
                  if patient.months_on_current_therapy is not None else "Not recorded")
    line(f"     Months on Therapy    : {months_str}")

    response_str = ("Unsatisfactory" if patient.unsatisfactory_response
                    else "Ongoing / Not assessed")
    line(f"     Response Assessment  : {response_str}")

    # --- 2. Recommended Actions ---
    line()
    line("[2]  RECOMMENDED ACTIONS")
    line(DSEP)

    for i, action in enumerate(actions, 1):
        urgency_badge = f"[{action.urgency}]" if action.urgency != "INFO" else ""
        line(f"     {i}.  {urgency_badge}  {action.category}: {action.description}")
        for detail in action.details:
            line(f"          {detail}")
        line()

    # --- 3. Audit Trail ---
    line("[3]  DECISION AUDIT LOG")
    line(DSEP)

    for step in engine.tracker.steps:
        try:
            dt = datetime.fromisoformat(step.timestamp)
            ts = dt.strftime("%H:%M:%S")
        except Exception:
            ts = "??:??:??"
        line(f"     [{ts}]  {step.rule}")
        line(f"              → {step.decision}")
        if step.inputs:
            inp_str = ", ".join(f"{k}={v}" for k, v in step.inputs.items())
            line(f"              inputs: {inp_str}")
        line()

    line(SEP)
    line("  ⚠  This tool supports clinical decision-making and does not replace")
    line("     professional judgment. Always apply individual patient context.")
    line(SEP)

    return "\n".join(lines)


# ============================================================
# 6. CONVENIENCE FACTORY / INTEGRATION BRIDGE
# ============================================================

def from_master_record(master: dict) -> ChronicConstipationPatient:
    """
    Constructs a ChronicConstipationPatient from fields matching
    the MasterClinicalRecord schema (demographics, constipation,
    alarms, hematology sub-dicts).
    """
    d  = master.get("demographics", {})
    c  = master.get("constipation", {})
    al = master.get("alarms", {})
    he = master.get("hematology", {})
    ex = master.get("extras", {})

    return ChronicConstipationPatient(
        # Demographics
        age=d.get("age"),
        sex=d.get("sex"),
        crcl_ml_min=ex.get("crcl_ml_min"),
        severe_hepatic_impairment=ex.get("severe_hepatic_impairment"),
        # Constipation (MasterClinicalRecord.Constipation fields)
        bowel_movements_per_week=c.get("bowel_movements_per_week"),
        hard_lumpy_stool=c.get("hard_stools"),
        straining=c.get("straining"),
        incomplete_evacuation=c.get("incomplete_evacuation"),
        anorectal_blockage=c.get("anorectal_blockage"),
        manual_maneuvers=ex.get("manual_maneuvers"),   # extend master dict
        # Duration
        symptom_months_in_last_6=ex.get("symptom_months_in_last_6", 0),
        # IBS-C Exclusion
        abdominal_pain_predominant=c.get("bloating") if ex.get("abdominal_pain_predominant") is None
                                   else ex.get("abdominal_pain_predominant"),
        bloating_predominant=ex.get("bloating_predominant"),
        # Alarm Features (MasterClinicalRecord.AlarmFeatures)
        alarm_family_hx_colorectal_cancer=al.get("family_history_crc"),
        alarm_unintended_weight_loss=al.get("weight_loss"),
        alarm_sudden_change_bowel_habit=al.get("change_in_bowel_habit"),
        alarm_blood_in_stool=al.get("blood_in_stool"),
        alarm_iron_deficiency_anemia=al.get("iron_def_anemia"),
        alarm_anal_mass_or_irregularity=ex.get("alarm_anal_mass_or_irregularity"),
        # Hematology
        positive_celiac_screen=ex.get("positive_celiac_screen"),
        # Treatment state
        treatment_tier=ex.get("treatment_tier", TreatmentTier.NAIVE),
        months_on_current_therapy=ex.get("months_on_current_therapy"),
        unsatisfactory_response=ex.get("unsatisfactory_response"),
        failed_laxative_classes_count=ex.get("failed_laxative_classes_count", 0),
        advice_service_consulted=ex.get("advice_service_consulted"),
        # Defecatory dysfunction
        traumatic_perineal_injury=ex.get("traumatic_perineal_injury"),
        outlet_blockage_sensation=ex.get("outlet_blockage_sensation"),
        needs_wiggle_to_defecate=ex.get("needs_wiggle_to_defecate"),
    )


# ============================================================
# 7. EXAMPLE USAGE
# ============================================================

# ============================================================
# EXAMPLE USAGE  (paste each block into a separate Jupyter cell)
# ============================================================

# ------ Scenario A: New patient, meets criteria, no alarms ------
patient_a = ChronicConstipationPatient(
    age=52,
    sex="female",
    symptom_months_in_last_6=4,
    bowel_movements_per_week=2,
    hard_lumpy_stool=True,
    straining=True,
    abdominal_pain_predominant=False,
    bloating_predominant=False,
    secondary_causes_reviewed=True,
    treatment_tier=TreatmentTier.NAIVE,
)

engine_a = ChronicConstipationPathwayEngine()
actions_a = engine_a.evaluate(patient_a)
print(generate_clinical_report(patient_a, actions_a, engine_a))

# ------ Scenario B: Failed lifestyle + osmotics, no alarms, elderly ------
patient_b = ChronicConstipationPatient(
    age=71,
    sex="female",
    crcl_ml_min=28,       # dose-reduce Prucalopride
    symptom_months_in_last_6=6,
    bowel_movements_per_week=1,
    hard_lumpy_stool=True,
    straining=True,
    incomplete_evacuation=True,
    manual_maneuvers=True,
    secondary_causes_reviewed=True,
    treatment_tier=TreatmentTier.FAILED_STIMULANT,
    failed_laxative_classes_count=2,
    months_on_current_therapy=5.0,
)

engine_b = ChronicConstipationPathwayEngine()
actions_b = engine_b.evaluate(patient_b)
print(generate_clinical_report(patient_b, actions_b, engine_b))

# ------ Scenario C: Alarm feature present ------
patient_c = ChronicConstipationPatient(
    age=58,
    sex="male",
    symptom_months_in_last_6=3,
    bowel_movements_per_week=2,
    hard_lumpy_stool=True,
    alarm_blood_in_stool=True,
    alarm_unintended_weight_loss=True,
)

engine_c = ChronicConstipationPathwayEngine()
actions_c = engine_c.evaluate(patient_c)
print(generate_clinical_report(patient_c, actions_c, engine_c))
