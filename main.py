import sys
from gui import OllamaPyQtApp
from PyQt5.QtWidgets import QApplication

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = OllamaPyQtApp()
    main_window.show()
    sys.exit(app.exec_())