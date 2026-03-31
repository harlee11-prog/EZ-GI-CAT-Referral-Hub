import streamlit as st

st.set_page_config(
    page_title="EZ GI CAT Clinical Decision Hub",
    page_icon="🩺",
    layout="wide",
)

PATHWAYS = [
    {"title": "H. Pylori", "page": "pages/1_H_Pylori.py", "pdf": "https://www.albertahealthservices.ca/assets/about/scn/ahs-scn-dh-pathway-hpylori.pdf", "group": "Upper GI", "desc": "Testing, treatment, and eradication follow-up."},
    {"title": "GERD", "page": "pages/3_GERD.py", "pdf": "https://www.albertahealthservices.ca/assets/info/aph/if-aph-scn-dh-pathway-gerd.pdf", "group": "Upper GI", "desc": "Assessment and management of reflux symptoms."},
    {"title": "Dyspepsia", "page": "pages/11_Dyspepsia.py", "pdf": "https://www.albertahealthservices.ca/assets/info/aph/if-aph-scn-dh-pathway-dyspepsia.pdf", "group": "Upper GI", "desc": "Initial workup, alarm features, and referral triggers."},
    {"title": "Gastric Cancer", "page": "pages/12_Gastric_Cancer_draft.py", "pdf": "https://www.albertahealthservices.ca/assets/info/aph/if-aph-prov-gastric-cancer-prevention-screening-and-diagnosis-primary-care-pathway.pdf", "group": "Upper GI", "desc": "Prevention, screening, diagnosis, and referral."},

    {"title": "IBS", "page": "pages/5_IBS.py", "pdf": "http://www.ahs.ca/assets/about/scn/ahs-scn-dh-pathway-ibs.pdf", "group": "Lower GI", "desc": "Diagnosis support and symptom-based pathway."},
    {"title": "Chronic Diarrhea", "page": "pages/9_Chronic_Diarrhea.py", "pdf": "http://www.ahs.ca/assets/about/scn/ahs-scn-dh-pathway-chronic-diarrhea.pdf", "group": "Lower GI", "desc": "Stepwise evaluation of persistent diarrhea."},
    {"title": "Chronic Constipation", "page": "pages/10_Constipation.py", "pdf": "https://www.albertahealthservices.ca/assets/about/scn/ahs-scn-dh-pathway-chronic-constipation.pdf", "group": "Lower GI", "desc": "Assessment and treatment planning for constipation."},
    {"title": "HRRB", "page": "pages/6_HRRB.py", "pdf": "https://www.albertahealthservices.ca/assets/about/scn/ahs-scn-cancer-high-risk-rectal-bleeding-pathway.pdf", "group": "Lower GI", "desc": "High-risk rectal bleeding pathway and escalation guidance."},

    {"title": "Liver Mass", "page": "pages/2_Liver_Mass.py", "pdf": "https://www.albertahealthservices.ca/assets/info/aph/if-aph-prov-liver-mass-primary-care-pathway.pdf", "group": "Liver", "desc": "Primary care pathway for liver mass evaluation."},
    {"title": "NAFLD", "page": "pages/4_NAFLD.py", "pdf": "http://www.ahs.ca/assets/about/scn/ahs-scn-dh-pathway-nafld.pdf", "group": "Liver", "desc": "Risk stratification and fibrosis assessment support."},
    {"title": "HCV", "page": "pages/8_HCV.py", "pdf": "http://www.ahs.ca/assets/about/scn/ahs-scn-dh-pathway-hepatitisc.pdf", "group": "Liver", "desc": "Hepatitis C assessment and pathway navigation."},

    {"title": "Iron Deficiency Anemia", "page": "pages/7_IDA.py", "pdf": "https://www.albertahealthservices.ca/assets/about/scn/ahs-scn-cancer-iron-deficiency-anemia-pathway.pdf", "group": "Cancer / Anemia", "desc": "Workup and referral pathway for iron deficiency anemia."},
]

st.markdown("""
<style>
#MainMenu {visibility: hidden !important;}
header {visibility: hidden !important;}
footer {visibility: hidden !important;}
[data-testid="stToolbar"] {display: none !important;}
[data-testid="stDecoration"] {display: none !important;}
[data-testid="stStatusWidget"] {display: none !important;}
.stAppDeployButton {display: none !important;}
div[class*="viewerBadge"] {display: none !important;}

.stApp {
    background: linear-gradient(180deg, #f6f8fb 0%, #eef3f8 100%);
}

.block-container {
    max-width: 1250px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

.hero {
    background: linear-gradient(135deg, #123b63 0%, #1e5a8a 100%);
    border-radius: 20px;
    padding: 2rem 2.2rem;
    color: white;
    margin-bottom: 1.5rem;
    box-shadow: 0 18px 40px rgba(18, 59, 99, 0.18);
}

.hero h1 {
    margin: 0;
    font-size: 2.3rem;
    font-weight: 800;
    letter-spacing: -0.5px;
}

.hero p {
    margin: 0.5rem 0 0 0;
    color: rgba(255,255,255,0.88);
    font-size: 1rem;
}

.stat-row {
    display: flex;
    gap: 0.75rem;
    margin-top: 1.25rem;
    flex-wrap: wrap;
}

.stat-pill {
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.16);
    border-radius: 999px;
    padding: 0.55rem 0.9rem;
    font-size: 0.9rem;
    color: white;
}

.section-label {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: #6b7280;
    font-weight: 700;
    margin: 1.3rem 0 0.8rem 0.1rem;
}

.tile {
    background: #ffffff;
    border: 1px solid #dbe4ee;
    border-radius: 18px;
    padding: 1.15rem 1.1rem 1rem 1.1rem;
    min-height: 210px;
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
    transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
    margin-bottom: 1rem;
}

.tile:hover {
    transform: translateY(-3px);
    box-shadow: 0 14px 34px rgba(15, 23, 42, 0.09);
    border-color: #b8c8da;
}

.tile-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 0.75rem;
    margin-bottom: 0.8rem;
}

.tile-title {
    font-size: 1.55rem;
    font-weight: 800;
    color: #1f2937;
    line-height: 1.1;
    margin: 0;
}

.tile-badge {
    font-size: 0.72rem;
    font-weight: 700;
    color: #1d4f7a;
    background: #eaf3fb;
    border: 1px solid #d4e5f5;
    border-radius: 999px;
    padding: 0.25rem 0.55rem;
    white-space: nowrap;
}

.tile-desc {
    font-size: 0.93rem;
    color: #667085;
    min-height: 48px;
    margin-bottom: 1rem;
}

.group-divider {
    margin-top: 0.4rem;
    margin-bottom: 0.8rem;
}

[data-testid="stPageLink"] a {
    background: #123b63 !important;
    color: white !important;
    border-radius: 12px !important;
    padding: 0.62rem 0.9rem !important;
    font-weight: 600 !important;
    text-align: center !important;
    border: none !important;
}

.stLinkButton a {
    border-radius: 12px !important;
    padding: 0.62rem 0.9rem !important;
    font-weight: 600 !important;
    border: 1px solid #d0d9e5 !important;
    background: #f8fafc !important;
    color: #334155 !important;
}

@media (max-width: 900px) {
    .hero h1 {
        font-size: 1.8rem;
    }
    .tile {
        min-height: auto;
    }
}
</style>
""", unsafe_allow_html=True)

groups = ["Upper GI", "Lower GI", "Liver", "Cancer / Anemia"]

st.markdown(f"""
<div class="hero">
    <h1>EZ GI CAT Clinical Decision Support Hub</h1>
    <p>Primary care decision pathways for common GI and liver presentations, with direct access to internal tools and AHS pathway PDFs.</p>
    <div class="stat-row">
        <div class="stat-pill">{len(PATHWAYS)} pathways</div>
        <div class="stat-pill">Primary care focused</div>
        <div class="stat-pill">PDF references linked</div>
        <div class="stat-pill">Clinical workflow hub</div>
    </div>
</div>
""", unsafe_allow_html=True)

for group in groups:
    items = [p for p in PATHWAYS if p["group"] == group]
    st.markdown(f'<div class="section-label">{group}</div>', unsafe_allow_html=True)
    cols = st.columns(3)

    for i, item in enumerate(items):
        with cols[i % 3]:
            st.markdown(
                f"""
                <div class="tile">
                    <div class="tile-top">
                        <div class="tile-title">{item['title']}</div>
                        <div class="tile-badge">{item['group']}</div>
                    </div>
                    <div class="tile-desc">{item['desc']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            a, b = st.columns([1.3, 1])
            with a:
                st.page_link(item["page"], label="Open pathway", use_container_width=True)
            with b:
                st.link_button("View PDF", item["pdf"], use_container_width=True)
