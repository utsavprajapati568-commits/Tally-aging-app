import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from fpdf import FPDF

from parser import parse_tally_xml, process_aging_analysis, generate_ai_insights

st.set_page_config(page_title="Audit Intelligence Dashboard", page_icon="📊", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 8px; border: 1px solid #e9ecef; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
    h1, h2, h3 { color: #1e293b; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
    div.stButton > button:first-child { background-color: #0f172a; color: white; border-radius: 6px; }
    </style>
""", unsafe_allow_html=True)

st.title("💼 Enterprise Receivables & Payables Intelligence System")
st.subheader("Automated Tally XML Aging Analysis and Cash Flow Forecast Engine")
st.markdown("---")

st.sidebar.header("⚙️ Control Panel")
uploaded_file = st.sidebar.file_uploader("Upload Tally XML Statement", type=["xml"])
analysis_date = st.sidebar.date_input("Evaluation/Cut-off Date", datetime.today())

if uploaded_file is not None:
    try:
        raw_df = parse_tally_xml(uploaded_file)
        
        if raw_df.empty:
            st.error("❌ The selected XML file doesn't contain standard Tally outstanding transactional elements.")
            st.stop()

        df_debtors = process_aging_analysis(raw_df, analysis_date, "Debtor")
        df_creditors = process_aging_analysis(raw_df, analysis_date, "Creditor")
        ai_insights = generate_ai_insights(df_debtors, df_creditors)

        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Executive Dashboard", "📈 Debtor Strategic View", "📉 Creditor Strategic View", "⏳ Cash Flow Matrix", "🤖 AI Insights Engine"
        ])

        with tab1:
            st.header("Executive Summary Matrix")
            
            total_dr = df_debtors['Outstanding Amount'].sum() if not df_debtors.empty else 0.0
            total_cr = df_creditors['Outstanding Amount'].sum() if not df_creditors.empty else 0.0
            avg_collection = df_debtors['Days Overdue'].mean() if not df_debtors.empty else 0.0
            avg_payment = df_creditors['Days Overdue'].mean() if not df_creditors.empty else 0.0
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Accounts Receivable", f"₹ {total_dr:,.2f}")
            m2.metric("Total Accounts Payable", f"₹ {total_cr:,.2f}")
            m3.metric("Avg Collection Cycle", f"{avg_collection:.1f} Days")
            m4.metric("Avg Payment Delay", f"{avg_payment:.1f} Days")
            
            st.markdown("### Structural Aging Breakdown")
            c1, c2 = st.columns(2)
            
            with c1:
                st.subheader("Receivables (Debtors) Aging Balance")
                if not df_debtors.empty:
                    fig_dr = px.bar(df_debtors.groupby('Aging Bucket', observed=False)['Outstanding Amount'].sum().reset_index(),
                                    x='Aging Bucket', y='Outstanding Amount', color='Aging Bucket',
                                    color_discrete_sequence=px.colors.sequential.Blugrn)
                    st.plotly_chart(fig_dr, use_container_width=True)
                else:
                    st.info("No active open debit records identified.")
                    
            with c2:
                st.subheader("Payables (Creditors) Aging Balance")
                if not df_creditors.empty:
                    fig_cr = px.bar(df_creditors.groupby('Aging Bucket', observed=False)['Outstanding Amount'].sum().reset_index(),
                                    x='Aging Bucket', y='Outstanding Amount', color='Aging Bucket',
                                    color_discrete_sequence=px.colors.sequential.Burg)
                    st.plotly_chart(fig_cr, use_container_width=True)
                else:
                    st.info("No active open credit records identified.")

        for active_tab, target_df, title in [(tab2, df_debtors, "Debtor Balance Sheet Summary"), (tab3, df_creditors, "Creditor Balance Sheet Summary")]:
            with active_tab:
                st.header(title)
                if not target_df.empty:
                    party_summary = target_df.groupby('Party Name').agg({
                        'Outstanding Amount': 'sum',
                        'Days Overdue': 'max'
                    }).rename(columns={'Days Overdue': 'Max Days Overdue'}).sort_values(by='Outstanding Amount', ascending=False)
                    
                    st.dataframe(party_summary.style.format({'Outstanding Amount': '₹{:,.2f}'}), use_container_width=True)
                    
                    st.subheader("Granular Transaction Invoices Ledger")
                    st.dataframe(target_df[['Party Name', 'Voucher Number', 'Voucher Date', 'Due Date', 'Outstanding Amount', 'Aging Bucket']], use_container_width=True)
                else:
                    st.info("No transaction data available for this ledger category.")

        with tab4:
            st.header("Predictive Cash Flow Timelines (Next 90 Days)")
            
            cf_buckets = ['0-30 Days', '31-60 Days', '61-90 Days']
            dr_flow = [df_debtors[df_debtors['Aging Bucket'] == b]['Outstanding Amount'].sum() if not df_debtors.empty else 0 for b in cf_buckets]
            cr_flow = [df_creditors[df_creditors['Aging Bucket'] == b]['Outstanding Amount'].sum() if not df_creditors.empty else 0 for b in cf_buckets]
            
            cf_df = pd.DataFrame({
                'Timeline horizon': cf_buckets,
                'Inflows (Collections)': dr_flow,
                'Outflows (Payments)': cr_flow
            })
            cf_df['Net Cash Delta'] = cf_df['Inflows (Collections)'] - cf_df['Outflows (Payments)']
            
            st.dataframe(cf_df.style.format({
                'Inflows (Collections)': '₹{:,.2f}', 'Outflows (Payments)': '₹{:,.2f}', 'Net Cash Delta': '₹{:,.2f}'
            }), use_container_width=True)
            
            fig_cf = px.line(cf_df, x='Timeline horizon', y=['Inflows (Collections)', 'Outflows (Payments)', 'Net Cash Delta'],
                             title="Liquidity Runway Projections", markers=True)
            st.plotly_chart(fig_cf, use_container_width=True)

        with tab5:
            st.header("🤖 Financial Auditing AI Analytics")
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🔴 Capital Asset Risks (Critical Risk Debtors)")
                for item in ai_insights['high_risk_debtors']:
                    st.error(f"**{item['Party Name']}** has an aggregate of **₹{item['Outstanding Amount']:,.2f}** stalled over 180 Days. Legal notices recommended.")
                
                st.subheader("⚠️ Collection Delinquency Alerts (Slow Payers)")
                for item in ai_insights['slow_paying_debtors']:
                    st.warning(f"**{item['Party Name']}**: Accumulating balance (**₹{item['Outstanding Amount']:,.2f}**) in 91-180 Days profile.")

            with col2:
                st.subheader("⚡ Targeted Capital Optimization Matrix")
                for i, item in enumerate(ai_insights['collection_priority'], 1):
                    st.info(f"**Priority #{i}: {item['Party Name']}** | Balance Weight: ₹{item['Outstanding Amount']:,.2f} (Max Overdue: {int(item['Days Overdue'])} Days)")

                st.subheader("🤝 Supply Chain Leverage (Top Creditors Liability)")
                for item in ai_insights['top_creditors']:
                    st.success(f"**{item['Party Name']}**: Outstanding balance liability of **₹{item['Outstanding Amount']:,.2f}** requires dynamic liquidity provisioning.")

        st.sidebar.markdown("---")
        st.sidebar.subheader("📥 Export Deliverables")
        
        def convert_to_excel():
            wb = Workbook()
            ws = wb.active
            ws.title = "Executive Summary"
            
            header_font = Font(name='Arial', size=11, bold=True, color='FFFFFF')
            title_font = Font(name='Arial', size=14, bold=True, color='1F4E78')
            header_fill = PatternFill(start_color='1F4E78', end_color='1F4E78', fill_type='solid')
            
            ws.append([])
            ws.append([f"EXECUTIVE ACCOUNTS AGING REPORT - AS OF {analysis_date.strftime('%d-%b-%Y')}"])
            ws.cell(row=2, column=1).font = title_font
            ws.append([])
            
            ws_dr = wb.create_sheet(title="Debtors Matrix")
            ws_dr.append(list(df_debtors.columns))
            for cell in ws_dr[1]:
                cell.font = header_font
                cell.fill = header_fill
            for r in df_debtors.itertuples(index=False):
                row_data = [str(val) if isinstance(val, (datetime, pd.Timestamp)) else val for val in r]
                ws_dr.append(row_data)
                
            ws_cr = wb.create_sheet(title="Creditors Matrix")
            ws_cr.append(list(df_creditors.columns))
            for cell in ws_cr[1]:
                cell.font = header_font
                cell.fill = header_fill
            for r in df_creditors.itertuples(index=False):
                row_data = [str(val) if isinstance(val, (datetime, pd.Timestamp)) else val for val in r]
                ws_cr.append(row_data)

            output = io.BytesIO()
            wb.save(output)
            return output.getvalue()

        st.sidebar.download_button(
            label="📊 Download Excel Report Bundle",
            data=convert_to_excel(),
            file_name=f"Aging_Analytics_{analysis_date.strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.sidebar.download_button(
            label="📄 Download Raw Extract (CSV)",
            data=raw_df.to_csv(index=False).encode('utf-8'),
            file_name=f"Tally_Extracted_Data_{analysis_date.strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

        def convert_to_pdf():
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=16, style='B')
            pdf.cell(200, 10, txt="EXECUTIVE FINANCIAL AGING DIRECTIVE", ln=1, align='C')
            pdf.set_font("Arial", size=10)
            pdf.cell(200, 10, txt=f"Analysis Base Date: {analysis_date.strftime('%d-%b-%Y')}", ln=2, align='C')
            pdf.ln(10)
            
            pdf.set_font("Arial", size=12, style='B')
            pdf.cell(200, 10, txt="Corporate Liquidity Overview Dashboard", ln=1)
            pdf.set_font("Arial", size=11)
            pdf.cell(200, 8, txt=f"Total Receivables Outstanding: INR {total_dr:,.2f}", ln=1)
            pdf.cell(200, 8, txt=f"Total Payables Outstanding: INR {total_cr:,.2f}", ln=1)
            pdf.ln(10)
            
            pdf.set_font("Arial", size=12, style='B')
            pdf.cell(200, 10, txt="AI-Powered Critical Risks Identified:", ln=1)
            pdf.set_font("Arial", size=10)
            for item in ai_insights['high_risk_debtors'][:3]:
                pdf.cell(200, 7, txt=f"- Risk Flag: {item['Party Name']} | Overdue Value: INR {item['Outstanding Amount']:,.2f} (>180 Days)", ln=1)
                
            return pdf.output()

        st.sidebar.download_button(
            label="📕 Download PDF Executive Briefing",
            data=bytes(convert_to_pdf()),
            file_name=f"Executive_Briefing_{analysis_date.strftime('%Y%m%d')}.pdf",
            mime="application/pdf"
        )

    except Exception as e:
        st.error(f"An unexpected parsing/processing issue occurred: {e}")
else:
    st.info("👋 Welcome! Please upload a valid Tally XML data file in the left control panel to launch dynamic analysis.")
