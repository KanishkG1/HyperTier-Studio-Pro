import sys
from PyQt6.QtWidgets import QApplication
from studio.gui import HyperTierGUI
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Hyper-Tier Studio Pro")
    window = HyperTierGUI()
    window.show()
    sys.exit(app.exec())
