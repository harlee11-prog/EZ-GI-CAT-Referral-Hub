import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import streamlit.components.v1 as components

from ibs_engine import run_ibs_pathway, Override, Action, DataRequest, Stop

st.set_page_config(page_title="IBS Pathway", page_icon="🫁", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden !important;}
    header {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    .card-urgent { background-color: #7a1a1a !important; border-left: 5px solid #ff4b4b; border-radius: 8px; padding: 16px 20px; margin-bottom: 12px; }
    .card-routine { background-color: #1a5c30 !important; border-left: 5px solid #21c55d; border-radius: 8px; padding: 16px 20px; margin-bottom: 12px; }
    .card-info { background-color: #1a3a5c !important; border-left: 5px solid #4b9eff; border-radius: 8px; padding: 16px 20px; margin-bottom: 12px; }
    .card-warning { background-color: #5c4a1a !important; border-left: 5px solid #ffbb33; border-radius: 8px; padding: 16px 20px; margin-bottom: 12px; }
    .card-title { font-size: 15px; font-weight: 700; margin-bottom: 6px; color: white; }
    .card-detail { font-size: 13px; color: #cccccc; margin: 2px 0; }
    .badge-urgent { background-color: #ff4b4b; color: white; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; margin-right: 8px; }
    .badge-routine { background-color: #21c55d; color: white; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; margin-right: 8px; }
    .badge-info { background-color: #4b9eff; color: white; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; margin-right: 8px; }
    .badge-warning { background-color: #ffbb33; color: #333; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; margin-right: 8px; }
    .section-header { font-size: 13px; font-weight: 600; color: #888888; text-transform: uppercase; letter-spacing: 1px; margin: 20px 0 10px 0; }
    </style>
""", unsafe_allow_html=True)

st.title("🫁 Irritable Bowel Syndrome (IBS) Pathway")
st.caption("Based on Alberta Health Services IBS Primary Care Pathway")
st.markdown("---")

left, right = st.columns([1, 1.4])

with left:
    st.subheader("Patient Information")

    st.markdown("**Rome IV Diagnostic Criteria**")
    st.caption("Pain must be present ≥1 day/week for ≥3 months, with ≥2 of 3 features")
    pain_days      = st.number_input("Abdominal pain days per week", 0, 7, 2)
    symptom_months = st.number_input("Symptom duration (months)", 0, 120, 4)
    pain_defec     = st.selectbox("Pain related to defecation?", ["Unknown", "Yes", "No"])
    freq_change    = st.selectbox("Pain with change in stool frequency?", ["Unknown", "Yes", "No"])
    form_change    = st.selectbox("Pain with change in stool form?", ["Unknown", "Yes", "No"])
    bool_map       = {"Unknown": None, "Yes": True, "No": False}

    st.markdown("**Baseline Investigations**")
    cbc_done       = st.checkbox("CBC done", value=True)
    ferritin_done  = st.checkbox("Ferritin done", value=True)
    celiac_done    = st.checkbox("Celiac screen done", value=True)
    celiac_pos     = st.checkbox("Celiac screen positive")

    st.markdown("**Alarm Features**")
    st.caption("Any alarm feature → urgent referral")
    fh_crc         = st.checkbox("Family history of CRC (1st degree)")
    fh_ibd         = st.checkbox("Family history of IBD (1st degree)")
    onset_50       = st.checkbox("Symptom onset after age 50")
    visible_blood  = st.checkbox("Visible blood in stool")
    nocturnal      = st.checkbox("Nocturnal symptoms")
    ida_present    = st.checkbox("Iron deficiency anemia")
    weight_loss    = st.number_input("Unintended weight loss % over 6–12 months (0 = none)", 0.0, 100.0, 0.0)

    st.markdown("**IBS Subtype**")
    st.caption("Based on stool form on symptomatic days")
    hard_pct       = st.slider("Hard/lumpy stool % of bowel movements", 0, 100, 10)
    loose_pct      = st.slider("Loose/watery stool % of bowel movements", 0, 100, 30)

    st.markdown("**IBD Check**")
    high_ibd       = st.selectbox("High clinical suspicion for IBD?", ["Unknown", "Yes", "No"])
    cal_result     = st.number_input("Fecal calprotectin (µg/g), 0 = not done", 0.0, 5000.0, 0.0)

    st.markdown("**Response to Treatment**")
    unsat          = st.selectbox("Response to treatment", ["Unknown", "Satisfactory", "Unsatisfactory"])
    unsat_map      = {"Unknown": None, "Satisfactory": False, "Unsatisfactory": True}

    # ── OVERRIDE ──
    st.markdown("---")
    st.subheader("⚠ Clinician Override")
    override_active = st.checkbox("Apply an override")
    overrides_list  = []
    if override_active:
        ov_node   = st.selectbox("Node to override", ["Confirm_IBS_Criteria", "Alarm_Features", "Determine_Subtype"])
        ov_field_map = {
            "Confirm_IBS_Criteria": "ibs_criteria_met",
            "Alarm_Features":       "alarm_features_present",
            "Determine_Subtype":    "ibs_subtype",
        }
        ov_field  = ov_field_map[ov_node]
        if ov_node == "Determine_Subtype":
            ov_value = st.selectbox("New subtype value", ["IBS-C", "IBS-D", "IBS-M", "IBS-U"])
        else:
            ov_value = st.selectbox("New value", ["True", "False"]) == "True"
        ov_reason   = st.text_area("Clinical reason (required)")
        ov_initials = st.text_input("Clinician initials")
        if ov_reason and ov_initials:
            overrides_list.append(Override(
                target_node=ov_node, field=ov_field,
                old_value=None, new_value=ov_value,
                reason=f"[{ov_initials}] {ov_reason}",
            ))
        elif override_active:
            st.warning("Fill in reason and initials to activate override.")

    run = st.button("▶ Run Pathway", type="primary", use_container_width=True)

with right:
    if run:
        patient_data = {
            "abdominal_pain_days_per_week":                 pain_days,
            "symptom_months_present":                       symptom_months,
            "pain_related_to_defecation":                   bool_map[pain_defec],
            "pain_with_change_in_stool_frequency":          bool_map[freq_change],
            "pain_with_change_in_stool_form":               bool_map[form_change],
            "cbc_done":                                     cbc_done or None,
            "ferritin_done":                                ferritin_done or None,
            "celiac_screen_done":                           celiac_done or None,
            "celiac_screen_positive":                       celiac_pos or None,
            "family_history_crc_first_degree":              fh_crc or None,
            "family_history_ibd_first_degree":              fh_ibd or None,
            "symptom_onset_after_age_50":                   onset_50 or None,
            "visible_blood_in_stool":                       visible_blood or None,
            "nocturnal_symptoms":                           nocturnal or None,
            "iron_deficiency_anemia_present":               ida_present or None,
            "unintended_weight_loss_percent_6_to_12_months": weight_loss if weight_loss > 0 else None,
            "hard_stool_percent":                           hard_pct,
            "loose_stool_percent":                          loose_pct,
            "high_suspicion_ibd":                           bool_map[high_ibd],
            "fecal_calprotectin_ug_g":                      cal_result if cal_result > 0 else None,
            "unsatisfactory_response_to_treatment":         unsat_map[unsat],
        }

        outputs, logs, applied_overrides = run_ibs_pathway(patient_data, overrides=overrides_list)

        # ── ANIMATED DIAGRAM ──
        all_nodes = [
            ("criteria",    "IBS\nCriteria"),
            ("baseline",    "Baseline\nInvestigations"),
            ("alarm",       "Alarm\nFeatures?"),
            ("subtype",     "Determine\nSubtype"),
            ("treatment",   "Subtype\nTreatment"),
            ("ibd",         "IBD\nCheck"),
            ("calprotectin","Fecal\nCalprotectin"),
            ("response",    "Management\nResponse"),
        ]
        edges = [
            ("criteria","baseline"), ("baseline","alarm"), ("alarm","subtype"),
            ("subtype","treatment"), ("treatment","ibd"), ("ibd","calprotectin"),
            ("calprotectin","response"),
        ]
        node_map = {
            "Confirm_IBS_Criteria":  "criteria",
            "Baseline_Investigations": "baseline",
            "Alarm_Features":        "alarm",
            "Determine_Subtype":     "subtype",
            "Subtype_Treatment":     "treatment",
            "IBD_Check":             "ibd",
            "Fecal_Calprotectin":    "calprotectin",
            "Management_Response":   "response",
        }
        visited = {"criteria"}
        for log in logs:
            n = node_map.get(log.node)
            if n: visited.add(n)

        n_nodes = len(all_nodes)
        node_w, node_h, gap, pad = 100, 60, 28, 30
        total_w = pad + n_nodes * node_w + (n_nodes - 1) * gap + pad
        positions = {nid: (pad + i * (node_w + gap), 30) for i, (nid, _) in enumerate(all_nodes)}

        svg = [
            f'<svg width="100%" viewBox="0 0 {total_w} 160" xmlns="http://www.w3.org/2000/svg" style="background:#0e0e0e;border-radius:14px;">',
            '<defs><marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round"/></marker></defs>',
        ]
        for a, b in edges:
            ax, ay = positions[a]; bx, by = positions[b]
            svg.append(f'<line data-from="{a}" data-to="{b}" x1="{ax+node_w}" y1="{ay+node_h//2}" x2="{bx}" y2="{by+node_h//2}" stroke="#333" stroke-width="2" marker-end="url(#arr)" style="transition:stroke 0.5s"/>')
        for nid, title in all_nodes:
            x, y = positions[nid]
            svg.append(f'<rect data-node="{nid}" x="{x}" y="{y}" width="{node_w}" height="{node_h}" rx="8" fill="#1e1e1e" stroke="#3a3a3a" stroke-width="1.5" style="transition:fill 0.5s,stroke 0.5s"/>')
            for li, line in enumerate(title.split("\n")):
                svg.append(f'<text x="{x+node_w//2}" y="{y+22+li*16}" text-anchor="middle" font-size="11" font-weight="700" fill="#666" font-family="Arial" data-label="{nid}" style="transition:fill 0.5s">{line}</text>')
        svg.append(f'<rect x="{pad}" y="110" width="12" height="12" rx="2" fill="#1a5c30" stroke="#21c55d" stroke-width="1.5"/><text x="{pad+18}" y="121" font-size="10" fill="#888" font-family="Arial">Followed</text>')
        svg.append(f'<rect x="{pad+90}" y="110" width="12" height="12" rx="2" fill="#1e1e1e" stroke="#3a3a3a" stroke-width="1.5"/><text x="{pad+108}" y="121" font-size="10" fill="#888" font-family="Arial">Not reached</text>')
        svg.append("</svg>")

        node_order = [nid for nid, _ in all_nodes]
        animated_html = f"""
        {"".join(svg)}
        <script>
        const visited = {list(visited)};
        const nodeOrder = {node_order};
        function animate() {{
            let i = 0;
            function step() {{
                if (i >= nodeOrder.length) return;
                const nid = nodeOrder[i];
                if (visited.includes(nid)) {{
                    const rect = document.querySelector('rect[data-node="' + nid + '"]');
                    const labels = document.querySelectorAll('text[data-label="' + nid + '"]');
                    const edgeIn = document.querySelector('line[data-to="' + nid + '"]');
                    if (rect) {{ rect.style.fill='#1a5c30'; rect.style.stroke='#21c55d'; }}
                    labels.forEach(l => l.style.fill='#ffffff');
                    if (edgeIn) edgeIn.setAttribute('stroke','#21c55d');
                }}
                i++; setTimeout(step, 400);
            }}
            step();
        }}
        setTimeout(animate, 200);
        </script>
        """
        st.subheader("🗺 Pathway Followed")
        components.html(animated_html, height=180, scrolling=False)
        st.markdown("---")

        for o in outputs:
            if isinstance(o, Stop):
                if (o.urgency or "").lower() == "urgent":
                    st.error(f"🚨 URGENT: {o.reason}")
                else:
                    st.info(f"ℹ {o.reason}")
            elif isinstance(o, DataRequest):
                st.warning(f"⏸ Pathway paused — missing: {', '.join(o.missing_fields)}")

        st.subheader("Clinical Recommendations")
        st.markdown('<div class="section-header">Recommended Actions</div>', unsafe_allow_html=True)

        def render_output(o):
            if isinstance(o, Action):
                urgency_raw = (o.urgency or "").lower()
                if urgency_raw == "urgent":
                    card_class, badge = "card-urgent", '<span class="badge-urgent">🔴 URGENT</span>'
                elif urgency_raw == "routine":
                    card_class, badge = "card-routine", '<span class="badge-routine">🟢 ROUTINE</span>'
                else:
                    card_class, badge = "card-info", '<span class="badge-info">🔵 INFO</span>'
                details = o.details if isinstance(o.details, dict) else {}
                supported = details.get("supported_by", [])
                options = details.get("options", [])
                details_html = "".join(f'<div class="card-detail">• {d}</div>' for d in supported)
                details_html += "".join(f'<div class="card-detail">• {d}</div>' for d in options)
                st.markdown(f'<div class="{card_class}"><div class="card-title">{badge} {o.label}</div>{details_html}</div>', unsafe_allow_html=True)
            elif isinstance(o, DataRequest):
                with st.container(border=True):
                    st.warning(f"**Missing data — blocked at: {o.blocking_node}**")
                    st.write(o.message)
                    st.write(f"**Required:** {', '.join(o.missing_fields)}")
            elif isinstance(o, Stop):
                for a in o.actions:
                    card_class = "card-urgent" if (o.urgency or "").lower() == "urgent" else "card-routine"
                    badge = '<span class="badge-urgent">🔴 URGENT</span>' if card_class == "card-urgent" else '<span class="badge-routine">🟢 DONE</span>'
                    details = a.details if isinstance(a.details, dict) else {}
                    supported = details.get("supported_by", [])
                    details_html = "".join(f'<div class="card-detail">• {d}</div>' for d in supported)
                    st.markdown(f'<div class="{card_class}"><div class="card-title">{badge} {a.label}</div>{details_html}</div>', unsafe_allow_html=True)

        for o in outputs:
            render_output(o)

        with st.expander("📋 Decision Audit Log"):
            for log in logs:
                st.markdown(f"**[{log.node}]** {log.decision}")
                if log.used_inputs:
                    st.json(log.used_inputs)

        if applied_overrides:
            with st.expander("🔏 Applied Overrides"):
                for ov in applied_overrides:
                    st.markdown(f"- **{ov.target_node} / {ov.field}**: `{ov.old_value}` → `{ov.new_value}`")
                    st.caption(f"Reason: {ov.reason}")
    else:
        st.info("Fill in patient details on the left and click ▶ Run Pathway")
