import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
from datetime import datetime

def parse_tally_xml(file_wrapper) -> pd.DataFrame:
    """
    Parses Tally XML file containing Ledger/Bill Outstanding data.
    """
    try:
        xml_content = file_wrapper.read()
        root = ET.fromstring(xml_content)
    except Exception as e:
        raise ValueError(f"Failed to parse XML file structure: {str(e)}")

    records = []
    
    for ledger in root.findall('.//LEDGER') or root.findall('.//BILLDETAILS') or root.findall('.//ROW'):
        def get_text(element, tag, default=""):
            node = element.find(tag)
            return node.text.strip() if node is not None and node.text else default

        party_name = get_text(ledger, 'PARTYNAME') or get_text(ledger, 'LEDGERNAME') or get_text(ledger, 'NAME')
        vouch_no = get_text(ledger, 'VOUCHERNUMBER') or get_text(ledger, 'BILLNUM') or "N/A"
        vouch_date_str = get_text(ledger, 'DATE') or get_text(ledger, 'BILLDATE')
        due_date_str = get_text(ledger, 'DUEDATE') or get_text(ledger, 'BILLDUEDATE')
        vouch_type = get_text(ledger, 'VOUCHERTYPE') or "Opening/Bill"
        
        dr_amt = float(get_text(ledger, 'DEBIT', '0').replace(',', ''))
        cr_amt = float(get_text(ledger, 'CREDIT', '0').replace(',', ''))
        ol_amt = float(get_text(ledger, 'AMOUNT', '0').replace(',', ''))
        
        if ol_amt == 0 and (dr_amt != 0 or cr_amt != 0):
            ol_amt = dr_amt - cr_amt

        if not party_name and ol_amt == 0:
            continue

        def parse_date(d_str):
            for fmt in ('%Y%m%d', '%d-%b-%Y', '%Y-%m-%d', '%d/%m/%Y'):
                try:
                    return pd.to_datetime(d_str, format=fmt)
                except:
                    continue
            return pd.NaT

        vouch_date = parse_date(vouch_date_str)
        due_date = parse_date(due_date_str)
        if pd.isna(due_date) and not pd.isna(vouch_date):
            due_date = vouch_date 

        records.append({
            'Party Name': party_name,
            'Voucher Number': vouch_no,
            'Voucher Date': vouch_date,
            'Due Date': due_date,
            'Bill Reference': vouch_no,
            'Debit Amount': dr_amt,
            'Credit Amount': cr_amt,
            'Outstanding Amount': ol_amt,
            'Ledger Name': party_name,
            'Voucher Type': vouch_type
        })

    if not records:
        return pd.DataFrame(columns=['Party Name', 'Voucher Number', 'Voucher Date', 'Due Date', 
                                     'Bill Reference', 'Debit Amount', 'Credit Amount', 
                                     'Outstanding Amount', 'Ledger Name', 'Voucher Type'])
    
    return pd.DataFrame(records)

def process_aging_analysis(df: pd.DataFrame, base_date: datetime, group_type: str = "Debtor") -> pd.DataFrame:
    """
    Splits data into Debtors or Creditors and maps balances into aging buckets.
    """
    if df.empty:
        return df

    df = df.copy()
    base_date = pd.to_datetime(base_date)
    
    if group_type == "Debtor":
        df = df[df['Outstanding Amount'] > 0]
    else:
        df = df[df['Outstanding Amount'] < 0]
        df['Outstanding Amount'] = df['Outstanding Amount'].abs()

    df['Days Overdue'] = (base_date - df['Due Date']).dt.days
    df['Days Overdue'] = df['Days Overdue'].apply(lambda x: x if x > 0 else 0)

    buckets = ['0-30 Days', '31-60 Days', '61-90 Days', '91-180 Days', 'Above 180 Days']
    df['Aging Bucket'] = pd.cut(
        df['Days Overdue'],
        bins=[-1, 30, 60, 90, 180, np.inf],
        labels=buckets
    )

    return df

def generate_ai_insights(df_debtors: pd.DataFrame, df_creditors: pd.DataFrame):
    """
    Generates rule-based dynamic accounting insights for the dashboard.
    """
    insights = {
        'high_risk_debtors': [],
        'slow_paying_debtors': [],
        'collection_priority': [],
        'top_creditors': []
    }

    if not df_debtors.empty:
        hr = df_debtors[df_debtors['Aging Bucket'] == 'Above 180 Days'].groupby('Party Name')['Outstanding Amount'].sum().reset_index()
        insights['high_risk_debtors'] = hr.sort_values(by='Outstanding Amount', ascending=False).head(5).to_dict('records')

        sp = df_debtors[df_debtors['Aging Bucket'] == '91-180 Days'].groupby('Party Name')['Outstanding Amount'].sum().reset_index()
        insights['slow_paying_debtors'] = sp.sort_values(by='Outstanding Amount', ascending=False).head(5).to_dict('records')

        cp = df_debtors.groupby('Party Name').agg({'Outstanding Amount': 'sum', 'Days Overdue': 'max'}).reset_index()
        cp['Priority Score'] = cp['Outstanding Amount'] * (cp['Days Overdue'] / 30)
        insights['collection_priority'] = cp.sort_values(by='Priority Score', ascending=False).head(5).to_dict('records')

    if not df_creditors.empty:
        tc = df_creditors.groupby('Party Name')['Outstanding Amount'].sum().reset_index()
        insights['top_creditors'] = tc.sort_values(by='Outstanding Amount', ascending=False).head(5).to_dict('records')

    return insights
      
