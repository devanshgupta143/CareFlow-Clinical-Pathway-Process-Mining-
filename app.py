import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Page Configuration
st.set_page_config(
    page_title="CareFlow Clinical Pathway Process Mining",
    page_icon="💙",
    layout="wide"
)

# Initialize Authentication State
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ==========================================
# LOGIN SCREEN (If not logged in)
# ==========================================
if not st.session_state.logged_in:
    st.markdown("""
        <style>
        .stApp { background-color: #f8fafc; }
        </style>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1.1, 0.9])

    with col1:
        st.markdown("### 💙 **CareFlow**")
        st.markdown("##### Clinical Pathway Process Mining")
        st.markdown("## Smarter Insights. Healthier Journeys.")
        st.write("Transforming patient data into actionable insights for better clinical outcomes.")
        st.info("🔄 **Patient Journey Flow:** Admission ➔ Diagnosis ➔ Treatment ➔ Discharge")

    with col2:
        st.markdown("### Welcome Back 👋")
        st.write("Sign in to access the CareFlow analytics platform.")
        
        with st.form("login_form"):
            username = st.text_input("Username / Email", placeholder="Username / Email")
            password = st.text_input("Password", type="password", placeholder="Password")
            submit_btn = st.form_submit_button("Sign In →", use_container_width=True)
            
            if submit_btn:
                if username == "admin" and password == "1234":
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("Invalid username or password. (Use admin / 1234)")
        
        st.caption("Practice Login: admin / 1234")
    
    st.stop()

# ==========================================
# MAIN APPLICATION (After successful login)
# ==========================================

st.sidebar.markdown("### 💙 CareFlow")
st.sidebar.caption("Clinical Pathway Process Mining")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    [
        "Overview", 
        "Patient Flow", 
        "Process Mining", 
        "Department Analysis", 
        "Performance Metrics", 
        "Reports"
    ]
)

st.sidebar.markdown("---")
st.sidebar.info("📅 **Data Period:**\n01 Jan 2025 – 30 Sep 2025")

if st.sidebar.button("Logout", use_container_width=True):
    st.session_state.logged_in = False
    st.rerun()

# ==========================================
# PAGE ROUTING & FULL CHARTS
# ==========================================

if page == "Overview":
    st.markdown("### **Executive Dashboard**")
    st.caption("Key insights into patient flow, operational performance and clinical efficiency")
    st.markdown("---")
    
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Patients", "12,482", "↑ 8.4%")
    m2.metric("Avg. Length of Stay", "4.2 Days", "↓ 12.5%", delta_color="inverse")
    m3.metric("Total Process Time", "18.6 Hours", "↓ 15.8%", delta_color="inverse")
    m4.metric("Readmission Rate", "6.3%", "↓ 2.1%", delta_color="inverse")
    m5.metric("Patient Satisfaction", "92%", "↑ 4.7%")
    
    st.markdown("---")
    
    c_flow, c_trend, c_vol = st.columns([1.5, 1.2, 1])
    with c_flow:
        st.subheader("Patient Flow Through Clinical Pathway")
        st.info("🔄 **Admission** (12,482) ➔ **Diagnosis** (11,856) ➔ **Treatment** (10,982) ➔ **Discharge** (10,421)")
    with c_trend:
        st.subheader("Average Length of Stay Trend")
        trend_df = pd.DataFrame({
            'Month': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep'],
            'Actual': [8.5, 7.8, 7.2, 7.4, 7.0, 6.8, 6.6, 6.5, 6.3],
            'Target': [8.0, 7.5, 7.0, 7.0, 6.8, 6.5, 6.5, 6.3, 6.0]
        })
        fig_line = px.line(trend_df, x='Month', y=['Actual', 'Target'], markers=True, height=220)
        fig_line.update_layout(margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig_line, use_container_width=True)
    with c_vol:
        st.subheader("Patient Volume by Dept")
        dept_data = pd.DataFrame({'Department': ['General Medicine', 'Surgery', 'Orthopedics', 'Cardiology', 'Others'], 'Share': [28, 22, 16, 12, 22]})
        fig_pie = px.pie(dept_data, names='Department', values='Share', hole=0.6, height=220)
        fig_pie.update_layout(margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True)

elif page == "Patient Flow":
    st.markdown("### **Patient Flow & Journey Tracking**")
    st.caption("Detailed pathway tracking from admission to discharge across departments.")
    st.markdown("---")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Active Inpatients", "2,410", "↑ 3.2%")
    c2.metric("Average Transfer Time", "42 mins", "↓ 8.1%")
    c3.metric("Discharge Efficiency", "88.4%", "↑ 5.0%")
    st.markdown("---")
    
    st.subheader("Patient Flow Status Matrix")
    st.dataframe(pd.DataFrame({
        'Patient ID': ['PT-1001', 'PT-1002', 'PT-1003', 'PT-1004'],
        'Department': ['General Medicine', 'Surgery', 'Cardiology', 'Orthopedics'],
        'Current Stage': ['Treatment', 'Diagnosis', 'Admission', 'Discharge'],
        'Elapsed Time (Hrs)': [6.5, 3.2, 1.8, 11.4],
        'Status': ['On Track', 'Delayed', 'On Track', 'Completed']
    }), use_container_width=True, hide_index=True)

elif page == "Process Mining":
    st.markdown("### **Process Mining & Patient Flow Analysis**")
    st.caption("Visualizing actual vs. ideal process and bottlenecks.")
    st.markdown("---")
    
    c_flow, c_bottleneck, c_dist = st.columns([1.5, 1.2, 1])
    with c_flow:
        st.subheader("Process Flow (Actual vs. Ideal)")
        st.success("Admission (2.1h) ➔ Diagnosis (4.3h) ➔ Treatment (7.8h) ➔ Discharge (4.4h)")
    with c_bottleneck:
        st.subheader("Bottleneck Analysis")
        st.dataframe(pd.DataFrame({
            'Process Step': ['Waiting for Diagnostics', 'Consultation Scheduling', 'Lab Results'],
            'Avg. Wait': ['2.8 h', '1.6 h', '1.2 h'],
            'Status': ['High', 'Medium', 'Low']
        }), use_container_width=True, hide_index=True)
    with c_dist:
        st.subheader("Cycle Time Distribution")
        cyc_df = pd.DataFrame({'Cycle Time (Hours)': ['0-6', '6-12', '12-18', '18-24'], 'Patients': [500, 1500, 1000, 700]})
        fig_cyc = px.bar(cyc_df, x='Cycle Time (Hours)', y='Patients', height=220)
        fig_cyc.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_cyc, use_container_width=True)

elif page == "Department Analysis":
    st.markdown("### **Departmental Performance & Workload Analysis**")
    st.markdown("---")
    dept_df = pd.DataFrame({
        'Department': ['General Medicine', 'Surgery', 'Orthopedics', 'Cardiology'],
        'Total Patients': [3500, 2750, 2000, 1500],
        'Bed Occupancy (%)': [91, 85, 78, 88]
    })
    col_a, col_b = st.columns(2)
    with col_a:
        fig_bar = px.bar(dept_df, x='Department', y='Total Patients', color='Department', height=300)
        st.plotly_chart(fig_bar, use_container_width=True)
    with col_b:
        fig_occ = px.bar(dept_df, x='Department', y='Bed Occupancy (%)', color='Bed Occupancy (%)', color_continuous_scale='Blues', height=300)
        st.plotly_chart(fig_occ, use_container_width=True)

elif page == "Performance Metrics":
    st.markdown("### **Clinical & Operational Performance Metrics**")
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.metric("Target Achievement", "94.2%", "↑ 2.1%")
    col2.metric("SLA Compliance", "91.8%", "↑ 1.4%")
    col3.metric("Resource Utilization", "87.5%", "↓ 0.5%")
    st.markdown("---")
    st.dataframe(pd.DataFrame({
        'Metric Name': ['Average Length of Stay', 'Process Time', 'Readmission Rate'],
        'Actual Value': ['4.2 Days', '18.6 Hours', '6.3%'],
        'Target Value': ['4.0 Days', '16.0 Hours', '< 8.0%']
    }), use_container_width=True, hide_index=True)

elif page == "Reports":
    st.markdown("### **Reports & Data Exports**")
    st.markdown("---")
    st.selectbox("Select Report Type", ["Summary Report", "Detailed Patient Log", "Bottleneck Analysis"])
    if st.button("Generate & Download Report", type="primary"):
        st.success("Report generated and ready for download!")
    st.dataframe(pd.DataFrame({
        'Record ID': ['REC-001', 'REC-002'],
        'Category': ['Clinical Path', 'Discharge Delay'],
        'Status': ['Verified', 'Pending Review']
    }), use_container_width=True, hide_index=True)