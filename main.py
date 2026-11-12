"""Khởi chạy ứng dụng desktop PySide6."""
import sys
from PySide6.QtWidgets import QApplication
from gui.main_window import Window

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())
