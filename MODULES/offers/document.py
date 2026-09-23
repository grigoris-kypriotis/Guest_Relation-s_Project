"""
Word document generation for offer lists.
"""

import os
import re
import win32com.client

from MODULES.offers.paths import TEMPLATE_PATH


def generate_word_document(data, minibar_data, today_docx, save_path, year_str):
    """
    Generate a Word document from offer list data.

    Attempts to use python-docx first, falls back to win32com.

    Args:
        data: List of offer dictionaries
        minibar_data: List of minibar data
        today_docx: Today's date in DD/MM format
        save_path: Output file path
        year_str: Year string in YYYY format
    """
    save_path = os.path.abspath(save_path)

    # Primary generator: python-docx (fast, fully portable, no MS Office installation required)
    try:
        import docx
        doc = docx.Document(os.path.abspath(TEMPLATE_PATH))

        # Replace delivery date placeholder
        for p in doc.paragraphs:
            if "Delivery Date: / /" in p.text:
                p.text = p.text.replace("Delivery Date: / /", f"Delivery Date: {today_docx}/{year_str}")

        if doc.tables:
            table = doc.tables[0]
            col_indices = {}
            for idx, c in enumerate(table.rows[0].cells):
                header = re.sub(r'[\r\a\n\t]', '', c.text).strip()
                if re.search(r"(?i)Room No", header): col_indices["Room No."] = idx
                if re.search(r"(?i)Dep Date", header): col_indices["Dep Date"] = idx
                if re.search(r"(?i)Pax", header): col_indices["Pax"] = idx
                if re.search(r"(?i)Delivery Date", header): col_indices["Delivery Date"] = idx
                if re.search(r"(?i)Order", header): col_indices["Order"] = idx
                if re.search(r"(?i)Mini bar", header): col_indices["Mini bar"] = idx

            current_row = 1
            for item in data:
                if current_row < len(table.rows):
                    row = table.rows[current_row]
                else:
                    row = table.add_row()
                if "Room No." in col_indices: row.cells[col_indices["Room No."]].text = str(item["RoomNo"])
                if "Dep Date" in col_indices: row.cells[col_indices["Dep Date"]].text = str(item["DepDate"])
                if "Pax" in col_indices: row.cells[col_indices["Pax"]].text = str(item["Pax"])
                if "Delivery Date" in col_indices: row.cells[col_indices["Delivery Date"]].text = today_docx
                if "Order" in col_indices: row.cells[col_indices["Order"]].text = str(item["Order"])
                current_row += 1

            if "Mini bar" in col_indices:
                mb_row = 1
                for room in minibar_data:
                    if mb_row < len(table.rows):
                        row = table.rows[mb_row]
                    else:
                        row = table.add_row()
                    row.cells[col_indices["Mini bar"]].text = str(room)
                    mb_row += 1

        doc.save(save_path)
        return
    except Exception as docx_err:
        pass

    # Fallback to win32com Word.Application if docx fails or is not available
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    doc = None
    try:
        doc = word.Documents.Open(os.path.abspath(TEMPLATE_PATH))
        word.Selection.HomeKey(Unit=6)
        word.Selection.Find.Execute(FindText="Delivery Date: / /", ReplaceWith=f"Delivery Date: {today_docx}/{year_str}", Replace=2)

        table = doc.Tables(1)
        col_indices = {}
        for c in range(1, table.Columns.Count + 1):
            header = re.sub(r'[\r\a\n\t]', '', table.Cell(1, c).Range.Text).strip()
            if re.search(r"(?i)Room No", header): col_indices["Room No."] = c
            if re.search(r"(?i)Dep Date", header): col_indices["Dep Date"] = c
            if re.search(r"(?i)Pax", header): col_indices["Pax"] = c
            if re.search(r"(?i)Delivery Date", header): col_indices["Delivery Date"] = c
            if re.search(r"(?i)Order", header): col_indices["Order"] = c
            if re.search(r"(?i)Mini bar", header): col_indices["Mini bar"] = c

        current_row = 2
        for item in data:
            if current_row > table.Rows.Count: table.Rows.Add()
            if "Room No." in col_indices: table.Cell(current_row, col_indices["Room No."]).Range.Text = str(item["RoomNo"])
            if "Dep Date" in col_indices: table.Cell(current_row, col_indices["Dep Date"]).Range.Text = str(item["DepDate"])
            if "Pax" in col_indices: table.Cell(current_row, col_indices["Pax"]).Range.Text = str(item["Pax"])
            if "Delivery Date" in col_indices: table.Cell(current_row, col_indices["Delivery Date"]).Range.Text = today_docx
            if "Order" in col_indices: table.Cell(current_row, col_indices["Order"]).Range.Text = str(item["Order"])
            current_row += 1

        if "Mini bar" in col_indices:
            mb_row = 2
            for room in minibar_data:
                if mb_row > table.Rows.Count: table.Rows.Add()
                table.Cell(mb_row, col_indices["Mini bar"]).Range.Text = str(room)
                mb_row += 1

        doc.SaveAs2(save_path)
    finally:
        if doc:
            try: doc.Close(False)
            except: pass
        try: word.Quit()
        except: pass
