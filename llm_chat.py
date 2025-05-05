import os
import threading
from PyQt5.QtWidgets import QTextEdit, QLineEdit, QVBoxLayout, QWidget, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
import requests
from PyPDF2 import PdfReader
import openpyxl
import docx
import numpy as np
from gui import COLOR_TEXT, COLOR_LOG_PROCESSED, COLOR_ERROR_TEXT  # Import color constants

class VectorStore:
    def __init__(self):
        self.documents = []
        self.embeddings = []

    def add_document(self, doc_id, text, embedding):
        self.documents.append((doc_id, text))
        self.embeddings.append(embedding)

    def is_empty(self):
        return len(self.documents) == 0

    def similarity_search(self, query_embedding, k=3):
        if not self.embeddings:
            return []
        similarities = [np.dot(query_embedding, emb) / (np.linalg.norm(query_embedding) * np.linalg.norm(emb)) for emb in self.embeddings]
        top_k_indices = np.argsort(similarities)[-k:][::-1]
        return [self.documents[i] for i in top_k_indices]

class LLMWorker(QObject):
    llm_status_updated = pyqtSignal(str)
    llm_progress_updated = pyqtSignal(int)
    llm_log_message = pyqtSignal(str, str)
    llm_processing_complete = pyqtSignal(int)
    chat_response_received = pyqtSignal(str, str)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._running_lock = threading.Lock()
        self._is_running = True

    def stop(self):
        with self._running_lock:
            self._is_running = False

    def is_running(self):
        with self._running_lock:
            return self._is_running

    def _is_exact_match(self, keyword, text):
        """Check if keyword is a whole word in text."""
        import re
        keyword = re.escape(keyword.strip())
        pattern = r'\b' + keyword + r'\b'
        return bool(re.search(pattern, text, re.IGNORECASE))

    @pyqtSlot(list, list, str)
    def run_llm_processing(self, source_folders, keywords, destination_folder):
        try:
            self.llm_status_updated.emit("LLM: Processing documents...")
            doc_count = 0
            total_files = sum(len(os.listdir(folder)) for folder in source_folders)
            for folder in source_folders:
                if not self.is_running():
                    self.llm_log_message.emit("LLM processing cancelled.", COLOR_ERROR_TEXT)
                    break
                for filename in os.listdir(folder):
                    if not self.is_running():
                        break
                    file_path = os.path.join(folder, filename)
                    if os.path.isfile(file_path) and any(self._is_exact_match(keyword, filename) for keyword in keywords):
                        self.llm_log_message.emit(f"Processing: {filename}", COLOR_LOG_PROCESSED)
                        doc_count += 1
                        progress = int((doc_count / total_files) * 100) if total_files > 0 else 0
                        self.llm_progress_updated.emit(progress)
            if self.is_running():
                self.llm_processing_complete.emit(doc_count)
            else:
                self.llm_log_message.emit("LLM processing stopped.", COLOR_ERROR_TEXT)
                self.llm_progress_updated.emit(0)
        except Exception as e:
            self.error_occurred.emit(f"LLM processing error: {str(e)}")

    @pyqtSlot(str)
    def run_chat_query(self, query):
        try:
            self.llm_status_updated.emit("LLM: Processing query...")
            response = f"Response to: {query}"  # Placeholder for actual LLM response
            self.chat_response_received.emit(response, COLOR_TEXT)
        except Exception as e:
            self.error_occurred.emit(f"Chat query error: {str(e)}")

def init_llm_tab(app):
    # LLM Log Tab
    app.llm_log_edit = QTextEdit()
    app.llm_log_edit.setReadOnly(True)
    app.llm_log_edit.setLineWrapMode(QTextEdit.NoWrap)
    app.tab_widget.addTab(app.llm_log_edit, "LLM Log")

    # Chat Tab
    chat_widget = QWidget()
    chat_layout = QVBoxLayout(chat_widget)
    app.chat_display_edit = QTextEdit()
    app.chat_display_edit.setReadOnly(True)
    chat_layout.addWidget(app.chat_display_edit, stretch=1)
    app.chat_input_edit = QLineEdit()
    app.chat_input_edit.setPlaceholderText("Type your query here...")
    app.chat_input_edit.setClearButtonEnabled(True)
    app.chat_input_edit.returnPressed.connect(app.send_chat_message)  # Connect to method defined in add_llm_methods
    chat_layout.addWidget(app.chat_input_edit)
    app.tab_widget.addTab(chat_widget, "Chat")

def add_llm_methods(app):
    def start_llm_processing():
        keywords = [kw.strip() for kw in app.keyword_input.text().split(",") if kw.strip()]
        if not app.folder_paths:
            QMessageBox.warning(app, "Input", "Add source folder(s) for LLM processing.")
            return
        if not keywords:
            QMessageBox.warning(app, "Input", "At least one keyword required for LLM processing.")
            return
        app.set_controls_enabled(False, task_type="llm")
        app.llm_log_edit.clear()
        app.append_message(app.llm_log_edit, f"--- Starting LLM Processing (Keywords: {', '.join(keywords)}) ---", COLOR_TEXT, True)
        app.progress_bar.setValue(0)
        app.progress_bar.setFormat("LLM: %p%")
        app.tab_widget.setCurrentWidget(app.llm_log_edit)
        app.start_llm_processing_signal.emit(app.folder_paths, keywords, app.destination_folder)

    def send_chat_message():
        query = app.chat_input_edit.text().strip()
        if not query:
            return
        if not app.vector_store or app.vector_store.is_empty():
            QMessageBox.warning(app, "No Documents", "Process documents first to enable chat.")
            return
        app.append_chat_message(f"User: {query}", "#FFFFFF")
        app.chat_input_edit.clear()
        app.start_chat_query_signal.emit(query)

    def set_chat_input_enabled(enabled):
        if hasattr(app, 'chat_input_edit'):
            app.chat_input_edit.setEnabled(enabled)

    app.start_llm_processing = start_llm_processing
    app.send_chat_message = send_chat_message
    app.set_chat_input_enabled = set_chat_input_enabled
    app.vector_store = VectorStore()