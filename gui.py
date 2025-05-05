import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QListWidget, QTextEdit, QProgressBar, QFileDialog, QMessageBox,
    QGroupBox, QTabWidget, QSplitter, QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QTextCursor, QColor, QFont
import html

# --- Configuration ---
COPY_TARGET_EXTENSIONS = [".xlsx", ".dxd", ".d7d"]

# --- Color Codes ---
COLOR_BG = "#000376"; COLOR_ACCENT = "#7275FE"; COLOR_TEXT = "#01B3C4"
COLOR_BORDER = "#9185BE"; COLOR_HOVER = "#B9BAFF"; COLOR_BUTTON_TEXT = "#FFFFFF"
COLOR_INPUT_BG = "#FFFFFF"; COLOR_INPUT_TEXT = "#000000"; COLOR_INPUT_BORDER = "#4A4A4A"
COLOR_DISABLED_BG = "#40448A"; COLOR_DISABLED_TEXT = "#888CCA"; COLOR_STATUS_TEXT = "#FFFFFF"
COLOR_SELECTION_TEXT = COLOR_BUTTON_TEXT; COLOR_PROGRESS_TEXT = COLOR_BUTTON_TEXT
COLOR_LOG_FOUND = "#CCCCCC"; COLOR_LOG_PROCESSED = "#A0A0A0"; COLOR_LOG_SKIPPED = "#808080"
COLOR_ERROR_TEXT = "#FF4C4C"

class OllamaPyQtApp(QMainWindow):
    start_file_copy_signal = pyqtSignal(list, list, str)
    start_llm_processing_signal = pyqtSignal(str, list, str)
    start_chat_query_signal = pyqtSignal(str)
    request_copy_confirmation_signal = pyqtSignal(bool, object)  # Signal for confirmation

    def __init__(self):
        super().__init__()
        self.folder_paths = []
        self.destination_folder = ""
        self.last_copy_keywords = []  # Store keywords used for copying
        self.llm_enabled = False
        self.worker_thread = None
        self.worker = None
        self.llm_worker = None
        self.llm_thread = None
        self.vector_store = None
        self.initUI()
        self.initWorker()
        self.setStyleSheet(create_stylesheet())

    def initUI(self):
        self.setWindowTitle("File Copier & Doc Query")
        self.setGeometry(100, 100, 1150, 900)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        top_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(top_splitter)

        # File Selection Group
        file_gb = QGroupBox("File Selection")
        file_gb.setObjectName("FileSelection")
        top_splitter.addWidget(file_gb)
        file_layout = QVBoxLayout(file_gb)
        self.llm_toggle = QCheckBox("Enable LLM Processing")
        self.llm_toggle.stateChanged.connect(self.toggle_llm)
        file_layout.addWidget(self.llm_toggle)
        file_layout.addWidget(QLabel("1. Source Folders:"))
        self.folder_list_widget = QListWidget()
        self.folder_list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.folder_list_widget.setMaximumHeight(100)
        file_layout.addWidget(self.folder_list_widget)
        file_btns = QHBoxLayout()
        b1 = QPushButton("Add Src"); b1.clicked.connect(self.add_folders)
        b2 = QPushButton("Rem Src"); b2.clicked.connect(self.remove_selected_folders)
        b3 = QPushButton("Clr Src"); b3.clicked.connect(self.clear_folders)
        file_btns.addWidget(b1); file_btns.addWidget(b2); file_btns.addWidget(b3); file_btns.addStretch(1)
        file_layout.addLayout(file_btns)
        file_layout.addWidget(QLabel("2. Keywords (comma-separated):"))
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("e.g., OF, UF, 5.4.4")
        self.keyword_input.setClearButtonEnabled(True)
        file_layout.addWidget(self.keyword_input)
        self.process_llm_button = QPushButton("Process Files for LLM")
        self.process_llm_button.setVisible(False)
        file_layout.addWidget(self.process_llm_button)
        file_layout.addStretch(1)

        # Copy Group
        copy_gb = QGroupBox("Keyword File Copier")
        top_splitter.addWidget(copy_gb)
        copy_layout = QVBoxLayout(copy_gb)
        copy_layout.addWidget(QLabel(f"1. Keywords (uses field left)"))
        copy_layout.addWidget(QLabel(f"2. Target Ext: {', '.join(COPY_TARGET_EXTENSIONS)}"))
        copy_layout.addWidget(QLabel("3. Destination Folder:"))
        dest_layout = QHBoxLayout()
        self.dest_folder_display = QLineEdit()
        self.dest_folder_display.setPlaceholderText("Select folder for copies...")
        self.dest_folder_display.setReadOnly(True)
        dest_layout.addWidget(self.dest_folder_display, 1)
        select_dest_btn = QPushButton("Select Dest")
        select_dest_btn.setObjectName("selectDestButton")
        select_dest_btn.clicked.connect(self.select_destination_folder)
        dest_layout.addWidget(select_dest_btn)
        copy_layout.addLayout(dest_layout)
        copy_btn_layout = QHBoxLayout()
        self.copy_files_button = QPushButton("4. Find & Copy")
        self.copy_files_button.setToolTip("Copy items matching keywords")
        self.copy_files_button.clicked.connect(self.start_file_copy_task)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setToolTip("Stop current task")
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self.stop_task)
        copy_btn_layout.addWidget(self.copy_files_button)
        copy_btn_layout.addWidget(self.stop_button)
        copy_layout.addLayout(copy_btn_layout)
        copy_layout.addStretch(1)
        top_splitter.setSizes([350, 300])

        # Output Group
        output_gb = QGroupBox("Output")
        main_layout.addWidget(output_gb, stretch=1)
        output_layout = QVBoxLayout(output_gb)
        prog_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.status_label = QLabel("Ready.")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setMinimumWidth(350)
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        prog_layout.addWidget(QLabel("Progress:"))
        prog_layout.addWidget(self.progress_bar)
        prog_layout.addWidget(self.status_label)
        output_layout.addLayout(prog_layout)
        self.tab_widget = QTabWidget()
        output_layout.addWidget(self.tab_widget, stretch=1)
        self.copy_log_edit = QTextEdit()
        self.copy_log_edit.setReadOnly(True)
        self.copy_log_edit.setLineWrapMode(QTextEdit.NoWrap)
        self.tab_widget.addTab(self.copy_log_edit, "Copy Log")
        
        self.set_controls_enabled(True)

    def toggle_llm(self, state):
        self.llm_enabled = state == Qt.Checked
        if self.llm_enabled:
            from llm_chat import init_llm_tab, add_llm_methods, LLMWorker
            self.vector_store = None  # Reset vector store
            add_llm_methods(self)  # Define methods first
            init_llm_tab(self)     # Then initialize tab
            # Initialize LLM worker and thread
            self.llm_thread = QThread(self)
            self.llm_worker = LLMWorker()
            self.llm_worker.moveToThread(self.llm_thread)
            self.start_llm_processing_signal.connect(self.llm_worker.run_llm_processing)
            self.start_chat_query_signal.connect(self.llm_worker.run_chat_query)
            self.llm_worker.llm_status_updated.connect(self.update_status)
            self.llm_worker.llm_progress_updated.connect(self.update_progress)
            self.llm_worker.llm_log_message.connect(self.append_llm_log_message)
            self.llm_worker.llm_processing_complete.connect(self.on_llm_processing_complete)
            self.llm_worker.chat_response_received.connect(self.append_chat_message)
            self.llm_worker.error_occurred.connect(self.show_error_message)
            self.llm_thread.start()
            self.process_llm_button.setVisible(True)
            self.process_llm_button.clicked.connect(self.start_llm_processing)
        else:
            self.process_llm_button.setVisible(False)
            try:
                self.process_llm_button.clicked.disconnect()
            except TypeError:
                pass
            if hasattr(self, 'llm_log_edit'):
                self.tab_widget.removeTab(self.tab_widget.indexOf(self.llm_log_edit))
            if hasattr(self, 'chat_display_edit'):
                self.tab_widget.removeTab(self.tab_widget.indexOf(self.chat_display_edit.parent()))
            if self.llm_worker and self.llm_thread and self.llm_thread.isRunning():
                self.llm_worker.stop()
                self.llm_thread.quit()
                self.llm_thread.wait(5000)
            self.vector_store = None
            self.llm_worker = None
            self.llm_thread = None

    def initWorker(self):
        from file_copy import CopyWorker
        self.worker_thread = QThread(self)
        self.worker = CopyWorker()
        self.worker.moveToThread(self.worker_thread)
        self.worker.copy_status_updated.connect(self.update_status)
        self.worker.copy_progress_updated.connect(self.update_progress)
        self.worker.copy_log_message.connect(self.append_copy_log_message)
        self.worker.copy_complete.connect(self.on_copy_complete)
        self.worker.error_occurred.connect(self.show_error_message)
        self.worker.request_copy_confirmation.connect(self.show_copy_confirmation)
        self.request_copy_confirmation_signal.connect(self.worker.proceed_with_copy)
        self.start_file_copy_signal.connect(self.worker.run_file_copy_task)
        self.worker_thread.start()

    def closeEvent(self, event):
        if self.worker_thread and self.worker_thread.isRunning():
            if self.worker:
                self.worker.stop()
            self.worker_thread.quit()
            self.worker_thread.wait(5000)
        if self.llm_enabled and self.llm_worker and self.llm_thread and self.llm_thread.isRunning():
            self.llm_worker.stop()
            self.llm_thread.quit()
            self.llm_thread.wait(5000)
        event.accept()

    def add_folders(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if folder and folder not in self.folder_paths:
            self.folder_paths.append(folder)
            self.folder_list_widget.addItem(folder)

    def remove_selected_folders(self):
        for item in self.folder_list_widget.selectedItems():
            row = self.folder_list_widget.row(item)
            folder = self.folder_list_widget.takeItem(row).text()
            if folder in self.folder_paths:
                self.folder_paths.remove(folder)

    def clear_folders(self):
        self.folder_list_widget.clear()
        self.folder_paths = []

    def select_destination_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if folder:
            self.destination_folder = folder
            self.dest_folder_display.setText(folder)

    def start_file_copy_task(self):
        keywords = [kw.strip() for kw in self.keyword_input.text().split(",") if kw.strip()]
        if not self.folder_paths:
            QMessageBox.warning(self, "Input", "Add source folder(s) for copy.")
            return
        if not keywords:
            QMessageBox.warning(self, "Input", "At least one keyword required for copy.")
            return
        if not self.destination_folder or not os.path.isdir(self.destination_folder):
            QMessageBox.warning(self, "Input", "Select valid destination folder.")
            return
        self.last_copy_keywords = keywords  # Store keywords for LLM processing
        self.set_controls_enabled(False, task_type="copy")
        self.copy_log_edit.clear()
        self.append_message(self.copy_log_edit, f"--- Starting File Copy Task (Keywords: {', '.join(keywords)}) ---", COLOR_TEXT, True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Copy: %p%")
        self.tab_widget.setCurrentWidget(self.copy_log_edit)
        self.start_file_copy_signal.emit(self.folder_paths, keywords, self.destination_folder)

    def stop_task(self):
        if self.worker and self.worker_thread and self.worker_thread.isRunning():
            self.worker.stop()
            self.append_message(self.copy_log_edit, "Copy task stopped by user.", COLOR_ERROR_TEXT)
            self.set_controls_enabled(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Copy Stopped")
            self.update_status("Copy stopped.")
        if self.llm_enabled and self.llm_worker and self.llm_thread and self.llm_thread.isRunning():
            self.llm_worker.stop()
            self.append_llm_log_message("LLM processing stopped by user.", COLOR_ERROR_TEXT)
            self.set_controls_enabled(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("LLM Stopped")
            self.update_status("LLM processing stopped.")

    def show_copy_confirmation(self, file_count, callback):
        response = QMessageBox.question(
            self,
            "Confirm Copy",
            f"Found {file_count} files. Do you want to continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        proceed = response == QMessageBox.Yes
        self.request_copy_confirmation_signal.emit(proceed, callback)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_status(self, message):
        self.status_label.setText(message)

    def append_copy_log_message(self, message, color):
        self.append_message(self.copy_log_edit, message, color=color)

    def append_llm_log_message(self, message, color, bold=False):
        if hasattr(self, 'llm_log_edit'):
            self.append_message(self.llm_log_edit, message, color=color, bold=bold)

    def on_copy_complete(self, files_copied, dirs_copied):
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Copy Complete")
        summary = f"\n--- Copy Done --- \nCopied {files_copied} files, {dirs_copied} dirs."
        self.append_message(self.copy_log_edit, summary, COLOR_TEXT, True)
        QMessageBox.information(self, "Copy Done", f"Finished copying.\nCopied {files_copied} files, {dirs_copied} directories.")
        # Trigger LLM processing if enabled
        if self.llm_enabled and self.destination_folder and self.last_copy_keywords:
            self.set_controls_enabled(False, task_type="llm")
            self.llm_log_edit.clear()
            self.append_message(self.llm_log_edit, f"--- Starting LLM Processing on Copied Files (Keywords: {', '.join(self.last_copy_keywords)}) ---", COLOR_TEXT, True)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("LLM: %p%")
            self.tab_widget.setCurrentWidget(self.llm_log_edit)
            self.start_llm_processing_signal.emit(self.destination_folder, self.last_copy_keywords, self.destination_folder)
        else:
            self.set_controls_enabled(True)

    def on_llm_processing_complete(self, doc_count):
        self.set_controls_enabled(True)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("LLM Processing Complete")
        summary = f"\n--- LLM Processing Done --- \nProcessed {doc_count} documents."
        self.append_llm_log_message(summary, COLOR_TEXT, True)
        QMessageBox.information(self, "LLM Processing Done", f"Finished processing {doc_count} documents.")

    def show_error_message(self, error):
        QMessageBox.critical(self, "Task Error", error)
        self.set_controls_enabled(True)
        self.update_status("Error occurred.")
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Error")

    def set_controls_enabled(self, enabled, task_type=None):
        self.folder_list_widget.setEnabled(enabled)
        self.keyword_input.setEnabled(enabled)
        self.dest_folder_display.setEnabled(enabled)
        select_dest_button = self.findChild(QPushButton, "selectDestButton")
        if select_dest_button:
            select_dest_button.setEnabled(enabled)
        for btn in self.folder_list_widget.parent().findChildren(QPushButton):
            if btn.text() in ["Add Src", "Rem Src", "Clr Src"]:
                btn.setEnabled(enabled)
        self.copy_files_button.setEnabled(enabled and task_type != "llm")
        self.stop_button.setVisible(not enabled and task_type in ["copy", "llm"])
        self.llm_toggle.setEnabled(enabled)
        if self.llm_enabled:
            self.process_llm_button.setEnabled(enabled and task_type != "copy")
            self.set_chat_input_enabled(enabled and not self.vector_store.is_empty() if self.vector_store else False)

    def append_message(self, widget, msg, color=None, bold=False):
        clr = COLOR_INPUT_TEXT if color is None else color
        widget.moveCursor(QTextCursor.End)
        cursor = widget.textCursor()
        fmt = cursor.charFormat()
        qc = QColor(clr)
        fmt.setForeground(qc if qc.isValid() else QColor(COLOR_INPUT_TEXT))
        fmt.setFontWeight(QFont.Bold if bold else QFont.Normal)
        cursor.setCharFormat(fmt)
        cursor.insertText(msg + "\n")
        widget.ensureCursorVisible()

    def append_chat_message(self, msg, clr_hex):
        safe_message = html.escape(msg).replace("\n", "<br>")
        html_content = f'<p style="margin: 2px 0; color:{clr_hex};">{safe_message}</p>'
        self.chat_display_edit.moveCursor(QTextCursor.End)
        self.chat_display_edit.insertHtml(html_content)
        self.chat_display_edit.ensureCursorVisible()

def create_stylesheet():
    return f"""
        QMainWindow, QWidget {{ background-color:{COLOR_BG}; color:{COLOR_TEXT}; font-family:Segoe UI,Arial; font-size:10pt; }}
        QGroupBox {{ font-weight:bold; color:{COLOR_TEXT}; border:1px solid {COLOR_BORDER}; border-radius:5px; margin-top:10px; padding:10px 5px 5px 5px; }}
        QGroupBox::title {{ subcontrol-origin:margin; subcontrol-position:top left; padding:0 5px; left:10px; background-color:{COLOR_BG}; color:{COLOR_TEXT}; border:none; }}
        QLabel {{ color:{COLOR_TEXT}; padding:2px; background-color:transparent; }}
        #StatusLabel {{ color:{COLOR_STATUS_TEXT}; }}
        QFormLayout QLabel, QGroupBox > QLabel {{ color:{COLOR_TEXT}; }}
        QLineEdit, QTextEdit, QListWidget {{ background-color:{COLOR_INPUT_BG}; color:{COLOR_INPUT_TEXT}; border:1px solid {COLOR_INPUT_BORDER}; border-radius:3px; padding:4px; font-size:10pt; }}
        QLineEdit:focus, QTextEdit:focus, QListWidget:focus {{ border:1px solid {COLOR_ACCENT}; }}
        QLineEdit:disabled, QTextEdit:disabled, QListWidget:disabled {{ background-color:#E0E0E0; color:#808080; border-color:#C0C0C0; }}
        QLineEdit[readOnly="true"] {{ background-color:#F0F0F0; }}
        QListWidget::item {{ padding:3px 0px; color:{COLOR_INPUT_TEXT}; background-color:{COLOR_INPUT_BG}; }}
        QListWidget::item:selected {{ background-color:{COLOR_ACCENT}; color:{COLOR_SELECTION_TEXT}; }}
        QPushButton {{ background-color:{COLOR_ACCENT}; color:{COLOR_BUTTON_TEXT}; border:1px solid {COLOR_BORDER}; border-radius:4px; padding:6px 12px; min-width:80px; font-weight:bold; }}
        QPushButton:hover {{ background-color:{COLOR_HOVER}; border:1px solid {COLOR_ACCENT}; }}
        QPushButton:pressed {{ background-color:{COLOR_BORDER}; }}
        QPushButton:disabled {{ background-color:{COLOR_DISABLED_BG}; color:{COLOR_DISABLED_TEXT}; border-color:{COLOR_DISABLED_BG}; }}
        QProgressBar {{ border:1px solid {COLOR_BORDER}; border-radius:4px; text-align:center; color:{COLOR_PROGRESS_TEXT}; }}
        QProgressBar::chunk {{ background-color:{COLOR_ACCENT}; border-radius:3px; margin:1px; }}
        QTabWidget::pane {{ border:1px solid {COLOR_BORDER}; border-top:none; background-color:{COLOR_INPUT_BG}; padding:5px; }}
        QTabBar::tab {{ background-color:{COLOR_DISABLED_BG}; color:{COLOR_DISABLED_TEXT}; border:1px solid {COLOR_BORDER}; border-bottom:none; border-top-left-radius:4px; border-top-right-radius:4px; padding:6px 10px; margin-right:2px; min-width:100px; }}
        QTabBar::tab:selected {{ background-color:{COLOR_ACCENT}; color:{COLOR_BUTTON_TEXT}; border:1px solid {COLOR_BORDER}; border-bottom:1px solid {COLOR_ACCENT}; margin-bottom:-1px; }}
        QTabBar::tab:hover {{ background-color:{COLOR_HOVER}; color:{COLOR_BUTTON_TEXT}; }}
        QTabBar::tab:!selected {{ margin-top:2px; }}
        QScrollBar:vertical {{ border:1px solid {COLOR_BORDER}; background:{COLOR_BG}; width:12px; margin:12px 0 12px 0; }}
        QScrollBar::handle:vertical {{ background:{COLOR_BORDER}; min-height:20px; border-radius:5px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ border:1px solid {COLOR_BORDER}; background:{COLOR_ACCENT}; height:10px; subcontrol-position:top; subcontrol-origin:margin; }}
        QScrollBar::sub-line:vertical {{ subcontrol-position:bottom; }}
        QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{ border:none; width:10px; height:10px; background:{COLOR_ACCENT}; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:none; }}
        #SeparatorLine {{ background-color:{COLOR_BORDER}; }}
    """