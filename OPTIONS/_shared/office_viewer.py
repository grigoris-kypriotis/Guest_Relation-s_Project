"""
OfficeViewer: Embedded Word/Excel COM automation viewer.
"""

import os
import win32gui
import win32con
import win32com.client

from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import QTimer, pyqtSignal


class OfficeViewer(QWidget):
    file_saved_and_closed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.office_app = None
        self.doc = None
        self.office_hwnd = None
        self.current_filepath = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.hide()

    def open_file(self, filepath: str) -> None:
        self.close_file()
        self.current_filepath = os.path.abspath(filepath)
        ext = os.path.splitext(filepath)[1].lower()

        try:
            if ext in ['.doc', '.docx']:
                self.office_app = win32com.client.DispatchEx("Word.Application")
                self.office_app.WindowState = 0
                self.office_app.Visible = True
                self.doc = self.office_app.Documents.Open(self.current_filepath)
                try:
                    self.office_app.ActiveWindow.ActivePane.View.Zoom.Percentage = 70
                except Exception:
                    pass
                self.office_hwnd = self.office_app.ActiveWindow.Hwnd
            elif ext in ['.csv', '.xls', '.xlsx']:
                self.office_app = win32com.client.DispatchEx("Excel.Application")
                self.office_app.WindowState = -4143
                self.office_app.Visible = True
                self.doc = self.office_app.Workbooks.Open(self.current_filepath)
                self.office_hwnd = self.office_app.Hwnd

            if self.office_hwnd:
                win32gui.SetParent(self.office_hwnd, int(self.winId()))
                style = win32gui.GetWindowLong(self.office_hwnd, win32con.GWL_STYLE)
                style = style & ~win32con.WS_CAPTION & ~win32con.WS_THICKFRAME & ~win32con.WS_SYSMENU
                win32gui.SetWindowLong(self.office_hwnd, win32con.GWL_STYLE, style)
                QTimer.singleShot(500, self.resize_office_window)
            self.show()
        except Exception as e:
            print(f"System Error (open_file): {e}")

    def save_file(self) -> None:
        if self.doc:
            try:
                self.doc.Save()
            except:
                pass

    def close_file(self) -> None:
        if self.doc:
            try:
                self.doc.Close(False)
            except:
                pass
            self.doc = None

        if self.office_app:
            try:
                self.office_app.Quit()
            except:
                pass
            self.office_app = None

        self.office_hwnd = None
        self.hide()

    def save_and_close(self) -> None:
        fp = self.current_filepath
        self.save_file()
        self.close_file()
        if fp:
            self.file_saved_and_closed.emit(fp)

    def resize_office_window(self) -> None:
        if self.office_hwnd:
            ratio = self.devicePixelRatioF()
            w = int(self.width() * ratio)
            h = int(self.height() * ratio)
            win32gui.SetWindowPos(
                self.office_hwnd,
                win32con.HWND_TOP,
                0, 0, w, h,
                win32con.SWP_FRAMECHANGED | win32con.SWP_SHOWWINDOW
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_office_window()
