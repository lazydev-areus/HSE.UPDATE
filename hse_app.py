# hse_app.py
import customtkinter as ctk
import tkinter as tk # Import tkinter
from tkinter import filedialog, messagebox
import os
import sys
import webbrowser # To open files/folders
import platform # To get drive info
import threading # Import threading to run background tasks
import requests # For making HTTP requests (e.g., checking updates)
import json # For reading/writing JSON files (e.g., history, update info)
import time # For timestamps
from datetime import datetime, timedelta # For managing update check intervals

# Install pywin32 if not already present: pip install pywin32
# This is required for win32api and ctypes in file_manager
try:
    import win32api
except ImportError:
    print("Warning: 'pywin32' library not found. Some features (like getting drives) may not work correctly.")
    print("Please install with 'pip install pywin32'.")


from file_manager import FileManager
from smart_features import SmartFeatures
from utils import get_file_icon, format_size, get_file_details, get_github_file_content, download_file

# --- Application Version ---
CURRENT_VERSION = "1.0.0" # This should be updated with each new release

# --- GitHub Update Repository Configuration ---
GITHUB_UPDATE_REPO_URL = "https://raw.githubusercontent.com/lazydev-areus/HSE.UPDATE/main/"
VERSION_FILE_URL = GITHUB_UPDATE_REPO_URL + "version.txt"
UPDATE_FILES_LIST_URL = GITHUB_UPDATE_REPO_URL + "update_files.json" # List of files to update

class HSEApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Set the window title and icon when the app is running
        self.title("Hurican Smart Explorer") # Full name when app is open
        try:
            # Ensure 'hse_icon.ico' is in the same directory as the executable after packaging
            # In PyInstaller, this file should be added via --add-data "hse_icon.ico;."
            self.iconbitmap("hse_icon.ico") 
        except tk.TclError:
            print("Warning: Could not load hse_icon.ico. Ensure it exists in the executable's directory.")

        self.geometry("1200x800")
        self.minsize(900, 600)
        ctk.set_appearance_mode("Dark")  # Modes: "System", "Dark", "Light" - Changed to Dark
        ctk.set_default_color_theme("dark-blue")  # Themes: "blue", "green", "dark-blue" - Changed to dark-blue

        self.file_manager = FileManager()
        self.smart_features = SmartFeatures()

        self.selected_item_path = None # Stores the path of the currently selected item
        self.copied_item_path = None
        self.is_cut_operation = False
        self.current_selected_frame = None # To track the selected frame

        self._setup_ui()
        self.update_file_list()
        self.update_smart_panels() # Update recent/frequent panels

        # --- Update Check Logic ---
        self.update_info = self._load_update_info()
        self.last_update_check_timestamp = self.update_info.get("last_check_timestamp", 0)
        self.deferred_update_until = self.update_info.get("deferred_until_timestamp", 0)
        
        # Check for updates on startup if enough time has passed
        self._trigger_update_check_on_startup()


    def _load_update_info(self):
        """Loads update information from hse_history.json."""
        history_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'hse_history.json')
        if os.path.exists(history_path):
            try:
                with open(history_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("update_info", {})
            except json.JSONDecodeError:
                print("Error decoding hse_history.json. Resetting update info.")
                return {}
        return {}

    def _save_update_info(self):
        """Saves update information to hse_history.json."""
        history_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'hse_history.json')
        try:
            # Load existing history data to preserve other information
            existing_data = {}
            if os.path.exists(history_path):
                with open(history_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            
            existing_data["update_info"] = {
                "last_check_timestamp": self.last_update_check_timestamp,
                "deferred_until_timestamp": self.deferred_update_until
            }

            with open(history_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=4)
        except Exception as e:
            print(f"Error saving update info to hse_history.json: {e}")


    def _trigger_update_check_on_startup(self):
        """Triggers an update check if conditions are met."""
        current_time = time.time()
        
        # Check if 24 hours passed since last check OR if deferred period has passed
        if (current_time - self.last_update_check_timestamp > 24 * 60 * 60) or \
           (current_time > self.deferred_update_until):
            
            self.status_bar.configure(text="Checking for updates...")
            threading.Thread(target=self._check_for_updates_threaded).start()
        else:
            print(f"Next update check in: {timedelta(seconds=(self.last_update_check_timestamp + 24 * 60 * 60) - current_time)}")

    def _check_for_updates_threaded(self):
        """Checks for updates in a separate thread."""
        self.last_update_check_timestamp = time.time()
        self._save_update_info() # Save the new check timestamp

        try:
            remote_version_content = get_github_file_content(VERSION_FILE_URL)
            if remote_version_content:
                remote_version = remote_version_content.strip()
                print(f"Local version: {CURRENT_VERSION}, Remote version: {remote_version}")

                if self._is_new_version_available(CURRENT_VERSION, remote_version):
                    self.after(0, lambda: self._show_update_prompt_ui(remote_version))
                else:
                    self.after(0, lambda: self.status_bar.configure(text="No updates available."))
            else:
                self.after(0, lambda: self.status_bar.configure(text="Failed to get remote version info."))
        except Exception as e:
            print(f"Error checking for updates: {e}")
            self.after(0, lambda: self.status_bar.configure(text=f"Error checking for updates: {e}"))

    def _is_new_version_available(self, local_v, remote_v):
        """Compares version strings (e.g., '1.0.0' vs '1.0.1')."""
        local_parts = [int(p) for p in local_v.split('.')]
        remote_parts = [int(p) for p in remote_v.split('.')]

        # Pad shorter version with zeros for comparison
        max_len = max(len(local_parts), len(remote_parts))
        local_parts += [0] * (max_len - len(local_parts))
        remote_parts += [0] * (max_len - len(remote_parts))

        return remote_parts > local_parts

    def _show_update_prompt_ui(self, new_version):
        """Shows the update prompt to the user."""
        if self.update_info.get("deferred_until_timestamp", 0) > time.time():
            # If user deferred recently, don't show prompt again until deferred time passes
            return

        response = messagebox.askyesno(
            "Update Available",
            f"A new version ({new_version}) of Hurican Smart Explorer is available!\n"
            "Do you want to update now? This will download the new files.\n"
            "You will need to restart the application manually after download."
        )
        if response:
            self.status_bar.configure(text="Downloading update...")
            threading.Thread(target=self._perform_update_threaded).start()
        else:
            self.deferred_update_until = time.time() + 24 * 60 * 60 # Defer for 24 hours
            self._save_update_info()
            self.status_bar.configure(text="Update deferred for 24 hours.")

    def _perform_update_threaded(self):
        """Downloads updated files in a separate thread."""
        try:
            # Get list of files to update from GitHub
            update_files_json = get_github_file_content(UPDATE_FILES_LIST_URL)
            if not update_files_json:
                raise Exception("Could not fetch update_files.json from GitHub.")
            
            files_to_update = json.loads(update_files_json)

            temp_update_dir = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "HSE_Update_Temp")
            os.makedirs(temp_update_dir, exist_ok=True)

            downloaded_count = 0
            for file_name in files_to_update:
                file_url = GITHUB_UPDATE_REPO_URL + file_name
                destination_path = os.path.join(temp_update_dir, file_name)
                
                # Ensure parent directories exist for the destination file
                os.makedirs(os.path.dirname(destination_path), exist_ok=True)

                self.after(0, lambda fn=file_name: self.status_bar.configure(text=f"Downloading {fn}..."))
                success = download_file(file_url, destination_path)
                if success:
                    downloaded_count += 1
                    print(f"Downloaded: {file_name}")
                else:
                    print(f"Failed to download: {file_name}")
                    self.after(0, lambda: messagebox.showerror("Download Error", f"Failed to download {file_name}. Update cancelled."))
                    return # Stop if any file fails

            if downloaded_count == len(files_to_update):
                self.after(0, lambda: messagebox.showinfo(
                    "Update Ready",
                    "Update files downloaded successfully!\n"
                    f"Please restart Hurican Smart Explorer to apply the update.\n"
                    f"New files are in: {temp_update_dir}\n"
                    f"You will need to manually copy these files to the application's main directory and overwrite existing ones."
                ))
                self.after(0, lambda: self.status_bar.configure(text="Update downloaded. Restart app."))
            else:
                self.after(0, lambda: messagebox.showerror("Update Failed", "Some files failed to download. Update aborted."))
                self.after(0, lambda: self.status_bar.configure(text="Update failed."))
            
        except Exception as e:
            print(f"Error during update process: {e}")
            self.after(0, lambda: messagebox.showerror("Update Error", f"An error occurred during update: {e}"))
            self.after(0, lambda: self.status_bar.configure(text="Update failed."))


    def _setup_ui(self):
        """
        Sets up the main UI layout and widgets.
        """
        # Configure main grid
        self.grid_columnconfigure(0, weight=1) # Only one main column for content
        self.grid_rowconfigure(1, weight=1) # Row for file list

        # Top frame (Address Bar, Search, Action Buttons)
        self.top_frame = ctk.CTkFrame(self, height=50, corner_radius=0)
        self.top_frame.grid(row=0, column=0, sticky="nsew")
        self.top_frame.grid_columnconfigure(3, weight=1) # Column for path_entry

        # Home Button
        self.home_button = ctk.CTkButton(self.top_frame, text="🏠 Home", command=self.go_home_directory, width=80)
        self.home_button.grid(row=0, column=0, padx=(10, 5), pady=10)

        # Up Button
        self.back_button = ctk.CTkButton(self.top_frame, text="⬆️ Up", command=self.go_up_directory, width=80)
        self.back_button.grid(row=0, column=1, padx=5, pady=10)

        # Drive selector dropdown
        self.drives = self._get_available_drives()
        self.drive_selector = ctk.CTkOptionMenu(self.top_frame, values=self.drives, command=self.change_drive)
        if self.drives:
            initial_drive = self.file_manager.current_path.split(os.sep)[0] + os.sep if self.file_manager.current_path and os.path.exists(self.file_manager.current_path.split(os.sep)[0] + os.sep) else self.drives[0]
            self.drive_selector.set(initial_drive)
        else:
            self.drive_selector.set("No drives found")
        self.drive_selector.grid(row=0, column=2, padx=5, pady=10)

        self.path_entry = ctk.CTkEntry(self.top_frame, placeholder_text="Current Path", width=400)
        self.path_entry.grid(row=0, column=3, padx=10, pady=10, sticky="ew")
        self.path_entry.bind("<Return>", self.change_directory_from_entry)

        self.search_entry = ctk.CTkEntry(self.top_frame, placeholder_text="Search...", width=200)
        self.search_entry.grid(row=0, column=4, padx=10, pady=10, sticky="ew")
        self.search_entry.bind("<Return>", self.perform_search)

        self.search_button = ctk.CTkButton(self.top_frame, text="🔍", command=self.perform_search, width=40)
        self.search_button.grid(row=0, column=5, padx=(0, 10), pady=10)

        # Action Frame (Action Buttons) - Placed below the address bar
        self.action_frame = ctk.CTkFrame(self, height=40, corner_radius=0)
        self.action_frame.grid(row=1, column=0, sticky="new", padx=10, pady=(0, 5))
        self.action_frame.grid_columnconfigure(5, weight=1) # To distribute buttons evenly

        self.copy_button = ctk.CTkButton(self.action_frame, text="Copy", command=self.copy_selected_item)
        self.copy_button.grid(row=0, column=0, padx=5, pady=5)

        self.cut_button = ctk.CTkButton(self.action_frame, text="Cut", command=self.move_selected_item_prep)
        self.cut_button.grid(row=0, column=1, padx=5, pady=5)

        self.paste_button = ctk.CTkButton(self.action_frame, text="Paste", command=self.paste_item)
        self.paste_button.grid(row=0, column=2, padx=5, pady=5)

        self.delete_button = ctk.CTkButton(self.action_frame, text="Delete", command=self.delete_selected_item, fg_color="red")
        self.delete_button.grid(row=0, column=3, padx=5, pady=5)

        self.rename_button = ctk.CTkButton(self.action_frame, text="Rename", command=self.rename_selected_item)
        self.rename_button.grid(row=0, column=4, padx=5, pady=5)

        self.new_folder_button = ctk.CTkButton(self.action_frame, text="New Folder", command=self.create_new_folder_dialog)
        self.new_folder_button.grid(row=0, column=5, padx=5, pady=5, sticky="e") # Push to the right

        # "Smart Tools" button - Opens a new window
        self.smart_tools_button = ctk.CTkButton(self.action_frame, text="🛠️ Smart Tools", command=self.open_smart_tools_window)
        self.smart_tools_button.grid(row=0, column=6, padx=(10, 5), pady=5, sticky="e") # Place at the end of the row

        # Main content frame (File list)
        self.main_content_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_content_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.main_content_frame.grid_rowconfigure(0, weight=1)
        self.main_content_frame.grid_columnconfigure(0, weight=1)

        # Tabview for main content (File List, Recent, Frequent)
        self.main_tabview = ctk.CTkTabview(self.main_content_frame, width=200)
        self.main_tabview.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        
        self.main_tabview.add("Files & Folders")
        self.main_tabview.add("Recent")
        self.main_tabview.add("Frequent")

        # Tab: Files & Folders (File Explorer)
        self.file_explorer_frame = ctk.CTkScrollableFrame(self.main_tabview.tab("Files & Folders"), fg_color="transparent")
        self.file_explorer_frame.pack(fill="both", expand=True)
        self.file_tree = self.file_explorer_frame # Assign file_tree to this frame

        # Tab: Recent
        self.recent_tab_frame = ctk.CTkScrollableFrame(self.main_tabview.tab("Recent"), fg_color="transparent")
        self.recent_tab_frame.pack(fill="both", expand=True)

        # Tab: Frequent
        self.frequent_tab_frame = ctk.CTkScrollableFrame(self.main_tabview.tab("Frequent"), fg_color="transparent")
        self.frequent_tab_frame.pack(fill="both", expand=True)


        # Status Bar
        self.status_bar = ctk.CTkLabel(self, text="Ready.", font=ctk.CTkFont(size=12))
        self.status_bar.grid(row=3, column=0, sticky="ew", padx=10, pady=5)

        # Right-click Menu (Context Menu) - Using tkinter.Menu
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Open", command=self.open_selected_item)
        self.context_menu.add_command(label="Copy", command=self.copy_selected_item)
        self.context_menu.add_command(label="Cut", command=self.move_selected_item_prep)
        self.context_menu.add_command(label="Paste", command=self.paste_item)
        self.context_menu.add_command(label="Delete", command=self.delete_selected_item)
        self.context_menu.add_command(label="Rename", command=self.rename_selected_item)
        self.context_menu.add_command(label="Create New Folder", command=self.create_new_folder_dialog)

        self.file_tree.bind("<Button-3>", self.show_context_menu) # Catch right-click event on the main frame

    def _get_available_drives(self):
        """
        Gets a list of available drives on Windows.
        """
        drives = []
        if platform.system() == "Windows":
            try:
                # Use win32api to list drives
                drives_bitmask = win32api.GetLogicalDrives()
                for i in range(26): # A-Z
                    if drives_bitmask & (1 << i):
                        drive_letter = chr(65 + i) + ":"
                        # Check if the drive is ready (e.g., USB not unplugged)
                        if os.path.exists(drive_letter + "\\"):
                            drives.append(drive_letter + "\\")
            except Exception as e:
                print(f"Error getting drive list: {e}")
                messagebox.showwarning("Warning", f"Could not get drive list: {e}\nPlease ensure 'pywin32' is installed.")
        # Add user's home directory as a quick option
        drives.insert(0, os.path.expanduser("~"))
        return drives

    def change_drive(self, drive_path):
        """
        Changes to the drive selected from the dropdown.
        """
        self.update_file_list(drive_path)

    def show_context_menu(self, event):
        """Displays the right-click menu."""
        # Get the widget on which the right-click event occurred
        widget = event.widget
        # Find the frame containing the file/folder item (item_frame)
        while widget and not hasattr(widget, 'file_path'):
            widget = widget.master
        
        if hasattr(widget, 'file_path'):
            self.selected_item_path = widget.file_path
            self.status_bar.configure(text=f"Selected: {os.path.basename(self.selected_item_path)}")
            # Enable menu options that require an item to be selected
            self.context_menu.entryconfig("Open", state="normal")
            self.context_menu.entryconfig("Copy", state="normal")
            self.context_menu.entryconfig("Cut", state="normal")
            self.context_menu.entryconfig("Delete", state="normal")
            self.context_menu.entryconfig("Rename", state="normal")
        else:
            self.selected_item_path = None # No specific item selected
            # Disable menu options that require an item to be selected
            self.context_menu.entryconfig("Open", state="disabled")
            self.context_menu.entryconfig("Copy", state="disabled")
            self.context_menu.entryconfig("Cut", state="disabled")
            self.context_menu.entryconfig("Delete", state="disabled")
            self.context_menu.entryconfig("Rename", state="disabled")
        
        # Always enable "Paste" and "Create New Folder" if an item is copied/cut
        if self.copied_item_path:
            self.context_menu.entryconfig("Paste", state="normal")
        else:
            self.context_menu.entryconfig("Paste", state="disabled")
        self.context_menu.entryconfig("Create New Folder", state="normal")

        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()


    def update_file_list(self, path=None):
        """
        Updates the file list in the main interface (File Explorer Tab).
        """
        if path is None:
            path = self.file_manager.current_path

        self.path_entry.delete(0, ctk.END)
        self.path_entry.insert(0, path)
        self.status_bar.configure(text=f"Loading: {path}")

        # Clear old widgets in file_tree and reset selection
        for widget in self.file_tree.winfo_children():
            widget.destroy()
        self.selected_item_path = None
        self.current_selected_frame = None

        files, error_message = self.file_manager.list_directory(path)

        if error_message:
            no_files_label = ctk.CTkLabel(self.file_tree, text=f"Error: {error_message}", font=ctk.CTkFont(size=16), text_color="red", wraplength=500)
            no_files_label.pack(pady=20)
            self.status_bar.configure(text=f"Error loading directory: {error_message}")
            return

        # Add "..." item to go back to parent directory
        if path != os.path.abspath(os.sep) and os.path.dirname(path) != path: # Don't show if at root of drive or path hasn't changed
            up_item_frame = ctk.CTkFrame(self.file_tree, fg_color="transparent")
            up_item_frame.pack(fill="x", padx=5, pady=2)
            up_label = ctk.CTkLabel(up_item_frame, text="⬆️ ...", font=ctk.CTkFont(size=14), anchor="w")
            up_label.pack(side="left", padx=5, pady=2)
            up_item_frame.bind("<Button-1>", lambda e: self.go_up_directory())
            up_item_frame.bind("<Double-Button-1>", lambda e: self.go_up_directory())
            up_item_frame.bind("<Enter>", lambda e, f=up_item_frame: f.configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["hover_color"]))
            up_item_frame.bind("<Leave>", lambda e, f=up_item_frame: f.configure(fg_color="transparent"))

        if not files:
            no_files_label = ctk.CTkLabel(self.file_tree, text="Empty folder.", font=ctk.CTkFont(size=16))
            no_files_label.pack(pady=20)
            self.status_bar.configure(text=f"Empty folder: {path}")
            return

        for item in files:
            self._add_file_item_to_tree(item, parent_frame=self.file_tree) # Add to main frame

        self.status_bar.configure(text=f"Loaded {len(files)} items in: {path}")

    def _add_file_item_to_tree(self, item, parent_frame, bind_double_click=True):
        """
        Adds a file/folder item to a specific frame.
        parent_frame: Parent frame to add the item to.
        bind_double_click: Whether to bind double-click event (default True).
        """
        item_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        item_frame.pack(fill="x", padx=5, pady=2)

        icon_label = ctk.CTkLabel(item_frame, text=item['icon'], font=ctk.CTkFont(size=18))
        icon_label.pack(side="left", padx=(5, 0), pady=2)

        name_label = ctk.CTkLabel(item_frame, text=item['name'], font=ctk.CTkFont(size=14), anchor="w")
        name_label.pack(side="left", padx=5, pady=2, expand=True, fill="x")

        if not item['is_dir']:
            size_label = ctk.CTkLabel(item_frame, text=item['formatted_size'], font=ctk.CTkFont(size=12), anchor="e")
            size_label.pack(side="right", padx=5, pady=2)

            mod_time_label = ctk.CTkLabel(item_frame, text=item['modified_time'], font=ctk.CTkFont(size=12), anchor="e")
            mod_time_label.pack(side="right", padx=5, pady=2)

        # Store full path in widget for easy access
        item_frame.file_path = item['path']
        item_frame.is_dir = item['is_dir']

        # Handle click event
        item_frame.bind("<Button-1>", lambda e, f=item_frame, p=item['path'], d=item['is_dir']: self._on_item_click(f, p, d))
        if bind_double_click:
            item_frame.bind("<Double-Button-1>", lambda e, p=item['path'], d=item['is_dir']: self._on_item_double_click(p, d))
        item_frame.bind("<Enter>", lambda e, f=item_frame: f.configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["hover_color"]))
        item_frame.bind("<Leave>", lambda e, f=item_frame: f.configure(fg_color="transparent"))

        # Bind events to child labels so clicking anywhere on the row works
        for child in item_frame.winfo_children():
            child.bind("<Button-1>", lambda e, f=item_frame, p=item['path'], d=item['is_dir']: self._on_item_click(f, p, d))
            if bind_double_click:
                child.bind("<Double-Button-1>", lambda e, p=item['path'], d=item['is_dir']: self._on_item_double_click(p, d))
            child.bind("<Enter>", lambda e, f=item_frame: f.configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["hover_color"]))
            child.bind("<Leave>", lambda e, f=item_frame: f.configure(fg_color="transparent"))


    def _on_item_click(self, item_frame, path, is_dir):
        """Handles single-click event on an item."""
        # Unhighlight old item (if any)
        if self.current_selected_frame:
            self.current_selected_frame.configure(fg_color="transparent")

        # Highlight new item
        item_frame.configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["hover_color"])
        self.current_selected_frame = item_frame
        
        self.selected_item_path = path # Store the path of the selected item
        self.status_bar.configure(text=f"Selected: {os.path.basename(path)}")

    def _on_item_double_click(self, path, is_dir):
        """Handles double-click event on an item."""
        self.smart_features.track_access(path) # Track access
        if is_dir:
            self.update_file_list(path)
        else:
            try:
                # Open file with system's default application
                os.startfile(path)
                self.status_bar.configure(text=f"Opened: {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not open file '{os.path.basename(path)}': {e}")
                self.status_bar.configure(text=f"Error opening file: {os.path.basename(path)}")
        self._reset_selection_highlight() # Unhighlight after opening/changing directory

    def go_home_directory(self):
        """Navigates to the user's Home directory."""
        home_path = os.path.expanduser("~")
        self.update_file_list(home_path)

    def go_up_directory(self):
        """Navigates up one directory level."""
        new_path = self.file_manager.go_up()
        self.update_file_list(new_path)

    def change_directory_from_entry(self, event=None):
        """Changes directory based on the path entered in the entry field."""
        path = self.path_entry.get()
        success, message = self.file_manager.change_directory(path)
        if success:
            self.update_file_list(path)
        else:
            messagebox.showerror("Error", message)
            self.path_entry.delete(0, ctk.END)
            self.path_entry.insert(0, self.file_manager.current_path) # Reset to old path

    def perform_search(self, event=None):
        """Performs file search."""
        keyword = self.search_entry.get()
        if not keyword:
            self.update_file_list() # If empty, display current list again
            return

        self.status_bar.configure(text=f"Searching for '{keyword}' in '{self.file_manager.current_path}'...")
        
        # Can add advanced search options here (e.g., dialog)
        results = self.file_manager.search_files(self.file_manager.current_path, keyword, search_type="name")

        # Clear old widgets in file_tree
        for widget in self.file_tree.winfo_children():
            widget.destroy()
        self.selected_item_path = None
        self.current_selected_frame = None

        if not results:
            no_results_label = ctk.CTkLabel(self.file_tree, text=f"No results found for '{keyword}'.", font=ctk.CTkFont(size=16))
            no_results_label.pack(pady=20)
            self.status_bar.configure(text=f"No search results for: '{keyword}'")
            return

        for item in results:
            self._add_file_item_to_tree(item, parent_frame=self.file_tree)

        self.status_bar.configure(text=f"Found {len(results)} results for '{keyword}'.")

    def update_smart_panels(self):
        """Updates smart panels (Recent, Frequent) in the main tabview."""
        # Update Recent panel
        for widget in self.recent_tab_frame.winfo_children():
            widget.destroy()
        recent_items = self.smart_features.get_recent_items()
        if not recent_items:
            ctk.CTkLabel(self.recent_tab_frame, text="No recent items.").pack(padx=5, pady=2, anchor="w")
        for item in recent_items:
            self._add_file_item_to_tree(item, parent_frame=self.recent_tab_frame) # Use common function

        # Update Frequent panel
        for widget in self.frequent_tab_frame.winfo_children():
            widget.destroy()
        frequent_items = self.smart_features.get_frequent_items()
        if not frequent_items:
            ctk.CTkLabel(self.frequent_tab_frame, text="No frequent items.").pack(padx=5, pady=2, anchor="w")
        for item in frequent_items:
            self._add_file_item_to_tree(item, parent_frame=self.frequent_tab_frame) # Use common function

    # --- File operation handlers from Context Menu and Action Buttons ---
    def open_selected_item(self):
        """Opens the selected item."""
        if hasattr(self, 'selected_item_path') and self.selected_item_path:
            item_details = get_file_details(self.selected_item_path)
            if item_details:
                self._on_item_double_click(item_details['path'], item_details['is_dir'])
            self.selected_item_path = None # Reset
            self._reset_selection_highlight()
        else:
            messagebox.showinfo("Notification", "Please select an item to open.")

    def copy_selected_item(self):
        """Copies the selected item."""
        if hasattr(self, 'selected_item_path') and self.selected_item_path:
            self.copied_item_path = self.selected_item_path
            self.is_cut_operation = False
            self.status_bar.configure(text=f"Copied: {os.path.basename(self.copied_item_path)}")
        else:
            messagebox.showinfo("Notification", "Please select an item to copy.")

    def move_selected_item_prep(self):
        """Prepares for cut (move) operation of the selected item."""
        if hasattr(self, 'selected_item_path') and self.selected_item_path:
            self.copied_item_path = self.selected_item_path
            self.is_cut_operation = True
            self.status_bar.configure(text=f"Cut: {os.path.basename(self.copied_item_path)}")
        else:
            messagebox.showinfo("Notification", "Please select an item to cut.")

    def paste_item(self):
        """Pastes the copied/cut item."""
        if not self.copied_item_path:
            messagebox.showinfo("Notification", "No item copied/cut.")
            return

        destination_dir = self.file_manager.current_path
        source_item_name = os.path.basename(self.copied_item_path)
        dest_path = os.path.join(destination_dir, source_item_name)

        if self.copied_item_path == dest_path:
            messagebox.showwarning("Overwrite Confirmation",
                                           "Cannot paste an item into itself.")
            return

        if os.path.exists(dest_path):
            response = messagebox.askyesno("Overwrite Confirmation",
                                           f"Item '{source_item_name}' already exists at destination. Do you want to overwrite it?")
            if not response:
                self.status_bar.configure(text="Paste operation cancelled.")
                return

        success = False
        operation_type = ""
        if self.is_cut_operation:
            operation_type = "moved"
        else:
            operation_type = "copied"

        success, message = self.file_manager.move_item(self.copied_item_path, destination_dir) if self.is_cut_operation else \
                           self.file_manager.copy_item(self.copied_item_path, destination_dir)

        if success:
            messagebox.showinfo("Success", f"Successfully {operation_type} '{source_item_name}'.")
            self.update_file_list()
            self.update_smart_panels()
            if self.is_cut_operation:
                self.copied_item_path = None # Clear cut item after pasting
                self.is_cut_operation = False
            self.status_bar.configure(text=f"Successfully {operation_type} '{source_item_name}'.")
        else:
            messagebox.showerror("Error", f"Failed to {operation_type} '{source_item_name}': {message}")
            self.status_bar.configure(text=f"Error {operation_type} '{source_item_name}'.")
        self._reset_selection_highlight()

    def delete_selected_item(self):
        """Deletes the selected item."""
        if hasattr(self, 'selected_item_path') and self.selected_item_path:
            item_name = os.path.basename(self.selected_item_path)
            response = messagebox.askyesno("Delete Confirmation", f"Are you sure you want to delete '{item_name}'?\nThis action cannot be undone!")
            if response:
                success, message = self.file_manager.delete_item(self.selected_item_path)
                if success:
                    messagebox.showinfo("Success", f"Successfully deleted '{item_name}'.")
                    self.update_file_list()
                    self.update_smart_panels()
                    self.selected_item_path = None
                    self.status_bar.configure(text=f"Successfully deleted '{item_name}'.")
                else:
                    messagebox.showerror("Error", f"Failed to delete '{item_name}': {message}")
                    self.status_bar.configure(text=f"Error deleting '{item_name}'.")
            self._reset_selection_highlight()
        else:
            messagebox.showinfo("Notification", "Please select an item to delete.")

    def rename_selected_item(self):
        """Renames the selected item."""
        if hasattr(self, 'selected_item_path') and self.selected_item_path:
            old_name = os.path.basename(self.selected_item_path)
            dialog = ctk.CTkInputDialog(text=f"Enter new name for '{old_name}':", title="Rename")
            new_name = dialog.get_input()
            if new_name and new_name != old_name:
                success, message = self.file_manager.rename_item(self.selected_item_path, new_name)
                if success:
                    messagebox.showinfo("Success", f"Successfully renamed to '{new_name}'.")
                    self.update_file_list()
                    self.update_smart_panels()
                    self.selected_item_path = None
                    self.status_bar.configure(text=f"Successfully renamed to '{new_name}'.")
                else:
                    messagebox.showerror("Error", f"Failed to rename '{old_name}' to '{new_name}': {message}")
                    self.status_bar.configure(text=f"Error renaming '{old_name}'.")
            elif new_name == old_name:
                messagebox.showinfo("Notification", "New name is the same as the old name.")
            else:
                messagebox.showinfo("Notification", "Rename operation cancelled.")
            self._reset_selection_highlight()
        else:
            messagebox.showinfo("Notification", "Please select an item to rename.")

    def create_new_folder_dialog(self):
        """Displays a dialog to create a new folder."""
        dialog = ctk.CTkInputDialog(text="Enter new folder name:", title="Create New Folder")
        folder_name = dialog.get_input()
        if folder_name:
            success, message = self.file_manager.create_folder(self.file_manager.current_path, folder_name)
            if success:
                messagebox.showinfo("Success", f"Successfully created folder '{folder_name}'.")
                self.update_file_list()
                self.status_bar.configure(text=f"Successfully created folder '{folder_name}'.")
            else:
                messagebox.showerror("Error", f"Failed to create folder '{folder_name}': {message}")
                self.status_bar.configure(text=f"Error creating folder '{folder_name}'.")
        else:
            messagebox.showinfo("Notification", "Create folder operation cancelled.")
        self._reset_selection_highlight()

    def _reset_selection_highlight(self):
        """Unhighlights the currently selected item."""
        if self.current_selected_frame:
            self.current_selected_frame.configure(fg_color="transparent")
            self.current_selected_frame = None
        self.selected_item_path = None

    def open_smart_tools_window(self):
        """Opens a separate window for smart tools."""
        if not hasattr(self, 'smart_tools_window') or not self.smart_tools_window.winfo_exists():
            self.smart_tools_window = SmartToolsWindow(self, self.file_manager, self.smart_features)
            # No longer grab_set() here
            self.smart_tools_window.focus()
        else:
            # If the window already exists, bring it back and to the front
            self.smart_tools_window.deiconify() # Restore if minimized/hidden
            self.smart_tools_window.focus() # Bring to front

# New class for the Smart Tools window
class SmartToolsWindow(ctk.CTkToplevel):
    def __init__(self, master, file_manager, smart_features):
        super().__init__(master)
        self.title("HSE Smart Tools")
        self.geometry("800x600")
        self.minsize(600, 400)
        self.transient(master) # Set main window as parent
        # self.grab_set() # Removed grab_set() to allow background execution

        self.file_manager = file_manager
        self.smart_features = smart_features
        self.selected_smart_tool_items = [] # To store selected items in the smart tools window

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.smart_features_tabview = ctk.CTkTabview(self, width=200)
        self.smart_features_tabview.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # --- Tab: Drive Info ---
        self.smart_features_tabview.add("Drive Info")
        self.drive_info_tab_frame = self.smart_features_tabview.tab("Drive Info")
        self.drive_info_tab_frame.grid_columnconfigure(0, weight=1)
        self.drive_info_tab_frame.grid_rowconfigure(2, weight=1) # Row for results frame

        self.refresh_drive_info_button = ctk.CTkButton(self.drive_info_tab_frame, text="Refresh Drive Info", command=self.show_drive_info_threaded)
        self.refresh_drive_info_button.grid(row=0, column=0, padx=5, pady=5, sticky="nw")
        
        # Status label, separate from results frame
        self.drive_info_status_label = ctk.CTkLabel(self.drive_info_tab_frame, text="Click 'Refresh Drive Info' to start.", wraplength=700, justify="left")
        self.drive_info_status_label.grid(row=1, column=0, padx=5, pady=5, sticky="nw")

        self.drive_info_content_frame = ctk.CTkScrollableFrame(self.drive_info_tab_frame, fg_color="transparent")
        self.drive_info_content_frame.grid(row=2, column=0, padx=5, pady=5, sticky="nsew")
        # drive_info_label will be created/updated dynamically within drive_info_content_frame


        # --- Tab: Duplicate Files ---
        self.smart_features_tabview.add("Duplicate Files")
        self.duplicate_files_tab_frame = self.smart_features_tabview.tab("Duplicate Files")
        self.duplicate_files_tab_frame.grid_columnconfigure(0, weight=1)
        self.duplicate_files_tab_frame.grid_rowconfigure(2, weight=1)

        self.duplicate_buttons_frame = ctk.CTkFrame(self.duplicate_files_tab_frame, fg_color="transparent")
        self.duplicate_buttons_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nw")
        self.find_duplicates_button = ctk.CTkButton(self.duplicate_buttons_frame, text="Find Duplicate Files", command=self.show_duplicate_files_threaded)
        self.find_duplicates_button.pack(side="left", padx=5, pady=5)
        self.delete_selected_duplicates_button = ctk.CTkButton(self.duplicate_buttons_frame, text="Delete Selected Items", command=lambda: self.delete_selected_smart_tool_items("duplicate"), fg_color="red")
        self.delete_selected_duplicates_button.pack(side="left", padx=5, pady=5)

        # Status label, separate from results frame
        self.duplicate_status_label = ctk.CTkLabel(self.duplicate_files_tab_frame, text="Click 'Find Duplicate Files' to start.", wraplength=700, justify="left")
        self.duplicate_status_label.grid(row=1, column=0, padx=5, pady=5, sticky="nw")

        self.duplicate_results_frame = ctk.CTkScrollableFrame(self.duplicate_files_tab_frame, fg_color="transparent")
        self.duplicate_results_frame.grid(row=2, column=0, padx=5, pady=5, sticky="nsew")


        # --- Tab: Large Files ---
        self.smart_features_tabview.add("Large Files")
        self.large_files_tab_frame = self.smart_features_tabview.tab("Large Files")
        self.large_files_tab_frame.grid_columnconfigure(0, weight=1)
        self.large_files_tab_frame.grid_rowconfigure(2, weight=1)

        self.large_buttons_frame = ctk.CTkFrame(self.large_files_tab_frame, fg_color="transparent")
        self.large_buttons_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nw")
        self.find_large_files_button = ctk.CTkButton(self.large_buttons_frame, text="Find Large Files", command=self.show_large_files_threaded)
        self.find_large_files_button.pack(side="left", padx=5, pady=5)
        self.delete_selected_large_button = ctk.CTkButton(self.large_buttons_frame, text="Delete Selected Items", command=lambda: self.delete_selected_smart_tool_items("large"), fg_color="red")
        self.delete_selected_large_button.pack(side="left", padx=5, pady=5)

        # Status label, separate from results frame
        self.large_status_label = ctk.CTkLabel(self.large_files_tab_frame, text="Click 'Find Large Files' to start.", wraplength=700, justify="left")
        self.large_status_label.grid(row=1, column=0, padx=5, pady=5, sticky="nw")

        self.large_results_frame = ctk.CTkScrollableFrame(self.large_files_tab_frame, fg_color="transparent")
        self.large_results_frame.grid(row=2, column=0, padx=5, pady=5, sticky="nsew")

        # --- Tab: Old Files ---
        self.smart_features_tabview.add("Old Files")
        self.old_files_tab_frame = self.smart_features_tabview.tab("Old Files")
        self.old_files_tab_frame.grid_columnconfigure(0, weight=1)
        self.old_files_tab_frame.grid_rowconfigure(2, weight=1)

        self.old_buttons_frame = ctk.CTkFrame(self.old_files_tab_frame, fg_color="transparent")
        self.old_buttons_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nw")
        self.find_old_files_button = ctk.CTkButton(self.old_buttons_frame, text="Find Old Files", command=self.show_old_files_threaded)
        self.find_old_files_button.pack(side="left", padx=5, pady=5)
        self.delete_selected_old_button = ctk.CTkButton(self.old_buttons_frame, text="Delete Selected Items", command=lambda: self.delete_selected_smart_tool_items("old"), fg_color="red")
        self.delete_selected_old_button.pack(side="left", padx=5, pady=5)

        # Status label, separate from results frame
        self.old_status_label = ctk.CTkLabel(self.old_files_tab_frame, text="Click 'Find Old Files' to start.", wraplength=700, justify="left")
        self.old_status_label.grid(row=1, column=0, padx=5, pady=5, sticky="nw")

        self.old_results_frame = ctk.CTkScrollableFrame(self.old_files_tab_frame, fg_color="transparent")
        self.old_results_frame.grid(row=2, column=0, padx=5, pady=5, sticky="nsew")

        # --- Tab: Contextual Suggestions ---
        self.smart_features_tabview.add("Contextual Suggestions")
        self.contextual_suggestions_tab_frame = self.smart_features_tabview.tab("Contextual Suggestions")
        self.contextual_suggestions_tab_frame.grid_columnconfigure(0, weight=1)
        self.contextual_suggestions_tab_frame.grid_rowconfigure(2, weight=1)

        self.contextual_buttons_frame = ctk.CTkFrame(self.contextual_suggestions_tab_frame, fg_color="transparent")
        self.contextual_buttons_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nw")
        self.update_contextual_suggestions_button = ctk.CTkButton(self.contextual_buttons_frame, text="Update Suggestions", command=self.show_contextual_suggestions_threaded)
        self.update_contextual_suggestions_button.pack(side="left", padx=5, pady=5)
        
        # Status label, separate from results frame
        self.contextual_status_label = ctk.CTkLabel(self.contextual_suggestions_tab_frame, text="Suggestions will appear here.", wraplength=700, justify="left")
        self.contextual_status_label.grid(row=1, column=0, padx=5, pady=5, sticky="nw")

        self.contextual_results_frame = ctk.CTkScrollableFrame(self.contextual_suggestions_tab_frame, fg_color="transparent")
        self.contextual_results_frame.grid(row=2, column=0, padx=5, pady=5, sticky="nsew")

        # When the window closes, hide it instead of destroying
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _on_closing(self):
        # Instead of destroy(), we hide the window
        self.withdraw()
        # No need for self.master.grab_release() as grab_set() was removed

    def _clear_frame_content(self, frame):
        """Clears all child widgets from a frame."""
        for widget in frame.winfo_children():
            widget.destroy()

    def _add_item_to_smart_results(self, item, parent_frame, bind_double_click=True, selectable=False):
        """
        Adds a file/folder item to the results frame of smart tools.
        parent_frame: Parent frame to add the item to.
        bind_double_click: Whether to bind double-click event (default True).
        selectable: Allows selecting the item for deletion (default False).
        """
        item_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        item_frame.pack(fill="x", padx=5, pady=2)

        if selectable:
            checkbox = ctk.CTkCheckBox(item_frame, text="", width=20)
            checkbox.pack(side="left", padx=(5, 0), pady=2)
            item_frame.checkbox = checkbox # Store reference to checkbox
            checkbox.configure(command=lambda: self._toggle_selection_smart_tool(item['path'], checkbox.get()))

        icon_label = ctk.CTkLabel(item_frame, text=item['icon'], font=ctk.CTkFont(size=16))
        icon_label.pack(side="left", padx=(5, 0), pady=2)

        name_label = ctk.CTkLabel(item_frame, text=item['name'], font=ctk.CTkFont(size=12), anchor="w")
        name_label.pack(side="left", padx=5, pady=2, expand=True, fill="x")

        if not item['is_dir']:
            size_label = ctk.CTkLabel(item_frame, text=item['formatted_size'], font=ctk.CTkFont(size=10), anchor="e")
            size_label.pack(side="right", padx=5, pady=2)

            mod_time_label = ctk.CTkLabel(item_frame, text=item['modified_time'], font=ctk.CTkFont(size=10), anchor="e")
            mod_time_label.pack(side="right", padx=5, pady=2)
        
        # Add full path for easy viewing
        path_label = ctk.CTkLabel(item_frame, text=f"Path: {item['path']}", font=ctk.CTkFont(size=10), anchor="w", wraplength=600)
        path_label.pack(side="left", padx=5, pady=2, fill="x", expand=True)

        # Handle click event
        if bind_double_click:
            item_frame.bind("<Button-1>", lambda e, p=item['path'], d=item['is_dir']: self._on_item_double_click_smart_tool(p, d))
            for child in item_frame.winfo_children():
                # Avoid binding event to checkbox so it works independently
                if isinstance(child, ctk.CTkCheckBox):
                    continue
                child.bind("<Button-1>", lambda e, p=item['path'], d=item['is_dir']: self._on_item_double_click_smart_tool(p, d))
        
        item_frame.bind("<Enter>", lambda e, f=item_frame: f.configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["hover_color"]))
        item_frame.bind("<Leave>", lambda e, f=item_frame: f.configure(fg_color="transparent"))
        for child in item_frame.winfo_children():
            if isinstance(child, ctk.CTkCheckBox):
                continue
            child.bind("<Enter>", lambda e, f=item_frame: f.configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["hover_color"]))
            child.bind("<Leave>", lambda e, f=item_frame: f.configure(fg_color="transparent"))

    def _toggle_selection_smart_tool(self, path, is_checked):
        """Adds or removes an item from the smart tool selection list."""
        if is_checked:
            if path not in self.selected_smart_tool_items:
                self.selected_smart_tool_items.append(path)
        else:
            if path in self.selected_smart_tool_items:
                self.selected_smart_tool_items.remove(path)
        print(f"Selected items in smart tool: {self.selected_smart_tool_items}")


    def _on_item_double_click_smart_tool(self, path, is_dir):
        """
        Handles double-click from smart tools.
        If it's a directory, switch the main Explorer to it. If it's a file, open the file.
        """
        if is_dir:
            self.master.update_file_list(path) # Switch main Explorer
            self.master.main_tabview.set("Files & Folders") # Switch to File Explorer tab
            self._on_closing() # Hide the smart tools window
        else:
            try:
                os.startfile(path)
                self.master.status_bar.configure(text=f"Opened: {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not open file '{os.path.basename(path)}': {e}")
                self.master.status_bar.configure(text=f"Error opening file: {os.path.basename(path)}")

    # --- Threaded functions for Smart Tools ---
    def show_drive_info_threaded(self):
        self._clear_frame_content(self.drive_info_content_frame)
        self.drive_info_status_label.configure(text="Loading information...", text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])
        self.update_idletasks() # Update UI to show loading message

        threading.Thread(target=self._run_drive_info_scan).start()

    def _run_drive_info_scan(self):
        current_drive = self.file_manager.current_path.split(os.sep)[0] + os.sep
        total_gb, free_gb, error_message = self.file_manager.get_drive_info(current_drive)
        self.after(0, self._update_drive_info_ui, total_gb, free_gb, error_message, current_drive)

    def _update_drive_info_ui(self, total_gb, free_gb, error_message, current_drive):
        if error_message:
            self.drive_info_status_label.configure(text=f"Error: {error_message}", text_color="red")
        else:
            used_gb = total_gb - free_gb
            info_text = (f"Drive: {current_drive}\n"
                         f"Total Capacity: {total_gb:.2f} GB\n"
                         f"Used: {used_gb:.2f} GB\n"
                         f"Free: {free_gb:.2f} GB")
            self.drive_info_status_label.configure(text=info_text, text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])
        self.master.status_bar.configure(text=f"Drive info updated for {current_drive}.")


    def show_duplicate_files_threaded(self):
        self._clear_frame_content(self.duplicate_results_frame)
        self.duplicate_status_label.configure(text="Scanning for duplicate files (this may take a while)...", text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])
        self.update_idletasks()
        self.selected_smart_tool_items = []

        threading.Thread(target=self._run_duplicate_scan).start()

    def _run_duplicate_scan(self):
        duplicates = self.smart_features.find_duplicate_files(self.file_manager.current_path)
        self.after(0, self._update_duplicate_ui, duplicates)

    def _update_duplicate_ui(self, duplicates):
        self._clear_frame_content(self.duplicate_results_frame)
        if not duplicates:
            self.duplicate_status_label.configure(text="No duplicate files found.")
        else:
            self.duplicate_status_label.configure(text="")
            for hash_val, file_paths in duplicates.items():
                ctk.CTkLabel(self.duplicate_results_frame, text=f"Hash Group: {hash_val[:10]}...", font=ctk.CTkFont(size=12, weight="bold")).pack(padx=5, pady=(5,0), anchor="w")
                for path in file_paths:
                    details = get_file_details(path)
                    if details:
                        self._add_item_to_smart_results(details, parent_frame=self.duplicate_results_frame, bind_double_click=True, selectable=True)
        self.master.status_bar.configure(text="Duplicate file scan complete.")


    def show_large_files_threaded(self):
        self._clear_frame_content(self.large_results_frame)
        self.large_status_label.configure(text="Scanning for large files...", justify="left", text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])
        self.update_idletasks()
        self.selected_smart_tool_items = []

        threading.Thread(target=self._run_large_scan).start()

    def _run_large_scan(self):
        large_files = self.smart_features.find_large_files(self.file_manager.current_path)
        self.after(0, self._update_large_ui, large_files)

    def _update_large_ui(self, large_files):
        self._clear_frame_content(self.large_results_frame)
        if not large_files:
            self.large_status_label.configure(text="No large files found.")
        else:
            self.large_status_label.configure(text="")
            for item in large_files:
                self._add_item_to_smart_results(item, parent_frame=self.large_results_frame, bind_double_click=True, selectable=True)
        self.master.status_bar.configure(text="Large file scan complete.")

    def show_old_files_threaded(self):
        self._clear_frame_content(self.old_results_frame)
        self.old_status_label.configure(text="Scanning for old files...", justify="left", text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])
        self.update_idletasks()
        self.selected_smart_tool_items = []

        threading.Thread(target=self._run_old_scan).start()

    def _run_old_scan(self):
        old_files = self.smart_features.find_old_unaccessed_files(self.file_manager.current_path)
        self.after(0, self._update_old_ui, old_files)

    def _update_old_ui(self, old_files):
        self._clear_frame_content(self.old_results_frame)
        if not old_files:
            self.old_status_label.configure(text="No old files found.")
        else:
            self.old_status_label.configure(text="")
            for item in old_files:
                self._add_item_to_smart_results(item, parent_frame=self.old_results_frame, bind_double_click=True, selectable=True)
        self.master.status_bar.configure(text="Old file scan complete.")

    def show_contextual_suggestions_threaded(self):
        self._clear_frame_content(self.contextual_results_frame)
        self.contextual_status_label.configure(text="Generating suggestions...", justify="left", text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])
        self.update_idletasks()
        self.selected_smart_tool_items = []

        threading.Thread(target=self._run_contextual_scan).start()

    def _run_contextual_scan(self):
        suggestions = self.smart_features.get_contextual_suggestions(self.file_manager.current_path)
        self.after(0, self._update_contextual_ui, suggestions)

    def _update_contextual_ui(self, suggestions):
        self._clear_frame_content(self.contextual_results_frame)
        if not suggestions:
            self.contextual_status_label.configure(text="No suggestions at this time.")
        else:
            self.contextual_status_label.configure(text="")
            for item in suggestions:
                self._add_item_to_smart_results(item, parent_frame=self.contextual_results_frame, bind_double_click=True, selectable=False)
        self.master.status_bar.configure(text="Contextual suggestions updated.")

    def delete_selected_smart_tool_items(self, feature_type):
        """Deletes selected items from smart tool results."""
        if not self.selected_smart_tool_items:
            messagebox.showinfo("Notification", "Please select at least one item to delete.")
            return

        response = messagebox.askyesno("Delete Confirmation", f"Are you sure you want to delete the {len(self.selected_smart_tool_items)} selected items?\nThis action cannot be undone!")
        if not response:
            return

        deleted_count = 0
        failed_count = 0
        for item_path in self.selected_smart_tool_items:
            success, message = self.file_manager.delete_item(item_path)
            if success:
                deleted_count += 1
                # Update smart features history if item is deleted
                self.smart_features.track_access(item_path) # Log access (or deletion)
            else:
                failed_count += 1
                print(f"Failed to delete '{item_path}': {message}")

        messagebox.showinfo("Deletion Result", f"Successfully deleted {deleted_count} items.\nFailed: {failed_count} items.")
        
        # Update result list after deletion
        if feature_type == "duplicate":
            self.show_duplicate_files_threaded()
        elif feature_type == "large":
            self.show_large_files_threaded()
        elif feature_type == "old":
            self.show_old_files_threaded()
        
        self.master.update_file_list() # Update main explorer
        self.master.update_smart_panels() # Update recent/frequent panels
        self.selected_smart_tool_items = [] # Clear selection list
