# -*- coding: utf-8 -*-
"""
High Risk Rectal Bleeding (HRRB) Pathway Page
Modelled to exactly match the NAFLD page structure and feature set.
"""

import os
import sys
import html
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from hrrb_engine import (
    run_hrrb_pathway,
    Action,
    DataRequest,
    Stop,
    Override,
)

st.set_page_config(
    page_title="High Risk Rectal Bleeding",
    page_icon="🩸",
    layout="wide",
)


# ── HELPERS ──────────────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())


def _pretty(s: str) -> str:
    return s.replace("_", " ").title()


def build_hrrb_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# High Risk Rectal Bleeding (HRRB) Pathway — Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Patient Context")
    lines.append(f"- **Sex:** {str(patient_data.get('sex', '')).capitalize() or 'Not specified'}")
    lines.append(f"- **Visible Blood (in stool/toilet):** {'Yes' if patient_data.get('rectal_bleeding_visible') else 'No'}")
    lines.append(f"- **Not just on tissue:** {'Yes' if patient_data.get('rectal_bleeding_not_just_tissue') else 'No'}")
    lines.append(f"- **New/Worsening:** {'Yes' if patient_data.get('rectal_bleeding_new_or_worsening') else 'No'}")
    lines.append(f"- **Persistent most days:** {'Yes' if patient_data.get('rectal_bleeding_persistent') else 'No'}")
    lines.append(f"- **Duration:** {patient_data.get('rectal_bleeding_duration_weeks', '—')} weeks")
    lines.append(f"- **Complete colonoscopy <2y:** {'Yes' if patient_data.get('complete_colonoscopy_within_2y') else ('No' if patient_data.get('complete_colonoscopy_within_2y') is False else 'Unknown')}")
    lines.append(f"- **DRE Completed:** {'Yes' if patient_data.get('dre_done') else 'No'}")
    lines.append(f"- **Hemoglobin:** {patient_data.get('hemoglobin', '—')} g/L")
    lines.append(f"- **Ferritin:** {patient_data.get('ferritin', '—')} µg/L")
    lines.append("")
    lines.append("## Clinical Recommendations")
    if not outputs:
        lines.append("- No recommendations generated.")
    else:
        for o in outputs:
            if isinstance(o, Action):
                urgency = (o.urgency or "info").upper()
                label = _safe_text(o.label)
                lines.append(f"- **[{urgency}]** {label}")
                if isinstance(o.details, dict):
                    for b in o.details.get("supported_by", []):
                        lines.append(f"  - {_safe_text(b)}")
            elif isinstance(o, Stop):
                reason = _safe_text(o.reason)
                lines.append(f"- **[STOP]** {reason}")
                if getattr(o, "actions", None):
                    for a in o.actions:
                        lines.append(f"  - Follow-up: {_safe_text(a.label)}")
            elif isinstance(o, DataRequest):
                msg = _safe_text(o.message)
                missing = ", ".join(f for f in o.missing_fields)
                lines.append(f"- **[DATA NEEDED]** {msg}")
                lines.append(f"  - Missing fields: {missing}")
    lines.append("")
    lines.append("## Active Overrides")
    if overrides:
        for ov in overrides:
            lines.append(
                f"- **{_safe_text(ov.target_node)}."
                f"{_safe_text(ov.field)}** → "
                f"`{_safe_text(ov.new_value)}` "
                f"(Reason: {_safe_text(ov.reason)})"
            )
    else:
        lines.append("- No active overrides.")
    lines.append("")
    lines.append("## Clinician Notes")
    lines.append(notes.strip() if notes and notes.strip() else "No clinician notes entered.")
    lines.append("")
    return "\n".join(lines)


# ── GLOBAL CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
.ctx-card {
  background:#1e3a5f;border:1px solid #2e5c8a;
  border-radius:10px;padding:14px 18px;
  margin-bottom:14px;font-size:14px;color:#e2e8f0;
}
.ctx-card b { color:#93c5fd; }
.section-label {
  font-size:11px;font-weight:700;letter-spacing:1.2px;
  color:#94a3b8;margin-bottom:6px;margin-top:18px;
}
.action-card {
  border-radius:10px;padding:14px 18px;
  margin-bottom:12px;font-size:13.5px;line-height:1.6;
}
.action-card.urgent  { background:#3b0a0a; border-left:5px solid #ef4444; color:#fecaca; }
.action-card.semi_urgent { background:#3b2200; border-left:5px solid #f97316; color:#fed7aa; }
.action-card.routine { background:#052e16; border-left:5px solid #22c55e; color:#bbf7d0; }
.action-card.info    { background:#0c1a2e; border-left:5px solid #3b82f6; color:#bfdbfe; }
.action-card.warning { background:#2d1a00; border-left:5px solid #f59e0b; color:#fde68a; }
.action-card.stop    { background:#2d0a0a; border-left:5px solid #ef4444; color:#fecaca; }
.badge {
  display:inline-block;font-size:11px;font-weight:bold;
  padding:2px 8px;border-radius:20px;margin-right:6px;
  text-transform:uppercase;letter-spacing:0.5px;
}
.badge.urgent      { background:#ef4444;color:#fff; }
.badge.semi_urgent { background:#f97316;color:#fff; }
.badge.routine     { background:#22c55e;color:#fff; }
.badge.info        { background:#3b82f6;color:#fff; }
.badge.warning     { background:#f59e0b;color:#000; }
.badge.stop        { background:#ef4444;color:#fff; }
.override-card {
  background:#1a1a2e;border:1px dashed #6366f1;
  border-radius:8px;padding:10px 14px;margin-top:8px;
  font-size:13px;color:#c7d2fe;
}
</style>
""",
    unsafe_allow_html=True,
)

st.title("High Risk Rectal Bleeding (HRRB) Pathway")
st.markdown("---")


# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "hrrb_overrides" not in st.session_state:
    st.session_state.hrrb_overrides = []
if "hrrb_has_run" not in st.session_state:
    st.session_state.hrrb_has_run = False
if "hrrb_notes" not in st.session_state:
    st.session_state.hrrb_notes = ""


left, right = st.columns([1, 1.5])


# ═════════════════════════════════════════════════════════════════════════════
# LEFT PANEL — INPUTS
# ═════════════════════════════════════════════════════════════════════════════
with left:
    st.subheader("Patient Information")

    # ── 1. Demographics ───────────────────────────────────────────────────────
    sex = st.selectbox("Sex", ["male", "female"])

    # ── 1. HRRB Symptom Criteria ──────────────────────────────────────────────
    st.markdown("**HRRB Entry Criteria — ALL must be present**")
    st.caption(
        "Blood visibly present in/on stool OR in toilet (not just tissue paper), "
        "new onset or worsening AND persistent (most days, >2 weeks), and unexplained."
    )
    visible = st.checkbox("Blood visibly present in/on stool OR in toilet")
    not_just_tissue = st.checkbox("Bleeding NOT just on tissue paper")
    new_worsening = st.checkbox("New onset or worsening")
    persistent = st.checkbox("Persistent — present most days of the week")
    duration = st.number_input(
        "Duration of bleeding symptoms (weeks)",
        min_value=0.0, step=1.0, value=0.0,
        help="Must be >2 weeks to meet persistence criterion",
    )
    colo_2y = st.radio(
        "Complete colonoscopy within the last 2 years?",
        ["No", "Yes", "Unknown"],
        index=0,
        help="HRRB is 'unexplained' only if NO complete colonoscopy within 2 years",
    )

    # ── 2. Medical History ────────────────────────────────────────────────────
    st.markdown("**Medical History**")
    hx_personal_crc = st.checkbox("Personal history of colorectal cancer (CRC)")
    hx_family_crc = st.checkbox("First-degree family history of CRC")
    hx_personal_ibd = st.checkbox("Personal history of IBD")
    hx_family_ibd = st.checkbox("First-degree family history of IBD")
    endo_results = st.text_input(
        "Results of most recent lower endoscopy (optional)",
        placeholder="e.g. Normal colonoscopy 2022, or Polyps removed 2020",
    )

    # ── 3. Physical Exam ──────────────────────────────────────────────────────
    st.markdown("**Physical Exam — Digital Rectal Examination (DRE)**")
    dre_done = st.checkbox("DRE completed")
    dre_pain = st.checkbox(
        "DRE not possible due to pain",
        help="If DRE cannot be completed due to pain, semi-urgent referral can still proceed",
    )

    # ── 4. Baseline Investigations ────────────────────────────────────────────
    st.markdown("**Baseline Investigations (required within 8 weeks of referral)**")
    col1, col2 = st.columns(2)
    with col1:
        cbc_8w   = st.checkbox("CBC within 8 weeks", value=False)
        iron_8w  = st.checkbox("Serum Iron within 8 weeks", value=False)
        ferr_8w  = st.checkbox("Ferritin within 8 weeks", value=False)
    with col2:
        creat_8w = st.checkbox("Creatinine within 8 weeks", value=False)
        tibc_8w  = st.checkbox("TIBC within 8 weeks", value=False)

    st.markdown("**Lab Values**")
    col_a, col_b = st.columns(2)
    with col_a:
        hb_val = st.number_input(
            "Hemoglobin (g/L)", min_value=0.0, step=1.0, value=0.0,
            help="Male threshold: general <130, urgent <110 | Female: general <120, urgent <100",
        )
        ferritin_val = st.number_input(
            "Ferritin (µg/L)", min_value=0.0, step=1.0, value=0.0,
            help="Iron deficiency: Male <30 µg/L, Female <20 µg/L",
        )
    with col_b:
        baseline_hb = st.number_input(
            "Prior baseline Hemoglobin (g/L)",
            min_value=0.0, step=1.0, value=0.0,
            help="If patient previously had known anemia, enter prior Hb for comparison",
        )
        prior_anemia = st.checkbox("Prior anemia documented")

    abd_us = st.checkbox(
        "Abdominal ultrasound ordered/completed",
        help="Consider ultrasound if abdominal pain is present",
    )
    fit_ordered = st.checkbox(
        "FIT ordered or planned ⚠",
        help="FIT should NOT be ordered for patients meeting HRRB criteria",
    )

    # ── 5. Alarm Features ────────────────────────────────────────────────────
    st.markdown("**Alarm Features — Consider for Urgency Triage**")

    with st.expander("Scenario A — Urgent indicators (mass / imaging)"):
        mass_abd     = st.checkbox("Palpable abdominal mass")
        mass_rectal  = st.checkbox("Palpable rectal mass")
        lesion_img   = st.checkbox("Suspected colorectal lesion on imaging")
        mets_img     = st.checkbox("Evidence of metastases on imaging")

    with st.expander("Scenario B — Severe anemia + iron deficiency (Urgent)"):
        st.caption(
            "Urgent: Hb <110 g/L (male) or <100 g/L (female) AND iron deficiency. "
            "Computed automatically from Hb and Ferritin entered above."
        )

    with st.expander("Scenario C — Semi-urgent features"):
        abd_pain     = st.checkbox("New, persistent, or worsening abdominal pain")
        wt_loss      = st.number_input(
            "Unintentional weight loss (% over 6 months)",
            min_value=0.0, step=0.5, value=0.0,
            help="≥5% triggers Scenario C",
        )
        bowel_change = st.checkbox("Concerning change in bowel habit (frequency or consistency)")

    # ── Run / Clear ───────────────────────────────────────────────────────────
    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.hrrb_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.hrrb_overrides = []
        if "hrrb_saved_output" in st.session_state:
            del st.session_state["hrrb_saved_output"]

    override_panel = st.container()


# ═════════════════════════════════════════════════════════════════════════════
# RIGHT PANEL
# ═════════════════════════════════════════════════════════════════════════════
with right:
    if not st.session_state.hrrb_has_run:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
    else:
        # ── Build patient data dict ────────────────────────────────────────────
        colo_map = {"Yes": True, "No": False, "Unknown": None}
        patient_data = {
            "sex": sex,
            "rectal_bleeding_visible": visible or None,
            "rectal_bleeding_not_just_tissue": not_just_tissue or None,
            "rectal_bleeding_new_or_worsening": new_worsening or None,
            "rectal_bleeding_persistent": persistent or None,
            "rectal_bleeding_most_days_per_week": persistent or None,
            "rectal_bleeding_duration_weeks": float(duration) if duration > 0 else None,
            "complete_colonoscopy_within_2y": colo_map[colo_2y],
            "personal_history_crc": hx_personal_crc or None,
            "family_history_crc_first_degree": hx_family_crc or None,
            "personal_history_ibd": hx_personal_ibd or None,
            "family_history_ibd_first_degree": hx_family_ibd or None,
            "most_recent_lower_endoscopy_result": endo_results if endo_results else None,
            "dre_done": dre_done or None,
            "dre_not_possible_due_to_pain": dre_pain or None,
            "cbc_within_8_weeks": cbc_8w or None,
            "creatinine_within_8_weeks": creat_8w or None,
            "serum_iron_within_8_weeks": iron_8w or None,
            "tibc_within_8_weeks": tibc_8w or None,
            "ferritin_within_8_weeks": ferr_8w or None,
            "hemoglobin": float(hb_val) if hb_val > 0 else None,
            "baseline_hemoglobin": float(baseline_hb) if baseline_hb > 0 else None,
            "prior_anemia_documented": prior_anemia or None,
            "ferritin": float(ferritin_val) if ferritin_val > 0 else None,
            "palpable_abdominal_mass": mass_abd or None,
            "palpable_rectal_mass": mass_rectal or None,
            "suspected_colorectal_lesion_on_imaging": lesion_img or None,
            "evidence_of_metastases_on_imaging": mets_img or None,
            "abdominal_pain_new_persistent_or_worsening": abd_pain or None,
            "weight_loss_percent_6_months": float(wt_loss) if wt_loss > 0 else None,
            "concerning_change_in_bowel_habit": bowel_change or None,
            "fit_ordered_or_planned": fit_ordered or None,
        }

        outputs, logs, applied_overrides = run_hrrb_pathway(
            patient_data, overrides=st.session_state.hrrb_overrides
        )

        # ── Derive SVG state flags ─────────────────────────────────────────────
        hrrb_confirmed = any(
            isinstance(o, Action) and o.code == "HRRB_CONFIRMED" for o in outputs
        )
        hrrb_failed = any(
            isinstance(o, Stop) and (
                "not met" in o.reason.lower()
                or "high-risk rectal bleeding criteria" in o.reason.lower()
            )
            for o in outputs
        )
        dre_blocked = any(
            isinstance(o, DataRequest) and o.blocking_node == "Physical_Exam"
            for o in outputs
        )
        alarm_blocked = any(
            isinstance(o, DataRequest) and o.blocking_node == "Alarm_Features"
            for o in outputs
        )

        scenario_a_met = False
        scenario_b_met = False
        scenario_c_met = False
        for o in outputs:
            if isinstance(o, Action) and o.code == "SCENARIOS_ASSESSED":
                scenario_a_met = bool(o.details.get("scenario_a", False))
                scenario_b_met = bool(o.details.get("scenario_b", False))
                scenario_c_met = bool(o.details.get("scenario_c", False))

        assigned_urgent = any(
            isinstance(o, Action) and o.code == "ASSIGN_URGENCY_HRRB" and o.urgency == "urgent"
            for o in outputs
        )
        assigned_semi = any(
            isinstance(o, Action) and o.code == "ASSIGN_URGENCY_HRRB" and o.urgency == "semi_urgent"
            for o in outputs
        )
        no_urgency_criteria = any(
            isinstance(o, Stop) and "no urgent or semi-urgent" in o.reason.lower()
            for o in outputs
        )
        pathway_complete = any(
            isinstance(o, Stop) and "pathway complete" in o.reason.lower()
            for o in outputs
        )

        # Visited logic
        history_visited = hrrb_confirmed
        exam_visited = hrrb_confirmed and not dre_blocked
        labs_visited = exam_visited
        alarm_visited = labs_visited and not alarm_blocked
        urgency_visited = assigned_urgent or assigned_semi

        # ─────────────────────────────────────────────────────────────────────
        # SVG PATHWAY VISUAL  (faithful to the AHS HRRB pathway PDF)
        # ─────────────────────────────────────────────────────────────────────
        C_MAIN    = "#16a34a"   # visited (green)
        C_UNVISIT = "#475569"   # not reached (slate)
        C_DIAMOND = "#1d4ed8"   # decision node (blue)
        C_URGENT  = "#dc2626"   # urgent (red)
        C_SEMI    = "#f97316"   # semi-urgent (orange)
        C_EXIT    = "#d97706"   # exit / branch (amber)
        C_TEXT    = "#ffffff"
        C_DIM     = "#94a3b8"
        C_BG      = "#0f172a"

        def nc(vis, urgent=False, semi=False, exit_=False):
            if not vis:      return C_UNVISIT
            if urgent:       return C_URGENT
            if semi:         return C_SEMI
            if exit_:        return C_EXIT
            return C_MAIN

        def dc(vis):
            return C_DIAMOND if vis else C_UNVISIT

        def mid(vis, urgent=False, semi=False, exit_=False):
            if not vis:  return "ma"
            if urgent:   return "mr"
            if semi:     return "ms"
            if exit_:    return "mo"
            return "mg"

        svg = []
        W, H = 700, 960
        svg.append(
            '<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="' + str(H) + '" '
            'viewBox="0 0 ' + str(W) + ' ' + str(H) + '" '
            'style="background:' + C_BG + ';border-radius:12px;font-family:Arial,sans-serif">'
        )
        svg.append(
            "<defs>"
            '<marker id="ma" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
            '<path d="M0,0 L0,6 L9,3 z" fill="#64748b"/></marker>'
            '<marker id="mg" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
            '<path d="M0,0 L0,6 L9,3 z" fill="#16a34a"/></marker>'
            '<marker id="mr" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
            '<path d="M0,0 L0,6 L9,3 z" fill="#dc2626"/></marker>'
            '<marker id="ms" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
            '<path d="M0,0 L0,6 L9,3 z" fill="#f97316"/></marker>'
            '<marker id="mo" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
            '<path d="M0,0 L0,6 L9,3 z" fill="#d97706"/></marker>'
            "</defs>"
        )

        def svgt(x, y, text, fill, size=11, bold=False, anchor="middle"):
            w = "bold" if bold else "normal"
            svg.append(
                f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
                f'fill="{fill}" font-size="{size}" font-weight="{w}">'
                f'{html.escape(str(text))}</text>'
            )

        def rect_node(x, y, w, h, color, line1, line2="", sub="", rx=8):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            svg.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
                f'fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>'
            )
            if line2:
                svgt(x + w / 2, y + h / 2 - 8, line1, tc, 11, True)
                svgt(x + w / 2, y + h / 2 + 7, line2, tc, 11, True)
            else:
                svgt(x + w / 2, y + h / 2 + 4, line1, tc, 11, True)
            if sub:
                svgt(x + w / 2, y + h - 8, sub, tc + "99", 9)

        def diamond_node(cx, cy, w, h, color, line1, line2=""):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            hw, hh = w / 2, h / 2
            pts = f"{cx},{cy - hh} {cx + hw},{cy} {cx},{cy + hh} {cx - hw},{cy}"
            svg.append(
                f'<polygon points="{pts}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>'
            )
            if line2:
                svgt(cx, cy - 7, line1, tc, 10, True)
                svgt(cx, cy + 8, line2, tc, 10, True)
            else:
                svgt(cx, cy + 4, line1, tc, 10, True)

        def exit_node(x, y, w, h, color, line1, line2="", rx=7):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            svg.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
                f'fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>'
            )
            if line2:
                svgt(x + w / 2, y + h / 2 - 7, line1, tc, 10, True)
                svgt(x + w / 2, y + h / 2 + 7, line2, tc, 9)
            else:
                svgt(x + w / 2, y + h / 2 + 4, line1, tc, 10, True)

        def vline(x, y1, y2, vis, urgent=False, semi=False, exit_=False, label=""):
            m = mid(vis, urgent, semi, exit_)
            stroke = {
                "mg": "#16a34a", "mr": "#dc2626",
                "ms": "#f97316", "mo": "#d97706",
            }.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(
                f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" '
                f'stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>'
            )
            if label:
                svgt(x + 6, (y1 + y2) / 2 - 3, label, stroke, 10, True, "start")

        def elbow_line(x1, y1, x2, y2, vis, urgent=False, semi=False, exit_=False, label=""):
            m = mid(vis, urgent, semi, exit_)
            stroke = {
                "mg": "#16a34a", "mr": "#dc2626",
                "ms": "#f97316", "mo": "#d97706",
            }.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(
                f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" '
                f'fill="none" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>'
            )
            if label:
                svgt((x1 + x2) / 2, y1 - 5, label, stroke, 10, True)

        # ── Layout ────────────────────────────────────────────────────────────
        CX = 350
        NW, NH = 210, 50
        DW, DH = 210, 62
        EW, EH = 148, 46
        LEXT = 18
        REXT = W - 18 - EW

        Y = {
            "symptoms":   20,
            "d_hrrb":    100,
            "hx":        210,
            "exam":      302,
            "labs":      394,
            "d_alarm":   482,
            "refer":     590,
            "no_urgency": 590,
            "low_risk":  590,
        }

        # ── 1. Symptoms Entry ──────────────────────────────────────────────────
        rect_node(
            CX - NW / 2, Y["symptoms"], NW, NH,
            nc(True), "1. HRRB Symptoms Check",
            sub="Blood visible, persistent >2 wks, unexplained",
        )

        # ── HRRB Criteria diamond ──────────────────────────────────────────────
        vline(CX, Y["symptoms"] + NH, Y["d_hrrb"], True)
        diamond_node(
            CX, Y["d_hrrb"] + DH / 2, DW, DH,
            dc(True), "HRRB Criteria Met?", "(All 3 criteria)",
        )

        # Low-risk exit (left) — if criteria NOT met
        exit_node(
            LEXT, Y["d_hrrb"] + (DH - EH) / 2, EW, EH,
            nc(hrrb_failed, exit_=True), "7. Low Risk Path", "Monitor & Re-evaluate",
        )
        elbow_line(
            CX - DW / 2, Y["d_hrrb"] + DH / 2,
            LEXT + EW, Y["d_hrrb"] + (DH - EH) / 2 + EH / 2,
            hrrb_failed, exit_=True, label="No",
        )

        # ── 2. Medical History ─────────────────────────────────────────────────
        vline(CX, Y["d_hrrb"] + DH, Y["hx"], hrrb_confirmed, label="Yes")
        rect_node(
            CX - NW / 2, Y["hx"], NW, NH,
            nc(history_visited), "2. Medical History",
            sub="CRC / IBD history & prior endoscopy",
        )

        # ── 3. Physical Exam ───────────────────────────────────────────────────
        vline(CX, Y["hx"] + NH, Y["exam"], history_visited)
        rect_node(
            CX - NW / 2, Y["exam"], NW, NH,
            nc(exam_visited), "3. Physical Exam",
            sub="Digital Rectal Exam (DRE)",
        )

        # ── 4. Baseline Investigations ─────────────────────────────────────────
        vline(CX, Y["exam"] + NH, Y["labs"], exam_visited)
        rect_node(
            CX - NW / 2, Y["labs"], NW, NH,
            nc(labs_visited), "4. Baseline Investigations",
            sub="CBC, Creatinine, Fe, TIBC, Ferritin",
        )

        # ── 5. Alarm Features diamond ──────────────────────────────────────────
        vline(CX, Y["labs"] + NH, Y["d_alarm"], labs_visited)
        diamond_node(
            CX, Y["d_alarm"] + DH / 2, DW, DH,
            dc(alarm_visited), "5. Alarm Scenarios?", "(A, B, C)",
        )

        # Urgent exit — left (Scenario A or B)
        urgent_label = "6. URGENT Refer" if assigned_urgent else "Scenario A / B"
        exit_node(
            LEXT, Y["d_alarm"] + (DH - EH) / 2 + 60, EW, EH + 8,
            nc(assigned_urgent, urgent=True), "6. URGENT Refer",
            "< 2 weeks (Scenario A/B)",
        )
        elbow_line(
            CX - DW / 2, Y["d_alarm"] + DH / 2,
            LEXT + EW, Y["d_alarm"] + (DH - EH) / 2 + 60 + (EH + 8) / 2,
            assigned_urgent, urgent=True, label="A/B",
        )

        # Semi-urgent exit — right (Scenario C / DRE pain)
        exit_node(
            REXT, Y["d_alarm"] + (DH - EH) / 2 + 60, EW, EH + 8,
            nc(assigned_semi, semi=True), "6. SEMI-URGENT",
            "< 8 weeks (Scenario C)",
        )
        elbow_line(
            CX + DW / 2, Y["d_alarm"] + DH / 2,
            REXT, Y["d_alarm"] + (DH - EH) / 2 + 60 + (EH + 8) / 2,
            assigned_semi, semi=True, label="C",
        )

        # No urgency criteria — bottom
        no_urgency_y = Y["d_alarm"] + DH + 18
        exit_node(
            CX - NW / 2, no_urgency_y, NW, 44,
            nc(no_urgency_criteria, exit_=True), "No Urgency Criteria",
            "Monitor & Re-evaluate",
        )
        vline(
            CX, Y["d_alarm"] + DH, no_urgency_y,
            no_urgency_criteria, exit_=True, label="None",
        )

        # ── Referral fax info box ──────────────────────────────────────────────
        ref_y = no_urgency_y + 44 + 30
        if urgency_visited:
            urgency_col = C_URGENT if assigned_urgent else C_SEMI
            urgency_txt = "URGENT (<2 weeks)" if assigned_urgent else "SEMI-URGENT (<8 weeks)"
            svg.append(
                f'<rect x="{CX - NW / 2}" y="{ref_y}" width="{NW}" height="58" '
                f'rx="8" fill="{urgency_col}" stroke="#ffffff18" stroke-width="1.5"/>'
            )
            svgt(CX, ref_y + 16, "6. Refer for Colonoscopy", C_TEXT, 11, True)
            svgt(CX, ref_y + 32, urgency_txt, C_TEXT, 10, False)
            svgt(CX, ref_y + 48, "FAST (Edm) / GI-CAT (Cgy)", C_TEXT + "cc", 9)
            vline(
                CX, no_urgency_y + 44, ref_y,
                urgency_visited,
                urgent=assigned_urgent, semi=assigned_semi,
            )

        # ── Legend ────────────────────────────────────────────────────────────
        ly = H - 22
        lx = 14
        for col, lbl in [
            (C_MAIN, "Visited"),
            (C_DIAMOND, "Decision"),
            (C_URGENT, "Urgent"),
            (C_SEMI, "Semi-Urgent"),
            (C_EXIT, "Exit/Branch"),
            (C_UNVISIT, "Not reached"),
        ]:
            svg.append(
                f'<rect x="{lx}" y="{ly - 11}" width="12" height="12" rx="2" fill="{col}"/>'
            )
            svgt(lx + 16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 108
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            '<div style="background:' + C_BG + ';padding:10px;border-radius:14px;overflow-x:auto">'
            + "".join(svg)
            + "</div>",
            height=990,
            scrolling=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        # ── Patient context card ───────────────────────────────────────────────
        hb_display = f"{hb_val:.0f} g/L" if hb_val > 0 else "—"
        ferr_display = f"{ferritin_val:.0f} µg/L" if ferritin_val > 0 else "—"
        urgency_display = (
            "🔴 URGENT (<2 weeks)" if assigned_urgent
            else "🟠 SEMI-URGENT (<8 weeks)" if assigned_semi
            else "—"
        )
        bleeding_status = (
            "All 3 HRRB criteria met" if hrrb_confirmed
            else "Criteria NOT met" if hrrb_failed
            else "Pending"
        )

        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Sex:</b> {sex.capitalize()}</span><br>'
            f'<span><b>HRRB Criteria:</b> {bleeding_status} &nbsp;|&nbsp; '
            f'<b>Duration:</b> {duration:.0f} wks &nbsp;|&nbsp; '
            f'<b>Prior Colonoscopy &lt;2y:</b> {colo_2y}</span><br>'
            f'<span><b>Hb:</b> {hb_display} &nbsp;|&nbsp; <b>Ferritin:</b> {ferr_display}</span><br>'
            f'<span><b>DRE:</b> {"Done" if dre_done else ("Not possible — pain" if dre_pain else "Not documented")}'
            f' &nbsp;|&nbsp; <b>Urgency:</b> {urgency_display}</span><br>'
            f'<span><b>Scenarios:</b> A: {"✓" if scenario_a_met else "✗"} &nbsp;'
            f'B: {"✓" if scenario_b_met else "✗"} &nbsp;'
            f'C: {"✓" if scenario_c_met else "✗"}</span>'
            "</div>",
            unsafe_allow_html=True,
        )

        override_candidates = []

        # ── Step grouping map ──────────────────────────────────────────────────
        STEP_GROUPS = {
            "step1": {
                "label": "Step 1 — HRRB Criteria Confirmation",
                "icon": "🔍",
                "cls": "routine",
                "codes": {
                    "HRRB_CONFIRMED",
                    "NOT_HIGH_RISK_RECTAL_BLEEDING",
                },
            },
            "step2": {
                "label": "Step 2 — Medical History",
                "icon": "📋",
                "cls": "routine",
                "codes": {
                    "HISTORY_CRC_PERSONAL", "HISTORY_CRC_FAMILY",
                    "HISTORY_IBD_PERSONAL", "HISTORY_IBD_FAMILY",
                    "CAPTURE_PERSONAL_HISTORY_CRC", "CAPTURE_FAMILY_HISTORY_CRC",
                    "CAPTURE_PERSONAL_HISTORY_IBD", "CAPTURE_FAMILY_HISTORY_IBD",
                    "CAPTURE_MOST_RECENT_ENDOSCOPY_RESULT",
                },
            },
            "step3": {
                "label": "Step 3 — Physical Exam (DRE)",
                "icon": "🩺",
                "cls": "routine",
                "codes": {
                    "DRE_NOT_COMPLETED_DUE_TO_PAIN",
                    "CAPTURE_DRE_STATUS",
                },
            },
            "step4": {
                "label": "Step 4 — Baseline Investigations",
                "icon": "🩸",
                "cls": "routine",
                "codes": {
                    "UPDATE_CBC", "CHECK_CBC_DATE",
                    "UPDATE_CREATININE", "CHECK_CREATININE_DATE",
                    "UPDATE_SERUM_IRON", "CHECK_SERUM_IRON_DATE",
                    "UPDATE_TIBC", "CHECK_TIBC_DATE",
                    "UPDATE_FERRITIN", "CHECK_FERRITIN_DATE",
                    "CONSIDER_ABDOMINAL_ULTRASOUND",
                    "DO_NOT_ORDER_FIT_HRRB",
                },
            },
            "step5": {
                "label": "Step 5 — Alarm Feature Scenarios (A, B, C)",
                "icon": "⚠️",
                "cls": "routine",
                "codes": {
                    "SCENARIOS_ASSESSED",
                    "CAPTURE_HB_FERRITIN_FOR_HRRB",
                },
            },
            "step6_urgency": {
                "label": "Step 6 — Urgency Assignment",
                "icon": "🚨",
                "cls": "urgent",
                "codes": {
                    "ASSIGN_URGENCY_HRRB",
                },
            },
            "step6_referral": {
                "label": "Step 6 — Colonoscopy Referral",
                "icon": "🏥",
                "cls": "urgent",
                "codes": {
                    "REFER_COLONOSCOPY_HRRB",
                    "NO_HRRB_URGENCY_CRITERIA",
                },
            },
        }

        # Build code → group lookup
        code_to_group: dict = {}
        for gkey, gdata in STEP_GROUPS.items():
            for c in gdata["codes"]:
                code_to_group[c] = gkey

        # Classify outputs
        grouped: dict = {k: [] for k in STEP_GROUPS}
        stops_and_requests = []

        for output in outputs:
            if isinstance(output, (Stop, DataRequest)):
                stops_and_requests.append(output)
            elif isinstance(output, Action):
                gkey = code_to_group.get(output.code)
                if gkey:
                    grouped[gkey].append(output)

        # Collect override candidates from Stops
        for output in outputs:
            if isinstance(output, Stop):
                for a in output.actions:
                    if a.override_options:
                        override_candidates.append(a)

        # ── Urgency pill helper ────────────────────────────────────────────────
        def _urgency_pill() -> str:
            if assigned_urgent:
                return (
                    '<span style="background:#dc2626;color:#fff;font-size:11px;font-weight:700;'
                    'padding:3px 10px;border-radius:20px;margin-left:8px">URGENT — &lt;2 weeks</span>'
                )
            if assigned_semi:
                return (
                    '<span style="background:#f97316;color:#fff;font-size:11px;font-weight:700;'
                    'padding:3px 10px;border-radius:20px;margin-left:8px">SEMI-URGENT — &lt;8 weeks</span>'
                )
            return ""

        # ── Render a group card ────────────────────────────────────────────────
        def render_group(gkey: str, actions: list) -> None:
            if not actions:
                return
            g = STEP_GROUPS[gkey]
            cls = g["cls"]
            icon = g["icon"]
            label = g["label"]
            pill = _urgency_pill() if gkey in ("step6_urgency", "step6_referral") else ""

            # Override semi_urgent class for step6 when semi-urgent
            if gkey == "step6_urgency" and assigned_semi:
                cls = "semi_urgent"
            if gkey == "step6_referral" and assigned_semi:
                cls = "semi_urgent"

            border_colors = {
                "routine": "#22c55e", "info": "#3b82f6",
                "urgent": "#ef4444", "semi_urgent": "#f97316",
                "warning": "#f59e0b",
            }
            bg_colors = {
                "routine": "#052e16", "info": "#0c1a2e",
                "urgent": "#3b0a0a", "semi_urgent": "#3b2200",
                "warning": "#2d1a00",
            }
            border = border_colors.get(cls, "#22c55e")
            bg = bg_colors.get(cls, "#052e16")

            for a in actions:
                if a.override_options:
                    override_candidates.append(a)

            bullets = "".join(
                f'<li style="margin-bottom:5px">{html.escape(a.label)}'
                + (
                    '<span style="font-size:10px;color:#a5b4fc;margin-left:8px">'
                    "⚙ override available</span>"
                    if a.override_options
                    else ""
                )
                + "</li>"
                for a in actions
            )

            st.markdown(
                f'<div style="background:{bg};border-left:5px solid {border};'
                f'border-radius:10px;padding:14px 18px;margin-bottom:14px">'
                f'<p style="margin:0 0 10px 0;font-size:13px;font-weight:700;'
                f'color:#e2e8f0;letter-spacing:0.3px">'
                f"{icon} {html.escape(label)}{pill}</p>"
                f'<ul style="margin:0;padding-left:18px;color:#cbd5e1;'
                f'font-size:13.5px;line-height:1.7">{bullets}</ul>'
                f"</div>",
                unsafe_allow_html=True,
            )

        # ── Render blocking / stop cards ───────────────────────────────────────
        def render_stop_request(output) -> None:
            if isinstance(output, DataRequest):
                missing_str = ", ".join(_pretty(f) for f in output.missing_fields)
                msg_html = html.escape(output.message)
                st.markdown(
                    '<div style="background:#2d1a00;border-left:5px solid #f59e0b;'
                    "border-radius:10px;padding:14px 18px;margin-bottom:14px\">"
                    '<p style="margin:0 0 8px;font-size:13px;font-weight:700;color:#fde68a">'
                    "⏳ Data Required to Proceed</p>"
                    f'<p style="margin:0 0 6px;font-size:13.5px;color:#fde68a">{msg_html}</p>'
                    f'<p style="margin:0;font-size:12px;color:#94a3b8">'
                    f'Missing: <code style="color:#fbbf24">{missing_str}</code></p>'
                    "</div>",
                    unsafe_allow_html=True,
                )
            elif isinstance(output, Stop):
                reason_lower = output.reason.lower()
                is_urgent_complete    = "pathway complete" in reason_lower and assigned_urgent
                is_semi_complete      = "pathway complete" in reason_lower and assigned_semi
                is_no_hrrb           = "not met" in reason_lower or "high-risk rectal bleeding criteria" in reason_lower
                is_no_urgency        = "no urgent or semi-urgent" in reason_lower
                is_safety_stop       = "safety stop" in reason_lower

                if is_urgent_complete:
                    bg, border, icon = "#3b0a0a", "#ef4444", "🚨"
                    title = "Pathway Complete — URGENT Referral for Colonoscopy (<2 weeks)"
                    tcol = "#fecaca"
                elif is_semi_complete:
                    bg, border, icon = "#3b2200", "#f97316", "📋"
                    title = "Pathway Complete — SEMI-URGENT Referral for Colonoscopy (<8 weeks)"
                    tcol = "#fed7aa"
                elif is_no_hrrb:
                    bg, border, icon = "#2d1a00", "#f59e0b", "ℹ️"
                    title = "HRRB Criteria Not Met — Low-Risk Pathway (under development)"
                    tcol = "#fde68a"
                elif is_no_urgency:
                    bg, border, icon = "#1e2e1e", "#6366f1", "🔄"
                    title = "HRRB Present — No Urgency Scenario Identified; Monitor & Re-evaluate"
                    tcol = "#c7d2fe"
                elif is_safety_stop:
                    bg, border, icon = "#2d0a0a", "#ef4444", "⛔"
                    title = output.reason
                    tcol = "#fecaca"
                else:
                    bg, border, icon = "#1e1e2e", "#6366f1", "ℹ️"
                    title = output.reason
                    tcol = "#c7d2fe"

                action_bullets = "".join(
                    f'<li style="margin-bottom:5px">{html.escape(a.label)}'
                    + (
                        '<span style="font-size:10px;color:#a5b4fc;margin-left:8px">'
                        "⚙ override available</span>"
                        if a.override_options
                        else ""
                    )
                    + "</li>"
                    for a in output.actions
                )
                action_block = (
                    f'<ul style="margin:10px 0 0;padding-left:18px;color:#cbd5e1;'
                    f"font-size:13.5px;line-height:1.7\">{action_bullets}</ul>"
                    if action_bullets
                    else ""
                )
                st.markdown(
                    f'<div style="background:{bg};border-left:5px solid {border};'
                    f"border-radius:10px;padding:14px 18px;margin-bottom:14px\">"
                    f'<p style="margin:0 0 {"6px" if action_block else "0"};font-size:13px;'
                    f'font-weight:700;color:{tcol}">{icon} {html.escape(title)}</p>'
                    f"{action_block}</div>",
                    unsafe_allow_html=True,
                )

        # ── Render everything ──────────────────────────────────────────────────
        st.markdown('<p class="section-label">RECOMMENDED ACTIONS</p>', unsafe_allow_html=True)

        # Blocking DataRequests first
        for o in stops_and_requests:
            if isinstance(o, DataRequest):
                render_stop_request(o)

        # Grouped action steps in order
        for gkey in STEP_GROUPS:
            render_group(gkey, grouped[gkey])

        # Terminal stops last
        for o in stops_and_requests:
            if isinstance(o, Stop):
                render_stop_request(o)

        # ── Clinician Notes ────────────────────────────────────────────────────
        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.caption("Optional free-text notes to be attached to the clinical recommendations.")
        st.session_state.hrrb_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.hrrb_notes,
            height=180,
        )

        # ── Save / Download ────────────────────────────────────────────────────
        def _serialize_output(o):
            if isinstance(o, Action):
                return {"type": "action", "code": o.code, "label": o.label, "urgency": o.urgency}
            if isinstance(o, Stop):
                return {"type": "stop", "reason": o.reason, "urgency": getattr(o, "urgency", None)}
            if isinstance(o, DataRequest):
                return {"type": "data_request", "message": o.message, "missing_fields": o.missing_fields}
            return {"type": "other", "repr": repr(o)}

        full_output = {
            "patient_context": patient_data,
            "clinical_recommendations": {
                "engine_outputs": [_serialize_output(o) for o in outputs],
                "overrides": [
                    {
                        "node": o.target_node,
                        "field": o.field,
                        "new_value": o.new_value,
                        "reason": o.reason,
                        "created_at": o.created_at.isoformat(),
                    }
                    for o in st.session_state.hrrb_overrides
                ],
                "clinician_notes": st.session_state.hrrb_notes,
            },
        }

        if st.button("💾 Save this output", key="hrrb_save_output"):
            st.session_state.hrrb_saved_output = {
                "saved_at": datetime.now().isoformat(),
                "payload": full_output,
            }
            st.success("Output saved for this session.")

        if "hrrb_saved_output" in st.session_state:
            md_text = build_hrrb_markdown(
                patient_data=patient_data,
                outputs=outputs,
                overrides=st.session_state.hrrb_overrides,
                notes=st.session_state.hrrb_notes,
            )
            st.download_button(
                label="⬇️ Download Markdown summary",
                data=md_text.encode("utf-8"),
                file_name="hrrb_summary.md",
                mime="text/markdown",
                key="hrrb_download_md",
            )

        # ── Override Panel ─────────────────────────────────────────────────────
        with override_panel:
            if override_candidates:
                st.markdown("---")
                st.markdown(
                    '<p class="section-label">CLINICIAN OVERRIDES</p>',
                    unsafe_allow_html=True,
                )
                st.caption(
                    "Override engine decisions where clinical judgement differs. "
                    "A documented reason is required for each override."
                )

                for a in override_candidates:
                    opt = a.override_options
                    raw_node = opt["node"]
                    raw_field = opt["field"]
                    node = _pretty(raw_node)
                    field = _pretty(raw_field)
                    allowed = opt.get("allowed", [True, False])

                    with st.expander(f"⚙️ Override: **{node}** → `{field}`"):
                        preview = a.label[:120] + ("…" if len(a.label) > 120 else "")
                        st.markdown(
                            f'<div class="override-card">Engine decision based on: <b>{html.escape(preview)}</b></div>',
                            unsafe_allow_html=True,
                        )
                        existing = next(
                            (
                                o
                                for o in st.session_state.hrrb_overrides
                                if o.target_node == raw_node and o.field == raw_field
                            ),
                            None,
                        )
                        current_val = existing.new_value if existing else None
                        new_val = st.radio(
                            f"Set `{field}` to:",
                            options=allowed,
                            index=allowed.index(current_val) if current_val in allowed else 0,
                            key=f"ov_val_{raw_node}_{raw_field}",
                            horizontal=True,
                        )
                        reason = st.text_input(
                            "Reason (required):",
                            value=existing.reason if existing else "",
                            key=f"ov_reason_{raw_node}_{raw_field}",
                            placeholder="Document clinical rationale...",
                        )
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button(
                                "✅ Apply Override",
                                key=f"ov_apply_{raw_node}_{raw_field}",
                            ):
                                if not reason.strip():
                                    st.error("A reason is required to apply an override.")
                                else:
                                    st.session_state.hrrb_overrides = [
                                        o
                                        for o in st.session_state.hrrb_overrides
                                        if not (
                                            o.target_node == raw_node
                                            and o.field == raw_field
                                        )
                                    ]
                                    st.session_state.hrrb_overrides.append(
                                        Override(
                                            target_node=raw_node,
                                            field=raw_field,
                                            old_value=None,
                                            new_value=new_val,
                                            reason=reason.strip(),
                                        )
                                    )
                                    st.success(
                                        "Override applied. Click **▶ Run Pathway** to re-evaluate."
                                    )
                        with col2:
                            if existing and st.button(
                                "🗑 Remove Override",
                                key=f"ov_remove_{raw_node}_{raw_field}",
                            ):
                                st.session_state.hrrb_overrides = [
                                    o
                                    for o in st.session_state.hrrb_overrides
                                    if not (
                                        o.target_node == raw_node
                                        and o.field == raw_field
                                    )
                                ]
                                st.success("Override removed.")

                if st.session_state.hrrb_overrides:
                    st.markdown(
                        '<p class="section-label">ACTIVE OVERRIDES</p>',
                        unsafe_allow_html=True,
                    )
                    for o in st.session_state.hrrb_overrides:
                        st.markdown(
                            '<div class="override-card">'
                            f"🛠 <b>{html.escape(_pretty(o.target_node))}</b> → "
                            f"<code>{html.escape(_pretty(o.field))}</code>"
                            f" set to <b>{html.escape(str(o.new_value))}</b><br>"
                            f'<span style="color:#a5b4fc">Reason: {html.escape(o.reason)}</span><br>'
                            f'<span style="color:#64748b;font-size:11px">'
                            f"Applied: {o.created_at.strftime('%H:%M:%S')}</span>"
                            "</div>",
                            unsafe_allow_html=True,
                        )

        # ── Decision Audit Log ─────────────────────────────────────────────────
        with st.expander("📋 Decision Audit Log"):
            for log in logs:
                try:
                    ts = datetime.fromisoformat(log.timestamp).strftime("%H:%M:%S")
                except Exception:
                    ts = "—"
                st.markdown(f"**[{ts}] {log.node}** → _{log.decision}_")
                if log.used_inputs:
                    st.caption(
                        "  ".join(
                            f"`{k}={v}`"
                            for k, v in log.used_inputs.items()
                            if v is not None
                        )
                    )
