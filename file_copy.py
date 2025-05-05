# file_copy.py
# --- IMPORTS ---
import os
import shutil
import threading
import hashlib
import re
import time # Added for timer
import traceback # Import traceback for detailed error logging
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

# --- CONFIGURATION ---
COPY_TARGET_EXTENSIONS = [".xlsx", ".dxd", ".d7d"]
FOLDER_NUM_REGEX = re.compile(r'(\d+\.\d+\.\d+)(?:_.*)?$')

# --- HELPER FUNCTIONS ---
def _extract_folder_number(folder_name):
    match = FOLDER_NUM_REGEX.match(folder_name)
    return match.group(1) if match else None

def normalize_turkish(text):
    return text.replace('ı', 'i')

# --- UPDATED SEARCH FUNCTION ---
def search_files_for_copy(source_roots, current_dirs, extensions, search_params, log_signal, is_running_func):
    """
    Recursively searches directories for files matching specified extensions and criteria.
    Now also calculates and returns the last folder component of the file's directory.

    Args:
        source_roots (list): The original list of top-level source directories provided by the user.
        current_dirs (list): List of directories to scan in this call (initially source_roots, then subdirs).
        extensions (list): List of target file extensions.
        search_params (dict): Contains 'pattern_keywords' and 'number_keywords' sets.
        log_signal (pyqtSignal): Signal to emit log messages.
        is_running_func (callable): Function to check if the task should continue running.

    Returns:
        tuple: (found_files_map, matched_files_details)
            found_files_map (dict): {
                matching_keyword: [(filepath, associated_number, last_folder_name), ...], ...
            }
            matched_files_details (list): [
                (filepath, found_by_keyword, extension, associated_number, last_folder_name), ...
            ]
    """
    found_files_map = {}
    matched_files_details = []
    normalized_extensions = {ext.lower() for ext in extensions}
    pattern_keywords = search_params.get('pattern_keywords', set())
    number_keywords = search_params.get('number_keywords', set())

    for current_dir in current_dirs:
        if not is_running_func(): break

        # Find the original source root for this current_dir to determine if a file is at the root
        current_source_root = None
        normalized_current_dir = os.path.normpath(current_dir)
        is_a_source_root = False
        for root in source_roots:
            normalized_root = os.path.normpath(root)
            # Check if current_dir is the root itself or a subdirectory of it
            if normalized_current_dir == normalized_root:
                current_source_root = root
                is_a_source_root = True # Mark if we are scanning a root dir itself
                break
            elif normalized_current_dir.startswith(normalized_root + os.sep):
                current_source_root = root
                break

        if not current_source_root:
            log_signal.emit(f"Warning: Could not determine source root for {current_dir}", "#FF8C00")
            continue

        # Folder number check for the current directory being scanned
        current_folder_name_only = os.path.basename(normalized_current_dir).lower()
        current_folder_number = _extract_folder_number(current_folder_name_only)
        current_folder_has_number_match = current_folder_number and current_folder_number in number_keywords

        try:
            for entry in os.scandir(current_dir):
                if not is_running_func(): break

                entry_path = entry.path
                entry_name = entry.name

                if entry.is_dir(follow_symlinks=False):
                    sub_results, sub_details = search_files_for_copy(
                        source_roots, [entry_path], extensions, search_params, log_signal, is_running_func
                    )
                    for kw, paths in sub_results.items():
                        found_files_map.setdefault(kw, []).extend(paths)
                    matched_files_details.extend(sub_details)

                elif entry.is_file(follow_symlinks=False):
                    filepath = entry_path
                    filename = entry_name
                    base, ext = os.path.splitext(filename)
                    file_ext_lower = ext.lower()

                    if file_ext_lower not in normalized_extensions: continue

                    filename_lower_normalized = normalize_turkish(filename.lower())
                    file_number_match = next((num_kw for num_kw in number_keywords if num_kw in filename_lower_normalized), None)
                    file_has_number_match = file_number_match is not None
                    has_associated_number_match = current_folder_has_number_match or file_has_number_match

                    if not has_associated_number_match: continue

                    associated_number = current_folder_number if current_folder_has_number_match else file_number_match
                    match_found = False
                    found_by_keyword = None

                    if file_ext_lower == '.xlsx':
                        found_by_keyword = next((pattern_kw for pattern_kw in pattern_keywords if pattern_kw in filename_lower_normalized), None)
                        if found_by_keyword: match_found = True
                    elif file_ext_lower in ['.dxd', '.d7d']:
                        match_found = True # Implicit match if number was associated
                        found_by_keyword = associated_number # Use the number itself as the keyword for grouping

                    if match_found and found_by_keyword:
                        # Calculate the last folder name of the *source* directory containing the file
                        try:
                            file_parent_dir = os.path.dirname(filepath)
                            # Check if the parent dir is one of the original source roots
                            is_in_source_root = False
                            normalized_parent_dir = os.path.normpath(file_parent_dir)
                            for root in source_roots:
                                if normalized_parent_dir == os.path.normpath(root):
                                    is_in_source_root = True
                                    break

                            if is_in_source_root:
                                # If file is directly in a source root, use a special marker or empty string
                                # Using empty string means it goes directly into destination_folder/keyword_folder
                                last_folder_name = ""
                            else:
                                # Otherwise, use the actual name of the immediate parent folder
                                last_folder_name = os.path.basename(file_parent_dir)

                            # Handle potential empty last_folder_name if path is unusual (e.g., root drive)
                            if not last_folder_name and not is_in_source_root:
                                log_signal.emit(f"Warning: Could not determine last folder name for {filepath}. Using '_UNKNOWN_SOURCE_FOLDER_'.", "#FF8C00")
                                last_folder_name = "_UNKNOWN_SOURCE_FOLDER_"

                        except Exception as e:
                            log_signal.emit(f"Warning: Error getting last folder name for {filepath}: {e}", "#FF8C00")
                            last_folder_name = "_FOLDERNAME_ERROR_" # Use placeholder on error

                        # Append result with last folder name
                        found_files_map.setdefault(found_by_keyword, []).append((filepath, associated_number, last_folder_name))
                        matched_files_details.append((filepath, found_by_keyword, file_ext_lower, associated_number, last_folder_name))

            if not is_running_func(): break

        except OSError as e:
            log_signal.emit(f"Error scanning directory {current_dir}: {e}", "#FF8C00")
        except Exception as e:
             log_signal.emit(f"Unexpected error processing directory {current_dir}: {e}", "#FF4C4C")
             traceback.print_exc() # Keep detailed traceback for unexpected issues

    return found_files_map, matched_files_details


# --- COPY WORKER CLASS ---
class CopyWorker(QObject):
    # Signals remain the same
    copy_status_updated = pyqtSignal(str)
    copy_progress_updated = pyqtSignal(int)
    copy_log_message = pyqtSignal(str, str)
    copy_complete = pyqtSignal(int, int, float) # Added float for duration
    error_occurred = pyqtSignal(str)
    request_copy_confirmation = pyqtSignal(int, object)

    def __init__(self):
        super().__init__()
        self._running_lock = threading.Lock()
        self._is_running = False
        self._proceed_with_copy = False

    # stop, is_running, _set_running remain the same
    def stop(self):
        with self._running_lock:
            self._is_running = False

    def is_running(self):
        with self._running_lock:
            return self._is_running

    def _set_running(self, state):
        with self._running_lock:
            self._is_running = state

    # get_file_hash remains the same
    def get_file_hash(self, file_path):
        sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    if not self.is_running(): return None
                    sha256.update(chunk)
            return sha256.hexdigest()
        except OSError as e:
            self.copy_log_message.emit(f"Hashing Error (OSError) for {os.path.basename(file_path)}: {e}", "#FF8C00")
            return None
        except Exception as e:
            self.copy_log_message.emit(f"Hashing Error for {os.path.basename(file_path)}: {e}", "#FF8C00")
            return None

    # get_unique_filename remains the same
    def get_unique_filename(self, dest_path):
        if not os.path.exists(dest_path):
            return dest_path
        base, ext = os.path.splitext(dest_path)
        counter = 1
        new_path = f"{base}_{counter}{ext}"
        while os.path.exists(new_path):
            counter += 1
            new_path = f"{base}_{counter}{ext}"
            if counter > 1000:
                 self.copy_log_message.emit(f"Warning: Could not find unique name for {base}{ext} after 1000 attempts.", "#FF8C00")
                 return f"{base}_ MANY_DUPLICATES_{counter}{ext}"
        return new_path

    # proceed_with_copy: Update signature for copy_complete signal
    @pyqtSlot(bool, object)
    def proceed_with_copy(self, proceed, callback):
        self._proceed_with_copy = proceed
        if proceed:
            if callable(callback):
                if self.is_running():
                    callback() # This will trigger the actual copy phase
                else:
                    self.copy_log_message.emit("Copy cancelled before confirmed copy could start.", "#FF4C4C")
                    self.copy_complete.emit(0, 0, 0.0) # Emit with 0 duration
                    self._set_running(False)
            else:
                 self.copy_log_message.emit("Error: Invalid callback received for confirmation.", "#FF0000")
                 self._set_running(False)
                 self.copy_complete.emit(0, 0, 0.0) # Emit with 0 duration
        else:
            self.copy_status_updated.emit("Copy cancelled by user.")
            self.copy_log_message.emit("Copy cancelled: User chose not to proceed.", "#FF4C4C")
            self.copy_complete.emit(0, 0, 0.0) # Emit with 0 duration
            self._set_running(False)

    # --- UPDATED copy_files METHOD ---
    def copy_files(self, all_paths_by_keyword, destination_folder, total_items):
        """
        Copies files, creating a subfolder in the destination named after the
        source file's immediate parent directory ('last_folder_name').

        Args:
            all_paths_by_keyword (list): List of tuples:
                [(original_keyword, [(filepath, matched_number, last_folder_name), ...]), ...]
            destination_folder (str): The root destination path.
            total_items (int): Total number of files expected to be copied.

        Returns:
            tuple: (files_copied_count, 0) - second element kept for potential future use (e.g., dirs created)
        """
        files_copied = 0
        copied_hashes = {} # Tracks content hashes {hash: dest_path} across the entire copy job
        items_processed = 0

        start_time = time.time() # Start timer for copy phase

        # Grouping by keyword ('OF', '5.4.4', etc.) is still relevant for logging/organization,
        # but the destination subfolder is now determined by last_folder_name.
        for original_keyword, paths in all_paths_by_keyword:
            if not self.is_running(): break
            if not paths: continue

            # We still log based on the original keyword group, but folder structure changes
            self.copy_log_message.emit(f"Processing group: {original_keyword}", "#A0A0A0")

            # Process each file within the keyword group
            for src_path, matched_number, last_folder_name in paths:
                if not self.is_running(): break

                base_filename = os.path.basename(src_path)

                # --- Calculate Final Destination Path ---
                # The primary subfolder is now determined by the source file's parent folder name.
                # If last_folder_name is empty, it means the file was in a source root.
                if last_folder_name:
                    final_dest_folder = os.path.join(destination_folder, last_folder_name)
                else:
                    # File was directly in one of the source roots, copy to base destination
                    final_dest_folder = destination_folder

                # Ensure destination path uses correct separators for the OS
                final_dest_folder = os.path.normpath(final_dest_folder)
                dest_path = os.path.join(final_dest_folder, base_filename)

                # --- Update Progress ---
                items_processed += 1
                self.copy_status_updated.emit(f"Copying [{items_processed}/{total_items}]: {base_filename}")
                progress = int((items_processed / total_items) * 100) if total_items > 0 else 0
                self.copy_progress_updated.emit(progress)

                # --- Perform Copy Operation ---
                try:
                    # 1. Ensure the destination folder exists
                    try:
                        if not os.path.exists(final_dest_folder):
                            os.makedirs(final_dest_folder, exist_ok=True)
                            # Optional: Log folder creation
                            log_subfolder_name = os.path.basename(final_dest_folder) if final_dest_folder != destination_folder else "[Root Dest]"
                            self.copy_log_message.emit(f"Created destination subfolder: {log_subfolder_name}", "#A0A0A0")
                    except OSError as e:
                        self.copy_log_message.emit(f"Error creating destination folder '{final_dest_folder}': {e}", "#FF4C4C")
                        continue # Skip this file if its destination folder cannot be created

                    # 2. Check if source file still exists
                    if not os.path.isfile(src_path):
                        self.copy_log_message.emit(f"Skipped (Source Not Found/Not File): {base_filename}", "#808080")
                        continue

                    # 3. Get source file hash
                    src_hash = self.get_file_hash(src_path)
                    if src_hash is None: # Hash failed or cancelled
                        if self.is_running(): self.copy_log_message.emit(f"Skipped (Hashing Failed): {base_filename}", "#FF8C00")
                        continue

                    # 4. Check for Content Duplicates (already copied anywhere in this run)
                    if src_hash in copied_hashes:
                        original_copy_path = copied_hashes[src_hash]
                        original_copy_name = os.path.basename(original_copy_path)
                        # Get relative path of the original copy for better logging
                        original_copy_rel_folder = os.path.relpath(os.path.dirname(original_copy_path), destination_folder)
                        self.copy_log_message.emit(f"Skipped File (Duplicate Content of '{original_copy_name}' in '{original_copy_rel_folder}'): {base_filename}", "#808080")
                        continue

                    # 5. Handle Destination *File* Existence (Name Conflict/Identical Content at *this specific path*)
                    rename_reason = None
                    if os.path.exists(dest_path):
                        dest_hash = self.get_file_hash(dest_path)
                        if dest_hash is None: # Hash failed or cancelled
                            if self.is_running(): rename_reason = "Dest Hash Failed"
                            else: break # Cancelled during dest hash
                        elif dest_hash == src_hash:
                            # Identical file already exists at this specific destination path
                            # Log relative to the destination_folder for clarity
                            dest_subfolder_log = os.path.relpath(final_dest_folder, destination_folder)
                            self.copy_log_message.emit(f"Skipped File (Identical Exists at Dest): {base_filename} in '{dest_subfolder_log}'", "#808080")
                            copied_hashes[src_hash] = dest_path # Mark as existing correctly
                            continue
                        else:
                            # Different file exists at destination, need rename
                            rename_reason = "Name Conflict"

                    # 6. Get unique filename if needed (only affects filename, not folder)
                    if rename_reason:
                         original_dest_path = dest_path
                         dest_path = self.get_unique_filename(dest_path) # Renames file within final_dest_folder
                         renamed_to = os.path.basename(dest_path)
                         dest_subfolder_log = os.path.relpath(final_dest_folder, destination_folder)
                         self.copy_log_message.emit(f"Renamed File ({rename_reason}): {base_filename} to {renamed_to} in '{dest_subfolder_log}'", "#FFA500")

                    # 7. Perform the actual copy
                    shutil.copy2(src_path, dest_path)
                    files_copied += 1
                    copied_hashes[src_hash] = dest_path # Add hash of the successfully copied file
                    # Log copy success (optional, can be verbose)
                    # log_dest_folder = os.path.relpath(final_dest_folder, destination_folder)
                    # self.copy_log_message.emit(f"Copied File: {base_filename} to '{log_dest_folder}'", "#A0A0A0")

                except OSError as copy_e:
                    dest_subfolder_log = os.path.relpath(final_dest_folder, destination_folder) if final_dest_folder != destination_folder else '[Root Dest]'
                    err = f"OS Error copying '{base_filename}' to '{dest_subfolder_log}': {copy_e}"
                    self.copy_log_message.emit(err, "#FF4C4C")
                except Exception as copy_e:
                    dest_subfolder_log = os.path.relpath(final_dest_folder, destination_folder) if final_dest_folder != destination_folder else '[Root Dest]'
                    err = f"Unexpected Error copying '{base_filename}' to '{dest_subfolder_log}': {copy_e}"
                    self.copy_log_message.emit(err, "#FF4C4C")
                    traceback.print_exc() # Keep detailed traceback for unexpected issues

            if not self.is_running(): break

        end_time = time.time()
        copy_duration = end_time - start_time

        return files_copied, 0, copy_duration # Return duration

    # --- UPDATED run_file_copy_task METHOD ---
    @pyqtSlot(list, list, str)
    def run_file_copy_task(self, source_folders, keywords, destination_folder):
        """Main entry point, searches and then copies files."""
        self._set_running(True)
        self._proceed_with_copy = False
        task_start_time = time.time() # Overall task timer (optional)

        try:
            self.copy_status_updated.emit("Copy: Searching...")
            self.copy_log_message.emit(f"--- Start Copy Task ---", "#01B3C4")
            self.copy_log_message.emit(f"Keywords: {', '.join(keywords)}", "#A0A0A0")
            # Normalize source folder paths for consistent comparison
            normalized_source_folders = [os.path.normpath(p) for p in source_folders]
            self.copy_log_message.emit(f"Source folders: {', '.join(normalized_source_folders)}", "#A0A0A0")
            self.copy_log_message.emit(f"Destination: {destination_folder}", "#A0A0A0")
            self.copy_progress_updated.emit(0)

            # Prepare Search Parameters
            pattern_keywords_set = { normalize_turkish(kw.lower().strip()) for kw in keywords if normalize_turkish(kw.lower().strip()) in ['of', 'uf', 'if'] }
            number_keywords_set = {kw.strip() for kw in keywords if FOLDER_NUM_REGEX.match(kw.strip())}
            if not pattern_keywords_set and not number_keywords_set:
                 self.copy_log_message.emit("No valid keywords provided.", "#FF4C4C")
                 self.copy_status_updated.emit("Copy: No valid keywords.")
                 self.copy_complete.emit(0, 0, 0.0) # Emit with 0 duration
                 self._set_running(False)
                 return
            search_params = { 'pattern_keywords': pattern_keywords_set, 'number_keywords': number_keywords_set }
            self.copy_log_message.emit(f"Normalized Patterns: {pattern_keywords_set}", "#A0A0A0")
            self.copy_log_message.emit(f"Number Keywords: {number_keywords_set}", "#A0A0A0")

            # --- Perform Search ---
            search_start_time = time.time()
            found_files_map, matched_files_details = search_files_for_copy(
                 normalized_source_folders, # Pass the original roots
                 normalized_source_folders, # Start searching from the roots
                 COPY_TARGET_EXTENSIONS,
                 search_params,
                 self.copy_log_message,
                 self.is_running
            )
            search_duration = time.time() - search_start_time
            self.copy_log_message.emit(f"Search phase took {search_duration:.2f} seconds.", "#A0A0A0")

            if not self.is_running():
                self.copy_log_message.emit("Copy task stopped during search.", "#FF4C4C")
                self.copy_complete.emit(0, 0, 0.0) # Emit with 0 duration
                return

            # --- Process Search Results (unpack the last_folder_name) ---
            original_keyword_map = {normalize_turkish(kw.lower().strip()): kw for kw in keywords if normalize_turkish(kw.lower().strip()) in ['of', 'uf', 'if']}
            original_keyword_map.update({kw.strip(): kw.strip() for kw in keywords if kw.strip() in number_keywords_set})

            all_paths_structured = {}
            for found_by_kw, paths_with_details in found_files_map.items():
                # Map internal keyword (like number or 'of') back to user-provided keyword
                original_user_keyword = original_keyword_map.get(found_by_kw)
                if original_user_keyword is None:
                    # If the keyword was derived (like a number from a folder), use it directly
                    if found_by_kw in number_keywords_set:
                         original_user_keyword = found_by_kw
                    else:
                         self.copy_log_message.emit(f"Warning: Could not map found keyword '{found_by_kw}' back to user input.", "#FF8C00")
                         original_user_keyword = f"UNKNOWN_MAP_{found_by_kw}" # Fallback

                # paths_with_details contains (filepath, num, last_folder_name) tuples
                all_paths_structured.setdefault(original_user_keyword, []).extend(paths_with_details)


            # Convert to list structure expected by copy_files, now with 3 elements per file tuple
            all_paths_list = [(kw, paths) for kw, paths in all_paths_structured.items() if paths]
            all_paths_list.sort(key=lambda item: item[0]) # Sort by original keyword
            for kw, paths in all_paths_list: paths.sort(key=lambda item: item[0]) # Sort by filepath within keyword group
            total_files_found = sum(len(paths) for _, paths in all_paths_list)

            # --- Log Summary (include last folder name) ---
            if matched_files_details:
                 self.copy_log_message.emit(f"--- Search Found {total_files_found} Files ---", "#01B3C4")
                 matched_files_details.sort(key=lambda x: x[0]) # Sort by filepath
                 for filepath, fbk, ext, num, last_folder in matched_files_details: # Unpack new element
                     folder_display = f"from folder '{last_folder}'" if last_folder else "from source root"
                     self.copy_log_message.emit(
                         f"  - {os.path.basename(filepath)} ({folder_display}) "
                         f"(Rule: {fbk}, Ext: {ext}, Num: {num})",
                         "#FF0000" # Highlight found files in red in the log
                     )
            else:
                 self.copy_log_message.emit("--- Search Found 0 Files ---", "#808080")

            # --- Handle No Files Found ---
            if total_files_found == 0:
                self.copy_status_updated.emit("Copy: Nothing found.")
                self.copy_complete.emit(0, 0, 0.0) # Emit with 0 duration
                self._set_running(False)
                return

            self.copy_status_updated.emit(f"Copy: Found {total_files_found} files.")

            # --- Internal function to perform the copy and handle completion ---
            def _start_actual_copy():
                if not self.is_running():
                    self.copy_log_message.emit("Copy cancelled before actual copy phase could start.", "#FF4C4C")
                    self.copy_complete.emit(0, 0, 0.0)
                    self._set_running(False)
                    return

                # Pass the list which now contains last folder names
                files_copied, dirs_copied, copy_duration = self.copy_files(all_paths_list, destination_folder, total_files_found)

                # Handle Completion after copy attempt
                if self.is_running():
                    status = f"Copy complete: Copied {files_copied} files."
                    self.copy_status_updated.emit(status)
                    self.copy_log_message.emit(f"Copying phase took {copy_duration:.2f} seconds.", "#A0A0A0")
                    self.copy_log_message.emit(f"--- Copy Finished ({status}) ---", "#01B3C4")
                    self.copy_complete.emit(files_copied, dirs_copied, copy_duration) # Emit with duration
                    self.copy_progress_updated.emit(100)
                else:
                    self.copy_log_message.emit("Copy task stopped during copying phase.", "#FF4C4C")
                    self.copy_complete.emit(files_copied, dirs_copied, copy_duration) # Emit partial results and duration
                self._set_running(False) # Task finished or stopped


            # --- Confirmation or Direct Copy Logic ---
            if total_files_found > 20: # Use threshold for confirmation
                def continue_copying_callback():
                    # This callback is called by proceed_with_copy if user clicks Yes
                    if self._proceed_with_copy:
                         self.copy_log_message.emit("User confirmed copy. Starting copy phase...", "#A0A0A0")
                         _start_actual_copy()
                    # If not self._proceed_with_copy, the cancellation is handled in proceed_with_copy slot

                self.copy_log_message.emit(f"Waiting for user confirmation ({total_files_found} files)...", "#FFA500")
                self.request_copy_confirmation.emit(total_files_found, continue_copying_callback)
                # The actual copy will start only after proceed_with_copy(True, continue_copying_callback) is called

            else:
                # Copy Directly (fewer than 21 files)
                self.copy_log_message.emit("Found 20 or fewer files, proceeding directly.", "#A0A0A0")
                _start_actual_copy()


        except Exception as e:
            # Critical Error Handling
            task_duration = time.time() - task_start_time
            traceback_str = traceback.format_exc()
            error_msg = f"Critical task error: {type(e).__name__} - {e}"
            self.copy_status_updated.emit("Copy Error!")
            self.copy_log_message.emit(f"--- Copy Task Failed (after {task_duration:.2f}s) ---", "#FF0000")
            self.copy_log_message.emit(error_msg, "#FF4C4C")
            self.copy_log_message.emit(f"Traceback:\n{traceback_str}", "#FF4C4C")
            self.error_occurred.emit(error_msg + f"\nSee log for details.")
            self.copy_complete.emit(0, 0, 0.0) # Emit with 0 duration on critical failure
            self._set_running(False)

# --- End of file_copy.py ---