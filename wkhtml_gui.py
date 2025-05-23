
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from tkinterdnd2 import DND_FILES, TkinterDnD
import subprocess
import threading
import os
import platform
import queue 
from urllib.parse import urlparse, urljoin, unquote
import re

try:
    import requests
    from bs4 import BeautifulSoup
    CRAWLER_DEPENDENCIES_MET = True
except ImportError:
    CRAWLER_DEPENDENCIES_MET = False

# determine the executable name based on OS
WKHTMLTOPDF_EXEC = "wkhtmltopdf.exe" if platform.system() == "Windows" else "wkhtmltopdf"

# constants for queue messages
LOG_MSG = "LOG_MSG"
MSGBOX_MSG = "MSGBOX_MSG"
BUTTON_STATE_MSG = "BUTTON_STATE_MSG"
ASK_PATH_MSG = "ASK_PATH_MSG"
CRAWL_COMPLETE_SIGNAL = "CRAWL_COMPLETE_SIGNAL"

class WkHtmlToPdfGUI(TkinterDnD.Tk if DND_FILES else tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WkHtmlToPdf GUI")
        self.geometry("700x900")

        self.input_items = [] 

        # --- Input Section ---
        input_frame = ttk.LabelFrame(self, text="Input HTML Documents (Files or URLs)")
        input_frame.pack(padx=10, pady=10, fill="x")
        self.input_listbox = tk.Listbox(input_frame, selectmode=tk.EXTENDED, height=6)
        self.input_listbox.pack(side=tk.LEFT, fill="both", expand=True, padx=5, pady=5)
        if DND_FILES:
            self.input_listbox.drop_target_register(DND_FILES)
            self.input_listbox.dnd_bind('<<Drop>>', self.add_dropped_files)
        else:
            ttk.Label(input_frame, text="Install 'tkinterdnd2' for drag-and-drop.").pack(pady=2)
        input_buttons_frame = ttk.Frame(input_frame)
        input_buttons_frame.pack(side=tk.LEFT, padx=5)
        ttk.Button(input_buttons_frame, text="Add File(s)", command=self.add_files).pack(fill="x", pady=2)
        ttk.Button(input_buttons_frame, text="Add URL", command=self.add_url_dialog).pack(fill="x", pady=2)
        ttk.Button(input_buttons_frame, text="Remove Selected", command=self.remove_selected).pack(fill="x", pady=2)
        ttk.Button(input_buttons_frame, text="Clear All", command=self.clear_all).pack(fill="x", pady=2)
        
        self.setup_crawler_ui()
        self.setup_options_ui()
        self.setup_output_ui() 
        self.setup_command_execution_ui()
        self.setup_log_ui()
        
        self.log_message("GUI Started. Each input item will be converted to a separate PDF.")
        self.check_wkhtmltopdf()
        if not CRAWLER_DEPENDENCIES_MET:
            self.log_message("Crawler disabled: 'requests' and/or 'beautifulsoup4' not found.", error=True)

        self.crawl_log_queue = queue.Queue()
        self.crawl_url_queue = queue.Queue()
        self.crawl_status_queue = queue.Queue()
        self.conversion_log_queue = queue.Queue()
        self.after(100, self.process_background_queues)

    def setup_options_ui(self):
        options_frame = ttk.LabelFrame(self, text="PDF Options (Applied to each PDF)")
        options_frame.pack(padx=10, pady=5, fill="x")
        options_grid = ttk.Frame(options_frame)
        options_grid.pack(fill="x", padx=5, pady=5)
        ttk.Label(options_grid, text="Page Size:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.page_size_var = tk.StringVar(value="A4")
        ttk.Combobox(options_grid, textvariable=self.page_size_var, values=["A4", "Letter", "Legal", "A3", "A5", "B5"], state="readonly").grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        ttk.Label(options_grid, text="Orientation:").grid(row=0, column=2, padx=5, pady=2, sticky="w")
        self.orientation_var = tk.StringVar(value="Portrait")
        ttk.Combobox(options_grid, textvariable=self.orientation_var, values=["Portrait", "Landscape"], state="readonly").grid(row=0, column=3, padx=5, pady=2, sticky="ew")
        self.grayscale_var = tk.BooleanVar()
        ttk.Checkbutton(options_grid, text="Grayscale", variable=self.grayscale_var).grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.disable_js_var = tk.BooleanVar()
        ttk.Checkbutton(options_grid, text="Disable JavaScript", variable=self.disable_js_var).grid(row=1, column=1, padx=5, pady=2, sticky="w")
        self.toc_var = tk.BooleanVar()
        ttk.Checkbutton(options_grid, text="Add Table of Contents (TOC)", variable=self.toc_var).grid(row=1, column=2, columnspan=2, padx=5, pady=2, sticky="w")
        ttk.Label(options_grid, text="Margins (mm):").grid(row=2, column=0, columnspan=4, padx=5, pady=5, sticky="w")
        ttk.Label(options_grid, text="Top:").grid(row=3, column=0, padx=5, pady=2, sticky="e")
        self.margin_top_var = tk.StringVar(value="10")
        ttk.Entry(options_grid, textvariable=self.margin_top_var, width=5).grid(row=3, column=1, padx=5, pady=2, sticky="w")
        ttk.Label(options_grid, text="Bottom:").grid(row=4, column=0, padx=5, pady=2, sticky="e")
        self.margin_bottom_var = tk.StringVar(value="10")
        ttk.Entry(options_grid, textvariable=self.margin_bottom_var, width=5).grid(row=4, column=1, padx=5, pady=2, sticky="w")
        ttk.Label(options_grid, text="Left:").grid(row=3, column=2, padx=5, pady=2, sticky="e")
        self.margin_left_var = tk.StringVar(value="10")
        ttk.Entry(options_grid, textvariable=self.margin_left_var, width=5).grid(row=3, column=3, padx=5, pady=2, sticky="w")
        ttk.Label(options_grid, text="Right:").grid(row=4, column=2, padx=5, pady=2, sticky="e")
        self.margin_right_var = tk.StringVar(value="10")
        ttk.Entry(options_grid, textvariable=self.margin_right_var, width=5).grid(row=4, column=3, padx=5, pady=2, sticky="w")
        options_grid.columnconfigure(1, weight=1)
        options_grid.columnconfigure(3, weight=1)

    def setup_output_ui(self):
        output_frame = ttk.LabelFrame(self, text="Output Directory (for generated PDFs)")
        output_frame.pack(padx=10, pady=5, fill="x")
        self.output_dir_var = tk.StringVar()
        ttk.Entry(output_frame, textvariable=self.output_dir_var, width=60).pack(side=tk.LEFT, fill="x", expand=True, padx=5, pady=5)
        ttk.Button(output_frame, text="Browse...", command=self.browse_output_directory).pack(side=tk.LEFT, padx=5, pady=5)

    def setup_command_execution_ui(self):
        cmd_frame = ttk.LabelFrame(self, text="Command & Execution")
        cmd_frame.pack(padx=10, pady=5, fill="x")
        self.command_preview_var = tk.StringVar()
        ttk.Entry(cmd_frame, textvariable=self.command_preview_var, state="readonly", font=("Courier", 9)).pack(fill="x", padx=5, pady=5)
        ttk.Button(cmd_frame, text="Generate Command Preview", command=self.update_command_preview).pack(side=tk.LEFT, padx=5, pady=5)
        self.convert_button = ttk.Button(cmd_frame, text="Convert to PDF(s)", command=self.start_batch_conversion)
        self.convert_button.pack(side=tk.RIGHT, padx=5, pady=5)

    def setup_log_ui(self):
        log_frame = ttk.LabelFrame(self, text="Log / Status")
        log_frame.pack(padx=10, pady=10, fill="both", expand=True)
        self.log_text = tk.Text(log_frame, height=8, wrap=tk.WORD, state=tk.DISABLED)
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=log_scrollbar.set)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.log_text.tag_config("error_tag", foreground="orange")

    def _add_input_item(self, item_value, display_text=None, update_preview=True):
        if item_value not in self.input_items:
            self.input_items.append(item_value)
            actual_display_text = display_text if display_text is not None else item_value
            self.input_listbox.insert(tk.END, actual_display_text)
            if update_preview: self.update_command_preview()
            return True
        return False

    def log_message(self, message, error=False):
        self.log_text.config(state=tk.NORMAL)
        if error: self.log_text.insert(tk.END, "WARNING: " + message + "\n", "error_tag")
        else: self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def check_wkhtmltopdf(self):
        try:
            process = subprocess.Popen([WKHTMLTOPDF_EXEC, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            stdout, stderr = process.communicate(timeout=5)
            if process.returncode == 0 and "wkhtmltopdf" in stdout: self.log_message(f"Found: {stdout.strip()}")
            else: self.log_message(f"wkhtmltopdf check failed. stdout: {stdout}, stderr: {stderr}", error=True); self.ask_wkhtmltopdf_path()
        except FileNotFoundError: self.log_message(f"'{WKHTMLTOPDF_EXEC}' not found in PATH.", error=True); self.ask_wkhtmltopdf_path()
        except Exception as e: self.log_message(f"Error checking wkhtmltopdf: {e}", error=True); self.ask_wkhtmltopdf_path()
            
    def ask_wkhtmltopdf_path(self):
        global WKHTMLTOPDF_EXEC
        if messagebox.askyesno("wkhtmltopdf Not Found", f"'{WKHTMLTOPDF_EXEC}' could not be verified.\nBrowse for executable?"):
            filepath = filedialog.askopenfilename(title="Select wkhtmltopdf Executable", filetypes=[("Executable", "*.exe" if platform.system() == "Windows" else "*"), ("All files", "*.*")])
            if filepath: WKHTMLTOPDF_EXEC = filepath; self.log_message(f"Using wkhtmltopdf: {WKHTMLTOPDF_EXEC}"); self.check_wkhtmltopdf()
            else: self.log_message("wkhtmltopdf path not provided.", error=True)
        else: self.log_message("Proceeding without verified wkhtmltopdf path.", error=True)

    def add_files(self):
        files = filedialog.askopenfilenames(title="Select HTML Files", filetypes=(("HTML files", "*.html *.htm"), ("All files", "*.*")))
        if files:
            added_count = sum(1 for f in files if self._add_input_item(f, os.path.basename(f) + f" ({f})", False))
            if added_count > 0: self.log_message(f"Added {added_count} file(s)."); self.update_command_preview()

    def add_dropped_files(self, event):
        files_str = event.data.strip('{}') if event.data.startswith('{') and event.data.endswith('}') else event.data
        dropped_files = re.findall(r'\{.*?\}|\S+', files_str) if '{' in files_str else files_str.split() 
        dropped_files = [f.strip('{}') for f in dropped_files]
        
        added_count = 0
        for file_path in dropped_files:
            if file_path.lower().endswith((".html", ".htm")) and os.path.exists(file_path):
                if self._add_input_item(file_path, os.path.basename(file_path) + f" ({file_path})", update_preview=False):
                    added_count +=1
            else: self.log_message(f"Skipped (not HTML/not found): {file_path}", error=True)
        if added_count > 0: self.log_message(f"Added {added_count} file(s) via DND."); self.update_command_preview()

    def add_url_dialog(self):
        url = simpledialog.askstring("Add URL", "Enter HTML URL:")
        if url:
            if self._add_input_item(url): self.log_message(f"Added URL: {url}")
            else: self.log_message(f"URL already in list: {url}")

    def remove_selected(self):
        selected_indices = self.input_listbox.curselection()
        if not selected_indices: self.log_message("No items selected to remove.", error=True); return
        for i in sorted(selected_indices, reverse=True): self.input_listbox.delete(i); del self.input_items[i]
        self.log_message(f"Removed {len(selected_indices)} item(s)."); self.update_command_preview()

    def clear_all(self):
        self.input_listbox.delete(0, tk.END); self.input_items.clear()
        self.log_message("Cleared all input items."); self.update_command_preview()

    def browse_output_directory(self):
        dir_path = filedialog.askdirectory(title="Select Output Directory")
        if dir_path: self.output_dir_var.set(dir_path); self.log_message(f"Output directory: {dir_path}"); self.update_command_preview()

    def generate_pdf_filename_for_item(self, input_item_str):
        if input_item_str.startswith("http://") or input_item_str.startswith("https://"):
            parsed_url = urlparse(input_item_str)
            path_part = os.path.basename(unquote(parsed_url.path))
            if not path_part or path_part == "/":
                path_elements = [elem for elem in unquote(parsed_url.path).strip('/').split('/') if elem]
                if not path_elements: path_part = "index"
                else: path_part = '_'.join(path_elements)
            name_base = f"{parsed_url.netloc}_{path_part}"
        else: # local file
            name_base = os.path.splitext(os.path.basename(input_item_str))[0]

        sanitized_name = re.sub(r'[^\w.\-]+', '_', name_base)
        sanitized_name = re.sub(r'_+', '_', sanitized_name).strip('_')
        if not sanitized_name: sanitized_name = "untitled_pdf"
        return f"{sanitized_name[:150]}.pdf"

    def build_single_item_command(self, input_item, output_pdf_path):
        if not input_item or not output_pdf_path: return None
        command = [WKHTMLTOPDF_EXEC]
        command.extend(["--page-size", self.page_size_var.get()])
        command.extend(["--orientation", self.orientation_var.get()])
        if self.grayscale_var.get(): command.append("--grayscale")
        if self.disable_js_var.get(): command.append("--disable-javascript")
        else: command.append("--enable-javascript")

        for opt, var_name_str in [("--margin-top", "margin_top_var"), ("--margin-bottom", "margin_bottom_var"), 
                                  ("--margin-left", "margin_left_var"), ("--margin-right", "margin_right_var")]:
            var_value = getattr(self, var_name_str).get()
            if var_value: command.extend([opt, var_value + "mm"])
        
        if self.toc_var.get(): command.append("toc")
        command.append(input_item)
        command.append(output_pdf_path)
        return command

    def update_command_preview(self, event=None):
        if not self.input_items:
            self.command_preview_var.set("Add input items and select output directory.")
            return
        
        output_dir = self.output_dir_var.get()
        if not output_dir:
            self.command_preview_var.set("Select an output directory.")
            return

        first_item = self.input_items[0]
        example_output_filename = self.generate_pdf_filename_for_item(first_item)
        example_output_path = os.path.join(output_dir, example_output_filename)
        
        command_list = self.build_single_item_command(first_item, example_output_path)
        
        num_items = len(self.input_items)
        preview_text = f"Batch mode: {num_items} item(s) to directory '{os.path.basename(output_dir)}'.\n"
        if command_list:
            preview_text += f"Preview for first item: {subprocess.list2cmdline(command_list)}"
        else:
            preview_text += "Could not generate preview for first item."
        self.command_preview_var.set(preview_text)


    def start_batch_conversion(self):
        input_items_snapshot = list(self.input_items)
        output_directory = self.output_dir_var.get()

        if not input_items_snapshot:
            self.log_message("No input HTML documents specified.", error=True); messagebox.showerror("Error", "Please add at least one HTML file or URL."); return
        if not output_directory:
            self.log_message("Output directory not specified.", error=True); messagebox.showerror("Error", "Please specify an output directory."); return
        if not os.path.isdir(output_directory):
            self.log_message(f"Output directory '{output_directory}' is not valid or does not exist.", error=True); messagebox.showerror("Error", f"Output directory '{output_directory}' is not valid or does not exist."); return

        self.log_message(f"Starting batch conversion of {len(input_items_snapshot)} item(s)...")
        self.convert_button.config(state=tk.DISABLED, text="Converting...")
        
        thread = threading.Thread(target=self.run_batch_conversion_thread, args=(input_items_snapshot, output_directory))
        thread.daemon = True
        thread.start()

    def run_batch_conversion_thread(self, input_items_list, output_dir_path):
        total_items = len(input_items_list)
        success_count = 0
        fail_count = 0

        for i, item_url_or_file in enumerate(input_items_list):
            self.conversion_log_queue.put((LOG_MSG, f"--- Processing item {i+1}/{total_items}: {item_url_or_file} ---", False))
            
            generated_pdf_name = self.generate_pdf_filename_for_item(item_url_or_file)
            full_output_pdf_path = os.path.join(output_dir_path, generated_pdf_name)
            
            command = self.build_single_item_command(item_url_or_file, full_output_pdf_path)
            if not command:
                self.conversion_log_queue.put((LOG_MSG, f"Skipping {item_url_or_file}: Could not build command.", True)); fail_count += 1; continue
            
            self.conversion_log_queue.put((LOG_MSG, f"Output PDF: {full_output_pdf_path}", False))
            self.conversion_log_queue.put((LOG_MSG, f"Command: {subprocess.list2cmdline(command)}", False))
            
            try:
                process_creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                           universal_newlines=True, creationflags=process_creation_flags)
                
                for line in iter(process.stdout.readline, ''): self.conversion_log_queue.put((LOG_MSG, f"wkhtmltopdf (stdout): {line.strip()}", False))
                for line in iter(process.stderr.readline, ''): self.conversion_log_queue.put((LOG_MSG, f"wkhtmltopdf (stderr): {line.strip()}", False))
                
                process.wait()

                if process.returncode == 0: self.conversion_log_queue.put((LOG_MSG, f"Successfully converted: {item_url_or_file}", False)); success_count += 1
                else: self.conversion_log_queue.put((LOG_MSG, f"Failed to convert {item_url_or_file}. Exit code: {process.returncode}", True)); fail_count += 1

            except FileNotFoundError:
                self.conversion_log_queue.put((LOG_MSG, f"'{WKHTMLTOPDF_EXEC}' not found. Install or set path.", True))
                self.conversion_log_queue.put((MSGBOX_MSG, "showerror", "Error", f"'{WKHTMLTOPDF_EXEC}' not found. Conversion stopped."))
                self.conversion_log_queue.put((ASK_PATH_MSG,)); fail_count = total_items - i; break
            except Exception as e: self.conversion_log_queue.put((LOG_MSG, f"Error converting {item_url_or_file}: {e}", True)); fail_count += 1
        
        self.conversion_log_queue.put((LOG_MSG, f"--- Batch conversion finished. Success: {success_count}, Failed: {fail_count} ---", False))
        self.conversion_log_queue.put((BUTTON_STATE_MSG, "normal", "Convert to PDF(s)"))
        if fail_count > 0 and success_count == 0 and not WKHTMLTOPDF_EXEC: pass
        elif fail_count > 0: self.conversion_log_queue.put((MSGBOX_MSG, "showwarning", "Batch Result", f"Batch finished with {fail_count} failure(s). Check log."))
        elif success_count > 0: self.conversion_log_queue.put((MSGBOX_MSG, "showinfo", "Batch Result", f"Batch successfully converted {success_count} item(s)."))

    def setup_crawler_ui(self):
        crawler_frame = ttk.LabelFrame(self, text="Site Crawler")
        crawler_frame.pack(padx=10, pady=5, fill="x")
        if not CRAWLER_DEPENDENCIES_MET: ttk.Label(crawler_frame, text="Crawler disabled: 'requests'/'beautifulsoup4' missing.", foreground="red").pack(padx=5, pady=5); return
        crawl_options_frame = ttk.Frame(crawler_frame)
        crawl_options_frame.pack(fill="x", padx=5, pady=5)
        ttk.Label(crawl_options_frame, text="Start URL:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.crawl_start_url_var = tk.StringVar(value="https://")
        ttk.Entry(crawl_options_frame, textvariable=self.crawl_start_url_var, width=40).grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        self.crawl_include_subdomains_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(crawl_options_frame, text="Include Subdomains", variable=self.crawl_include_subdomains_var).grid(row=0, column=2, padx=10, pady=2, sticky="w")
        ttk.Label(crawl_options_frame, text="Max Pages (0=unlimited):").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.crawl_max_pages_var = tk.StringVar(value="50")
        ttk.Entry(crawl_options_frame, textvariable=self.crawl_max_pages_var, width=7).grid(row=1, column=1, padx=5, pady=2, sticky="w")
        self.crawl_button = ttk.Button(crawl_options_frame, text="Crawl Site & Add URLs", command=self.start_crawl_operation)
        self.crawl_button.grid(row=1, column=2, padx=10, pady=5, sticky="e")
        self.crawl_status_var = tk.StringVar(value="Crawler idle.")
        ttk.Label(crawl_options_frame, textvariable=self.crawl_status_var).grid(row=2, column=0, columnspan=3, padx=5, pady=2, sticky="w")
        crawl_options_frame.columnconfigure(1, weight=1)
    
    def get_base_domain_for_scope(self, netloc):
        parts = netloc.split('.')
        if not parts or not parts[0]: return netloc 
        if len(parts) == 1 or all(part.isdigit() for part in parts): return netloc
        common_slds = {'co', 'com', 'org', 'net', 'ac', 'edu', 'gov', 'mil', 'ne', 'or'}
        if len(parts) > 2 and parts[-2] in common_slds: return '.'.join(parts[-3:])
        elif len(parts) >= 2: return '.'.join(parts[-2:])
        else: return netloc

    def start_crawl_operation(self):
        if not CRAWLER_DEPENDENCIES_MET: self.log_message("Crawler disabled.", error=True); return
        start_url = self.crawl_start_url_var.get()
        if not start_url.startswith(("http://", "https://")): messagebox.showerror("Invalid URL", "Start URL must be http:// or https://"); return
        try: max_pages = int(self.crawl_max_pages_var.get()); max_pages = 0 if max_pages < 0 else max_pages
        except ValueError: messagebox.showerror("Invalid Input", "Max Pages must be a number."); return
        
        self.crawl_button.config(state=tk.DISABLED); self.crawl_status_var.set("Starting crawl...")
        self.log_message(f"Crawl: {start_url} (Max: {max_pages if max_pages > 0 else 'unlimited'}, SubD: {self.crawl_include_subdomains_var.get()})")
        self.log_message("Note: This crawler does not currently respect robots.txt.", error=True)
        thread = threading.Thread(target=self.execute_crawl_thread, args=(start_url, self.crawl_include_subdomains_var.get(), max_pages))
        thread.daemon = True; thread.start()

    def execute_crawl_thread(self, start_url, include_subdomains, max_pages):
        try:
            q_crawl = queue.Queue(); q_crawl.put(start_url)
            visited_urls = set(); found_html_pages_count = 0
            scope_domain = self.get_base_domain_for_scope(urlparse(start_url).netloc)
            self.crawl_log_queue.put(f"Scope domain: {scope_domain}")
            headers = {'User-Agent': "WkHtmlToPdfGUI-Crawler/1.0"}

            while not q_crawl.empty() and (max_pages == 0 or found_html_pages_count < max_pages):
                current_url = q_crawl.get()
                parsed_c_url = urlparse(current_url)
                current_url = urljoin(f"{parsed_c_url.scheme}://{parsed_c_url.netloc}", unquote(parsed_c_url.path))
                if current_url in visited_urls: continue
                visited_urls.add(current_url)
                self.crawl_status_queue.put(f"Found: {found_html_pages_count}, Crawling: {current_url[:70]}...")
                try:
                    response = requests.get(current_url, headers=headers, timeout=10, allow_redirects=True)
                    response.raise_for_status()
                    if 'text/html' in response.headers.get('content-type', '').lower():
                        self.crawl_url_queue.put(response.url)
                        found_html_pages_count += 1
                        soup = BeautifulSoup(response.text, 'html.parser')
                        for link in soup.find_all('a', href=True):
                            abs_url = urljoin(response.url, link['href'])
                            parsed_a_url = urlparse(abs_url)
                            if parsed_a_url.scheme not in ('http', 'https') or not parsed_a_url.netloc: continue
                            abs_url = urljoin(f"{parsed_a_url.scheme}://{parsed_a_url.netloc}", unquote(parsed_a_url.path))
                            
                            in_scope = (parsed_a_url.netloc == scope_domain) or \
                                       (include_subdomains and parsed_a_url.netloc.endswith("." + scope_domain))
                            if in_scope and abs_url not in visited_urls: q_crawl.put(abs_url)
                    else: self.crawl_log_queue.put(f"Skipped (not HTML): {current_url}")
                except requests.exceptions.RequestException as e: self.crawl_log_queue.put(f"Crawl error for {current_url}: {e}")
                except Exception as e: self.crawl_log_queue.put(f"Processing error {current_url}: {e}")
            self.crawl_status_queue.put(f"Crawl finished. Found {found_html_pages_count} HTML pages.")
            self.crawl_log_queue.put(f"Crawl completed. Added {found_html_pages_count} unique HTML pages.")
        except Exception as e: self.crawl_log_queue.put(f"Critical crawl error: {e}"); self.crawl_status_queue.put("Crawl failed.")
        finally: self.crawl_status_queue.put(CRAWL_COMPLETE_SIGNAL)

    def process_background_queues(self):
        # process crawler queues
        while not self.crawl_log_queue.empty():
            try: self.log_message(f"CRAWL: {self.crawl_log_queue.get_nowait()}")
            except queue.Empty: break
        
        while not self.crawl_status_queue.empty():
            try:
                status = self.crawl_status_queue.get_nowait()
                if status == CRAWL_COMPLETE_SIGNAL: 
                    self.crawl_button.config(state=tk.NORMAL)
                    self.update_command_preview() 
                else: self.crawl_status_var.set(status)
            except queue.Empty: break

        # Process URLs found by crawler
        added_new_url_from_crawl = False
        while not self.crawl_url_queue.empty(): 
            try:
                url = self.crawl_url_queue.get_nowait()
                if self._add_input_item(url, display_text=url, update_preview=False):
                   added_new_url_from_crawl = True
            except queue.Empty:
                break 
        
        if added_new_url_from_crawl: 
            self.update_command_preview()


        # process conversion log queue
        while not self.conversion_log_queue.empty():
            try:
                msg_type, *payload = self.conversion_log_queue.get_nowait()
                if msg_type == LOG_MSG: self.log_message(payload[0], error=payload[1])
                elif msg_type == MSGBOX_MSG: getattr(messagebox, payload[0])(payload[1], payload[2])
                elif msg_type == BUTTON_STATE_MSG:
                    self.convert_button.config(state=(tk.NORMAL if payload[0] == "normal" else tk.DISABLED), text=payload[1])
                elif msg_type == ASK_PATH_MSG: self.ask_wkhtmltopdf_path()
            except queue.Empty: break
            except Exception as e: print(f"Error processing conversion queue: {e}")

        self.after(100, self.process_background_queues)


if __name__ == "__main__":
    if DND_FILES is None: print("tkinterdnd2 not found. DND disabled. (pip install tkinterdnd2)")
    if not CRAWLER_DEPENDENCIES_MET: print("Crawler deps missing: 'requests','beautifulsoup4'. (pip install requests beautifulsoup4)")
    app = WkHtmlToPdfGUI()
    app.update_command_preview() 
    app.mainloop()

