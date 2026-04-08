# pathway_handoff.py
# ─────────────────────────────────────────────────────────────────────────────
# Shared cross-pathway handoff helper for EZ-GI-CAT Referral Hub
#
# Usage (in each page file, at the top after imports):
#   from pathway_handoff import apply_handoff, queue_handoff, show_handoff_banner, HANDOFF_KEY
#
# How it works:
#   • When an engine output triggers a route (e.g. ROUTE_HPYLORI_PATHWAY),
#     the SOURCE page calls queue_handoff(target_page, patient_data).
#   • On the NEXT render of the TARGET page, apply_handoff() detects the
#     queued payload, pre-fills session-state widget keys, and clears the
#     queue so it only fires once.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st

HANDOFF_KEY = "_cross_pathway_handoff"

# Fields that every pathway page reads from the patient_data dict.
# (Kept for documentation; you do not have to use this list explicitly.)
_COMMON_FIELDS = [
    "age", "sex",
    "pregnant", "breastfeeding",
    # Alarm features (shared across all three)
    "familyhistoryuppergicancerfirstdegree",
    "familyhistoryesophagealorgastriccancerfirstdegree",
    "symptomonsetafterage60",
    "ageover60newpersistentsymptomsover3months",
    "unintendedweightloss",
    "blackstoolorbloodinvomit",
    "dysphagia", "progressivedysphagia",
    "persistentvomiting",
    "irondeficiencyanemiapresent",
    "activelybleedingnow",
    # H. pylori result (shared between Dyspepsia and H. Pylori pages)
    "hpyloritestdone", "hpyloriresultpositive",
    "hptestresult", "hptesttype",
    # PPI status (shared between GERD and Dyspepsia)
    "ppioncedailytrialdone", "ppioncedailyresponseadequate",
    "ppibidtrialdone", "ppibidresponseadequate",
    # Symptom overlap
    "predominantheartburn", "predominantregurgitation",
    "predominantepigastricpain", "predominantepigastricdiscomfort",
    "predominantupperabdominalbloating",
    "symptomdurationmonths",
]


def queue_handoff(target_page, patient_data):
    """
    Call this from a source page when a cross-pathway route is triggered.

    target_page : one of "1_H._Pylori", "2_GERD", "3_Dyspepsia"
    patient_data: the full patient_data dict collected by the source page
    """
    st.session_state[HANDOFF_KEY] = {
        "target": target_page,
        # Only carry non-None values across
        "data": {k: v for k, v in patient_data.items() if v is not None},
    }


def apply_handoff(current_page):
    """
    Call this near the top of each page (before widgets are rendered).

    If a handoff payload is waiting for this page:
      • Returns the transferred patient_data dict
      • Clears the handoff queue so it only fires once
    Otherwise returns None.
    """
    payload = st.session_state.get(HANDOFF_KEY)
    if payload and payload.get("target") == current_page:
        # One‑shot: clear after reading so we don't re-apply indefinitely
        del st.session_state[HANDOFF_KEY]
        return payload.get("data", {})
    return None


def show_handoff_banner(source_label, transferred_fields):
    """
    Render an info banner when a handoff has just been applied.

    source_label: human‑readable name of the source pathway
    transferred_fields: list of field names that were carried over
    """
    if not transferred_fields:
        return

    # Show up to 6 field names inline, then "+N more" if longer.
    fields_str = ", ".join("`%s`" % f for f in transferred_fields[:6])
    if len(transferred_fields) > 6:
        fields_str += " … (+%d more)" % (len(transferred_fields) - 6)

    st.info(
        "↩️ **Patient data carried over from %s pathway.** "
        "Pre-filled fields: %s. Review and adjust as needed."
        % (source_label, fields_str),
        icon="🔗",
    )
