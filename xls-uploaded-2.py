import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="eVidyaloka M&E Impact Dashboard", layout="wide")

# --- 2. EXECUTIVE THEME ---
st.markdown("""
    <style>
    .main { background-color: #f8fafc; color: #0f172a; }
    h1, h2, h3 { color: #001f3f !important; font-family: 'Segoe UI', sans-serif; }
    .focus-bar {
        background-color: #001f3f; color: white; padding: 15px 25px;
        border-radius: 8px; margin-bottom: 25px; font-weight: 600; font-size: 1.1rem;
    }
    .insight-box {
        background-color: #ffffff; padding: 20px; border-radius: 10px;
        border-left: 5px solid #001f3f; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    div[data-testid="stMetric"] {
        background-color: #ffffff; border-radius: 10px; padding: 15px !important;
        border: 1px solid #cbd5e1; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    [data-testid="stMetricValue"] { font-size: 1.6rem !important; color: #001f3f !important; }
    section[data-testid="stSidebar"] { background-color: #ffffff !important; border-right: 1px solid #e2e8f0; }
    .stTabs [aria-selected="true"] { background-color: #001f3f !important; color: #ffffff !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATA UPLOAD CENTER ---
st.title("eVidyaloka M&E Impact Dashboard")
st.markdown("### 📂 Master Workbook Upload")
uploaded_file = st.file_uploader("Upload Excel Workbook (.xlsx)", type=["xlsx"])


# --- 4. DYNAMIC DATA LOADING LOGIC ---
@st.cache_data
def load_and_process_dynamic(file):
    excel_file = pd.ExcelFile(file)
    sheet_names = excel_file.sheet_names

    # Fuzzy Matching: Find sheets containing 'Baseline' or 'Endline'
    bl_sheet = next((s for s in sheet_names if 'baseline' in s.lower()), None)
    el_sheet = next((s for s in sheet_names if 'endline' in s.lower()), None)

    if not bl_sheet or not el_sheet:
        raise ValueError(f"Could not find required sheets. Found: {sheet_names}")

    df_bl = pd.read_excel(file, sheet_name=bl_sheet)
    df_el = pd.read_excel(file, sheet_name=el_sheet)

    # Pre-processing
    df_bl['Score_%'] = (df_bl['Obtained Marks'] / df_bl['Total Marks']) * 100
    df_el['Score_%'] = (df_el['Obtained Marks'] / df_el['Total Marks']) * 100

    # Matched Cohort Analysis (The 358 unique students)
    df_matched = pd.merge(df_el, df_bl[['Student ID', 'Grade', 'Subject', 'Score_%', 'Obtained Marks']],
                          on=['Student ID', 'Grade', 'Subject'], how='inner', suffixes=('_EL', '_BL'))

    rise_cats = ['Reviving', 'Initiating', 'Shaping', 'Evolving']

    def get_tier(p):
        if p < 35: return 'Reviving'
        if p < 50: return 'Initiating'
        if p < 75: return 'Shaping'
        return 'Evolving'

    df_matched['Tier_EL'] = pd.Categorical(df_matched['Score_%_EL'].apply(get_tier), categories=rise_cats, ordered=True)
    df_matched['Tier_BL'] = pd.Categorical(df_matched['Score_%_BL'].apply(get_tier), categories=rise_cats, ordered=True)

    return df_bl, df_el, df_matched, bl_sheet, el_sheet


# --- 5. DASHBOARD EXECUTION ---
if uploaded_file:
    try:
        df_bl, df_el, df_matched, bl_name, el_name = load_and_process_dynamic(uploaded_file)

        # --- SIDEBAR FILTERS ---
        with st.sidebar:
            st.success(f"Loaded: {bl_name} & {el_name}")
            st.header("Executive Filters")
            sel_donor = st.selectbox("Donor Profile", ["All Donors"] + sorted(df_bl['Donor'].unique().tolist()))
            sel_state = st.selectbox("Region / State", ["All States"] + sorted(df_bl['State'].unique().tolist()))
            sel_grade = st.selectbox("Grade Level", ["All Grades"] + sorted(df_bl['Grade'].unique().tolist()))
            sel_subject = st.selectbox("Focus Subject", ["All Subjects"] + sorted(df_bl['Subject'].unique().tolist()))
            st.markdown("---")
            view_limit = st.selectbox("Centers to Display", options=["10", "20", "All"], index=0)

        # Filtering Logic
        f_bl_g, f_el_g, f_m_g = df_bl.copy(), df_el.copy(), df_matched.copy()
        for df in [f_bl_g, f_el_g, f_m_g]:
            if sel_donor != "All Donors": df.query("Donor == @sel_donor", inplace=True)
            if sel_state != "All States": df.query("State == @sel_state", inplace=True)
            if sel_grade != "All Grades": df.query("Grade == @sel_grade", inplace=True)

        f_bl_f = f_bl_g[f_bl_g['Subject'] == sel_subject] if sel_subject != "All Subjects" else f_bl_g
        f_el_f = f_el_g[f_el_g['Subject'] == sel_subject] if sel_subject != "All Subjects" else f_el_g
        f_m_f = f_m_g[f_m_g['Subject'] == sel_subject] if sel_subject != "All Subjects" else f_m_g

        # --- MAIN VISUALS ---
        st.markdown(
            f"""<div class="focus-bar">Context: {sel_subject} | Region: {sel_state} | Grade Scope: {sel_grade}</div>""",
            unsafe_allow_html=True)
        tab1, tab2, tab3 = st.tabs(["📊 Executive Summary", "📍 Center Performance", "📈 RISE Analysis"])

        with tab1:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("States", f_bl_f['State'].nunique())
            c2.metric("Schools", f_bl_f['Centre Name'].nunique())
            c3.metric("Matched Students", len(f_m_f))  # longitudinal cohort
            c4.metric("Avg (Baseline)", f"{f_bl_f['Obtained Marks'].mean():.2f}/10")
            c5.metric("Avg (Endline)", f"{f_el_f['Obtained Marks'].mean():.2f}/10")

            st.markdown("### Learning Outcomes Analysis")
            if not f_m_g.empty:
                matrix = f_m_g.groupby(['Grade', 'Subject']).agg(
                    Students=('Student ID', 'count'), Avg_BL=('Score_%_BL', 'mean'),
                    Avg_EL=('Score_%_EL', 'mean'), Std_Dev=('Obtained Marks_EL', 'std')
                ).reset_index()
                matrix['% Growth'] = matrix['Avg_EL'] - matrix['Avg_BL']
                matrix['Growth_Display'] = matrix['% Growth'].apply(lambda x: f"{x:+.1f}% {'↑' if x > 0 else '↓'}")
                st.dataframe(matrix[['Grade', 'Subject', 'Students', 'Growth_Display', 'Std_Dev']].style.map(
                    lambda x: 'color: #10b981;' if '↑' in str(x) else 'color: #ef4444;',
                    subset=['Growth_Display']).format(precision=1), use_container_width=True, hide_index=True)

        with tab2:
            st.subheader("Center Performance & Migration")
            search = st.text_input("🔍 Find a Center:", "")
            view_c = st.selectbox("Rank By:", ["Endline Scores", "Baseline Scores"])
            target = f_el_f if "Endline" in view_c else f_bl_f
            rank = target.groupby('Centre Name')['Obtained Marks'].mean().sort_values(ascending=False).reset_index()
            if search: rank = rank[rank['Centre Name'].str.contains(search, case=False)]
            if view_limit != "All" and not search: rank = rank.head(int(view_limit))
            st.plotly_chart(px.bar(rank, x='Obtained Marks', y='Centre Name', orientation='h', color='Obtained Marks',
                                   color_continuous_scale='Blues', text_auto='.1f').update_layout(
                plot_bgcolor='rgba(0,0,0,0)', xaxis_range=[0, 10]), use_container_width=True)

            st.markdown("### 📍 Center-wise RISE Migration (% Change)")
            if not f_m_f.empty:
                bl_d = pd.crosstab(f_m_f['Centre Name'], f_m_f['Tier_BL'], normalize='index') * 100
                el_d = pd.crosstab(f_m_f['Centre Name'], f_m_f['Tier_EL'], normalize='index') * 100
                mig = (el_d - bl_d).reindex(columns=['Reviving', 'Initiating', 'Shaping', 'Evolving'], fill_value=0)
                if search:
                    mig = mig[mig.index.str.contains(search, case=False)]
                elif view_limit != "All":
                    mig = mig.head(int(view_limit))
                st.dataframe(mig.style.background_gradient(cmap='RdYlGn', axis=None).format("{:+.1f}%"),
                             use_container_width=True)

        with tab3:
            if not f_m_f.empty:
                st.subheader("RISE Model Analysis")
                # Grouped bar chart with strict order and visual polish
                bl_dist = f_m_f['Tier_BL'].value_counts(normalize=True).reindex(
                    ['Reviving', 'Initiating', 'Shaping', 'Evolving']).fillna(0) * 100
                el_dist = f_m_f['Tier_EL'].value_counts(normalize=True).reindex(
                    ['Reviving', 'Initiating', 'Shaping', 'Evolving']).fillna(0) * 100
                plot_df = pd.DataFrame({'Tier': ['Reviving', 'Initiating', 'Shaping', 'Evolving'] * 2,
                                        'Percentage': list(bl_dist.values) + list(el_dist.values),
                                        'Assessment': ['Baseline'] * 4 + ['Endline'] * 4})
                fig = px.bar(plot_df, x='Tier', y='Percentage', color='Tier', barmode='group', facet_col='Assessment',
                             color_discrete_map={'Reviving': '#ef4444', 'Initiating': '#f59e0b', 'Shaping': '#3b82f6',
                                                 'Evolving': '#10b981'}, text_auto='.1f',
                             category_orders={"Tier": ["Reviving", "Initiating", "Shaping", "Evolving"]})
                fig.update_layout(bargap=0.1, plot_bgcolor='rgba(0,0,0,0)')
                fig.update_traces(textposition='outside')
                st.plotly_chart(fig, use_container_width=True)

                st.markdown(
                    f"""<div class="insight-box">• <b>Risk Reduction:</b> {bl_dist['Reviving'] - el_dist['Reviving']:.1f}% decrease in Reviving tier.<br>• <b>Excellence Growth:</b> {el_dist['Evolving'] - bl_dist['Evolving']:.1f}% increase in Evolving tier.</div>""",
                    unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error: {e}. Check if sheet names contain 'Baseline' and 'Endline'.")
else:
    st.info("👋 Upload a workbook with 'Baseline' and 'Endline' sheets to start.")