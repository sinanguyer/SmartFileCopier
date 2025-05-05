# SmartFileCopier


# File Copier & Document Query Tool

**A desktop application for finding and copying files based on keywords and folder structure, with optional integration for querying document content using a local Ollama LLM.**

This tool, built with Python and PyQt5, helps streamline workflows where specific files need to be gathered from various source locations based on defined criteria (like project identifiers or version numbers found in filenames or folder names).

**(Optional: Add a screenshot here)**
`![Screenshot of the application](screenshot.png)`

## Features

*   **Keyword-Based File Copying:**
    *   Select multiple source folders to search within.
    *   Specify keywords, which can be:
        *   **Pattern Keywords:** Pre-defined text patterns (e.g., `OF`, `UF`, `IF` as currently implemented).
        *   **Numeric Pattern Keywords:** Strings matching a specific numeric format (e.g., `X.Y.Z` like `6.1.0`, `10.2.15`, etc., defined by a regular expression in the code).
    *   Searches for files with specific extensions (configurable, default: `.xlsx`, `.dxd`, `.d7d`).
    *   **Smart Matching Logic:**
        *   `.xlsx` files are matched if their filename contains one of the **Pattern Keywords** (e.g., `OF`, `UF`, `IF`).
        *   All targeted file types (`.xlsx`, `.dxd`, `.d7d`) are matched if either their filename *or* their immediate parent folder name contains one of the **Numeric Pattern Keywords** (matching the `X.Y.Z` format).
    *   Copies found files to a specified destination folder.
    *   **Preserves Source Context:** Creates subfolders within the destination based on the *immediate parent folder name* of the original source file. Files found directly in a selected source root folder are copied to the destination root.
    *   Handles file name conflicts by appending suffixes (`_1`, `_2`, etc.).
    *   Prevents copying duplicate files based on content hash (SHA256).
    *   Asks for confirmation before copying large numbers of files (>20).
*   **Responsive GUI:**
    *   Built with PyQt5.
    *   Uses background threads for searching and copying to prevent UI freezes.
    *   Provides real-time progress bar and status updates.
    *   Detailed logging for copy operations (found files, skipped files, errors) in a dedicated tab.
    *   Stop button to cancel ongoing tasks.
    *   Customizable UI theme.
*   **Optional LLM Document Query (Ollama Integration):**
    *   Enable LLM features via a checkbox.
    *   **Process Documents:** After copying (or manually triggered), process the text content of supported files (`.pdf`, `.docx`, `.xlsx` - *requires `llm_chat.py`*) found using keywords in the source folders (or within the destination folder after a copy).
    *   **Chat Interface:** Query the content of the processed documents using a natural language interface.
    *   Requires a running Ollama instance.
    *   LLM processing and chat responses run in a separate thread.
    *   Dedicated tabs for LLM processing logs and the chat interface.

## Requirements

*   Python 3.6+
*   Dependencies listed in `requirements.txt`:
    *   PyQt5
    *   requests
    *   PyPDF2
    *   openpyxl
    *   python-docx
    *   numpy
*   **(Optional)** A running [Ollama](https://ollama.com/) instance accessible locally for the LLM features. You will also need to have pulled a model (e.g., `ollama pull llama3`).
*   The `llm_chat.py` script (containing `LLMWorker`, `VectorStore`, etc.) must be present in the same directory if you intend to use the LLM features.

## Installation

1.  **Clone the repository or download the scripts:**
    ```bash
    git clone <your-repo-url>
    cd <your-repo-name>
    ```
    Or simply place `main.py`, `gui.py`, `file_copy.py`, and `llm_chat.py` (if using LLM features) in the same directory.

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install the required packages:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **(Optional)** Ensure Ollama is installed, running, and you have pulled a model if you plan to use the LLM features.

## Usage

1.  **Run the application:**
    ```bash
    python main.py
    ```

2.  **Configure File Copying:**
    *   Click "Add Src" to select source folders.
    *   Use "Rem Src" / "Clr Src" to manage the source list.
    *   In the "Keywords" field, enter comma-separated keywords (e.g., `OF, UF, 6.1.0, 10.2.15`). The tool will differentiate between pattern keywords (like `OF`) and numeric pattern keywords (like `6.1.0`).
    *   Click "Select Dest" to choose the main destination folder.
    *   Click "Find & Copy".
    *   Confirm if prompted (for >20 files).
    *   Monitor progress via the UI and "Copy Log" tab.

3.  **Use LLM Features (Optional):**
    *   Check "Enable LLM Processing".
    *   Trigger processing via the "Process Files for LLM" button or potentially automatically after a copy (depends on `llm_chat.py` implementation). Processing uses the keywords from the input field to find relevant files in the source folders (or destination, if post-copy).
    *   Monitor the "LLM Log".
    *   Use the "Chat" tab to query processed documents.

4.  **Stop Task:** Click "Stop" to cancel active operations.

## Configuration & Customization

*   **Target File Extensions:** The extensions searched for during the copy process are defined in the `COPY_TARGET_EXTENSIONS` list within both `gui.py` and `file_copy.py` (ideally, this should be consolidated). You can modify this list to target different file types (e.g., add `.txt`, `.pdf`). **Note:** Modifying only the extension list might require adjustments to the keyword matching logic in `file_copy.py` (`search_files_for_copy` function) if the new file types need different matching rules than the existing ones.
*   **Numeric Keyword Pattern:** The regular expression defining the format for numeric keywords (currently `\d+\.\d+\.\d+` for `X.Y.Z`) is located in `file_copy.py` near the top (`FOLDER_NUM_REGEX`). You can modify this regex to match different numeric or versioning patterns.
*   **Pattern Keywords:** The specific text patterns recognized as 'Pattern Keywords' (currently `of`, `uf`, `if`) are hardcoded within the `run_file_copy_task` method in `file_copy.py`. These could be modified or made configurable.
*   **UI Colors:** The application's color theme is defined via constants at the top of `gui.py`.
*   **Copy Confirmation Threshold:** The number of files triggering the confirmation dialog (>20) is hardcoded in the `run_file_copy_task` method in `file_copy.py`.
*   **LLM Endpoint/Model:** The specific Ollama endpoint and model used are likely configured within the `llm_chat.py` script.
