import tkinter as tk
from tkinter import filedialog, messagebox, Listbox, Scrollbar
import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD
import threading
import os
import time
import shutil # For shutil.which

# --- pdfkit and wkhtmltopdf ---
import pdfkit
from bs4 import BeautifulSoup
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from pypdf import PdfWriter, PdfReader

# Global variables for wkhtmltopdf configuration
WKHTMLTOPDF_PATH = ""
PDFKIT_CONFIG = None

def check_and_configure_wkhtmltopdf(manual_path=None):
    global WKHTMLTOPDF_PATH, PDFKIT_CONFIG
    path_to_test = manual_path
    if not path_to_test:
        exe_name = "wkhtmltopdf.exe" if os.name == 'nt' else "wkhtmltopdf"
        found_in_path = shutil.which(exe_name)
        if found_in_path: path_to_test = found_in_path
        elif os.name == 'nt':
            common_locations = [
                os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "wkhtmltopdf", "bin", exe_name),
                os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "wkhtmltopdf", "bin", exe_name)
            ]
            for loc in common_locations:
                if os.path.exists(loc) and os.path.isfile(loc): path_to_test = loc; break
    if path_to_test and os.path.exists(path_to_test) and os.path.isfile(path_to_test):
        try:
            test_config = pdfkit.configuration(wkhtmltopdf=path_to_test)
            pdfkit.PDFKit("<html><body>test</body></html>", 'string', configuration=test_config).to_pdf()
            WKHTMLTOPDF_PATH = path_to_test; PDFKIT_CONFIG = test_config
            print(f"wkhtmltopdf configured successfully: {WKHTMLTOPDF_PATH}")
            return True
        except Exception as e:
            print(f"Error testing wkhtmltopdf at '{path_to_test}': {e}")
            WKHTMLTOPDF_PATH = ""; PDFKIT_CONFIG = None
            return False
    else:
        if manual_path: print(f"Provided wkhtmltopdf path '{manual_path}' is not valid or does not exist.")
        WKHTMLTOPDF_PATH = ""; PDFKIT_CONFIG = None
        return False

def convert_html_to_pdf_raw(html_filepath, pdf_filepath):
    try:
        with open(html_filepath, 'r', encoding='utf-8', errors='ignore') as f: html_content = f.read()
        soup = BeautifulSoup(html_content, 'html.parser')
        for s in soup(["script", "style"]): s.decompose()
        text_lines = ['\n' if e.name in ['p','br','div','h1','h2','h3','h4','h5','h6','li','tr'] else e.get_text(separator=' ',strip=True) for e in soup.find_all(True)]
        full_text = "\n".join([l.strip() for l in ' '.join(text_lines).replace('\n ', '\n').strip().splitlines() if l.strip()])
        doc, styles, story = SimpleDocTemplate(pdf_filepath, pagesize=letter), getSampleStyleSheet(), []
        for para_text in full_text.split('\n'):
            if para_text.strip(): story.append(Paragraph(para_text.replace('&', '&').replace('<', '<').replace('>', '>'), styles['Normal']))
            story.append(Spacer(1, 0.1 * inch))
        if not story: story.append(Paragraph("No text content found in HTML.", styles['Normal']))
        doc.build(story); return True
    except Exception as e:
        print(f"Error RAW conversion {html_filepath}: {e}")
        try: c=canvas.Canvas(pdf_filepath,pagesize=letter);c.drawString(inch,10*inch,f"Error (Raw): {os.path.basename(html_filepath)}");c.drawString(inch,9.5*inch,str(e));c.save()
        except: pass
        return False

def convert_html_to_pdf_pretty(html_filepath, pdf_filepath):
    global PDFKIT_CONFIG
    try:
        options = {'page-size':'A4','margin-top':'0.75in','margin-right':'0.75in','margin-bottom':'0.75in','margin-left':'0.75in','encoding':"UTF-8",'no-outline':None,'enable-local-file-access':None}
        if PDFKIT_CONFIG: pdfkit.from_file(html_filepath,pdf_filepath,options=options,configuration=PDFKIT_CONFIG); return True
        else:
            msg="wkhtmltopdf not configured for 'Pretty Text'."
            print(f"{msg} for {html_filepath}")
            try:c=canvas.Canvas(pdf_filepath,pagesize=letter);c.drawString(inch,10*inch,f"Error (Pretty): {os.path.basename(html_filepath)}");c.drawString(inch,9.5*inch,msg);c.save()
            except:pass
            return False
    except Exception as e: # Catches OSError from pdfkit and other exceptions
        print(f"Error PRETTY conversion {html_filepath}: {e}")
        try: c=canvas.Canvas(pdf_filepath,pagesize=letter);c.drawString(inch,10*inch,f"Error (Pretty): {os.path.basename(html_filepath)}");c.drawString(inch,9.5*inch,str(e));c.save()
        except:pass
        return False

def merge_pdfs(pdf_filepaths, output_filepath):
    try:
        merger = PdfWriter(); valid_pdfs_merged = 0
        for pdf_path in pdf_filepaths:
            if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                try:
                    reader = PdfReader(pdf_path)
                    if reader.pages: merger.append(reader); valid_pdfs_merged +=1
                    else: print(f"Skipping empty/invalid PDF: {pdf_path}")
                except Exception as e: print(f"Could not read PDF {pdf_path} for merging: {e}")
            else: print(f"Skipping non-existent/empty PDF for merging: {pdf_path}")
        if valid_pdfs_merged > 0:
            with open(output_filepath, 'wb') as f: merger.write(f)
            merger.close(); return True
        else:
            print(f"No valid PDFs to merge into {output_filepath}.")
            try:c=canvas.Canvas(output_filepath,pagesize=letter);c.drawString(inch,10*inch,"No valid PDF content merged.");c.save()
            except:pass
            return False
    except Exception as e: print(f"Error merging PDFs into {output_filepath}: {e}"); return False

class App(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)
        self.title("HTML to PDF Converter v4")
        self.geometry("850x800") # Increased width for new button
        ctk.set_appearance_mode("system"); ctk.set_default_color_theme("blue")
        self.html_files = []; self.output_dir = ""; self.output_file = ""
        self.wkhtml_configured = check_and_configure_wkhtmltopdf()
        self._build_ui()
        if not self.wkhtml_configured:
             self.status_label.configure(text="wkhtmltopdf not found for 'Pretty'. Set path or use 'Raw'.", text_color="orange")

    def _build_ui(self):
        main_frame = ctk.CTkFrame(self); main_frame.pack(padx=20, pady=20, fill="both", expand=True)

        # --- File Input Frame ---
        input_controls_frame = ctk.CTkFrame(main_frame)
        input_controls_frame.pack(pady=10, padx=10, fill="x")

        dnd_label = ctk.CTkLabel(input_controls_frame, text="Drag & Drop .html files or", font=("Arial", 14))
        dnd_label.pack(side="left", padx=(10,5), pady=10)
        
        self.select_files_button = ctk.CTkButton(input_controls_frame, text="Select Files", command=self.select_files)
        self.select_files_button.pack(side="left", padx=5, pady=10)

        self.scan_dir_button = ctk.CTkButton(input_controls_frame, text="Scan Directory (Recursive)", command=self.select_directory_and_scan_recursive)
        self.scan_dir_button.pack(side="left", padx=5, pady=10)
        
        # DND registration for the label and the frame it's in.
        input_controls_frame.drop_target_register(DND_FILES)
        input_controls_frame.dnd_bind('<<Drop>>', self.handle_drop)
        dnd_label.drop_target_register(DND_FILES)
        dnd_label.dnd_bind('<<Drop>>', self.handle_drop)

        # File list
        list_frame = ctk.CTkFrame(main_frame)
        list_frame.pack(pady=10, padx=10, fill="both", expand=True)
        ctk.CTkLabel(list_frame, text="Selected HTML Files:").pack(anchor="w", padx=5)
        self.listbox = Listbox(list_frame, selectmode=tk.EXTENDED, width=70, height=10, bg="#2E2E2E", fg="white", borderwidth=0, highlightthickness=0) # Darker theme for listbox
        self.listbox_scrollbar = ctk.CTkScrollbar(list_frame, command=self.listbox.yview) # Use CTkScrollbar
        self.listbox.configure(yscrollcommand=self.listbox_scrollbar.set)
        self.listbox_scrollbar.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True, padx=(0,5)) # Add padding for scrollbar
        self.clear_list_button = ctk.CTkButton(main_frame, text="Clear List", command=self.clear_list)
        self.clear_list_button.pack(pady=(0,10))

        # Conversion options
        options_frame = ctk.CTkFrame(main_frame); options_frame.pack(pady=10, padx=10, fill="x")
        options_frame.columnconfigure(1, weight=0); options_frame.columnconfigure(3, weight=0)
        ctk.CTkLabel(options_frame, text="Conversion Mode:", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.conversion_mode_var = tk.StringVar(value="pretty" if self.wkhtml_configured else "raw")
        self.pretty_radio = ctk.CTkRadioButton(options_frame, text="Pretty Text", variable=self.conversion_mode_var, value="pretty")
        self.pretty_radio.grid(row=1, column=0, padx=10, pady=2, sticky="w")
        self.wkhtml_info_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
        self.wkhtml_info_frame.grid(row=1, column=1, sticky="w", padx=0)
        self.wkhtml_status_label = ctk.CTkLabel(self.wkhtml_info_frame, text="", font=("Arial", 10))
        self.wkhtml_status_label.pack(side="left", padx=(0,2))
        self.configure_wkhtml_button = ctk.CTkButton(self.wkhtml_info_frame, text="", command=self.prompt_for_wkhtmltopdf_path_ui, width=100, height=24, font=("Arial",10))
        self.configure_wkhtml_button.pack(side="left")
        self.update_wkhtml_status_ui()
        self.raw_radio = ctk.CTkRadioButton(options_frame, text="Raw Text (faster, text only)", variable=self.conversion_mode_var, value="raw")
        self.raw_radio.grid(row=2, column=0, padx=10, pady=2, sticky="w", columnspan=2)
        ctk.CTkLabel(options_frame, text="PDF Output:", font=("Arial", 12, "bold")).grid(row=0, column=2, padx=(30,5), pady=5, sticky="w")
        self.pdf_output_var = tk.StringVar(value="separate")
        self.output_separate_radio = ctk.CTkRadioButton(options_frame, text="Separate PDFs", variable=self.pdf_output_var, value="separate", command=self.update_output_options)
        self.output_separate_radio.grid(row=1, column=2, padx=(35,0), pady=2, sticky="w")
        self.output_single_radio = ctk.CTkRadioButton(options_frame, text="Single PDF", variable=self.pdf_output_var, value="single", command=self.update_output_options)
        self.output_single_radio.grid(row=2, column=2, padx=(35,0), pady=2, sticky="w")

        # Output path
        self.output_path_frame = ctk.CTkFrame(main_frame); self.output_path_frame.pack(pady=10, padx=10, fill="x")
        self.output_dir_label = ctk.CTkLabel(self.output_path_frame, text="Output Dir:")
        self.output_dir_entry_var = tk.StringVar()
        self.output_dir_entry = ctk.CTkEntry(self.output_path_frame, textvariable=self.output_dir_entry_var, width=300, state="readonly")
        self.output_dir_button = ctk.CTkButton(self.output_path_frame, text="Select Dir", command=self.select_output_dir)
        self.output_file_label = ctk.CTkLabel(self.output_path_frame, text="Output File:")
        self.output_file_entry_var = tk.StringVar()
        self.output_file_entry = ctk.CTkEntry(self.output_path_frame, textvariable=self.output_file_entry_var, width=300, state="readonly")
        self.output_file_button = ctk.CTkButton(self.output_path_frame, text="Select File", command=self.select_output_file)
        self.update_output_options()

        # Actions
        action_frame = ctk.CTkFrame(main_frame); action_frame.pack(pady=20, padx=10, fill="x")
        self.convert_button = ctk.CTkButton(action_frame, text="Convert to PDF", command=self.start_conversion_thread, font=("Arial", 14, "bold"), height=40)
        self.convert_button.pack(side="left", padx=10, expand=True, fill="x")
        self.progress_bar = ctk.CTkProgressBar(main_frame, orientation="horizontal", mode="determinate"); self.progress_bar.pack(pady=(0,5), padx=10, fill="x"); self.progress_bar.set(0)
        self.status_label = ctk.CTkLabel(main_frame, text="Ready.", font=("Arial", 12)); self.status_label.pack(pady=(0,10), padx=10, fill="x")

    def update_wkhtml_status_ui(self):
        state = "normal" if self.wkhtml_configured else "disabled"
        self.pretty_radio.configure(state=state)
        if not self.wkhtml_configured and self.conversion_mode_var.get() == "pretty": self.conversion_mode_var.set("raw")
        self.wkhtml_status_label.configure(text="(OK)" if self.wkhtml_configured else "(Not Found)", text_color="green" if self.wkhtml_configured else "orange")
        self.configure_wkhtml_button.configure(text="Change" if self.wkhtml_configured else "Set Path")

    def prompt_for_wkhtmltopdf_path_ui(self):
        exe = "wkhtmltopdf.exe" if os.name == 'nt' else "wkhtmltopdf"
        types = [(f"{exe} executable", exe), ("All files", "*.*")]
        init_dir = os.path.expanduser("~")
        if os.name == 'nt':
            pf = os.environ.get("ProgramFiles", "C:\\Program Files")
            bin_p = os.path.join(pf, "wkhtmltopdf", "bin")
            if os.path.isdir(bin_p): init_dir = bin_p
            elif os.path.isdir(os.path.join(pf,"wkhtmltopdf")): init_dir=os.path.join(pf,"wkhtmltopdf")
        path = filedialog.askopenfilename(title=f"Select {exe}", initialdir=init_dir, filetypes=types, parent=self)
        if path:
            if not os.path.basename(path).lower().startswith("wkhtmltopdf"):
                messagebox.showwarning("Invalid File", f"'{os.path.basename(path)}' doesn't look like {exe}.", parent=self)
            self.wkhtml_configured = check_and_configure_wkhtmltopdf(manual_path=path)
            if self.wkhtml_configured:
                self.status_label.configure(text=f"wkhtmltopdf: {WKHTMLTOPDF_PATH}", text_color="green")
                messagebox.showinfo("Success", f"wkhtmltopdf configured:\n{WKHTMLTOPDF_PATH}", parent=self)
            else:
                self.status_label.configure(text="Failed to init wkhtmltopdf.", text_color="red")
                messagebox.showerror("Error", f"Could not init wkhtmltopdf with:\n{path}\nCheck executable.", parent=self)
            self.update_wkhtml_status_ui()

    def handle_drop(self, event):
        files = [f for f in self.tk.splitlist(event.data) if f.lower().endswith((".html", ".htm"))]
        added = self._add_files_to_list(files)
        if added > 0: self.status_label.configure(text=f"{added} HTML file(s) added from drop.")
        elif files: self.status_label.configure(text="Dropped HTML file(s) already in list.")
        else: self.status_label.configure(text="No new HTML files in drop.")

    def select_files(self):
        files = filedialog.askopenfilenames(title="Select HTML files", filetypes=(("HTML", "*.html *.htm"), ("All", "*.*")), parent=self)
        if files:
            added = self._add_files_to_list(list(files))
            self.status_label.configure(text=f"{added if added > 0 else 'No new'} HTML file(s) selected. Total: {len(self.html_files)}")
    
    def _add_files_to_list(self, file_paths):
        added_count = 0
        for f_path in file_paths:
            if f_path not in self.html_files:
                self.html_files.append(f_path)
                self.listbox.insert(tk.END, os.path.basename(f_path))
                added_count += 1
        return added_count

    def select_directory_and_scan_recursive(self):
        directory = filedialog.askdirectory(title="Select Directory to Scan Recursively", parent=self)
        if directory:
            self.set_ui_state(False) # Disable UI
            self.status_label.configure(text=f"Scanning directory: {directory}...")
            self.progress_bar.configure(mode="indeterminate") # Indicate busy
            self.progress_bar.start()

            scan_thread = threading.Thread(target=self._scan_directory_worker, args=(directory,), daemon=True)
            scan_thread.start()

    def _scan_directory_worker(self, root_dir):
        found_paths = []
        for dirpath, _, filenames in os.walk(root_dir):
            for filename in filenames:
                if filename.lower().endswith((".html", ".htm")):
                    full_path = os.path.join(dirpath, filename)
                    found_paths.append(full_path)
        # Schedule UI update back on the main thread
        self.after(0, self._finalize_recursive_scan, found_paths)


    def _finalize_recursive_scan(self, found_paths):
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0) # Reset determinate progress bar

        added_count = self._add_files_to_list(found_paths)
        
        self.status_label.configure(text=f"Scan complete. Added {added_count} new HTML file(s). Total: {len(self.html_files)}.")
        self.set_ui_state(True) # Re-enable UI

    def clear_list(self):
        self.html_files.clear(); self.listbox.delete(0, tk.END)
        self.status_label.configure(text="File list cleared."); self.progress_bar.set(0)

    def update_output_options(self):
        opt = self.pdf_output_var.get()
        show_dir = opt == "separate"
        self.output_dir_label.grid(row=0,column=0,padx=5,pady=5,sticky="w") if show_dir else self.output_dir_label.grid_remove()
        self.output_dir_entry.grid(row=0,column=1,padx=5,pady=5,sticky="ew") if show_dir else self.output_dir_entry.grid_remove()
        self.output_dir_button.grid(row=0,column=2,padx=5,pady=5) if show_dir else self.output_dir_button.grid_remove()
        self.output_file_label.grid(row=0,column=0,padx=5,pady=5,sticky="w") if not show_dir else self.output_file_label.grid_remove()
        self.output_file_entry.grid(row=0,column=1,padx=5,pady=5,sticky="ew") if not show_dir else self.output_file_entry.grid_remove()
        self.output_file_button.grid(row=0,column=2,padx=5,pady=5) if not show_dir else self.output_file_button.grid_remove()
        self.output_path_frame.columnconfigure(1, weight=1)

    def select_output_dir(self):
        d = filedialog.askdirectory(title="Select Output Directory", parent=self)
        if d: self.output_dir = d; self.output_dir_entry_var.set(d); self.status_label.configure(text=f"Out dir: {d}")

    def select_output_file(self):
        f = filedialog.asksaveasfilename(title="Save PDF As",defaultextension=".pdf",filetypes=(("PDF","*.pdf"),("All","*.*")), parent=self)
        if f: self.output_file = f; self.output_file_entry_var.set(f); self.status_label.configure(text=f"Out file: {f}")

    def set_ui_state(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.select_files_button.configure(state=state)
        self.scan_dir_button.configure(state=state) # New button
        self.clear_list_button.configure(state=state)
        self.convert_button.configure(state=state)
        self.output_dir_button.configure(state=state); self.output_file_button.configure(state=state)
        self.configure_wkhtml_button.configure(state=state)
        self.raw_radio.configure(state=state); self.output_separate_radio.configure(state=state); self.output_single_radio.configure(state=state)
        if enabled: self.update_wkhtml_status_ui()
        else: self.pretty_radio.configure(state="disabled")

    def start_conversion_thread(self):
        if not self.html_files: messagebox.showerror("Error", "No HTML files.", parent=self); return
        opt = self.pdf_output_var.get()
        if opt == "separate" and not self.output_dir: messagebox.showerror("Error", "Select output directory.", parent=self); return
        if opt == "single" and not self.output_file: messagebox.showerror("Error", "Select output PDF file.", parent=self); return
        if self.conversion_mode_var.get() == "pretty" and not self.wkhtml_configured:
             messagebox.showerror("Config Error", "wkhtmltopdf not set for 'Pretty Text'.", parent=self); return
        self.set_ui_state(False); self.progress_bar.set(0); self.status_label.configure(text="Starting conversion...")
        threading.Thread(target=self._conversion_worker, daemon=True).start()

    def _conversion_worker(self):
        conv_type, out_opt, total = self.conversion_mode_var.get(), self.pdf_output_var.get(), len(self.html_files)
        temp_pdfs, succ_cnt, fail_cnt = [], 0, 0
        start_tm = time.time(); temp_dir = ""
        try:
            target_dir = self.output_dir if out_opt=="separate" else ""
            if out_opt=="separate": os.makedirs(target_dir,exist_ok=True)
            elif out_opt=="single":
                base_out_dir = os.path.dirname(self.output_file) or "."
                temp_dir = os.path.join(base_out_dir,f"html_pdf_temp_{int(time.time())}")
                os.makedirs(temp_dir,exist_ok=True); target_dir = temp_dir
            
            for i, html_f in enumerate(self.html_files):
                base = os.path.splitext(os.path.basename(html_f))[0]
                pdf_n = f"{base}_{i}.pdf" if out_opt=="single" else f"{base}.pdf"
                pdf_p = os.path.join(target_dir, pdf_n)
                self.status_label.configure(text=f"Proc {i+1}/{total}: {os.path.basename(html_f)} ({conv_type})")
                
                ok = convert_html_to_pdf_raw(html_f,pdf_p) if conv_type=="raw" else convert_html_to_pdf_pretty(html_f,pdf_p)
                
                if ok and os.path.exists(pdf_p) and os.path.getsize(pdf_p)>0:
                    succ_cnt+=1
                    if out_opt=="single": temp_pdfs.append(pdf_p)
                else: fail_cnt+=1; print(f"Fail/Empty: {html_f}")
                self.progress_bar.set((i+1)/total * (0.9 if out_opt=="single" else 1.0))
                self.update_idletasks()

            if out_opt=="single":
                if temp_pdfs:
                    self.status_label.configure(text=f"Merging {len(temp_pdfs)} PDFs...")
                    if merge_pdfs(temp_pdfs, self.output_file): succ_cnt = 1; fail_cnt = total - len(temp_pdfs)
                    else: self.status_label.configure(text=f"Merge fail: {self.output_file}.",text_color="red"); succ_cnt=0; fail_cnt=total
                elif total > 0:
                    self.status_label.configure(text="No valid PDFs to merge.",text_color="orange")
                    try:c=canvas.Canvas(self.output_file,pagesize=letter);c.drawString(inch,10*inch,"No PDFs for merge.");c.save()
                    except:pass
                    succ_cnt=0; fail_cnt=total
                self.progress_bar.set(1.0)
        except Exception as e:
            self.status_label.configure(text=f"Error: {e}",text_color="red")
            messagebox.showerror("Conversion Error", f"Error: {e}", parent=self)
            print(f"Worker error: {e}")
        finally:
            if temp_dir and os.path.exists(temp_dir):
                try: shutil.rmtree(temp_dir); print(f"Cleaned temp: {temp_dir}")
                except Exception as e_rm: print(f"Err removing temp {temp_dir}: {e_rm}")
            
            dur = time.time() - start_tm
            if out_opt == "single":
                msg = f"Single PDF '{os.path.basename(self.output_file)}'. {len(temp_pdfs)}/{total} merged. Time: {dur:.2f}s" if succ_cnt==1 and os.path.exists(self.output_file) and os.path.getsize(self.output_file)>0 else f"Single PDF fail/empty. {len(temp_pdfs)}/{total} inputs. Time: {dur:.2f}s"
                col = "green" if succ_cnt==1 and not fail_cnt else "red"
            else:
                msg = f"{succ_cnt}/{total} PDFs created. Fails: {fail_cnt}. Time: {dur:.2f}s"
                col = "green" if fail_cnt==0 else ("orange" if succ_cnt>0 else "red")
            self.status_label.configure(text=msg, text_color=col)
            self.set_ui_state(True)

if __name__ == "__main__":
    app = App()
    app.mainloop()