"""
Screen: Stock overview (no AI, instant). Same as app.py menu option 5.
Calls tools.procurement.get_inventory(); nothing is computed here.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # make "src" importable

import streamlit as st

import ui_common
from tools import procurement

ui_common.setup_page("Stock overview", "📦", "Every item, its stock level and what is running low. No AI.",
                     need_user=False)

# Category filter: the list of real categories comes from the tool itself.
all_items = procurement.get_inventory()
if "error" in all_items:
    st.error(f"Shop data could not be read: {all_items['error']}")
    st.stop()
choice = st.selectbox("Category", ["All"] + all_items["categories_available"])
result = all_items if choice == "All" else procurement.get_inventory(choice)

low = [i for i in result["items"] if i["is_low"]]
st.markdown(f'<div style="background:#FFF6E5;border:1px solid #F5D9A0;border-radius:12px;'
            f'padding:10px 16px;margin-bottom:12px;">📊 <b>{len(low)}</b> of <b>{result["count"]}</b> '
            f'items are low on stock</div>', unsafe_allow_html=True)

rows = [{"Item ID": i["item_id"], "Item": i["item_name"], "Category": i["category"],
         "In stock": i["current_stock"], "Reorder point": i["reorder_point"],
         "Status": "⚠️ LOW" if i["is_low"] else "OK"} for i in result["items"]]
st.dataframe(rows, hide_index=True, width="stretch")
