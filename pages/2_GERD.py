import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components
from gerd_engine import (
    run_gerd_pathway, Action, DataRequest, Stop, Override,
)

st.set_page_config(page_title="GERD", page_icon="🔥", layout="wide")

# ── MARKDOWN HELPER ──────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())


def build_gerd_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# GERD Pathway – Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Patient Context")
    lines.append(f"- **Age / Sex:** {patient_data.get('age')} / {str(patient_data.get('sex','—')).capitalize()}")
    lines.append(f"- **Heartburn:** {patient_data.get('predominant_heartburn')}")
    lines.append(f"- **Regurgitation:** {patient_data.get('predominant_regurgitation')}")
    lines.append(f"- **Symptoms per week:** {patient_data.get('symptoms_per_week', '—')}")
    lines.append(f"- **GERD symptom years:** {patient_data.get('gerd_symptom_years', '—')}")
    lines.append(f"- **Known Barrett's:** {patient_data.get('known_barretts_esophagus', False)}")
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
                    for b in o.details.get("bullets", []):
                        lines.append(f"  - {_safe_text(b)}")
                    for n in o.details.get("notes", []):
                        lines.append(f"  - Note: {_safe_text(n)}")
                    for s in o.details.get("supported_by", []):
                        lines.append(f"  - Support: {_safe_text(s)}")
                    skip = {"bullets", "notes", "supported_by"}
                    for k, v in o.details.items():
                        if k in skip:
                            continue
                        if isinstance(v, list) and v:
                            for item in v:
                                lines.append(f"  - {_safe_text(k).replace('_',' ').title()}: {_safe_text(item)}")
                        elif v not in (None, False, "", []):
                            lines.append(f"  - {_safe_text(k).replace('_',' ').title()}: {_safe_text(v)}")
            elif isinstance(o, Stop):
                lines.append(f"- **[STOP]** {_safe_text(o.reason)}")
                if getattr(o, "actions", None):
                    for a in o.actions:
                        lines.append(f"  - Follow-up: {_safe_text(a.label)}")
            elif isinstance(o, DataRequest):
                missing = ", ".join(o.missing_fields)
                lines.append(f"- **[DATA NEEDED]** {_safe_text(o.message)}")
                lines.append(f"  - Missing fields: {missing}")
                if getattr(o, "suggested_actions", None):
                    for a in o.suggested_actions:
                        lines.append(f"  - Suggested action: {_safe_text(a.label)}")

    lines.append("")
    lines.append("## Active Overrides")
    if overrides:
        for ov in overrides:
            lines.append(
                f"- **{_safe_text(ov.target_node)}.{_safe_text(ov.field)}** -> "
                f"`{_safe_text(ov.new_value)}` (Reason: {_safe_text(ov.reason)})"
            )
    else:
        lines.append("- No active overrides.")
    lines.append("")

    lines.append("## Clinician Notes")
    lines.append(notes.strip() if notes and notes.strip() else "No clinician notes entered.")
    lines.append("")

    return "\n".join(lines)


# ── GLOBAL CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
.ctx-card {
    background: #1e3a5f; border: 1px solid #2e5c8a;
    border-radius: 10px; padding: 14px 18px;
    margin-bottom: 14px; font-size: 14px; color: #e2e8f0;
}
.ctx-card b { color: #93c5fd; }
.section-label {
    font-size: 11px; font-weight: 700; letter-spacing: 1.2px;
    color: #94a3b8; margin-bottom: 6px; margin-top: 18px;
}
.action-card {
    border-radius: 10px; padding: 14px 18px;
    margin-bottom: 12px; font-size: 13.5px; line-height: 1.6;
}
.action-card.urgent  { background:#3b0a0a; border-left:5px solid #ef4444; color:#fecaca; }
.action-card.routine { background:#052e16; border-left:5px solid #22c55e; color:#bbf7d0; }
.action-card.info    { background:#0c1a2e; border-left:5px solid #3b82f6; color:#bfdbfe; }
.action-card.warning { background:#2d1a00; border-left:5px solid #f59e0b; color:#fde68a; }
.action-card.stop    { background:#2d0a0a; border-left:5px solid #ef4444; color:#fecaca; }
.action-card h4 { margin:0 0 6px 0; font-size:14px; }
.action-card ul { margin:6px 0 0 16px; padding:0; }
.action-card li { margin-bottom:3px; }
.badge {
    display:inline-block; font-size:11px; font-weight:bold;
    padding:2px 8px; border-radius:20px; margin-right:6px;
    text-transform:uppercase; letter-spacing:0.5px;
}
.badge.urgent  { background:#ef4444; color:#fff; }
.badge.routine { background:#22c55e; color:#fff; }
.badge.info    { background:#3b82f6; color:#fff; }
.badge.warning { background:#f59e0b; color:#000; }
.badge.stop    { background:#ef4444; color:#fff; }
.override-card {
    background:#1a1a2e; border:1px dashed #6366f1;
    border-radius:8px; padding:10px 14px; margin-top:8px;
    font-size:13px; color:#c7d2fe;
}
</style>
""", unsafe_allow_html=True)

st.title("🔥 GERD Pathway")
st.markdown("---")

# ── SESSION STATE ────────────────────────────────────────────────────────────
if "gerd_overrides" not in st.session_state:
    st.session_state.gerd_overrides = []
if "gerd_has_run" not in st.session_state:
    st.session_state.gerd_has_run = False
if "gerd_notes" not in st.session_state:
    st.session_state.gerd_notes = ""

left, right = st.columns([1, 1.5])

# ── LEFT PANEL ───────────────────────────────────────────────────────────────
with left:
    st.subheader("Patient Information")

    age = st.number_input("Age", 1, 120, 52)
    sex = st.selectbox("Sex", ["male", "female"])

    st.markdown("**1. Suspected GERD — Entry Symptoms**")
    predominant_heartburn = st.checkbox("Predominant heartburn")
    predominant_regurgitation = st.checkbox("Predominant regurgitation")
    dominant_chest_pain = st.checkbox("Chest pain is a dominant feature")

    st.markdown("**2. Dyspepsia Screen**")
    predominant_epigastric_pain = st.checkbox("Predominant epigastric pain / discomfort")
    predominant_upper_abdominal_bloating = st.checkbox("Upper abdominal distension or bloating")

    st.markdown("**3. Alarm Features**")
    actively_bleeding_now = st.checkbox("⚠ Active / acute GI bleeding NOW")
    al_weight_loss = st.checkbox("Unintended weight loss >5% (over 6–12 months)")
    al_dysphagia = st.checkbox("Progressive dysphagia")
    al_odynophagia = st.checkbox("Odynophagia (painful swallowing)")
    al_vomiting = st.checkbox("Persistent vomiting (not cannabis-related)")
    al_gi_bleed = st.checkbox("Black stool or blood in vomit")
    al_ida = st.checkbox("Iron deficiency anemia")
    al_mass = st.checkbox("Abdominal mass")

    st.markdown("**4. Barrett's Esophagus Risk**")
    gerd_symptom_years_sel = st.selectbox(
        "GERD symptom duration",
        ["Unknown / <5 years", "5–10 years", ">10 years"],
    )
    gerd_symptom_years_map = {"Unknown / <5 years": None, "5–10 years": 6, ">10 years": 11}

    symptoms_per_week_sel = st.selectbox(
        "Symptom frequency per week",
        ["Unknown", "<1 (infrequent)", "1–1.9 (weekly)", "≥2 (frequent)"],
    )
    spw_map = {"Unknown": None, "<1 (infrequent)": 0.5, "1–1.9 (weekly)": 1.0, "≥2 (frequent)": 2.0}

    caucasian = st.checkbox("Caucasian")
    current_or_history_smoking = st.checkbox("Current or past tobacco smoking")
    family_hx_barretts = st.checkbox("Family history (1st degree) of Barrett's or esophageal cancer")
    history_of_sleeve_gastrectomy = st.checkbox("History of sleeve gastrectomy")
    known_barretts_esophagus = st.checkbox("Known Barrett's esophagus")
    barretts_screen_positive = st.checkbox("Barrett's screening test already positive")

    st.markdown("**Waist Measurements** *(for central obesity assessment)*")
    waist_cm_input = st.number_input("Waist circumference (cm) — 0 = not measured", 0.0, 250.0, 0.0, step=0.5)
    waist_cm = waist_cm_input if waist_cm_input > 0 else None
    whr_input = st.number_input("Waist-hip ratio — 0 = not measured", 0.0, 3.0, 0.0, step=0.01)
    whr = whr_input if whr_input > 0 else None

    st.markdown("**5. Non-Pharmacological Therapy**")
    st.caption("Non-pharmacological counselling is always recommended (smoking, diet, weight, meal timing).")

    st.markdown("**6. Pharmacological Therapy**")
    ppi_od_done_sel = st.selectbox(
        "Once-daily PPI trial (4–8 weeks)",
        ["Not yet started", "Completed"],
    )
    ppi_od_done = ppi_od_done_sel == "Completed"

    ppi_od_response = None
    ppi_adherence_correct = None
    ppi_adherence_adequate = None
    ppi_bid_done = None
    ppi_bid_response = None

    if ppi_od_done:
        ppi_od_resp_sel = st.selectbox(
            "Response to once-daily PPI",
            ["Unknown", "Adequate (symptoms resolved)", "Inadequate"],
        )
        ppi_od_response_map = {
            "Unknown": None,
            "Adequate (symptoms resolved)": True,
            "Inadequate": False,
        }
        ppi_od_response = ppi_od_response_map[ppi_od_resp_sel]

        if ppi_od_response is False:
            st.markdown("*PPI adherence check (before escalating):*")
            ppi_adherence_correct = st.checkbox("PPI taken correctly — 30 min before breakfast", value=True)
            ppi_adherence_adequate = st.checkbox("Patient adherence to daily PPI adequate", value=True)

            ppi_bid_done_sel = st.selectbox(
                "Twice-daily (BID) PPI trial (4–8 weeks)",
                ["Not yet started", "Completed"],
                key="ppi_bid_done_sel",
            )
            ppi_bid_done = ppi_bid_done_sel == "Completed"

            if ppi_bid_done:
                ppi_bid_resp_sel = st.selectbox(
                    "Response to BID PPI",
                    ["Unknown", "Adequate (symptoms resolved)", "Inadequate"],
                )
                ppi_bid_response_map = {
                    "Unknown": None,
                    "Adequate (symptoms resolved)": True,
                    "Inadequate": False,
                }
                ppi_bid_response = ppi_bid_response_map[ppi_bid_resp_sel]

    st.markdown("**7. Maintenance / Deprescribing**")
    symptoms_resolved_sel = st.selectbox(
        "Symptoms resolved after PPI?",
        ["Unknown", "Yes", "No"],
    )
    symptoms_resolved_map = {"Unknown": None, "Yes": True, "No": False}
    symptoms_resolved = symptoms_resolved_map[symptoms_resolved_sel]

    symptoms_return_sel = st.selectbox(
        "Symptoms returned after taper/stop?",
        ["Unknown", "Yes", "No"],
    )
    symptoms_return_map = {"Unknown": None, "Yes": True, "No": False}
    symptoms_return = symptoms_return_map[symptoms_return_sel]

    st.markdown("**8. Overall Management Response**")
    unsat_sel = st.selectbox(
        "Overall response to GERD pharmacologic therapy",
        ["Unknown", "Satisfactory", "Unsatisfactory"],
    )
    unsat_map = {"Unknown": None, "Satisfactory": False, "Unsatisfactory": True}
    unsatisfactory_response = unsat_map[unsat_sel]

    advice_considered = None
    if unsatisfactory_response is True:
        advice_considered = st.checkbox("Advice service already consulted / considered")

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.gerd_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.gerd_overrides = []
        if "gerd_saved_output" in st.session_state:
            del st.session_state["gerd_saved_output"]
        st.rerun()

    override_panel = st.container()

# ── RIGHT PANEL ──────────────────────────────────────────────────────────────
with right:
    if st.session_state.gerd_has_run:

        patient_data = {
            "age": age,
            "sex": sex,
            # Entry
            "predominant_heartburn": predominant_heartburn or None,
            "predominant_regurgitation": predominant_regurgitation or None,
            "dominant_chest_pain": dominant_chest_pain or None,
            # Dyspepsia
            "predominant_epigastric_pain": predominant_epigastric_pain or None,
            "predominant_upper_abdominal_bloating": predominant_upper_abdominal_bloating or None,
            # Alarm
            "actively_bleeding_now": actively_bleeding_now or None,
            "unintended_weight_loss": al_weight_loss or None,
            "progressive_dysphagia": al_dysphagia or None,
            "odynophagia": al_odynophagia or None,
            "persistent_vomiting": al_vomiting or None,
            "black_stool_or_blood_in_vomit": al_gi_bleed or None,
            "iron_deficiency_anemia_present": al_ida or None,
            "abdominal_mass": al_mass or None,
            # Barrett's
            "gerd_symptom_years": gerd_symptom_years_map[gerd_symptom_years_sel],
            "symptoms_per_week": spw_map[symptoms_per_week_sel],
            "caucasian": caucasian or None,
            "current_or_history_smoking": current_or_history_smoking or None,
            "family_history_barretts_or_esophageal_cancer_first_degree": family_hx_barretts or None,
            "history_of_sleeve_gastrectomy": history_of_sleeve_gastrectomy or None,
            "known_barretts_esophagus": known_barretts_esophagus or None,
            "barretts_screen_positive": barretts_screen_positive or None,
            "waist_circumference_cm": waist_cm,
            "waist_hip_ratio": whr,
            # Pharmacologic
            "ppi_once_daily_trial_done": ppi_od_done if ppi_od_done else None,
            "ppi_once_daily_response_adequate": ppi_od_response,
            "ppi_taken_correctly_before_breakfast": ppi_adherence_correct,
            "ppi_adherence_adequate": ppi_adherence_adequate,
            "ppi_bid_trial_done": ppi_bid_done,
            "ppi_bid_response_adequate": ppi_bid_response,
            # Maintenance
            "symptoms_resolved_after_ppi": symptoms_resolved,
            "symptoms_return_after_taper": symptoms_return,
            # Management response
            "unsatisfactory_response_to_pharmacologic_therapy": unsatisfactory_response,
            "advice_service_considered": advice_considered or None,
        }

        outputs, logs, applied_overrides = run_gerd_pathway(
            patient_data, overrides=st.session_state.gerd_overrides
        )

        # ── Pathway state flags for the SVG flowchart ──────────────────────
        gerd_entry_met = any(
            isinstance(o, Action) and o.code == "GERD_ENTRY_MET" for o in outputs
        )
        is_dyspepsia_stop = any(
            isinstance(o, Stop) and "dyspeptic" in o.reason.lower() for o in outputs
        )
        has_alarm = any(
            isinstance(o, Stop) and "alarm" in o.reason.lower() for o in outputs
        ) or any(
            isinstance(o, Action) and o.code == "URGENT_ENDOSCOPY_REFERRAL" for o in outputs
        )
        barretts_refer = any(
            isinstance(o, Stop) and "barrett" in o.reason.lower() for o in outputs
        )
        went_non_pharm = any(
            isinstance(o, Action) and o.code == "COUNSEL_SMOKING_CESSATION" for o in outputs
        )
        went_pharm = any(
            isinstance(o, Action) and o.code in {
                "H2RA_OR_ANTACID_PRN", "START_PPI_ONCE_DAILY",
                "OPTIMIZE_PPI_BID", "PPI_ONCE_DAILY_SUCCESS",
            } for o in outputs
        )
        mild_branch = any(
            isinstance(o, Action) and o.code == "H2RA_OR_ANTACID_PRN" for o in outputs
        )
        ppi_od_success = any(
            isinstance(o, Action) and o.code == "PPI_ONCE_DAILY_SUCCESS" for o in outputs
        )
        ppi_bid_action = any(
            isinstance(o, Action) and o.code == "OPTIMIZE_PPI_BID" for o in outputs
        )
        ppi_bid_success = any(
            isinstance(o, Action) and o.code == "PPI_BID_SUCCESS" for o in outputs
        )
        went_maintenance = any(
            isinstance(o, Action) and o.code in {
                "TITRATE_TO_LOWEST_EFFECTIVE_PPI", "PPI_MAINTENANCE",
                "KNOWN_BARRETTS_LIFETIME_PPI",
            } for o in outputs
        )
        pathway_complete = any(
            isinstance(o, Stop) and "complete" in o.reason.lower() for o in outputs
        )
        refer_final = any(
            isinstance(o, Stop) and "failed gerd" in o.reason.lower() or
            (isinstance(o, Stop) and "consultation/endoscopy" in o.reason.lower()
             and "alarm" not in o.reason.lower() and "barrett" not in o.reason.lower())
            for o in outputs
        )
        active_bleeding_stop = any(
            isinstance(o, Stop) and "bleeding" in o.reason.lower() for o in outputs
        )

        # ── SVG FLOWCHART ───────────────────────────────────────────────────
        C_MAIN = "#16a34a"; C_UNVISIT = "#475569"; C_DIAMOND = "#1d4ed8"
        C_URGENT = "#dc2626"; C_EXIT = "#d97706"
        C_TEXT = "#ffffff"; C_DIM = "#94a3b8"; C_BG = "#0f172a"

        def nc(vis, urgent=False, exit_=False):
            if not vis:
                return C_UNVISIT
            if urgent:
                return C_URGENT
            if exit_:
                return C_EXIT
            return C_MAIN

        def dc(vis):
            return C_DIAMOND if vis else C_UNVISIT

        def mid(vis, urgent=False, exit_=False):
            if not vis:
                return "ma"
            if urgent:
                return "mr"
            if exit_:
                return "mo"
            return "mg"

        svg = []
        W, H = 700, 1080
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
            '<marker id="mo" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
            '<path d="M0,0 L0,6 L9,3 z" fill="#d97706"/></marker>'
            "</defs>"
        )

        def svgt(x, y, text, fill, size=11, bold=False, anchor="middle"):
            w = "bold" if bold else "normal"
            svg.append(
                f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
                f'fill="{fill}" font-size="{size}" font-weight="{w}">{html.escape(str(text))}</text>'
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
            pts = f"{cx},{cy-hh} {cx+hw},{cy} {cx},{cy+hh} {cx-hw},{cy}"
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

        def vline(x, y1, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(
                f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" '
                f'stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>'
            )
            if label:
                svgt(x + 6, (y1 + y2) / 2 - 3, label, stroke, 10, True, "start")

        def elbow_line(x1, y1, x2, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(
                f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" '
                f'fill="none" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>'
            )
            if label:
                svgt((x1 + x2) / 2, y1 - 5, label, stroke, 10, True)

        # Layout constants
        CX = 350; NW, NH = 180, 50; DW, DH = 188, 58; EW, EH = 142, 46
        LEXT = 24; REXT = W - 24 - EW

        Y = {
            "entry":    18,
            "d_dysp":   95,
            "d_alarm":  200,
            "d_barre":  310,
            "non_ph":   410,
            "d_freq":   490,
            "mild":     580,
            "ppi_od":   580,
            "ppi_bid":  670,
            "d_maint":  760,
            "maint":    855,
            "d_mgmt":   955,
        }

        # ── NODE 1: Suspected GERD entry ──
        rect_node(CX - NW / 2, Y["entry"], NW, NH,
                  nc(True), "1. Suspected GERD",
                  sub="Heartburn / Regurgitation")
        vline(CX, Y["entry"] + NH, Y["d_dysp"], True)

        # ── NODE 2: Dyspepsia screen diamond ──
        diamond_node(CX, Y["d_dysp"] + DH / 2, DW, DH,
                     dc(gerd_entry_met or is_dyspepsia_stop),
                     "2. Dyspepsia?",
                     "Epigastric / bloating?")
        dysp_vis = is_dyspepsia_stop
        exit_node(REXT, Y["d_dysp"] + (DH - EH) / 2, EW, EH,
                  nc(dysp_vis, exit_=True), "→ Dyspepsia", "Pathway")
        elbow_line(CX + DW / 2, Y["d_dysp"] + DH / 2,
                   REXT, Y["d_dysp"] + (DH - EH) / 2 + EH / 2,
                   dysp_vis, exit_=True, label="Yes")

        v_past_dysp = gerd_entry_met and not is_dyspepsia_stop
        vline(CX, Y["d_dysp"] + DH, Y["d_alarm"], v_past_dysp, label="No")

        # ── NODE 3: Alarm features diamond ──
        diamond_node(CX, Y["d_alarm"] + DH / 2, DW, DH,
                     dc(v_past_dysp),
                     "3. Alarm", "Features?")
        alarm_exit_vis = has_alarm and v_past_dysp
        exit_node(REXT, Y["d_alarm"] + (DH - EH) / 2, EW, EH,
                  nc(alarm_exit_vis or active_bleeding_stop, urgent=True),
                  "⚠ Refer", "GI / Endoscopy")
        elbow_line(CX + DW / 2, Y["d_alarm"] + DH / 2,
                   REXT, Y["d_alarm"] + (DH - EH) / 2 + EH / 2,
                   alarm_exit_vis or active_bleeding_stop, urgent=True, label="Yes")

        v_past_alarm = v_past_dysp and not has_alarm and not active_bleeding_stop
        vline(CX, Y["d_alarm"] + DH, Y["d_barre"], v_past_alarm, label="No")

        # ── NODE 4: Barrett's risk diamond ──
        diamond_node(CX, Y["d_barre"] + DH / 2, DW, DH,
                     dc(v_past_alarm),
                     "4. Barrett's", "Risk Assessment")
        barrett_exit_vis = barretts_refer and v_past_alarm
        exit_node(REXT, Y["d_barre"] + (DH - EH) / 2, EW, EH,
                  nc(barrett_exit_vis, exit_=True),
                  "High Risk", "→ Refer / Screen")
        elbow_line(CX + DW / 2, Y["d_barre"] + DH / 2,
                   REXT, Y["d_barre"] + (DH - EH) / 2 + EH / 2,
                   barrett_exit_vis, exit_=True, label="High")

        v_past_barre = v_past_alarm and not barretts_refer
        vline(CX, Y["d_barre"] + DH, Y["non_ph"], v_past_barre, label="No")

        # ── NODE 5: Non-pharmacological therapy ──
        rect_node(CX - NW / 2, Y["non_ph"], NW, NH,
                  nc(went_non_pharm),
                  "5. Non-Pharmacological",
                  sub="Lifestyle / Diet / Smoking")
        vline(CX, Y["non_ph"] + NH, Y["d_freq"], went_non_pharm)

        # ── NODE 6: Symptom frequency diamond ──
        diamond_node(CX, Y["d_freq"] + DH / 2, DW, DH,
                     dc(went_pharm or went_non_pharm),
                     "6. Pharmacological",
                     "Symptoms ≥2×/week?")

        # Mild branch – left exit
        exit_node(LEXT, Y["mild"] + 2, EW, EH,
                  nc(mild_branch, exit_=True), "H2RA /", "Antacids PRN")
        elbow_line(CX - DW / 2, Y["d_freq"] + DH / 2,
                   LEXT + EW, Y["mild"] + EH / 2,
                   mild_branch, exit_=True, label="<2×")

        # PPI once-daily box (right side of freq diamond)
        PPI_X = CX + DW / 2 + 8
        PPI_W = 120
        ppi_od_vis = went_pharm and not mild_branch
        svg.append(
            f'<rect x="{PPI_X}" y="{Y["ppi_od"]}" width="{PPI_W}" height="{NH}" rx="7" '
            f'fill="{nc(ppi_od_vis)}" stroke="#ffffff18" stroke-width="1.5"/>'
        )
        tc_pod = C_TEXT if ppi_od_vis else C_DIM
        svgt(PPI_X + PPI_W / 2, Y["ppi_od"] + NH / 2 - 6, "PPI Once Daily", tc_pod, 10, True)
        svgt(PPI_X + PPI_W / 2, Y["ppi_od"] + NH / 2 + 8, "4–8 weeks", tc_pod, 9)
        if went_pharm and not mild_branch:
            m_pod = "mg"
            stroke_pod = "#16a34a"
            svg.append(
                f'<polyline points="{CX+DW/2},{Y["d_freq"]+DH/2} {PPI_X},{Y["d_freq"]+DH/2} {PPI_X},{Y["ppi_od"]}" '
                f'fill="none" stroke="{stroke_pod}" stroke-width="2" marker-end="url(#{m_pod})"/>'
            )
            svgt(PPI_X - 24, Y["d_freq"] + DH / 2 - 5, "≥2×", stroke_pod, 10, True)

        # PPI BID box (below ppi_od)
        ppi_bid_vis = ppi_bid_action
        svg.append(
            f'<rect x="{PPI_X}" y="{Y["ppi_bid"]}" width="{PPI_W}" height="{NH}" rx="7" '
            f'fill="{nc(ppi_bid_vis)}" stroke="#ffffff18" stroke-width="1.5"/>'
        )
        tc_pbid = C_TEXT if ppi_bid_vis else C_DIM
        svgt(PPI_X + PPI_W / 2, Y["ppi_bid"] + NH / 2 - 6, "Optimize PPI", tc_pbid, 10, True)
        svgt(PPI_X + PPI_W / 2, Y["ppi_bid"] + NH / 2 + 8, "BID 4–8 wks", tc_pbid, 9)
        # connect ppi_od to ppi_bid
        m_bid = mid(ppi_bid_vis)
        stroke_bid = {"mg": "#16a34a"}.get(m_bid, "#64748b")
        dash_bid = "" if ppi_bid_vis else 'stroke-dasharray="5,3"'
        svg.append(
            f'<line x1="{PPI_X + PPI_W / 2}" y1="{Y["ppi_od"] + NH}" '
            f'x2="{PPI_X + PPI_W / 2}" y2="{Y["ppi_bid"]}" '
            f'stroke="{stroke_bid}" stroke-width="2" {dash_bid} marker-end="url(#{m_bid})"/>'
        )
        if ppi_bid_vis:
            svgt(PPI_X + PPI_W / 2 + 6, (Y["ppi_od"] + NH + Y["ppi_bid"]) / 2 - 3,
                 "Inadequate", stroke_bid, 9, False, "start")

        # ── NODE 7: Maintenance / deprescribing ──
        vline(CX, Y["d_freq"] + DH, Y["d_maint"], went_maintenance)
        rect_node(CX - NW / 2, Y["d_maint"], NW, NH,
                  nc(went_maintenance),
                  "7. Maintenance /",
                  "Deprescribing",
                  sub="Lowest dose · Annual taper")

        # Arrow from ppi_od success to maintenance (elbow from right side)
        if ppi_od_success or ppi_bid_success:
            m_mnt = "mg"
            stroke_mnt = "#16a34a"
            src_y = Y["ppi_od"] + NH if ppi_od_success else Y["ppi_bid"] + NH
            tgt_x = CX - NW / 2
            tgt_y = Y["d_maint"] + NH / 2
            svg.append(
                f'<polyline points="{PPI_X},{src_y} {PPI_X},{tgt_y} {tgt_x},{tgt_y}" '
                f'fill="none" stroke="{stroke_mnt}" stroke-width="2" marker-end="url(#{m_mnt})"/>'
            )
            svgt(PPI_X - 6, (src_y + tgt_y) / 2, "Resolved", stroke_mnt, 9, False, "end")

        # ── NODE 8: Management response ──
        vline(CX, Y["d_maint"] + NH, Y["d_mgmt"],
              went_maintenance or pathway_complete or refer_final)
        rect_node(CX - NW / 2, Y["d_mgmt"], NW, NH,
                  nc(went_maintenance or pathway_complete or refer_final),
                  "8. Management", "Response",
                  sub="Satisfactory?")

        complete_vis = pathway_complete
        exit_node(LEXT, Y["d_mgmt"] + (NH - EH) // 2, EW, EH,
                  nc(complete_vis, exit_=True), "✓ Complete", "Patient Medical Home")
        elbow_line(CX - NW / 2, Y["d_mgmt"] + NH / 2,
                   LEXT + EW, Y["d_mgmt"] + (NH - EH) // 2 + EH / 2,
                   complete_vis, exit_=True, label="Yes")

        refer_vis = refer_final
        exit_node(REXT, Y["d_mgmt"] + (NH - EH) // 2, EW, EH,
                  nc(refer_vis, urgent=True), "Refer", "Consultation / Scope")
        elbow_line(CX + NW / 2, Y["d_mgmt"] + NH / 2,
                   REXT, Y["d_mgmt"] + (NH - EH) // 2 + EH / 2,
                   refer_vis, urgent=True, label="Unsat.")

        # ── Legend ──
        ly = H - 20; lx = 18
        for col, lbl in [
            (C_MAIN, "Visited"), (C_DIAMOND, "Decision"),
            (C_URGENT, "Urgent"), (C_EXIT, "Exit/Off-ramp"), (C_UNVISIT, "Not reached"),
        ]:
            svg.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx + 16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 110
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            '<div style="background:' + C_BG + ';padding:10px;border-radius:14px;overflow-x:auto">'
            + "".join(svg) + "</div>",
            height=1100, scrolling=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        # ── Patient context card ──
        alarm_fields = [
            ("unintended_weight_loss", "Weight loss >5%"),
            ("progressive_dysphagia", "Dysphagia"),
            ("odynophagia", "Odynophagia"),
            ("persistent_vomiting", "Vomiting"),
            ("black_stool_or_blood_in_vomit", "GI bleed signs"),
            ("iron_deficiency_anemia_present", "IDA"),
            ("abdominal_mass", "Abdominal mass"),
            ("actively_bleeding_now", "Active bleeding"),
        ]
        active_alarms = [label for key, label in alarm_fields if patient_data.get(key)]
        alarm_str = ", ".join(active_alarms) if active_alarms else "None"

        spw_display = spw_map[symptoms_per_week_sel]
        spw_str = f"{spw_display}×/week" if spw_display is not None else "Unknown"

        barretts_str = "Known Barrett's – lifetime PPI" if known_barretts_esophagus else (
            "Positive screen – refer" if barretts_screen_positive else "Not indicated / not screened"
        )

        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>Symptom Frequency:</b> {spw_str}'
            f' &nbsp;|&nbsp; <b>Duration:</b> {gerd_symptom_years_sel}</span><br>'
            f'<span><b>Alarm Features:</b> {alarm_str}</span><br>'
            f'<span><b>Barrett\'s Status:</b> {barretts_str}</span><br>'
            f'<span><b>Overall Response:</b> {unsat_sel}</span>'
            "</div>",
            unsafe_allow_html=True,
        )

        override_candidates = []

        # ── Render helpers ──
        def _detail_html(details) -> str:
            if not details:
                return ""
            items = ""
            if isinstance(details, dict):
                for bullet in details.get("bullets", []):
                    items += f"<li>{html.escape(str(bullet))}</li>"
                for note in details.get("notes", []):
                    items += f'<li style="color:#fde68a">⚠️ {html.escape(str(note))}</li>'
                for src in details.get("supported_by", []):
                    items += f"<li>📌 {html.escape(str(src))}</li>"
                skip = {"bullets", "notes", "supported_by"}
                for k, v in details.items():
                    if k in skip:
                        continue
                    if isinstance(v, list) and v:
                        items += "".join(f"<li>{html.escape(str(i))}</li>" for i in v)
                    elif v not in (None, False, "", []):
                        items += f"<li><b>{html.escape(str(k))}:</b> {html.escape(str(v))}</li>"
            elif isinstance(details, list):
                items = "".join(f"<li>{html.escape(str(d))}</li>" for d in details if str(d).strip())
            return f'<ul style="margin:6px 0 0 16px;padding:0">{items}</ul>' if items else ""

        def render_action(a: Action, extra_cls: str = "") -> None:
            urgency_to_cls = {
                "urgent": "urgent", "warning": "warning",
                None: "routine", "": "routine",
            }
            cls = urgency_to_cls.get(a.urgency or "", "routine")
            if extra_cls:
                cls = extra_cls
            badge_label = (a.urgency or "info").upper()
            label_html = html.escape(a.label).replace("\n   ", "<br>&nbsp;&nbsp;&nbsp;").replace("\n", "<br>")
            detail_html = _detail_html(a.details)
            override_html = (
                '<p style="margin:6px 0 0;font-size:11px;color:#a5b4fc">'
                "🔒 Override available — reason required</p>"
                if a.override_options else ""
            )
            st.markdown(
                f'<div class="action-card {cls}">'
                f'<h4><span class="badge {cls}">{badge_label}</span> {label_html}</h4>'
                f"{detail_html}{override_html}"
                "</div>",
                unsafe_allow_html=True,
            )
            if a.override_options:
                override_candidates.append(a)

        st.markdown('<p class="section-label">RECOMMENDED ACTIONS</p>', unsafe_allow_html=True)

        for output in outputs:
            if isinstance(output, Action):
                render_action(output)
            elif isinstance(output, DataRequest):
                missing_str = ", ".join(f"`{f}`" for f in output.missing_fields)
                msg_html = html.escape(output.message).replace("\n", "<br>")
                st.markdown(
                    '<div class="action-card warning">'
                    f'<h4><span class="badge warning">DATA NEEDED</span>'
                    f' ⏳ {msg_html}</h4>'
                    f'<ul><li>Missing fields: {missing_str}</li></ul>'
                    "</div>",
                    unsafe_allow_html=True,
                )
                for sa in output.suggested_actions:
                    render_action(sa, extra_cls="info")
            elif isinstance(output, Stop):
                reason_html = html.escape(output.reason).replace("\n   ", "<br>&nbsp;&nbsp;&nbsp;").replace("\n", "<br>")
                st.markdown(
                    '<div class="action-card stop">'
                    f'<h4><span class="badge stop">STOP</span>'
                    f' 🛑 {reason_html}</h4>'
                    "</div>",
                    unsafe_allow_html=True,
                )
                for a in output.actions:
                    render_action(a)

        # ── Clinician Notes ──
        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.caption("Optional free-text notes to be attached to the clinical recommendations.")
        st.session_state.gerd_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.gerd_notes,
            height=180,
        )

        # ── Save / Download ──
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
                    for o in st.session_state.gerd_overrides
                ],
                "clinician_notes": st.session_state.gerd_notes,
            },
        }

        if st.button("💾 Save this output", key="gerd_save_output"):
            st.session_state.gerd_saved_output = {
                "saved_at": datetime.now().isoformat(),
                "payload": full_output,
            }
            st.success("Output saved for this session.")

        if "gerd_saved_output" in st.session_state:
            md_text = build_gerd_markdown(
                patient_data=patient_data,
                outputs=outputs,
                overrides=st.session_state.gerd_overrides,
                notes=st.session_state.gerd_notes,
            )
            st.download_button(
                label="⬇️ Download Markdown summary",
                data=md_text.encode("utf-8"),
                file_name="gerd_summary.md",
                mime="text/markdown",
                key="gerd_download_md",
            )

        # ── Overrides panel ──
        def _pretty(s: str) -> str:
            return s.replace("_", " ").title()

        with override_panel:
            if override_candidates:
                st.markdown("---")
                st.markdown('<p class="section-label">CLINICIAN OVERRIDES</p>', unsafe_allow_html=True)
                st.caption(
                    "Override engine decisions where clinical judgement differs. "
                    "A documented reason is required for each override."
                )

                for a in override_candidates:
                    opt = a.override_options
                    raw_node = opt["node"]
                    raw_field = opt["field"]
                    node_lbl = _pretty(raw_node)
                    field_lbl = _pretty(raw_field)
                    allowed = opt.get("allowed", [True, False])

                    with st.expander(f"⚙️ Override: **{node_lbl}** → `{field_lbl}`"):
                        preview = a.label[:120] + ("…" if len(a.label) > 120 else "")
                        st.markdown(
                            f'<div class="override-card">Engine decision based on: <b>{html.escape(preview)}</b></div>',
                            unsafe_allow_html=True,
                        )
                        existing = next(
                            (o for o in st.session_state.gerd_overrides
                             if o.target_node == raw_node and o.field == raw_field),
                            None,
                        )
                        current_val = existing.new_value if existing else None
                        new_val = st.radio(
                            f"Set `{field_lbl}` to:",
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
                            if st.button("✅ Apply Override", key=f"ov_apply_{raw_node}_{raw_field}"):
                                if not reason.strip():
                                    st.error("A reason is required to apply an override.")
                                else:
                                    st.session_state.gerd_overrides = [
                                        o for o in st.session_state.gerd_overrides
                                        if not (o.target_node == raw_node and o.field == raw_field)
                                    ]
                                    st.session_state.gerd_overrides.append(
                                        Override(
                                            target_node=raw_node,
                                            field=raw_field,
                                            old_value=None,
                                            new_value=new_val,
                                            reason=reason.strip(),
                                        )
                                    )
                                    st.success("Override applied. Click **▶ Run Pathway** to re-evaluate.")
                        with col2:
                            if existing and st.button("🗑 Remove Override", key=f"ov_remove_{raw_node}_{raw_field}"):
                                st.session_state.gerd_overrides = [
                                    o for o in st.session_state.gerd_overrides
                                    if not (o.target_node == raw_node and o.field == raw_field)
                                ]
                                st.success("Override removed.")

                if st.session_state.gerd_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.gerd_overrides:
                        st.markdown(
                            '<div class="override-card">'
                            f'🛠 <b>{html.escape(_pretty(o.target_node))}</b> → '
                            f'<code>{html.escape(_pretty(o.field))}</code>'
                            f' set to <b>{html.escape(str(o.new_value))}</b><br>'
                            f'<span style="color:#a5b4fc">Reason: {html.escape(o.reason)}</span><br>'
                            f'<span style="color:#64748b;font-size:11px">'
                            f'Applied: {o.created_at.strftime("%H:%M:%S")}</span>'
                            "</div>",
                            unsafe_allow_html=True,
                        )

        # ── Audit log ──
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
                            f"`{k}={v}`" for k, v in log.used_inputs.items() if v is not None
                        )
                    )
    else:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
