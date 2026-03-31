import os, sys
import html
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components

# Import from the GERD engine
from gerd_engine import (
    run_gerd_pathway, Action, DataRequest, Stop, Override
)

st.set_page_config(page_title="GERD", layout="wide")

# ── MARKDOWN EXPORT HELPER ───────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())

def build_gerd_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# GERD Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Patient Context")
    lines.append(f"- **Age / Sex:** {patient_data.get('age', 'N/A')} / {str(patient_data.get('sex', 'N/A')).capitalize()}")
    
    # Core symptoms
    hb = "Yes" if patient_data.get("predominant_heartburn") else "No"
    rg = "Yes" if patient_data.get("predominant_regurgitation") else "No"
    lines.append(f"- **Predominant Heartburn:** {hb}")
    lines.append(f"- **Predominant Regurgitation:** {rg}")
    
    freq = patient_data.get("symptoms_per_week")
    lines.append(f"- **Symptom frequency:** {_safe_text(freq) + ' times/week' if freq is not None else 'Unknown'}")
    
    # Alarms
    alarms = [
        ("actively_bleeding_now", "Active bleeding"),
        ("unintended_weight_loss", "Unintended weight loss"),
        ("progressive_dysphagia", "Progressive dysphagia"),
        ("odynophagia", "Odynophagia"),
        ("persistent_vomiting", "Persistent vomiting"),
        ("black_stool_or_blood_in_vomit", "Black stool / blood in vomit"),
        ("iron_deficiency_anemia_present", "Iron deficiency anemia"),
        ("abdominal_mass", "Abdominal mass")
    ]
    active_alarms = [lbl for k, lbl in alarms if patient_data.get(k)]
    lines.append(f"- **Alarm Features:** {', '.join(active_alarms) if active_alarms else 'None reported'}")
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

                    skip = {"bullets", "notes", "supported_by", "regimen_key"}
                    for k, v in o.details.items():
                        if k in skip:
                            continue
                        if isinstance(v, list):
                            for item in v:
                                lines.append(f"  - {_safe_text(k).replace('_', ' ').title()}: {_safe_text(item)}")
                        elif v not in (None, False, "", []):
                            lines.append(f"  - {_safe_text(k).replace('_', ' ').title()}: {_safe_text(v)}")

            elif isinstance(o, Stop):
                reason = _safe_text(o.reason)
                lines.append(f"- **[STOP]** {reason}")
                if getattr(o, "actions", None):
                    for a in o.actions:
                        lines.append(f"  - Follow-up: {_safe_text(a.label)}")

            elif isinstance(o, DataRequest):
                msg = _safe_text(o.message)
                missing = ", ".join(field for field in o.missing_fields)
                lines.append(f"- **[DATA NEEDED]** {msg}")
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

st.title(" Gastroesophageal Reflux Disease (GERD) Pathway")
st.markdown("---")

# ── SESSION STATE ────────────────────────────────────────────────────────────
if "gerd_overrides" not in st.session_state:
    st.session_state.gerd_overrides = []

if "gerd_has_run" not in st.session_state:
    st.session_state.gerd_has_run = False

if "gerd_notes" not in st.session_state:
    st.session_state.gerd_notes = ""

left, right = st.columns([1, 1.5])

# ── LEFT PANEL (INPUTS) ──────────────────────────────────────────────────────
with left:
    st.subheader("Patient Information")
    
    st.markdown("**Demographics & Metrics**")
    colA, colB = st.columns(2)
    with colA:
        age = st.number_input("Age", 1, 120, 52)
        sex = st.selectbox("Sex", ["male", "female"])
        caucasian = st.checkbox("Caucasian")
    with colB:
        waist_cm = st.number_input("Waist Circumference (cm)", 0, 250, 0)
        waist_hip = st.number_input("Waist-Hip Ratio", 0.0, 2.0, 0.0, step=0.1)

    st.markdown("**GERD Symptoms**")
    pred_heartburn = st.checkbox("Predominant Heartburn")
    pred_regurgitation = st.checkbox("Predominant Regurgitation")
    dom_chest_pain = st.checkbox("Dominant Chest Pain (Requires Cardiac Excl.)")
    
    st.markdown("**Dyspepsia Symptoms**")
    pred_epigastric = st.checkbox("Predominant Epigastric Pain/Discomfort")
    pred_bloating = st.checkbox("Predominant Upper Abdominal Bloating")

    st.markdown("**Chronicity & Frequency**")
    symptom_years = st.number_input("Duration of GERD Symptoms (Years)", 0, 80, 0)
    freq_sel = st.selectbox("Symptoms Frequency (Times per Week)", ["Unknown", "0-1 times/week", "2 or more times/week"])
    freq_val = None
    if freq_sel == "0-1 times/week":
        freq_val = 1
    elif freq_sel == "2 or more times/week":
        freq_val = 3

    st.markdown("**Barrett's Esophagus Risk Factors**")
    hx_smoking = st.checkbox("Current or past history of tobacco smoking")
    fh_cancer = st.checkbox("Family history (1st-degree) Barrett's / Esophageal Cancer")
    hx_sleeve = st.checkbox("History of sleeve gastrectomy")
    known_barretts = st.checkbox("Already has known Barrett's esophagus")
    pos_screen = st.checkbox("Recent Barrett's screening was positive")

    st.markdown("**Alarm Features**")
    al_bleed_now = st.checkbox("Actively bleeding now (Urgent)")
    al_weight_loss = st.checkbox("Unintended weight loss (> 5% over 6-12 months)")
    al_dysphagia = st.checkbox("Progressive dysphagia")
    al_odynophagia = st.checkbox("Odynophagia (painful swallowing)")
    al_vomiting = st.checkbox("Persistent vomiting (not cannabis use)")
    al_gi_bleed = st.checkbox("Black stool or blood in vomit")
    al_ida = st.checkbox("Iron deficiency anemia")
    al_mass = st.checkbox("Abdominal mass")

    st.markdown("**Pharmacologic Therapy History**")
    
    def tri_state(label):
        val = st.selectbox(label, ["Unknown/Not Attempted", "Yes", "No"])
        if val == "Yes": return True
        if val == "No": return False
        return None

    ppi_once_trial = tri_state("Trialed PPI Once Daily for 4-8 weeks?")
    ppi_once_resp = tri_state("Was response adequate to Once Daily PPI?")
    ppi_correct = tri_state("PPI taken correctly (30 min before breakfast)?")
    ppi_adherence = tri_state("Adequate adherence to PPI?")
    ppi_bid_trial = tri_state("Trialed Optimized PPI Twice Daily (BID)?")
    ppi_bid_resp = tri_state("Was response adequate to BID PPI?")
    ppi_resolved = tri_state("Did symptoms resolve fully after PPI use?")
    ppi_return = tri_state("Did symptoms return after deprescribing taper?")
    unsat_resp = tri_state("Overall unsatisfactory response to pharmacologic therapy?")
    advice_used = tri_state("Has advice service been considered/used?")

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.gerd_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.gerd_overrides = []
        if "gerd_saved_output" in st.session_state:
            del st.session_state["gerd_saved_output"]
        st.rerun()

    override_panel = st.container()

# ── RIGHT PANEL (OUTPUTS & FLOWCHART) ────────────────────────────────────────
with right:
    if st.session_state.gerd_has_run:
        
        # Build payload mapping to engine
        patient_data = {
            "age": age,
            "sex": sex,
            "waist_circumference_cm": waist_cm if waist_cm > 0 else None,
            "waist_hip_ratio": waist_hip if waist_hip > 0.0 else None,
            "caucasian": caucasian,
            "gerd_symptom_years": symptom_years if symptom_years > 0 else None,
            "symptoms_per_week": freq_val,
            "current_or_history_smoking": hx_smoking,
            "family_history_barretts_or_esophageal_cancer_first_degree": fh_cancer,
            "predominant_heartburn": pred_heartburn,
            "predominant_regurgitation": pred_regurgitation,
            "dominant_chest_pain": dom_chest_pain,
            "predominant_epigastric_pain": pred_epigastric,
            "predominant_upper_abdominal_bloating": pred_bloating,
            "actively_bleeding_now": al_bleed_now,
            "unintended_weight_loss": al_weight_loss,
            "progressive_dysphagia": al_dysphagia,
            "odynophagia": al_odynophagia,
            "persistent_vomiting": al_vomiting,
            "black_stool_or_blood_in_vomit": al_gi_bleed,
            "iron_deficiency_anemia_present": al_ida,
            "abdominal_mass": al_mass,
            "known_barretts_esophagus": known_barretts,
            "barretts_screen_positive": pos_screen,
            "history_of_sleeve_gastrectomy": hx_sleeve,
            "ppi_once_daily_trial_done": ppi_once_trial,
            "ppi_once_daily_response_adequate": ppi_once_resp,
            "ppi_taken_correctly_before_breakfast": ppi_correct,
            "ppi_adherence_adequate": ppi_adherence,
            "ppi_bid_trial_done": ppi_bid_trial,
            "ppi_bid_response_adequate": ppi_bid_resp,
            "symptoms_resolved_after_ppi": ppi_resolved,
            "symptoms_return_after_taper": ppi_return,
            "unsatisfactory_response_to_pharmacologic_therapy": unsat_resp,
            "advice_service_considered": advice_used,
        }

        outputs, logs, applied_overrides = run_gerd_pathway(
            patient_data, overrides=st.session_state.gerd_overrides
        )

        # ── SVG FLOWCHART LOGIC ──
        # Determine paths logically to light up flowchart
        has_gerd = pred_heartburn or pred_regurgitation
        is_dyspepsia = pred_epigastric or pred_bloating
        has_alarm = any([al_bleed_now, al_weight_loss, al_dysphagia, al_odynophagia, al_vomiting, al_gi_bleed, al_ida, al_mass])
        
        path_gerd = True
        path_dysp = has_gerd
        path_alarm = path_dysp and not is_dyspepsia
        path_barrett = path_alarm and not has_alarm
        path_nonpharm = path_barrett and not pos_screen
        path_pharm = path_nonpharm # Assumed passes through non-pharm
        
        # Colors & styling matching H. pylori page
        C_MAIN = "#16a34a"; C_UNVISIT = "#475569"; C_DIAMOND = "#1d4ed8"
        C_URGENT = "#dc2626"; C_EXIT = "#d97706"
        C_TEXT = "#ffffff"; C_DIM = "#94a3b8"; C_BG = "#0f172a"

        def nc(vis, urgent=False, exit_=False):
            if not vis: return C_UNVISIT
            if urgent: return C_URGENT
            if exit_: return C_EXIT
            return C_MAIN

        def dc(vis):
            return C_DIAMOND if vis else C_UNVISIT

        def mid(vis, urgent=False, exit_=False):
            if not vis: return "ma"
            if urgent: return "mr"
            if exit_: return "mo"
            return "mg"

        svg = []
        W, H = 700, 850
        svg.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{H}" '
            f'viewBox="0 0 {W} {H}" style="background:{C_BG};border-radius:12px;font-family:Arial,sans-serif">'
        )
        svg.append(
            "<defs>"
            '<marker id="ma" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#64748b"/></marker>'
            '<marker id="mg" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#16a34a"/></marker>'
            '<marker id="mr" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#dc2626"/></marker>'
            '<marker id="mo" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#d97706"/></marker>'
            "</defs>"
        )

        def svgt(x, y, text, fill, size=11, bold=False, anchor="middle"):
            w = "bold" if bold else "normal"
            svg.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="{fill}" font-size="{size}" font-weight="{w}">{html.escape(str(text))}</text>')

        def rect_node(x, y, w, h, color, line1, line2="", sub="", rx=8):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>')
            if line2:
                svgt(x+w/2, y+h/2-8, line1, tc, 11, True)
                svgt(x+w/2, y+h/2+7, line2, tc, 11, True)
            else:
                svgt(x+w/2, y+h/2+4, line1, tc, 11, True)
            if sub:
                svgt(x+w/2, y+h-8, sub, tc+"99", 9)

        def diamond_node(cx, cy, w, h, color, line1, line2=""):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            hw, hh = w/2, h/2
            pts = f"{cx},{cy-hh} {cx+hw},{cy} {cx},{cy+hh} {cx-hw},{cy}"
            svg.append(f'<polygon points="{pts}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>')
            if line2:
                svgt(cx, cy-7, line1, tc, 10, True)
                svgt(cx, cy+8, line2, tc, 10, True)
            else:
                svgt(cx, cy+4, line1, tc, 10, True)

        def exit_node(x, y, w, h, color, line1, line2="", rx=7):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>')
            if line2:
                svgt(x+w/2, y+h/2-7, line1, tc, 10, True)
                svgt(x+w/2, y+h/2+7, line2, tc, 9)
            else:
                svgt(x+w/2, y+h/2+4, line1, tc, 10, True)

        def vline(x, y1, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>')
            if label:
                svgt(x+6, (y1+y2)/2-3, label, stroke, 10, True, "start")

        def elbow_line(x1, y1, x2, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" fill="none" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>')
            if label:
                svgt((x1+x2)/2, y1-5, label, stroke, 10, True)

        CX = 350; NW, NH = 180, 50; DW, DH = 180, 58; EW, EH = 140, 46
        LEXT = 30; REXT = W - 30 - EW
        Y = {
            "start": 20, "d_gerd": 100, "d_dysp": 200, "d_alarm": 300,
            "barretts": 400, "nonpharm": 500, "pharm": 600, "mgt": 700
        }

        # Flow starts
        rect_node(CX-NW/2, Y["start"], NW, NH, nc(True), "Patient Presents", "Heartburn/Regurgitation")
        vline(CX, Y["start"]+NH, Y["d_gerd"], True)
        
        # 1. Suspected GERD
        diamond_node(CX, Y["d_gerd"]+DH/2, DW, DH, dc(True), "1. Suspected GERD?")
        v_not_gerd = not has_gerd
        exit_node(LEXT, Y["d_gerd"]+(DH-EH)/2, EW, EH, nc(v_not_gerd, exit_=True), "No", "Not GERD Pathway")
        elbow_line(CX-DW/2, Y["d_gerd"]+DH/2, LEXT+EW, Y["d_gerd"]+(DH-EH)/2+EH/2, v_not_gerd, exit_=True, label="No")

        vline(CX, Y["d_gerd"]+DH, Y["d_dysp"], path_dysp, label="Yes")
        
        # 2. Dyspepsia
        diamond_node(CX, Y["d_dysp"]+DH/2, DW, DH, dc(path_dysp), "2. Dyspepsia", "Predominant?")
        v_is_dysp = path_dysp and is_dyspepsia
        exit_node(REXT, Y["d_dysp"]+(DH-EH)/2, EW, EH, nc(v_is_dysp, exit_=True), "Yes", "→ Dyspepsia Pathway")
        elbow_line(CX+DW/2, Y["d_dysp"]+DH/2, REXT, Y["d_dysp"]+(DH-EH)/2+EH/2, v_is_dysp, exit_=True, label="Yes")

        vline(CX, Y["d_dysp"]+DH, Y["d_alarm"], path_alarm, label="No")
        
        # 3. Alarm Features
        diamond_node(CX, Y["d_alarm"]+DH/2, DW, DH, dc(path_alarm), "3. Alarm Features?")
        v_has_alarm = path_alarm and has_alarm
        exit_node(REXT, Y["d_alarm"]+(DH-EH)/2, EW, EH, nc(v_has_alarm, urgent=True), "Yes", "→ Urgent Endoscopy")
        elbow_line(CX+DW/2, Y["d_alarm"]+DH/2, REXT, Y["d_alarm"]+(DH-EH)/2+EH/2, v_has_alarm, urgent=True, label="Yes")

        vline(CX, Y["d_alarm"]+DH, Y["barretts"], path_barrett, label="No")

        # 4. Barrett's Risk
        rect_node(CX-NW/2, Y["barretts"], NW, NH, nc(path_barrett), "4. Barrett's Risk", "Assessment")
        exit_node(LEXT, Y["barretts"]+(NH-EH)/2, EW, EH, nc(pos_screen, urgent=True), "High Risk / Pos", "→ Endoscopy")
        elbow_line(CX-NW/2, Y["barretts"]+NH/2, LEXT+EW, Y["barretts"]+(NH-EH)/2+EH/2, pos_screen, urgent=True, label="Yes")

        vline(CX, Y["barretts"]+NH, Y["nonpharm"], path_nonpharm)

        # 5. Non-Pharm
        rect_node(CX-NW/2, Y["nonpharm"], NW, NH, nc(path_nonpharm), "5. Non-Pharmacological", "Therapy")
        vline(CX, Y["nonpharm"]+NH, Y["pharm"], path_pharm, label="Ineffective")

        # 6. Pharmacological
        rect_node(CX-NW/2, Y["pharm"], NW, NH, nc(path_pharm), "6. Pharmacological", "Therapy (H2RA/PPI)")
        vline(CX, Y["pharm"]+NH, Y["mgt"], path_pharm)

        # 7. Management Response
        diamond_node(CX, Y["mgt"]+DH/2, DW, DH, dc(path_pharm), "7. Response / Mgt", "Adequate?")
        v_unsat = path_pharm and unsat_resp is True
        exit_node(REXT, Y["mgt"]+(DH-EH)/2, EW, EH, nc(v_unsat, exit_=True), "Unsatisfactory", "Refer / Advice")
        elbow_line(CX+DW/2, Y["mgt"]+DH/2, REXT, Y["mgt"]+(DH-EH)/2+EH/2, v_unsat, exit_=True, label="No")

        v_sat = path_pharm and not v_unsat
        exit_node(CX-EW/2, Y["mgt"]+DH+20, EW, EH, nc(v_sat, exit_=v_sat), "Controlled", "Patient Medical Home")
        vline(CX, Y["mgt"]+DH, Y["mgt"]+DH+20, v_sat, exit_=v_sat, label="Yes")

        # Legend
        ly = H - 22; lx = 18
        for col, lbl in [
            (C_MAIN, "Visited"), (C_DIAMOND, "Decision"),
            (C_URGENT, "Urgent"), (C_EXIT, "Exit/Off-ramp"), (C_UNVISIT, "Not reached"),
        ]:
            svg.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx+16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 110
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            f'<div style="background:{C_BG};padding:10px;border-radius:14px;overflow-x:auto">{"".join(svg)}</div>',
            height=880, scrolling=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        # Context Strings
        ctx_freq = f"{freq_val} times/week" if freq_val is not None else "Unknown"
        active_alarms = [lbl for k, lbl in [
            ("actively_bleeding_now", "Active Bleeding"),
            ("unintended_weight_loss", "Weight Loss"),
            ("progressive_dysphagia", "Dysphagia"),
            ("odynophagia", "Odynophagia"),
            ("persistent_vomiting", "Vomiting"),
            ("black_stool_or_blood_in_vomit", "GI Bleed Signs"),
            ("iron_deficiency_anemia_present", "IDA"),
            ("abdominal_mass", "Abd Mass")
        ] if patient_data.get(k)]
        alarm_str = ", ".join(active_alarms) if active_alarms else "None"

        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>Predominant Symptom:</b> {"Heartburn/Regurgitation" if has_gerd else "Other"}</span><br>'
            f'<span><b>Frequency:</b> {ctx_freq}</span><br>'
            f'<span><b>Alarm Features:</b> {alarm_str}</span>'
            "</div>",
            unsafe_allow_html=True,
        )

        override_candidates = []

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
                skip = {"bullets", "notes", "supported_by", "regimen_key"}
                for k, v in details.items():
                    if k in skip: continue
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
            if extra_cls: cls = extra_cls

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
                    f'<div class="action-card warning">'
                    f'<h4><span class="badge warning">DATA NEEDED</span> ⏳ {msg_html}</h4>'
                    f'<ul><li>Missing fields: {missing_str}</li></ul>'
                    "</div>",
                    unsafe_allow_html=True,
                )
                for sa in output.suggested_actions:
                    render_action(sa, extra_cls="info")
            elif isinstance(output, Stop):
                reason_html = html.escape(output.reason).replace("\n   ", "<br>&nbsp;&nbsp;&nbsp;").replace("\n", "<br>")
                st.markdown(
                    f'<div class="action-card stop">'
                    f'<h4><span class="badge stop">STOP</span> 🛑 {reason_html}</h4>'
                    "</div>",
                    unsafe_allow_html=True,
                )
                for a in output.actions:
                    render_action(a)

        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.caption("Optional free-text notes to be attached to the clinical recommendations.")
        st.session_state.gerd_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.gerd_notes,
            height=180,
        )

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
                        "node": o.target_node, "field": o.field,
                        "new_value": o.new_value, "reason": o.reason,
                        "created_at": o.created_at.isoformat(),
                    } for o in st.session_state.gerd_overrides
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

        def _pretty(s: str) -> str:
            return s.replace("_", " ").title()

        with override_panel:
            if override_candidates:
                st.markdown("---")
                st.markdown('<p class="section-label">CLINICIAN OVERRIDES</p>', unsafe_allow_html=True)
                st.caption("Override engine decisions where clinical judgement differs. A documented reason is required.")

                for a in override_candidates:
                    opt = a.override_options
                    raw_node = opt["node"]
                    raw_field = opt["field"]
                    node_name = _pretty(raw_node)
                    field_name = _pretty(raw_field)
                    allowed = opt.get("allowed", [True, False])

                    with st.expander(f"⚙️ Override: **{node_name}** → `{field_name}`"):
                        preview = a.label[:120] + ("…" if len(a.label) > 120 else "")
                        st.markdown(f'<div class="override-card">Engine decision based on: <b>{html.escape(preview)}</b></div>', unsafe_allow_html=True)
                        existing = next((o for o in st.session_state.gerd_overrides if o.target_node == raw_node and o.field == raw_field), None)
                        current_val = existing.new_value if existing else None
                        
                        new_val = st.radio(
                            f"Set `{field_name}` to:",
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
                                    st.session_state.gerd_overrides = [o for o in st.session_state.gerd_overrides if not (o.target_node == raw_node and o.field == raw_field)]
                                    st.session_state.gerd_overrides.append(
                                        Override(target_node=raw_node, field=raw_field, old_value=None, new_value=new_val, reason=reason.strip())
                                    )
                                    st.success("Override applied. Click **▶ Run Pathway** to re-evaluate.")
                        with col2:
                            if existing and st.button("🗑 Remove Override", key=f"ov_remove_{raw_node}_{raw_field}"):
                                st.session_state.gerd_overrides = [o for o in st.session_state.gerd_overrides if not (o.target_node == raw_node and o.field == raw_field)]
                                st.success("Override removed.")

                if st.session_state.gerd_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.gerd_overrides:
                        st.markdown(
                            f'<div class="override-card">'
                            f'🛠 <b>{html.escape(_pretty(o.target_node))}</b> → <code>{html.escape(_pretty(o.field))}</code> set to <b>{html.escape(str(o.new_value))}</b><br>'
                            f'<span style="color:#a5b4fc">Reason: {html.escape(o.reason)}</span><br>'
                            f'<span style="color:#64748b;font-size:11px">Applied: {o.created_at.strftime("%H:%M:%S")}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

        with st.expander("📋 Decision Audit Log"):
            for log in logs:
                try:
                    ts = datetime.fromisoformat(log.timestamp).strftime("%H:%M:%S")
                except Exception:
                    ts = "—"
                st.markdown(f"**[{ts}] {log.node}** → _{log.decision}_")
                if log.used_inputs:
                    st.caption("  ".join(f"`{k}={v}`" for k, v in log.used_inputs.items() if v is not None))
    else:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
