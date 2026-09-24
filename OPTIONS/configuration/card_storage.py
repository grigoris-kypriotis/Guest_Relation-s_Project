# -*- coding: utf-8 -*-
"""Card Storage: Document storage location configuration."""
import os
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QLineEdit, QMessageBox, QFileDialog
from MODULES.data_manager import OUTPUT_DIR
from OPTIONS.configuration.card_shared import create_card, btn_browse_style

def build_storage_card(widget) -> QFrame:
    """Builds the Document Storage Locations card (Card 6)."""
    card_storage_frame = create_card("DOCUMENT STORAGE LOCATIONS", accent_color="#2563EB")
    st_layout = card_storage_frame.layout()
    
    st_desc = QLabel("Configure where generated Offer Lists and Cake Memos are stored.")
    st_desc.setStyleSheet("color: #64748B; font-size: 11px; border: none;")
    st_desc.setWordWrap(True)
    st_layout.addWidget(st_desc)

    row_offers_dir = QHBoxLayout()
    lbl_offers_dir = QLabel("Offer Lists Output Directory:")
    lbl_offers_dir.setFixedWidth(230)
    lbl_offers_dir.setStyleSheet("font-weight: bold; color: #1E293B; border: none;")
    widget.txt_offer_lists_dir = QLineEdit(os.path.join(OUTPUT_DIR, "OFFERS"))
    widget.txt_offer_lists_dir.setStyleSheet("background-color: #F8F9FA; padding: 4px 8px; border: 1px solid #A7F3D0; border-radius: 4px;")
    btn_browse_offers = QPushButton("Browse")
    btn_browse_offers.setStyleSheet(btn_browse_style)
    btn_browse_offers.clicked.connect(widget._browse_offers_dir)
    btn_open_offers = QPushButton("Open")
    btn_open_offers.clicked.connect(lambda: widget._open_folder(widget.txt_offer_lists_dir.text()))
    row_offers_dir.addWidget(lbl_offers_dir)
    row_offers_dir.addWidget(widget.txt_offer_lists_dir)
    row_offers_dir.addWidget(btn_browse_offers)
    row_offers_dir.addWidget(btn_open_offers)
    st_layout.addLayout(row_offers_dir)

    row_cakes_dir = QHBoxLayout()
    lbl_cakes_dir = QLabel("Cake Memos Output Directory:")
    lbl_cakes_dir.setFixedWidth(230)
    lbl_cakes_dir.setStyleSheet("font-weight: bold; color: #1E293B; border: none;")
    widget.txt_cake_memos_dir = QLineEdit(os.path.join(OUTPUT_DIR, "CAKE_MEMOS"))
    widget.txt_cake_memos_dir.setStyleSheet("background-color: #F8F9FA; padding: 4px 8px; border: 1px solid #A7F3D0; border-radius: 4px;")
    btn_browse_cakes = QPushButton("Browse")
    btn_browse_cakes.setStyleSheet(btn_browse_style)
    btn_browse_cakes.clicked.connect(widget._browse_cakes_dir)
    btn_open_cakes = QPushButton("Open")
    btn_open_cakes.clicked.connect(lambda: widget._open_folder(widget.txt_cake_memos_dir.text()))
    row_cakes_dir.addWidget(lbl_cakes_dir)
    row_cakes_dir.addWidget(widget.txt_cake_memos_dir)
    row_cakes_dir.addWidget(btn_browse_cakes)
    row_cakes_dir.addWidget(btn_open_cakes)
    st_layout.addLayout(row_cakes_dir)

    widget.lbl_storage_summary = QLabel("")
    widget.lbl_storage_summary.setStyleSheet("color: #2563EB; font-size: 11px; font-weight: bold; padding-top: 4px; border: none;")
    st_layout.addWidget(widget.lbl_storage_summary)
    return card_storage_frame

class StorageMixin:
    """Mixin providing document storage directory management methods."""
    
    def _browse_offers_dir(self) -> None:
        """Opens directory chooser for offer lists directory."""
        folder = QFileDialog.getExistingDirectory(self, "Select Offer Lists Output Directory", self.txt_offer_lists_dir.text())
        if folder:
            self.txt_offer_lists_dir.setText(folder)

    def _browse_cakes_dir(self) -> None:
        """Opens directory chooser for cake memos directory."""
        folder = QFileDialog.getExistingDirectory(self, "Select Cake Memos Output Directory", self.txt_cake_memos_dir.text())
        if folder:
            self.txt_cake_memos_dir.setText(folder)

    def _open_folder(self, path: str) -> None:
        """Open a directory in Windows Explorer."""
        path = path.strip()
        if os.path.exists(path):
            os.startfile(path)
        else:
            try:
                os.makedirs(path, exist_ok=True)
                os.startfile(path)
            except Exception as e:
                if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                    QMessageBox.warning(self, "Folder Error", f"Could not open folder: {path}")

    def _refresh_storage_summary(self) -> None:
        """Count files in the offer lists and cake memos directories."""
        offers_dir = self.txt_offer_lists_dir.text().strip()
        cakes_dir = self.txt_cake_memos_dir.text().strip()
        offer_count = 0
        cake_count = 0
        if os.path.exists(offers_dir):
            for root, dirs, files in os.walk(offers_dir):
                offer_count += sum(1 for f in files if f.lower().endswith(('.docx', '.doc', '.pdf')))
        if os.path.exists(cakes_dir):
            for root, dirs, files in os.walk(cakes_dir):
                cake_count += sum(1 for f in files if f.lower().endswith(('.docx', '.doc', '.pdf')))
        self.lbl_storage_summary.setText(f"{offer_count} Offer List(s) stored  |  {cake_count} Cake Memo(s) stored")
