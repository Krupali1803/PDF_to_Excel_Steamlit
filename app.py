import streamlit as st
import pdfplumber
import pandas as pd
import os
import warnings
import logging

logging.getLogger("pdfminer").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

st.title("PDF Table Extractor")
st.write("Upload a PDF to extract tables.")

uploaded_file = st.file_uploader("Choose a PDF", type="pdf")

if uploaded_file:
   pdf_path = f"temp_{uploaded_file.name}"
   with open(pdf_path, "wb") as f:
      f.write(uploaded_file.getbuffer())
   pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]
   excel_path = f"{pdf_basename}_smart_grouping.xlsx"

   table_groups = []
   def match_existing_group(header_candidate):
      for group in table_groups:
         if len(group['header']) == len(header_candidate):
            return group
      return None

   try:
      with pdfplumber.open(pdf_path) as pdf:
         for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            for table in tables:
               if not table or not any(any(cell for cell in row) for row in table):
                  continue
               for i, row in enumerate(table):
                  if any(cell and str(cell).strip() != "" for cell in row):
                     header_candidate = [str(cell).strip() if cell else "" for cell in row]
                     data_rows = table[i + 1:]
                     break
               else:
                  continue
               group = match_existing_group(header_candidate)
               if group:
                  df = pd.DataFrame(data_rows, columns=group['header'])
                  df['Page'] = page_num
                  group['data'].append(df)
                  group['pages'].add(page_num)
               else:
                  df = pd.DataFrame(data_rows, columns=header_candidate)
                  df['Page'] = page_num
                  table_groups.append({
                     'header': tuple(header_candidate),
                     'data': [df],
                     'pages': {page_num}
                  })

      if table_groups:
         with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            summary = [{
               "Group": f"Group_{i+1}",
               "Pages": ", ".join(map(str, sorted(group['pages']))),
               "Columns": ", ".join(group['header'])
            } for i, group in enumerate(table_groups)]
            pd.DataFrame(summary).to_excel(writer, sheet_name="Summary", index=False)
            for i, group in enumerate(table_groups):
               sheet_name = f"Group_{i+1}"
               combined_df = pd.concat(group['data'], ignore_index=True)
               combined_df.to_excel(writer, sheet_name=sheet_name, index=False)
         st.success(f"✅ Saved to {excel_path}")
         with open(excel_path, "rb") as f:
            st.download_button(
               label="Download Excel",
               data=f,
               file_name=excel_path,
               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
      else:
         st.warning("⚠️ No valid tables found.")
   except Exception as e:
      st.error(f"❌ Error: {e}")
   if os.path.exists(pdf_path):
      os.remove(pdf_path)