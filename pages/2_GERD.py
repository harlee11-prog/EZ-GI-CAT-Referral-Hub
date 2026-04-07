import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import html
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components
from gerdengine import run_gerd_pathway, Action, DataRequest, Stop, Override

st.set_page_config(page_title="GERD", page_icon="🫁", layout="wide")

def safe_text(text) -> str:
    if text is None: return ""
    return " ".join(str(text).replace("\u00a0", " ").split())

def build_gerd_markdown(patient_data, outputs, overrides, notes) -> str:
    lines = []
    lines.append("# GERD Pathway Clinical Summary")
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Patient Context")
    lines.append(f"- Age/Sex: {patient_data.get('age')} {str(patient_data.get('sex','')).capitalize()}")
    lines.append(f"- Heartburn: {patient_data.get('predominant_heartburn')}")
    lines.append(f"- Regurgitation: {patient_data.get('predominant_regurgitation')}")
    lines.append(f"- Symptoms per week: {patient_data.get('symptoms_per_week', '')}")
    lines.append(f"- GERD symptom years: {patient_data.get('gerd_symptom_years', '')}")
    lines.append(f"- Known Barrett's: {patient_data.get('known_barretts_esophagus', False)}")
    lines.append("")
    lines.append("## Clinical Recommendations")
    if not outputs:
        lines.append("- No recommendations generated.")
    else:
        for o in outputs:
            if isinstance(o, Action):
                urgency = (o.urgency or "info").upper()
                label = safe_text(o.label)
                lines.append(f"- [{urgency}] {label}")
                if isinstance(o.details, dict):
                    for b in o.details.get("bullets", []): lines.append(f"  - {safe_text(b)}")
                    for n in o.details.get("notes", []): lines.append(f"  - Note: {safe_text(n)}")
                    for s in o.details.get("supported_by", []): lines.append(f"  - Support: {safe_text(s)}")
                    skip = {"bullets","notes","supported_by"}
                    for k, v in o.details.items():
                        if k in skip: continue
                        if isinstance(v, list) and v:
                            for item in v: lines.append(f"  - {safe_text(k).replace('_',' ').title()}: {safe_text(item)}")
                        elif v not in (None, False, ""):
                            lines.append(f"  - {safe_text(k).replace('_',' ').title()}: {safe_text(v)}")
            elif isinstance(o, Stop):
                lines.append(f"- STOP: {safe_text(o.reason)}")
                if getattr(o, 'actions', None):
                    for a in o.actions: lines.append(f"  - Follow-up: {safe_text(a.label)}")
            elif isinstance(o, DataRequest):
                missing = ", ".join(o.missing_fields)
                lines.append(f"- DATA NEEDED: {safe_text(o.message)}")
                lines.append(f"  - Missing fields: {missing}")
    lines.append("")
    lines.append("## Active Overrides")
    if overrides:
        for ov in overrides:
            lines.append(f"- {safe_text(ov.target_node)}.{safe_text(ov.field)} → {safe_text(ov.new_value)} (Reason: {safe_text(ov.reason)})")
    else:
        lines.append("- No active overrides.")
    lines.append("")
    lines.append("## Clinician Notes")
    lines.append(notes.strip() if notes and notes.strip() else "No clinician notes entered.")
    return "\n".join(lines)

# ── Global CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
.ctx-card {
    background: #1e3a5f; border: 1px solid #2e5c8a; border-radius: 10px;
    padding: 14px 18px; margin-bottom: 14px; font-size: 14px; color: #e2e8f0;
}
.ctx-card b { color: #93c5fd; }
.section-label {
    font-size: 11px; font-weight: 700; letter-spacing: 1.2px;
    color: #94a3b8; margin-bottom: 6px; margin-top: 18px;
}
.action-card {
    border-radius: 10px; padding: 14px 18px; margin-bottom: 12px;
    font-size: 13.5px; line-height: 1.6;
}
.action-card.urgent   { background:#3b0a0a; border-left:5px solid #ef4444; color:#fecaca; }
.action-card.routine  { background:#052e16; border-left:5px solid #22c55e; color:#bbf7d0; }
.action-card.info     { background:#0c1a2e; border-left:5px solid #3b82f6; color:#bfdbfe; }
.action-card.warning  { background:#2d1a00; border-left:5px solid #f59e0b; color:#fde68a; }
.action-card.stop     { background:#2d0a0a; border-left:5px solid #ef4444; color:#fecaca; }
.action-card h4       { margin: 0 0 6px 0; font-size: 14px; }
.action-card ul       { margin: 6px 0 0 16px; padding: 0; }
.action-card li       { margin-bottom: 3px; }
.badge {
    display:inline-block; font-size:11px; font-weight:bold;
    padding:2px 8px; border-radius:20px; margin-right:6px;
    text-transform:uppercase; letter-spacing:0.5px;
}
.badge.urgent   { background:#ef4444; color:#fff; }
.badge.routine  { background:#22c55e; color:#fff; }
.badge.info     { background:#3b82f6; color:#fff; }
.badge.warning  { background:#f59e0b; color:#000; }
.badge.stop     { background:#ef4444; color:#fff; }
.override-card {
    background:#1a1a2e; border:1px dashed #6366f1; border-radius:8px;
    padding:10px 14px; margin-top:8px; font-size:13px; color:#c7d2fe;
}
</style>
""", unsafe_allow_html=True)

st.title("🫁 GERD Pathway")
st.markdown("---")

# ── Session State ────────────────────────────────────────────────────────────
if "gerd_overrides" not in st.session_state: st.session_state.gerd_overrides = []
if "gerd_has_run" not in st.session_state: st.session_state.gerd_has_run = False
if "gerd_notes" not in st.session_state: st.session_state.gerd_notes = ""

left, right = st.columns([1, 1.5])

with left:
    st.subheader("Patient Information")
    age = st.number_input("Age", 1, 120, 52)
    sex = st.selectbox("Sex", ["male", "female"])

    st.markdown("**1. Suspected GERD – Entry Symptoms**")
    predominant_heartburn = st.checkbox("Predominant heartburn")
    predominant_regurgitation = st.checkbox("Predominant regurgitation")
    dominant_chest_pain = st.checkbox("Chest pain is a dominant feature")

    st.markdown("**2. Dyspepsia Screen**")
    predominant_epigastric_pain = st.checkbox("Predominant epigastric pain / discomfort")
    predominant_upper_abdominal_bloating = st.checkbox("Upper abdominal distension or bloating")

    st.markdown("**3. Alarm Features**")
    actively_bleeding_now = st.checkbox("⚠️ Active / acute GI bleeding NOW")
    al_weight_loss = st.checkbox("Unintended weight loss >5% over 6–12 months")
    al_dysphagia = st.checkbox("Progressive dysphagia")
    al_odynophagia = st.checkbox("Odynophagia (painful swallowing)")
    al_vomiting = st.checkbox("Persistent vomiting (not cannabis-related)")
    al_gi_bleed = st.checkbox("Black stool or blood in vomit")
    al_ida = st.checkbox("Iron deficiency anemia")
    al_mass = st.checkbox("Abdominal mass")

    st.markdown("**4. Barrett's Esophagus Risk**")
    gerd_symptom_years_sel = st.selectbox(
        "GERD symptom duration",
        ["Unknown / <5 years", "5–10 years", ">10 years"]
    )
    gerd_symptom_years_map = {"Unknown / <5 years": None, "5–10 years": 6, ">10 years": 11}

    symptoms_per_week_sel = st.selectbox(
        "Symptom frequency per week",
        ["Unknown", "<1 (infrequent)", "1–1.9 (weekly)", "≥2 (frequent)"]
    )
    spw_map = {"Unknown": None, "<1 (infrequent)": 0.5, "1–1.9 (weekly)": 1.0, "≥2 (frequent)": 2.0}

    caucasian = st.checkbox("Caucasian")
    current_or_history_smoking = st.checkbox("Current or past tobacco smoking")
    family_hx_barretts = st.checkbox("Family history (1st degree) of Barrett's or esophageal cancer")
    history_of_sleeve_gastrectomy = st.checkbox("History of sleeve gastrectomy")
    known_barretts_esophagus = st.checkbox("Known Barrett's esophagus")
    barretts_screen_positive = st.checkbox("Barrett's screening test already positive")

    st.markdown("**Waist Measurements** (for central obesity)")
    waist_cm_input = st.number_input("Waist circumference (cm) — 0 = not measured", 0.0, 250.0, 0.0, step=0.5)
    whr_input = st.number_input("Waist-hip ratio — 0 = not measured", 0.0, 3.0, 0.0, step=0.01)
    waist_cm = waist_cm_input if waist_cm_input > 0 else None
    whr = whr_input if whr_input > 0 else None

    st.markdown("**5. Non-Pharmacological Therapy**")
    st.caption("Lifestyle counselling (smoking, diet, weight, meal timing) is always recommended.")

    st.markdown("**6. Pharmacological Therapy**")
    ppiod_done_sel = st.selectbox("Once-daily PPI trial (4–8 weeks)", ["Not yet started", "Completed"])
    ppiod_done = ppiod_done_sel == "Completed"
    ppiod_response = None
    ppi_adherence_correct = None
    ppi_adherence_adequate = None
    ppibid_done = None
    ppibid_response = None

    if ppiod_done:
        ppiod_resp_sel = st.selectbox(
            "Response to once-daily PPI",
            ["Unknown", "Adequate (symptoms resolved)", "Inadequate"]
        )
        ppiod_response_map = {"Unknown": None, "Adequate (symptoms resolved)": True, "Inadequate": False}
        ppiod_response = ppiod_response_map[ppiod_resp_sel]

        if ppiod_response is False:
            st.markdown("_PPI adherence check before escalating:_")
            ppi_adherence_correct = st.checkbox("PPI taken correctly (30 min before breakfast)", value=True)
            ppi_adherence_adequate = st.checkbox("Patient adherence to daily PPI adequate", value=True)
            ppibid_done_sel = st.selectbox(
                "Twice-daily (BID) PPI trial (4–8 weeks)",
                ["Not yet started", "Completed"],
                key="ppibid_done_sel"
            )
            ppibid_done = ppibid_done_sel == "Completed"
            if ppibid_done:
                ppibid_resp_sel = st.selectbox(
                    "Response to BID PPI",
                    ["Unknown", "Adequate (symptoms resolved)", "Inadequate"]
                )
                ppibid_response_map = {"Unknown": None, "Adequate (symptoms resolved)": True, "Inadequate": False}
                ppibid_response = ppibid_response_map[ppibid_resp_sel]

    st.markdown("**7. Maintenance & Deprescribing**")
    symptoms_resolved_sel = st.selectbox("Symptoms resolved after PPI?", ["Unknown", "Yes", "No"])
    symptoms_resolved_map = {"Unknown": None, "Yes": True, "No": False}
    symptoms_resolved = symptoms_resolved_map[symptoms_resolved_sel]

    symptoms_return_sel = st.selectbox("Symptoms returned after taper/stop?", ["Unknown", "Yes", "No"])
    symptoms_return_map = {"Unknown": None, "Yes": True, "No": False}
    symptoms_return = symptoms_return_map[symptoms_return_sel]

    st.markdown("**8. Overall Management Response**")
    unsat_sel = st.selectbox(
        "Overall response to GERD pharmacologic therapy",
        ["Unknown", "Satisfactory", "Unsatisfactory"]
    )
    unsat_map = {"Unknown": None, "Satisfactory": False, "Unsatisfactory": True}
    unsatisfactory_response = unsat_map[unsat_sel]

    advice_considered = None
    if unsatisfactory_response is True:
        advice_considered = st.checkbox("Advice service already consulted / considered")

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.gerd_has_run = True

    if st.button("Clear Overrides", use_container_width=True):
        st.session_state.gerd_overrides = []
        if "gerd_saved_output" in st.session_state:
            del st.session_state["gerd_saved_output"]
        st.rerun()

    override_panel = st.container()

# ── RIGHT PANEL ──────────────────────────────────────────────────────────────
with right:
    if st.session_state.gerd_has_run:
        patient_data = dict(
            age=age, sex=sex,
            predominant_heartburn=predominant_heartburn or None,
            predominant_regurgitation=predominant_regurgitation or None,
            dominant_chest_pain=dominant_chest_pain or None,
            predominant_epigastric_pain=predominant_epigastric_pain or None,
            predominant_upper_abdominal_bloating=predominant_upper_abdominal_bloating or None,
            actively_bleeding_now=actively_bleeding_now or None,
            unintended_weight_loss=al_weight_loss or None,
            progressive_dysphagia=al_dysphagia or None,
            odynophagia=al_odynophagia or None,
            persistent_vomiting=al_vomiting or None,
            black_stool_or_blood_in_vomit=al_gi_bleed or None,
            iron_deficiency_anemia_present=al_ida or None,
            abdominal_mass=al_mass or None,
            gerd_symptom_years=gerd_symptom_years_map[gerd_symptom_years_sel],
            symptoms_per_week=spw_map[symptoms_per_week_sel],
            caucasian=caucasian or None,
            current_or_history_smoking=current_or_history_smoking or None,
            family_history_barretts_or_esophageal_cancer_first_degree=family_hx_barretts or None,
            history_of_sleeve_gastrectomy=history_of_sleeve_gastrectomy or None,
            known_barretts_esophagus=known_barretts_esophagus or None,
            barretts_screen_positive=barretts_screen_positive or None,
            waist_circumference_cm=waist_cm,
            waist_hip_ratio=whr,
            ppi_once_daily_trial_done=ppiod_done if ppiod_done else None,
            ppi_once_daily_response_adequate=ppiod_response,
            ppi_taken_correctly_before_breakfast=ppi_adherence_correct,
            ppi_adherence_adequate=ppi_adherence_adequate,
            ppi_bid_trial_done=ppibid_done,
            ppi_bid_response_adequate=ppibid_response,
            symptoms_resolved_after_ppi=symptoms_resolved,
            symptoms_return_after_taper=symptoms_return,
            unsatisfactory_response_to_pharmacologic_therapy=unsatisfactory_response,
            advice_service_considered=advice_considered or None,
        )

        outputs, logs, applied_overrides = run_gerd_pathway(
            patient_data, overrides=st.session_state.gerd_overrides
        )

        # ── Pathway state flags ───────────────────────────────────────────
        gerd_entry_met       = any(isinstance(o, Action) and o.code == "GERD_ENTRY_MET" for o in outputs)
        is_dyspepsia_stop    = any(isinstance(o, Stop) and "dyspeptic" in o.reason.lower() for o in outputs)
        has_alarm            = any((isinstance(o, Stop) and "alarm" in o.reason.lower()) or
                                   (isinstance(o, Action) and o.code == "URGENT_ENDOSCOPY_REFERRAL") for o in outputs)
        barretts_refer       = any(isinstance(o, Stop) and "barrett" in o.reason.lower() for o in outputs)
        went_nonpharm        = any(isinstance(o, Action) and o.code == "COUNSEL_SMOKING_CESSATION" for o in outputs)
        went_pharm           = any(isinstance(o, Action) and o.code in {
                                   "H2RA_OR_ANTACID_PRN","START_PPI_ONCE_DAILY","OPTIMIZE_PPI_BID",
                                   "PPI_ONCE_DAILY_SUCCESS"} for o in outputs)
        mild_branch          = any(isinstance(o, Action) and o.code == "H2RA_OR_ANTACID_PRN" for o in outputs)
        ppiod_success        = any(isinstance(o, Action) and o.code == "PPI_ONCE_DAILY_SUCCESS" for o in outputs)
        ppibid_action        = any(isinstance(o, Action) and o.code == "OPTIMIZE_PPI_BID" for o in outputs)
        ppibid_success       = any(isinstance(o, Action) and o.code == "PPI_BID_SUCCESS" for o in outputs)
        maint_vis            = any(isinstance(o, Action) and o.code in {
                                   "TITRATE_TO_LOWEST_EFFECTIVE_PPI","PPI_MAINTENANCE",
                                   "KNOWN_BARRETTS_LIFETIME_PPI","CAPTURE_PPI_RESOLUTION_STATUS"} for o in outputs)
        pathway_complete     = any(isinstance(o, Stop) and "complete" in o.reason.lower() for o in outputs)
        refer_final          = any((isinstance(o, Stop) and
                                    ("failed_gerd" in o.reason.lower() or
                                     ("consultation_endoscopy" in o.reason.lower()
                                      and "alarm" not in o.reason.lower()
                                      and "barrett" not in o.reason.lower()))) for o in outputs)
        active_bleeding_stop = any(isinstance(o, Stop) and "bleeding" in o.reason.lower() for o in outputs)

        # ── SVG FLOWCHART ─────────────────────────────────────────────────
        CBG      = "0f172a"
        CMAIN    = "16a34a"
        CUNVISIT = "475569"
        CDIAMOND = "1d4ed8"
        CURGENT  = "dc2626"
        CEXIT    = "d97706"
        CTEXT    = "ffffff"
        CDIM     = "94a3b8"

        def nc(vis, urgent=False, exit=False):
            if not vis:   return CUNVISIT
            if urgent:    return CURGENT
            if exit:      return CEXIT
            return CMAIN

        def dc(vis):
            return CDIAMOND if vis else CUNVISIT

        def mid(vis, urgent=False, exit=False):
            if not vis:  return "ma"
            if urgent:   return "mr"
            if exit:     return "mo"
            return "mg"

        W, H = 720, 1020
        svg = []
        svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{H}" viewBox="0 0 {W} {H}" style="background:#{CBG};border-radius:12px" font-family="Arial,sans-serif">')
        svg.append(
            '<defs>'
            '<marker id="ma" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#64748b"/></marker>'
            '<marker id="mg" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#16a34a"/></marker>'
            '<marker id="mr" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#dc2626"/></marker>'
            '<marker id="mo" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#d97706"/></marker>'
            '</defs>'
        )

        def svgt(x, y, text, fill, size=11, bold=False, anchor="middle"):
            w = "bold" if bold else "normal"
            svg.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="#{fill}" font-size="{size}" font-weight="{w}">{html.escape(str(text))}</text>')

        def rectnode(x, y, w, h, color, line1, line2=None, sub=None, rx=8):
            tc = CTEXT if color != CUNVISIT else CDIM
            svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="#{color}" stroke="#ffffff18" stroke-width="1.5"/>')
            if line2:
                svgt(x + w//2, y + h//2 - 8, line1, tc, 11, True)
                svgt(x + w//2, y + h//2 + 7, line2, tc, 11, True)
            else:
                svgt(x + w//2, y + h//2 + 4, line1, tc, 11, True)
            if sub:
                svgt(x + w//2, y + h - 8, sub, tc + "99", 9)

        def diamondnode(cx, cy, w, h, color, line1, line2=None):
            tc = CTEXT if color != CUNVISIT else CDIM
            hw, hh = w//2, h//2
            pts = f"{cx},{cy-hh} {cx+hw},{cy} {cx},{cy+hh} {cx-hw},{cy}"
            svg.append(f'<polygon points="{pts}" fill="#{color}" stroke="#ffffff18" stroke-width="1.5"/>')
            if line2:
                svgt(cx, cy - 7, line1, tc, 10, True)
                svgt(cx, cy + 8, line2, tc, 10, True)
            else:
                svgt(cx, cy + 4, line1, tc, 10, True)

        def exitnode(x, y, w, h, color, line1, line2=None, rx=7):
            tc = CTEXT if color != CUNVISIT else CDIM
            svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="#{color}" stroke="#ffffff18" stroke-width="1.5"/>')
            if line2:
                svgt(x + w//2, y + h//2 - 7, line1, tc, 10, True)
                svgt(x + w//2, y + h//2 + 7, line2, tc, 9)
            else:
                svgt(x + w//2, y + h//2 + 4, line1, tc, 10, True)

        def vline(x, y1, y2, vis, urgent=False, exit=False, label=None):
            m = mid(vis, urgent, exit)
            stroke = {"mg": "16a34a", "mr": "dc2626", "mo": "d97706"}.get(m, "64748b")
            dash = '' if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="#{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>')
            if label:
                svgt(x + 6, (y1 + y2)//2 - 3, label, stroke, 10, True, "start")

        def elbowline(x1, y1, x2, y2, vis, urgent=False, exit=False, label=None):
            m = mid(vis, urgent, exit)
            stroke = {"mg": "16a34a", "mr": "dc2626", "mo": "d97706"}.get(m, "64748b")
            dash = '' if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" fill="none" stroke="#{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>')
            if label:
                svgt((x1 + x2)//2, y1 - 5, label, stroke, 10, True)

        # ── Layout constants ──────────────────────────────────────────────
        CX   = 360          # horizontal spine centre
        NW, NH = 190, 50    # rect node  width / height
        DW, DH = 200, 62    # diamond    width / height
        EW, EH = 140, 44    # exit box   width / height
        LEXT = 18           # left exit  X
        REXT = W - 18 - EW  # right exit X  (= 562)

        Y = dict(
            entry  = 15,
            ddysp  = 95,
            dalarm = 200,
            dbarre = 305,
            nonph  = 410,
            dfreq  = 490,
            ppiod  = 590,
            ppibid = 670,
            maint  = 760,
            mgmt   = 855,
        )

        # ── Node 1: Suspected GERD ────────────────────────────────────────
        rectnode(CX - NW//2, Y["entry"], NW, NH,
                 nc(True), "1. Suspected GERD", sub="Heartburn · Regurgitation")
        vline(CX, Y["entry"] + NH, Y["ddysp"], True)

        # ── Node 2: Dyspepsia ─────────────────────────────────────────────
        d2vis = gerd_entry_met or is_dyspepsia_stop
        diamondnode(CX, Y["ddysp"] + DH//2, DW, DH, dc(d2vis),
                    "2. Is it Dyspepsia?", "Epigastric · Bloating?")
        dyspvis = is_dyspepsia_stop
        exitnode(REXT, Y["ddysp"] + DH//2 - EH//2, EW, EH,
                 nc(dyspvis, exit=True), "Dyspepsia", "Pathway")
        elbowline(CX + DW//2, Y["ddysp"] + DH//2,
                  REXT, Y["ddysp"] + DH//2,
                  dyspvis, exit=True, label="Yes")
        vpast_dysp = gerd_entry_met and not is_dyspepsia_stop
        vline(CX, Y["ddysp"] + DH, Y["dalarm"], vpast_dysp, label="No")

        # ── Node 3: Alarm Features ────────────────────────────────────────
        diamondnode(CX, Y["dalarm"] + DH//2, DW, DH, dc(vpast_dysp),
                    "3. Alarm Features?", "Any present?")
        alarm_exit_vis = (has_alarm or active_bleeding_stop) and vpast_dysp
        exitnode(REXT, Y["dalarm"] + DH//2 - EH//2, EW, EH,
                 nc(alarm_exit_vis, urgent=True), "Refer", "GI · Endoscopy")
        elbowline(CX + DW//2, Y["dalarm"] + DH//2,
                  REXT, Y["dalarm"] + DH//2,
                  alarm_exit_vis, urgent=True, label="Yes")
        vpast_alarm = vpast_dysp and not has_alarm and not active_bleeding_stop
        vline(CX, Y["dalarm"] + DH, Y["dbarre"], vpast_alarm, label="No")

        # ── Node 4: Barrett's Risk ────────────────────────────────────────
        diamondnode(CX, Y["dbarre"] + DH//2, DW, DH, dc(vpast_alarm),
                    "4. Barrett's Risk", "\u22653 risk factors?")
        barrett_exit_vis = barretts_refer and vpast_alarm
        exitnode(REXT, Y["dbarre"] + DH//2 - EH//2, EW, EH,
                 nc(barrett_exit_vis, exit=True), "High Risk", "\u2192 Screen / Refer")
        elbowline(CX + DW//2, Y["dbarre"] + DH//2,
                  REXT, Y["dbarre"] + DH//2,
                  barrett_exit_vis, exit=True, label="High")
        vpast_barre = vpast_alarm and not barretts_refer
        vline(CX, Y["dbarre"] + DH, Y["nonph"], vpast_barre, label="No")

        # ── Node 5: Non-Pharmacological ───────────────────────────────────
        rectnode(CX - NW//2, Y["nonph"], NW, NH, nc(went_nonpharm),
                 "5. Non-Pharmacological", sub="Lifestyle \u00b7 Diet \u00b7 Smoking")
        vline(CX, Y["nonph"] + NH, Y["dfreq"], went_nonpharm, label="Ineffective")

        # ── Node 6: Symptom Frequency ─────────────────────────────────────
        freq_vis = went_pharm or went_nonpharm
        diamondnode(CX, Y["dfreq"] + DH//2, DW, DH, dc(freq_vis),
                    "6. Symptoms", "<2\u00d7/week?")

        # H2RA left exit – vertically centred on diamond
        h2ra_cy = Y["dfreq"] + DH//2
        h2ra_y  = h2ra_cy - EH//2
        exitnode(LEXT, h2ra_y, EW, EH, nc(mild_branch, exit=True), "H2RA /", "Antacids PRN")
        elbowline(CX - DW//2, h2ra_cy, LEXT + EW, h2ra_cy,
                  mild_branch, exit=True, label="<2\u00d7")

        # ≥2× spine down to PPI OD
        ppiod_vis = went_pharm and not mild_branch
        vline(CX, Y["dfreq"] + DH, Y["ppiod"], ppiod_vis, label="\u22652\u00d7")

        # ── PPI Once Daily ────────────────────────────────────────────────
        rectnode(CX - NW//2, Y["ppiod"], NW, NH, nc(ppiod_vis),
                 "PPI Once Daily", "4\u20138 weeks", sub="30 min before breakfast")

        RRAIL = CX + NW//2 + 44  # right bypass rail X

        # PPI OD resolved → skip BID, jump to Maintenance
        if ppiod_success:
            rs   = "16a34a"
            ty1  = Y["ppiod"] + NH//2
            ty2  = Y["maint"] + NH//2
            svg.append(f'<polyline points="{CX+NW//2},{ty1} {RRAIL},{ty1} {RRAIL},{ty2} {CX+NW//2},{ty2}" fill="none" stroke="#{rs}" stroke-width="2" marker-end="url(#mg)"/>')
            svgt(RRAIL + 4, (ty1 + ty2)//2, "Resolved", rs, 9, False, "start")

        # ── Optimize PPI BID ──────────────────────────────────────────────
        vline(CX, Y["ppiod"] + NH, Y["ppibid"], ppibid_action, label="Inadequate")
        rectnode(CX - NW//2, Y["ppibid"], NW, NH, nc(ppibid_action),
                 "Optimize PPI BID", "4\u20138 weeks")

        # PPI BID resolved → jump to Maintenance
        if ppibid_success:
            rs   = "16a34a"
            ty1  = Y["ppibid"] + NH//2
            ty2  = Y["maint"] + NH//2
            svg.append(f'<polyline points="{CX+NW//2},{ty1} {RRAIL},{ty1} {RRAIL},{ty2} {CX+NW//2},{ty2}" fill="none" stroke="#{rs}" stroke-width="2" marker-end="url(#mg)"/>')
            svgt(RRAIL + 4, (ty1 + ty2)//2, "Resolved", rs, 9, False, "start")

        # BID → Maintenance straight down (when not resolved)
        ppibid_to_maint = ppibid_action and not ppibid_success
        vline(CX, Y["ppibid"] + NH, Y["maint"], ppibid_to_maint)

        # ── Node 7: Maintenance / Deprescribing ───────────────────────────
        rectnode(CX - NW//2, Y["maint"], NW, NH, nc(maint_vis),
                 "7. Maintenance /", "Deprescribing", sub="Lowest dose \u00b7 Annual taper")
        vline(CX, Y["maint"] + NH, Y["mgmt"], maint_vis)

        # ── H2RA route: bottom of box → down → elbow right to Mgmt ──────
        if mild_branch:
            hx      = LEXT + EW//2      # H2RA centre X
            hy_bot  = h2ra_y + EH       # bottom of H2RA box
            mgmt_top = Y["mgmt"]
            svg.append(
                f'<polyline points="{hx},{hy_bot} {hx},{mgmt_top} {CX - NW//2},{mgmt_top}" '
                f'fill="none" stroke="#d97706" stroke-width="2" marker-end="url(#mo)"/>'
            )

        # ── Node 8: Management Response ───────────────────────────────────
        mgmt_node_vis = maint_vis or pathway_complete or refer_final
        rectnode(CX - NW//2, Y["mgmt"], NW, NH, nc(mgmt_node_vis),
                 "8. Management", "Response", sub="Satisfactory?")

        # Complete LEFT
        complete_vis = pathway_complete
        exit_cy = Y["mgmt"] + NH//2
        exitnode(LEXT, exit_cy - EH//2, EW, EH,
                 nc(complete_vis, exit=True), "\u2713 Complete", "Medical Home")
        elbowline(CX - NW//2, exit_cy, LEXT + EW, exit_cy,
                  complete_vis, exit=True, label="Yes")

        # Refer RIGHT
        refer_vis = refer_final
        exitnode(REXT, exit_cy - EH//2, EW, EH,
                 nc(refer_vis, urgent=True), "Refer", "Consult / Scope")
        elbowline(CX + NW//2, exit_cy, REXT, exit_cy,
                  refer_vis, urgent=True, label="Unsat.")

        # ── Legend ────────────────────────────────────────────────────────
        ly = H - 22
        lx = 18
        for col, lbl in [
            (CMAIN, "Visited"), (CDIAMOND, "Decision"), (CURGENT, "Urgent"),
            (CEXIT, "Exit/Off-ramp"), (CUNVISIT, "Not reached")
        ]:
            svg.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="2" fill="#{col}"/>')
            svgt(lx + 16, ly, lbl, "94a3b8", 10, anchor="start")
            lx += 112

        svg.append("</svg>")

        # ── Render flowchart ──────────────────────────────────────────────
        st.subheader("Pathway Followed")
        components.html(
            f'<div style="background:#{CBG};padding:10px;border-radius:14px;overflow-x:auto">{"".join(svg)}</div>',
            height=1040, scrolling=True,
        )

        # ── Patient context card ──────────────────────────────────────────
        alarm_fields = [
            ("unintended_weight_loss","Weight loss >5%"), ("progressive_dysphagia","Dysphagia"),
            ("odynophagia","Odynophagia"), ("persistent_vomiting","Vomiting"),
            ("black_stool_or_blood_in_vomit","GI bleed signs"),
            ("iron_deficiency_anemia_present","IDA"), ("abdominal_mass","Abdominal mass"),
            ("actively_bleeding_now","Active bleeding"),
        ]
        active_alarms = [label for key, label in alarm_fields if patient_data.get(key)]
        alarm_str = ", ".join(active_alarms) if active_alarms else "None"
        spw_display = spw_map[symptoms_per_week_sel]
        spw_str = f"{spw_display}/week" if spw_display is not None else "Unknown"
        barretts_str = (
            "Known Barrett's → lifetime PPI" if known_barretts_esophagus
            else "Positive screen → refer" if barretts_screen_positive
            else "Not indicated / not screened"
        )

        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(f"""
<div class="ctx-card">
  <span><b>Age / Sex:</b> {age} {sex.capitalize()}</span><br>
  <span><b>Symptom Frequency:</b> {spw_str} &nbsp;&nbsp; <b>Duration:</b> {gerd_symptom_years_sel}</span><br>
  <span><b>Alarm Features:</b> {alarm_str}</span><br>
  <span><b>Barrett's Status:</b> {barretts_str}</span><br>
  <span><b>Overall Response:</b> {unsat_sel}</span>
</div>
""", unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        # ── Render helpers ────────────────────────────────────────────────
        def detail_html(details) -> str:
            if not details: return ""
            items = []
            if isinstance(details, dict):
                for bullet in details.get("bullets", []):
                    items.append(f"<li>{html.escape(str(bullet))}</li>")
                for note in details.get("notes", []):
                    items.append(f'<li style="color:#fde68a">{html.escape(str(note))}</li>')
                for src in details.get("supported_by", []):
                    items.append(f"<li>{html.escape(str(src))}</li>")
                skip = {"bullets","notes","supported_by"}
                for k, v in details.items():
                    if k in skip: continue
                    if isinstance(v, list) and v:
                        items += [f"<li><b>{html.escape(str(k))}</b>: {html.escape(str(i))}</li>" for i in v]
                    elif v not in (None, False, ""):
                        items.append(f"<li><b>{html.escape(str(k))}</b>: {html.escape(str(v))}</li>")
            elif isinstance(details, list):
                items = [f"<li>{html.escape(str(d))}</li>" for d in details if str(d).strip()]
            return f'<ul style="margin:6px 0 0 16px;padding:0">{"".join(items)}</ul>' if items else ""

        override_candidates = []

        def render_action(a: Action, extra_cls: str = None):
            urgency_to_cls = {"urgent":"urgent","warning":"warning",None:"routine","routine":"routine"}
            cls = urgency_to_cls.get(a.urgency or "", "routine")
            if extra_cls: cls = extra_cls
            badge_label = (a.urgency or "info").upper()
            label_html = html.escape(a.label).replace("\n", "<br>&nbsp;&nbsp;&nbsp;").replace("|", "<br>")
            d_html = detail_html(a.details)
            override_html = '<p style="margin:6px 0 0;font-size:11px;color:#a5b4fc">Override available — reason required</p>' if a.override_options else ""
            st.markdown(
                f'<div class="action-card {cls}">'
                f'<h4><span class="badge {cls}">{badge_label}</span>{label_html}</h4>'
                f'{d_html}{override_html}</div>',
                unsafe_allow_html=True
            )
            if a.override_options:
                override_candidates.append(a)

        st.markdown('<p class="section-label">RECOMMENDED ACTIONS</p>', unsafe_allow_html=True)

        for output in outputs:
            if isinstance(output, Action):
                render_action(output)
            elif isinstance(output, DataRequest):
                missing_str = ", ".join(f"<code>{f}</code>" for f in output.missing_fields)
                msg_html = html.escape(output.message).replace("\n", "<br>").replace("|", "<br>")
                st.markdown(
                    f'<div class="action-card warning">'
                    f'<h4><span class="badge warning">DATA NEEDED</span>{msg_html}</h4>'
                    f'<ul><li>Missing fields: {missing_str}</li></ul></div>',
                    unsafe_allow_html=True
                )
                for sa in output.suggested_actions:
                    render_action(sa, extra_cls="info")
            elif isinstance(output, Stop):
                reason_html = html.escape(output.reason).replace("\n", "<br>&nbsp;&nbsp;&nbsp;").replace("|", "<br>")
                st.markdown(
                    f'<div class="action-card stop">'
                    f'<h4><span class="badge stop">STOP</span>{reason_html}</h4></div>',
                    unsafe_allow_html=True
                )
                for a in output.actions:
                    render_action(a)

        # ── Active Overrides ──────────────────────────────────────────────
        if st.session_state.gerd_overrides:
            st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
            for o in st.session_state.gerd_overrides:
                st.markdown(
                    f'<div class="override-card">'
                    f'<b>{html.escape(str(o.target_node))}</b> '
                    f'<code>{html.escape(str(o.field))}</code> set to '
                    f'<b>{html.escape(str(o.new_value))}</b><br>'
                    f'<span style="color:#a5b4fc">Reason: {html.escape(o.reason)}</span><br>'
                    f'<span style="color:#64748b;font-size:11px">Applied {o.created_at.strftime("%H:%M:%S")}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

        # ── Download / Save ───────────────────────────────────────────────
        if "gerd_saved_output" in st.session_state:
            md_text = build_gerd_markdown(
                patient_data=patient_data, outputs=outputs,
                overrides=st.session_state.gerd_overrides,
                notes=st.session_state.gerd_notes,
            )
            st.download_button(
                label="⬇ Download Markdown summary",
                data=md_text.encode("utf-8"),
                file_name="gerd_summary.md",
                mime="text/markdown",
                key="gerd_download_md",
            )

        def serialize_output(o):
            if isinstance(o, Action):  return {"type":"action","code":o.code,"label":o.label,"urgency":o.urgency}
            if isinstance(o, Stop):    return {"type":"stop","reason":o.reason,"urgency":getattr(o,"urgency",None)}
            if isinstance(o, DataRequest): return {"type":"data_request","message":o.message,"missing_fields":o.missing_fields}
            return {"type":"other","repr":repr(o)}

        full_output = {
            "patient_context": patient_data,
            "clinical_recommendations": [serialize_output(o) for o in outputs],
            "overrides": [
                {"node":o.target_node,"field":o.field,"new_value":o.new_value,
                 "reason":o.reason,"created_at":o.created_at.isoformat()}
                for o in st.session_state.gerd_overrides
            ],
            "clinician_notes": st.session_state.gerd_notes,
        }

        if st.button("💾 Save this output", key="gerd_save_output"):
            st.session_state["gerd_saved_output"] = {"saved_at": datetime.now().isoformat(), "payload": full_output}
            st.success("Output saved for this session.")

        # ── Decision Audit Log ────────────────────────────────────────────
        with st.expander("📋 Decision Audit Log"):
            for log in logs:
                try:    ts = datetime.fromisoformat(log.timestamp).strftime("%H:%M:%S")
                except: ts = "–"
                st.markdown(f"`{ts}` **{log.node}** → {log.decision}")
                if log.used_inputs:
                    st.caption("  " + "  ".join(f"{k}={v}" for k, v in log.used_inputs.items() if v is not None))

        # ── Clinician Notes ────────────────────────────────────────────────
        st.markdown("---")
        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.caption("Optional free-text notes to be attached to the clinical recommendations.")
        st.session_state.gerd_notes = st.text_area(
            "Notes to attach to the saved output",
            value=st.session_state.gerd_notes,
            height=180,
        )

    else:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")

# ── Overrides Panel ──────────────────────────────────────────────────────────
with override_panel:
    if st.session_state.gerd_has_run and override_candidates:
        st.markdown("---")
        st.markdown('<p class="section-label">CLINICIAN OVERRIDES</p>', unsafe_allow_html=True)
        st.caption("Override engine decisions where clinical judgement differs. A documented reason is required.")

        for a in override_candidates:
            opt       = a.override_options
            raw_node  = opt["node"]
            raw_field = opt["field"]
            node_lbl  = raw_node.replace("_", " ").title()
            field_lbl = raw_field.replace("_", " ").title()
            allowed   = opt.get("allowed", [True, False])

            preview = a.label[:120] if len(a.label) > 120 else a.label
            with st.expander(f"Override: {node_lbl} — {field_lbl}"):
                st.markdown(
                    f'<div class="override-card">Engine decision based on <b>{html.escape(preview)}</b></div>',
                    unsafe_allow_html=True
                )
                existing = next(
                    (o for o in st.session_state.gerd_overrides
                     if o.target_node == raw_node and o.field == raw_field), None
                )
                current_val = existing.new_value if existing else None
                new_val = st.radio(
                    f"Set {field_lbl} to:",
                    options=allowed,
                    index=allowed.index(current_val) if current_val in allowed else 0,
                    key=f"ov_val_{raw_node}_{raw_field}",
                    horizontal=True,
                )
                reason = st.text_input(
                    "Reason (required)",
                    value=existing.reason if existing else "",
                    key=f"ov_reason_{raw_node}_{raw_field}",
                    placeholder="Document clinical rationale...",
                )
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Apply Override", key=f"ov_apply_{raw_node}_{raw_field}"):
                        if not reason.strip():
                            st.error("A reason is required to apply an override.")
                        else:
                            st.session_state.gerd_overrides = [
                                o for o in st.session_state.gerd_overrides
                                if not (o.target_node == raw_node and o.field == raw_field)
                            ]
                            st.session_state.gerd_overrides.append(Override(
                                target_node=raw_node, field=raw_field,
                                old_value=None, new_value=new_val,
                                reason=reason.strip(),
                            ))
                            st.success("Override applied. Click ▶ Run Pathway to re-evaluate.")
                with col2:
                    if existing and st.button("Remove Override", key=f"ov_remove_{raw_node}_{raw_field}"):
                        st.session_state.gerd_overrides = [
                            o for o in st.session_state.gerd_overrides
                            if not (o.target_node == raw_node and o.field == raw_field)
                        ]
                        st.success("Override removed.")
