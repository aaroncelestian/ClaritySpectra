#!/usr/bin/env python3
# Raman Spectrum Analysis Tool - Core Spectra Class
# Core functionality for importing, analyzing, and identifying Raman spectra

import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, savgol_filter
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import spsolve
from scipy.spatial.distance import correlation
import pandas as pd
import pickle
from datetime import datetime


class RamanSpectra:
    """Class for handling and analyzing Raman spectra data."""
    
    def __init__(self):
        """Initialize the RamanSpectra object."""
        self.current_spectra = None
        self.current_wavenumbers = None
        self.processed_spectra = None
        self.peaks = None
        self.background = None
        self.metadata = {}  # Added metadata dictionary
        self.database = {}
        self.db_path = "raman_database.pkl"
        self.hey_classification = {}  # dictionary to store Hey Classification data
        
        # Peak fitting attributes
        self.fitted_peaks = None  # List of fitted peak data
        self.peak_fit_result = None  # Dictionary containing fit results
        
        # Try to load existing database if it exists
        if os.path.exists(self.db_path):
            self.load_database()
            
        # Try to load Hey Classification data if file exists
        hey_csv_path = "RRUFF_Export_with_Hey_Classification.csv"
        if os.path.exists(hey_csv_path):
            self.load_hey_classification(hey_csv_path)
            
            
    # def load_hey_classification(self, csv_path):
    #     """
    #     Load Hey Classification data from CSV file.

    #     Parameters:
    #     -----------
    #     csv_path : str
    #         Path to the CSV file containing Hey Classification data.

    #     Returns:
    #     --------
    #     dict
    #         Dictionary mapping mineral names to their Hey Classifications.
    #     """
    #     try:
    #         # Read the CSV file
    #         df = pd.read_csv(csv_path)
            
    #         # Create dictionary mapping mineral names to classifications
    #         hey_classification = {}
    #         for _, row in df.iterrows():
    #             mineral_name = row['NAME']
    #             classification = row['HEY CLASSIFICATION']
    #             if pd.notna(mineral_name) and pd.notna(classification):
    #                 hey_classification[mineral_name] = classification
            
    #         # Store the classification data
    #         self.hey_classification = hey_classification
    #         return hey_classification
            
    #     except Exception as e:
    #         print(f"Error loading Hey Classification data: {str(e)}")
    #         return None

    
    def extract_base_mineral_name(self, name):
        """
        Extract the base mineral name from a compound name string.
        
        Parameters:
        -----------
        name : str
            The mineral name string to process
        
        Returns:
        --------
        str
            The extracted base mineral name
        """
        if not name or not isinstance(name, str):
            return ""
        
        # Convert to lowercase for consistent processing
        cleaned = name.lower().strip()
        
        # Remove common suffixes
        common_suffixes = ['-type', ' var.', ' var ', ' group', ' series', ' family', 
                          ' like', ' structure', ' form', '-rich', '-poor', 
                          '(syn)', '(nat)', 'synthetic', 'natural']
        for suffix in common_suffixes:
            if cleaned.endswith(suffix):
                cleaned = cleaned[:-len(suffix)].strip()
        
        # Remove common prefixes if they're not the entire name
        common_prefixes = ['hydro', 'meta', 'para', 'proto', 'pseudo', 'ortho', 'clino']
        for prefix in common_prefixes:
            if cleaned.startswith(prefix) and len(cleaned) > len(prefix) + 1:
                cleaned = cleaned[len(prefix):].strip()
        
        # Remove characters that often appear in database names but not in mineral names
        # like underscores, numbers, and special notation
        cleaned = ''.join(c for c in cleaned if c.isalpha() or c.isspace())
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        
        # Additional processing for database entry formats
        # If the name has any of these patterns, extract just the mineral name part
        patterns = [
            r'(.+?)_+r\d+',           # Pattern like "mineral_r12345"
            r'(.+?)__r\d+',           # Pattern like "mineral__r12345" 
            r'(.+?)_+raman',          # Pattern like "mineral_raman"
            r'(.+?)_+\d+',            # Pattern like "mineral_532"
            r'(.+?)_oriented',        # Pattern like "mineral_oriented"
            r'(.+?)_random',          # Pattern like "mineral_random"
            r'(.+?)_powder'           # Pattern like "mineral_powder"
        ]
        
        for pattern in patterns:
            import re
            match = re.match(pattern, cleaned, re.IGNORECASE)
            if match:
                cleaned = match.group(1)
                break
        
        return cleaned.strip()
    
    
    def update_hey_classification_database(self):
        """Update Hey Classification for all entries in the database with improved name extraction."""
        import tkinter as tk
        from tkinter import ttk, messagebox
        import os
        import time
        
        if not self.database:
            messagebox.showinfo("Database", "The database is empty.")
            return
        
        # Check if Hey Classification data is loaded
        if not hasattr(self, 'hey_classification') or not self.hey_classification:
            # Try to load Hey Classification data if not already loaded
            hey_csv_path = "RRUFF_Export_with_Hey_Classification.csv"
            if os.path.exists(hey_csv_path):
                self.hey_classification = self.load_hey_classification(hey_csv_path)
            
            # Check again if data was loaded
            if not hasattr(self, 'hey_classification') or not self.hey_classification:
                messagebox.showerror("Error", "Hey Classification data could not be loaded.")
                return
        
        # Create progress window with improved layout
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Updating Hey Classification")
        progress_window.geometry("800x600")
        progress_window.resizable(True, True)
        
        # Make sure the window stays on top
        progress_window.lift()
        progress_window.attributes('-topmost', True)
        
        # Create main frame with padding
        main_frame = ttk.Frame(progress_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create header with title and description
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(header_frame, text="Updating Hey Classification Database", 
                 font=("TkDefaultFont", 12, "bold")).pack(anchor=tk.W)
        ttk.Label(header_frame, text="Processing database entries and updating metadata...",
                 font=("TkDefaultFont", 9)).pack(anchor=tk.W)
        
        # Create progress section
        progress_section = ttk.LabelFrame(main_frame, text="Progress", padding=10)
        progress_section.pack(fill=tk.X, pady=(0, 10))
        
        # Overall progress bar with improved styling
        progress_frame = ttk.Frame(progress_section)
        progress_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(progress_frame, text="Overall Progress:").pack(anchor=tk.W)
        progress = ttk.Progressbar(progress_frame, length=400, mode="determinate", 
                                 style="green.Horizontal.TProgressbar")
        progress.pack(fill=tk.X, pady=(0, 5))
        
        # Create a custom style for the progress bar
        style = ttk.Style()
        style.configure("green.Horizontal.TProgressbar", 
                       background='green', 
                       troughcolor='lightgray')
        
        # Status label with percentage
        status_var = tk.StringVar(value="Starting update...")
        status_label = ttk.Label(progress_section, textvariable=status_var)
        status_label.pack(anchor=tk.W)
        
        # Statistics frame
        stats_frame = ttk.Frame(progress_section)
        stats_frame.pack(fill=tk.X, pady=(5, 0))
        
        # Create statistics labels
        stats_vars = {
            "Total": tk.StringVar(value="0"),
            "Updated": tk.StringVar(value="0"),
            "Already Had": tk.StringVar(value="0"),
            "Not Found": tk.StringVar(value="0")
        }
        
        for label, var in stats_vars.items():
            frame = ttk.Frame(stats_frame)
            frame.pack(side=tk.LEFT, padx=5)
            ttk.Label(frame, text=f"{label}:", font=("TkDefaultFont", 9, "bold")).pack(anchor=tk.W)
            ttk.Label(frame, textvariable=var, font=("TkDefaultFont", 9)).pack(anchor=tk.W)
        
        # Create log section with improved styling
        log_section = ttk.LabelFrame(main_frame, text="Update Log", padding=10)
        log_section.pack(fill=tk.BOTH, expand=True)
        
        # Create log text area with improved styling
        log_frame = ttk.Frame(log_section)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        log_text = tk.Text(log_frame, height=15, width=80, wrap=tk.WORD, 
                         font=("Courier", 9), bg="white", fg="black")
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview)
        log_text.config(yscrollcommand=log_scrollbar.set)
        
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure tags for log text with improved colors
        log_text.tag_configure("success", foreground="green", font=("Courier", 9, "bold"))
        log_text.tag_configure("warning", foreground="orange", font=("Courier", 9, "bold"))
        log_text.tag_configure("error", foreground="red", font=("Courier", 9, "bold"))
        log_text.tag_configure("info", foreground="blue", font=("Courier", 9))
        
        # Get database items and update progress bar maximum
        db_items = list(self.database.items())
        progress["maximum"] = len(db_items)
        
        # Statistics counters
        total = len(db_items)
        updated = 0
        already_had = 0
        not_found = 0
        
        # Update function for progress with improved formatting and forced updates
        def update_progress(current, name, status, log_message=None, tag="info"):
            # Update progress bar
            progress["value"] = current
            percentage = int((current / total) * 100) if total > 0 else 0
            
            # Update status with more detailed information
            status_var.set(f"{status} - {percentage}% complete ({current}/{total})")
            
            # Update statistics
            stats_vars["Total"].set(str(total))
            stats_vars["Updated"].set(str(updated))
            stats_vars["Already Had"].set(str(already_had))
            stats_vars["Not Found"].set(str(not_found))
            
            # Add log message with timestamp if provided
            if log_message:
                timestamp = datetime.now().strftime("%H:%M:%S")
                formatted_message = f"[{timestamp}] {log_message}"
                log_text.insert(tk.END, formatted_message + "\n", tag)
                log_text.see(tk.END)
            
            # Force window updates
            progress_window.update_idletasks()
            progress_window.update()
            time.sleep(0.01)  # Small delay to ensure updates are visible
        
        # Function to extract mineral name from database entry name
        def extract_mineral_name(entry_name):
            # First check for double underscore pattern: MineralName__RXXXXXX__
            if '__' in entry_name:
                parts = entry_name.split('__')
                return parts[0]  # Return first part
            
            # If no double underscore, check for single underscore pattern
            elif '_' in entry_name:
                # Extract everything before the first occurrence of "_R"
                import re
                match = re.match(r'([^_]+)_R', entry_name)
                if match:
                    return match.group(1)
                
                # Try to extract alphabetic characters before first underscore
                parts = entry_name.split('_')
                return parts[0]
            
            # If no underscore at all, just return the name
            return entry_name
        
        # Process each database entry
        for i, (name, data) in enumerate(db_items):
            # Update progress display
            update_progress(i, name, f"Processing {name}")
            
            # Skip entries without metadata
            if 'metadata' not in data or not data['metadata']:
                data['metadata'] = {}  # Create metadata dict if it doesn't exist
            
            metadata = data['metadata']
            
            # Check if Hey Classification already exists
            if 'HEY CLASSIFICATION' in metadata and metadata['HEY CLASSIFICATION']:
                already_had += 1
                update_progress(i, name, f"Processing {name}", 
                              f"Skipped {name}: Already has Hey Classification '{metadata['HEY CLASSIFICATION']}'", "info")
                continue
            
            # Extract mineral name from the database entry name
            mineral_name = extract_mineral_name(name)
            
            # Update the metadata with the extracted name
            if mineral_name:
                metadata['NAME'] = mineral_name
                update_progress(i, name, f"Processing {name}", 
                              f"Extracted mineral name '{mineral_name}' from entry name", "info")
            else:
                update_progress(i, name, f"Processing {name}", 
                              f"Could not extract mineral name from '{name}'", "warning")
                continue
            
            # Try to add Hey Classification using the mineral name
            hey_class = self.get_hey_classification(mineral_name)
            
            if hey_class:
                # Update the metadata with Hey Classification
                metadata['HEY CLASSIFICATION'] = hey_class
                
                # Also derive chemical family if Hey Classification is found
                if ' - ' in hey_class:
                    # Extract the first part as chemical family (before the hyphen)
                    family = hey_class.split(' - ')[0].strip()
                    metadata['CHEMICAL FAMILY'] = family
                    update_progress(i, name, f"Processing {name}", 
                                  f"Updated {name}: Added Hey Classification '{hey_class}' and Chemical Family '{family}'", "success")
                else:
                    update_progress(i, name, f"Processing {name}", 
                                  f"Updated {name}: Added Hey Classification '{hey_class}'", "success")
                                  
                updated += 1
            else:
                # Try with cleaned name
                cleaned_name = self._clean_mineral_name(mineral_name)
                if cleaned_name and cleaned_name != mineral_name:
                    hey_class = self.get_hey_classification(cleaned_name)
                    
                    if hey_class:
                        # Update the metadata with Hey Classification
                        metadata['HEY CLASSIFICATION'] = hey_class
                        
                        # Also derive chemical family
                        if ' - ' in hey_class:
                            family = hey_class.split(' - ')[0].strip()
                            metadata['CHEMICAL FAMILY'] = family
                            update_progress(i, name, f"Processing {name}", 
                                          f"Updated {name}: Added Hey Classification '{hey_class}' and Chemical Family '{family}' (using cleaned name)", "success")
                        else:
                            update_progress(i, name, f"Processing {name}", 
                                          f"Updated {name}: Added Hey Classification '{hey_class}' (using cleaned name)", "success")
                        
                        updated += 1
                        continue
                
                # Try with more aggressive cleaning
                very_clean_name = self.extract_base_mineral_name(mineral_name)
                if very_clean_name and very_clean_name != mineral_name and very_clean_name != cleaned_name:
                    hey_class = self.get_hey_classification(very_clean_name)
                    
                    if hey_class:
                        # Update the metadata with Hey Classification
                        metadata['HEY CLASSIFICATION'] = hey_class
                        
                        # Also derive chemical family
                        if ' - ' in hey_class:
                            family = hey_class.split(' - ')[0].strip()
                            metadata['CHEMICAL FAMILY'] = family
                            update_progress(i, name, f"Processing {name}", 
                                          f"Updated {name}: Added Hey Classification '{hey_class}' and Chemical Family '{family}' (using aggressively cleaned name)", "success")
                        else:
                            update_progress(i, name, f"Processing {name}", 
                                          f"Updated {name}: Added Hey Classification '{hey_class}' (using aggressively cleaned name)", "success")
                        
                        updated += 1
                        continue
                
                # If we get here, we couldn't find a match
                not_found += 1
                update_progress(i, name, f"Processing {name}", 
                              f"Could not find Hey Classification for '{mineral_name}'", "warning")
        
        # Final progress update
        update_progress(total, "", "Complete", 
                      f"Update complete! Updated: {updated}, Already had: {already_had}, Not found: {not_found}", "info")
        
        # Save the database
        saved = self.save_database()
        if saved:
            log_text.insert(tk.END, f"Database saved successfully to {self.db_path}\n", "success")
        else:
            log_text.insert(tk.END, "Warning: Could not save database\n", "error")
        log_text.see(tk.END)
        
        # Add close button
        ttk.Button(main_frame, text="Close", command=progress_window.destroy).pack(pady=10)
        
        # Update main GUI database statistics
        if hasattr(self, 'update_database_stats'):
            self.update_database_stats()
        
        # Update metadata filter options if the method exists
        if hasattr(self, 'update_metadata_filter_options'):
            self.update_metadata_filter_options()
        
        # Make progress window modal
        progress_window.transient(self.root)
        progress_window.grab_set()
        self.root.wait_window(progress_window)
    
    
    # Update the existing batch_import method with improved processing
    def post_process_database_entries(self):
        """Run post-processing on database entries to update Hey Classification and Chemical Family."""
        updated = 0
        total_entries = len(self.database)
        
        for name, data in self.database.items():
            if 'metadata' in data and data['metadata']:
                metadata = data['metadata']
                
                # Ensure NAME exists
                if 'NAME' not in metadata or not metadata['NAME']:
                    # Extract name from the database entry key
                    parts = name.split('__')
                    if len(parts) > 0:
                        mineral_name = parts[0]
                        metadata['NAME'] = mineral_name
                
                # Try to add Hey Classification if it's missing
                if ('HEY CLASSIFICATION' not in metadata or not metadata['HEY CLASSIFICATION']) and 'NAME' in metadata and metadata['NAME']:
                    mineral_name = metadata['NAME']
                    
                    # First try with the name as is
                    hey_class = self.get_hey_classification(mineral_name)
                    
                    # If that fails, try with a cleaned name
                    if not hey_class:
                        cleaned_name = self.extract_base_mineral_name(mineral_name)
                        if cleaned_name and cleaned_name != mineral_name:
                            hey_class = self.get_hey_classification(cleaned_name)
                    
                    # Update metadata if Hey Classification was found
                    if hey_class:
                        metadata['HEY CLASSIFICATION'] = hey_class
                        
                        # Also derive chemical family if missing
                        if ('CHEMICAL FAMILY' not in metadata or not metadata['CHEMICAL FAMILY']) and ' - ' in hey_class:
                            family = hey_class.split(' - ')[0].strip()
                            metadata['CHEMICAL FAMILY'] = family
                        
                        updated += 1
        
        # Return number of updated entries
        return updated
    
    
    
    def update_hey_classification_from_spectra_files(self):
        """Update Hey Classification by parsing the original spectra files to extract mineral names."""
        import tkinter as tk
        from tkinter import ttk, messagebox, filedialog
        import os
        import re
        
        if not self.database:
            messagebox.showinfo("Database", "The database is empty.")
            return
        
        # Ask for directory containing the original spectra files
        spectra_dir = filedialog.askdirectory(title="Select Directory with Original Spectrum Files")
        if not spectra_dir:
            return
        
        # Check if Hey Classification data is loaded
        if not hasattr(self, 'hey_classification') or not self.hey_classification:
            # Try to load Hey Classification data if not already loaded
            hey_csv_path = "RRUFF_Export_with_Hey_Classification.csv"
            if os.path.exists(hey_csv_path):
                self.hey_classification = self.load_hey_classification(hey_csv_path)
            
            # Check again if data was loaded
            if not hasattr(self, 'hey_classification') or not self.hey_classification:
                messagebox.showerror("Error", "Hey Classification data could not be loaded.")
                return
        
        # Create progress window
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Updating Hey Classification")
        progress_window.geometry("600x400")
        
        # Create progress bar
        ttk.Label(progress_window, text="Updating Hey Classification by parsing spectra files...").pack(pady=10)
        progress = ttk.Progressbar(progress_window, length=400, mode="determinate")
        progress.pack(pady=10)
        
        # Create status label
        status_var = tk.StringVar(value="Starting update...")
        status_label = ttk.Label(progress_window, textvariable=status_var)
        status_label.pack(pady=5)
        
        # Create log text area
        log_frame = ttk.Frame(progress_window)
        log_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        log_text = tk.Text(log_frame, height=15, width=60, wrap=tk.WORD)
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview)
        log_text.config(yscrollcommand=log_scrollbar.set)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure tags for log text
        log_text.tag_configure("success", foreground="green")
        log_text.tag_configure("warning", foreground="orange")
        log_text.tag_configure("error", foreground="red")
        log_text.tag_configure("info", foreground="blue")
        
        # Get database items and update progress bar maximum
        db_items = list(self.database.items())
        progress["maximum"] = len(db_items)
        
        # Statistics counters
        total = len(db_items)
        updated = 0
        already_had = 0
        not_found = 0
        file_not_found = 0
        
        # Create mapping from database entry name to spectra file
        file_mapping = {}
        
        # Function to find original file from database entry name
        def find_original_file(db_entry_name):
            # Try direct match first
            direct_match = os.path.join(spectra_dir, db_entry_name)
            if os.path.exists(direct_match):
                return direct_match
            
            # Try adding common extensions
            for ext in ['.txt', '.csv', '.dat', '.sp']:
                file_path = os.path.join(spectra_dir, db_entry_name + ext)
                if os.path.exists(file_path):
                    return file_path
            
            # Extract RRUFF ID from database entry name, if present
            rruff_id = None
            if '__' in db_entry_name:
                parts = db_entry_name.split('__')
                for part in parts:
                    if part.startswith('R') and part[1:].isdigit():
                        rruff_id = part
                        break
            
            # If we found an RRUFF ID, search for files containing it
            if rruff_id:
                for filename in os.listdir(spectra_dir):
                    if rruff_id in filename:
                        return os.path.join(spectra_dir, filename)
            
            # Last resort: Try to match by searching for the prefix part
            if '__' in db_entry_name:
                prefix = db_entry_name.split('__')[0]
                for filename in os.listdir(spectra_dir):
                    if filename.startswith(prefix):
                        return os.path.join(spectra_dir, filename)
            
            return None
        
        # Update function for progress
        def update_progress(current, name, status, log_message=None, tag="info"):
            progress["value"] = current
            percentage = int((current / total) * 100) if total > 0 else 0
            status_var.set(f"{status} - {percentage}% complete ({current}/{total})")
            
            if log_message:
                log_text.insert(tk.END, log_message + "\n", tag)
                log_text.see(tk.END)
            
            progress_window.update_idletasks()
        
        # Function to extract mineral name from spectra file
        def extract_mineral_name_from_file(file_path):
            try:
                with open(file_path, 'r', errors='replace') as f:
                    # Read first 20 lines to look for metadata
                    for i, line in enumerate(f):
                        if i >= 20:  # Only check first 20 lines
                            break
                        
                        line = line.strip()
                        
                        # Check for NAMES field
                        if line.startswith('##NAMES=') or line.startswith('#NAMES='):
                            return line.split('=', 1)[1].strip()
                        
                        # Check for NAME field
                        if line.startswith('##NAME=') or line.startswith('#NAME='):
                            return line.split('=', 1)[1].strip()
                        
                        # Check for MINERAL field
                        if line.startswith('##MINERAL=') or line.startswith('#MINERAL='):
                            return line.split('=', 1)[1].strip()
                        
                        # Check for colon format
                        if ':' in line and line.startswith('#'):
                            key, value = line[1:].split(':', 1)
                            key = key.strip().upper()
                            if key in ['NAME', 'MINERAL', 'MINERAL NAME', 'NAMES']:
                                return value.strip()
                
                # If we've reached here, check if the filename itself contains the mineral name
                filename = os.path.basename(file_path)
                # Look for patterns like "Actinolite_R123456"
                match = re.match(r'([A-Za-z]+)[_-]', filename)
                if match:
                    return match.group(1)
                
                return None
            except Exception as e:
                update_progress(0, file_path, "Error", f"Error reading file {file_path}: {str(e)}", "error")
                return None
        
        # Process each database entry
        for i, (name, data) in enumerate(db_items):
            # Update progress display
            update_progress(i, name, f"Processing {name}")
            
            # Skip entries without metadata
            if 'metadata' not in data or not data['metadata']:
                data['metadata'] = {}  # Create metadata dict if it doesn't exist
            
            metadata = data['metadata']
            
            # Check if Hey Classification already exists
            if 'HEY CLASSIFICATION' in metadata and metadata['HEY CLASSIFICATION']:
                already_had += 1
                update_progress(i, name, f"Processing {name}", 
                              f"Skipped {name}: Already has Hey Classification '{metadata['HEY CLASSIFICATION']}'", "info")
                continue
            
            # Find the original spectra file
            spectra_file = find_original_file(name)
            if not spectra_file:
                file_not_found += 1
                update_progress(i, name, f"Processing {name}", 
                              f"Could not find original spectra file for {name}", "warning")
                continue
            
            # Extract mineral name from the file
            mineral_name = extract_mineral_name_from_file(spectra_file)
            if not mineral_name:
                update_progress(i, name, f"Processing {name}", 
                              f"Could not extract mineral name from file {os.path.basename(spectra_file)}", "warning")
                continue
            
            # Update the metadata with the extracted name
            metadata['NAME'] = mineral_name
            update_progress(i, name, f"Processing {name}", 
                          f"Extracted mineral name '{mineral_name}' from file {os.path.basename(spectra_file)}", "info")
            
            # Try to add Hey Classification using the mineral name
            hey_class = self.get_hey_classification(mineral_name)
            
            if hey_class:
                # Update the metadata with Hey Classification
                metadata['HEY CLASSIFICATION'] = hey_class
                
                # Also derive chemical family if Hey Classification is found
                if ' - ' in hey_class:
                    # Extract the first part as chemical family (before the hyphen)
                    family = hey_class.split(' - ')[0].strip()
                    metadata['CHEMICAL FAMILY'] = family
                    update_progress(i, name, f"Processing {name}", 
                                  f"Updated {name}: Added Hey Classification '{hey_class}' and Chemical Family '{family}'", "success")
                else:
                    update_progress(i, name, f"Processing {name}", 
                                  f"Updated {name}: Added Hey Classification '{hey_class}'", "success")
                                  
                updated += 1
            else:
                # Try with cleaned name
                cleaned_name = self._clean_mineral_name(mineral_name)
                if cleaned_name and cleaned_name != mineral_name:
                    hey_class = self.get_hey_classification(cleaned_name)
                    
                    if hey_class:
                        # Update the metadata with Hey Classification
                        metadata['HEY CLASSIFICATION'] = hey_class
                        
                        # Also derive chemical family
                        if ' - ' in hey_class:
                            family = hey_class.split(' - ')[0].strip()
                            metadata['CHEMICAL FAMILY'] = family
                            update_progress(i, name, f"Processing {name}", 
                                          f"Updated {name}: Added Hey Classification '{hey_class}' and Chemical Family '{family}' (using cleaned name)", "success")
                        else:
                            update_progress(i, name, f"Processing {name}", 
                                          f"Updated {name}: Added Hey Classification '{hey_class}' (using cleaned name)", "success")
                        
                        updated += 1
                        continue
                
                # Try with more aggressive cleaning
                very_clean_name = self.extract_base_mineral_name(mineral_name)
                if very_clean_name and very_clean_name != mineral_name and very_clean_name != cleaned_name:
                    hey_class = self.get_hey_classification(very_clean_name)
                    
                    if hey_class:
                        # Update the metadata with Hey Classification
                        metadata['HEY CLASSIFICATION'] = hey_class
                        
                        # Also derive chemical family
                        if ' - ' in hey_class:
                            family = hey_class.split(' - ')[0].strip()
                            metadata['CHEMICAL FAMILY'] = family
                            update_progress(i, name, f"Processing {name}", 
                                          f"Updated {name}: Added Hey Classification '{hey_class}' and Chemical Family '{family}' (using aggressively cleaned name)", "success")
                        else:
                            update_progress(i, name, f"Processing {name}", 
                                          f"Updated {name}: Added Hey Classification '{hey_class}' (using aggressively cleaned name)", "success")
                        
                        updated += 1
                        continue
                
                # If we get here, we couldn't find a match
                not_found += 1
                update_progress(i, name, f"Processing {name}", 
                              f"Could not find Hey Classification for '{mineral_name}'", "warning")
        
        # Final progress update
        update_progress(total, "", "Complete", 
                      f"Update complete! Updated: {updated}, Already had: {already_had}, Not found: {not_found}, Files not found: {file_not_found}", "info")
        
        # Save the database
        saved = self.save_database()
        if saved:
            log_text.insert(tk.END, f"Database saved successfully to {self.db_path}\n", "success")
        else:
            log_text.insert(tk.END, "Warning: Could not save database\n", "error")
        log_text.see(tk.END)
        
        # Add close button
        ttk.Button(progress_window, text="Close", command=progress_window.destroy).pack(pady=10)
        
        # Update main GUI database statistics
        if hasattr(self, 'update_database_stats'):
            self.update_database_stats()
        
        # Update metadata filter options if the method exists
        if hasattr(self, 'update_metadata_filter_options'):
            self.update_metadata_filter_options()
        
        # Make progress window modal
        progress_window.transient(self.root)
        progress_window.grab_set()
        self.root.wait_window(progress_window)

    
    
    
    
    def get_hey_classification(self, mineral_name):
        """
        Get Hey Classification for a given mineral name.
        Uses advanced matching techniques.

        Parameters:
        -----------
        mineral_name : str
            Name of the mineral to look up.

        Returns:
        --------
        str or None
            Hey Classification name if found, None otherwise.
        """
        if not mineral_name or not isinstance(mineral_name, str) or not self.hey_classification:
            return None

        # Print debug info
        print(f"Looking up Hey Classification for: '{mineral_name}'")
        
        # Simple exact match
        if mineral_name in self.hey_classification:
            metadata = self.hey_classification[mineral_name]
            if isinstance(metadata, dict) and 'HEY CLASSIFICATION' in metadata:
                result = metadata['HEY CLASSIFICATION']
                print(f"Found exact match: {result}")
                return result
            elif isinstance(metadata, str):  # Handle old format for backward compatibility
                print(f"Found exact match (old format): {metadata}")
                return metadata

        # Try advanced matching
        matched_name, matched_metadata = self.match_mineral_name(mineral_name)
        if matched_metadata:
            if isinstance(matched_metadata, dict) and 'HEY CLASSIFICATION' in matched_metadata:
                classification = matched_metadata['HEY CLASSIFICATION']
                print(f"Found match via matching algorithm: {classification} (matched with '{matched_name}')")
                return classification
            elif isinstance(matched_metadata, str):  # Handle old format for backward compatibility
                print(f"Found match via matching algorithm (old format): {matched_metadata} (matched with '{matched_name}')")
                return matched_metadata

        print(f"No Hey Classification found for: '{mineral_name}'")
        return None

    
    
    def import_spectrum(self, filepath):
        """
        Import Raman spectrum from file with enhanced metadata extraction.
        Special focus on properly identifying chemical family and mineral name fields
        to ensure Hey Classification is correctly assigned.
        
        Parameters:
        -----------
        filepath : str
            Path to the file containing Raman spectrum data.
                
        Returns:
        --------
        tuple
            Wavenumbers and intensity values.
        """
        try:
            # Read file content as text first to check for header information
            metadata = {}
            data_lines = []
            
            # Define mappings for common field name variations (case insensitive)
            field_mappings = {
                # Map various name fields to standard 'NAME' key
                'NAME': ['NAME', 'MINERAL', 'MINERAL NAME', 'COMPOUND', 'SAMPLE', 'MATERIAL'],
                # Map various chemical family fields to standard 'CHEMICAL FAMILY' key
                'CHEMICAL FAMILY': ['CHEMICAL FAMILY', 'FAMILY', 'CHEMICAL CLASS', 'CLASSIFICATION', 
                                   'MINERAL FAMILY', 'MINERAL CLASS', 'MINERAL TYPE', 'CHEMISTRY'],
                # Map various ID fields
                'RRUFFID': ['RRUFFID', 'RRUFF ID', 'RRUFF IDs', 'ID', 'SAMPLE ID', 'REFERENCE ID'],
                # Map chemistry fields
                'IDEAL CHEMISTRY': ['IDEAL CHEMISTRY', 'CHEMISTRY', 'FORMULA', 'CHEMICAL FORMULA'],
                # Map locality fields
                'LOCALITY': ['LOCALITY', 'LOCATION', 'SOURCE', 'ORIGIN'],
                # Map description fields
                'DESCRIPTION': ['DESCRIPTION', 'DESC', 'NOTES', 'COMMENT', 'COMMENTS']
            }
            
            # Reverse mapping for quick lookup
            field_lookup = {}
            for standard_key, variations in field_mappings.items():
                for variant in variations:
                    field_lookup[variant.upper()] = standard_key
            
            # Process file headers and extract data lines
            print(f"Importing spectrum from {filepath}")
            with open(filepath, 'r', errors='replace') as f:
                line_index = 0
                for line in f:
                    line_index += 1
                    stripped_line = line.strip()
                    
                    # Check for metadata in various formats
                    if stripped_line.startswith('#'):
                        # Process as metadata line starting with #
                        clean_line = stripped_line[1:].strip()
                        self._process_metadata_line(clean_line, metadata, field_lookup)
                        
                    elif line_index <= 20 and (':' in stripped_line or '=' in stripped_line):
                        # Check early lines for metadata even without # prefix
                        if not any(c.isdigit() for c in stripped_line.split(':', 1)[0] if ':' in stripped_line):
                            self._process_metadata_line(stripped_line, metadata, field_lookup)
                        else:
                            # Likely data with numeric values, not metadata
                            data_lines.append(line)
                    else:
                        # Not metadata, add to data lines
                        data_lines.append(line)
            
            print(f"Extracted metadata fields: {list(metadata.keys())}")
            
            # Process special cases and ensure critical fields are properly normalized
            self._normalize_metadata_fields(metadata)
            
            # Try to add Hey Classification based on mineral name
            if 'NAME' in metadata and metadata['NAME']:
                mineral_name = metadata['NAME']
                print(f"Looking up Hey Classification for: {mineral_name}")
                
                # Get Hey Classification and other metadata
                matched_name, matched_metadata = self.match_mineral_name(mineral_name)
                if matched_metadata:
                    print(f"Found Hey Classification data for: {mineral_name}")
                    
                    # Add all metadata fields we found
                    if isinstance(matched_metadata, dict):
                        for key, value in matched_metadata.items():
                            metadata[key] = value
                        print(f"Added metadata fields: {list(matched_metadata.keys())}")
                    elif isinstance(matched_metadata, str):  # Support old format
                        metadata['HEY CLASSIFICATION'] = matched_metadata
                        print(f"Added Hey Classification: {matched_metadata}")
                else:
                    print(f"No Hey Classification found for: {mineral_name}")
                    
                    # Try additional name cleanup and retry
                    cleaned_name = self._clean_mineral_name(mineral_name)
                    if cleaned_name != mineral_name:
                        print(f"Trying cleaned name: {cleaned_name}")
                        matched_name, matched_metadata = self.match_mineral_name(cleaned_name)
                        if matched_metadata:
                            # Add all metadata fields we found
                            if isinstance(matched_metadata, dict):
                                for key, value in matched_metadata.items():
                                    metadata[key] = value
                                print(f"Added metadata fields using cleaned name: {list(matched_metadata.keys())}")
                            elif isinstance(matched_metadata, str):  # Support old format
                                metadata['HEY CLASSIFICATION'] = matched_metadata
                                print(f"Found Hey Classification with cleaned name: {matched_metadata}")
            
            # Save metadata for later use
            self.metadata = metadata
            print(f"Final metadata: {metadata}")
            
            # Combine data lines for parsing
            data_content = ''.join(data_lines)
            
            # If no data lines were found, raise error
            if not data_content.strip():
                raise ImportError("No data found in file after processing metadata")
            
            # Write data lines to a temporary file for pandas to parse
            temp_file = filepath + ".temp"
            with open(temp_file, 'w') as f:
                f.write(data_content)
            
            # Guess delimiter based on content
            possible_delimiters = [',', '\t', ';', ' ']
            delimiter_counts = {delim: data_content.count(delim) for delim in possible_delimiters}
            likely_delimiter = max(delimiter_counts, key=delimiter_counts.get)
            
            # Check if file might have headers
            first_line = data_lines[0] if data_lines else ""
            has_header = not any(c.isdigit() for c in first_line.split(likely_delimiter)[0])
            
            # Special handling for line scan splitter format
            # Check if first line looks like "Wavenumber (cm-1)\tIntensity" pattern
            if (has_header and likely_delimiter == '\t' and 
                len(data_lines) > 0 and 
                any(term in first_line.lower() for term in ['wavenumber', 'raman', 'cm-1', 'intensity'])):
                print("Detected line scan splitter format")
                # Force tab delimiter with header for this format
                parsing_approaches = [
                    lambda: pd.read_csv(temp_file, sep='\t', header=0),
                    lambda: pd.read_csv(temp_file, sep='\t', header=None),
                    lambda: pd.read_csv(temp_file, sep=likely_delimiter, header=0 if has_header else None),
                ]
            else:
                # Try different parsing approaches
                parsing_approaches = [
                    # With header detection
                    lambda: pd.read_csv(temp_file, sep=likely_delimiter, header=0 if has_header else None),
                    # Force comma delimiter with header
                    lambda: pd.read_csv(temp_file, header=0),
                    # Force comma delimiter without header
                    lambda: pd.read_csv(temp_file, header=None),
                    # Force tab delimiter
                    lambda: pd.read_csv(temp_file, sep='\t', header=None),
                    # Force whitespace delimiter
                    lambda: pd.read_csv(temp_file, delim_whitespace=True, header=None),
                    # Try semicolon delimiter
                    lambda: pd.read_csv(temp_file, sep=';', header=None),
                    # Last resort - custom parser
                    lambda: pd.DataFrame(np.loadtxt(temp_file, ndmin=2))
                ]

            data = None
            # Try each approach until one works
            for i, parse_approach in enumerate(parsing_approaches):
                try:
                    data = parse_approach()
                    if not data.empty and data.shape[1] >= 2:
                        print(f"Successfully parsed with approach {i+1}")
                        break
                except Exception as e:
                    print(f"Parsing approach {i+1} failed: {e}")
                    continue
            
            # Clean up temporary file
            try:
                os.remove(temp_file)
            except:
                pass
            
            if data is None or data.empty:
                raise ImportError("Could not parse file format")
            
            # Check if we have enough data
            if data.shape[0] < 2:
                raise ImportError("Not enough data points in file")
            
            if data.shape[1] < 2:
                raise ImportError("Need at least two columns (wavenumber and intensity)")
            
            # Extract wavenumbers and intensities
            # First, check if all columns can be converted to numeric
            numeric_cols = []
            for i in range(data.shape[1]):
                try:
                    # Try to convert column to numeric, ignoring errors
                    numeric_data = pd.to_numeric(data.iloc[:, i], errors='coerce')
                    # Check if most values are numeric (not NaN)
                    if not numeric_data.isna().all() and (numeric_data.isna().sum() / len(numeric_data)) < 0.5:
                        numeric_cols.append(i)
                        print(f"Column {i} ({data.columns[i] if i < len(data.columns) else 'Unnamed'}) detected as numeric")
                except Exception as e:
                    print(f"Column {i} failed numeric conversion: {e}")
                    pass
            
            print(f"Found {len(numeric_cols)} numeric columns: {numeric_cols}")
            
            if len(numeric_cols) < 2:
                print(f"Data shape: {data.shape}")
                print(f"Columns: {data.columns.tolist()}")
                print(f"First few rows:\n{data.head()}")
                raise ImportError("Need at least two numeric columns")
            
            # Usually the first numeric column is wavenumbers
            wavenumber_col = numeric_cols[0]
            
            # For intensities, check for column names if headers exist
            intensity_col = numeric_cols[1]  # Default to second numeric column
            for i in numeric_cols[1:]:
                col_name = str(data.columns[i]).lower()
                if any(term in col_name for term in ['intens', 'count', 'signal', 'raman', 'cps']):
                    intensity_col = i
                    break
            
            # Extract data as numpy arrays
            wavenumbers = pd.to_numeric(data.iloc[:, wavenumber_col], errors='coerce').values
            intensities = pd.to_numeric(data.iloc[:, intensity_col], errors='coerce').values
            
            # Remove any NaN values (which would come from header rows or invalid data)
            valid_indices = ~(np.isnan(wavenumbers) | np.isnan(intensities))
            wavenumbers = wavenumbers[valid_indices]
            intensities = intensities[valid_indices]
            
            # Check for invalid values after cleaning
            if len(wavenumbers) == 0 or len(intensities) == 0:
                raise ImportError("No valid numeric data found after processing")
                
            if np.isnan(wavenumbers).any() or np.isnan(intensities).any():
                raise ImportError("Data contains NaN values after processing")
            
            # Store the current spectrum
            self.current_wavenumbers = wavenumbers
            self.current_spectra = intensities
            self.processed_spectra = None
            self.peaks = None
            self.background = None
            
            return wavenumbers, intensities
            
        except Exception as e:
            raise ImportError(f"Error importing spectrum: {str(e)}")

    def _process_metadata_line(self, line, metadata, field_lookup):
        """
        Process a single metadata line and extract key-value pairs.
        Strips leading '#' from keys.
        """
        # Try to parse as key-value pair with colon
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.lstrip('#').strip().upper()
            value = value.strip()
            # Map to standard key if known variant
            if key in field_lookup:
                standard_key = field_lookup[key]
                metadata[standard_key] = value
            else:
                metadata[key] = value
        elif '=' in line:
            key, value = line.split('=', 1)
            key = key.lstrip('#').strip().upper()
            value = value.strip()
            if key in field_lookup:
                standard_key = field_lookup[key]
                metadata[standard_key] = value
            else:
                metadata[key] = value
        elif line.strip():
            note_key = f"NOTE_{len([k for k in metadata.keys() if k.startswith('NOTE_')])}"
            metadata[note_key] = line.strip()

    def _normalize_metadata_fields(self, metadata):
        """
        Normalize and clean up metadata fields.
        
        Parameters:
        -----------
        metadata : dict
            Dictionary of metadata to normalize
        """
        # Ensure NAME field is properly extracted from various possibilities
        if 'NAME' not in metadata or not metadata['NAME']:
            # Try to construct name from other fields
            if 'RRUFFID' in metadata and metadata['RRUFFID']:
                # Extract mineral name from RRUFF ID (e.g., "R050031" -> extract from database)
                rruff_id = metadata['RRUFFID']
                print(f"No explicit NAME field, trying to extract from RRUFFID: {rruff_id}")
                # Look up in Hey classification data if possible
                for mineral_name, _ in self.hey_classification.items():
                    if rruff_id.lower() in mineral_name.lower():
                        metadata['NAME'] = mineral_name
                        print(f"Extracted name from RRUFFID: {mineral_name}")
                        break
            
            # Check if chemical family exists and NAME doesn't
            if ('NAME' not in metadata or not metadata['NAME']) and 'CHEMICAL FAMILY' in metadata:
                # Try to use first word of chemical family as a fallback name
                family = metadata['CHEMICAL FAMILY']
                if family:
                    potential_name = family.split()[0]
                    metadata['NAME'] = potential_name
                    print(f"Using first word of CHEMICAL FAMILY as NAME: {potential_name}")
        
        # Check for CHEMICAL FAMILY or derive it from NAME if possible
        if 'CHEMICAL FAMILY' not in metadata and 'NAME' in metadata:
            name = metadata['NAME']
            # Try to get family by reverse lookup from Hey Classification
            if name:
                for mineral, classification in self.hey_classification.items():
                    if name.lower() == mineral.lower():
                        # Extract family from classification (usually first part before hyphen)
                        if classification and ' - ' in classification:
                            family = classification.split(' - ')[0].strip()
                            metadata['CHEMICAL FAMILY'] = family
                            print(f"Derived CHEMICAL FAMILY from Hey Classification: {family}")
                            break

    def _clean_mineral_name(self, name):
        """
        Clean mineral name for better matching with Hey Classification.
        
        Parameters:
        -----------
        name : str
            Mineral name to clean
        
        Returns:
        --------
        str
            Cleaned mineral name
        """
        if not name or not isinstance(name, str):
            return ""
            
        # Convert to lowercase for consistent processing
        cleaned = name.lower().strip()
        
        # Remove common suffixes
        common_suffixes = ['-type', ' var.', ' var ', ' group', ' series', ' family', 
                           ' like', ' structure', ' form', '-rich', '-poor']
        for suffix in common_suffixes:
            if cleaned.endswith(suffix):
                cleaned = cleaned[:-len(suffix)].strip()
                break
        
        # Remove common prefixes if they're not the entire name
        common_prefixes = ['hydro', 'meta', 'para', 'proto', 'pseudo', 'ortho', 'clino']
        for prefix in common_prefixes:
            if cleaned.startswith(prefix) and len(cleaned) > len(prefix) + 1:
                cleaned = cleaned[len(prefix):].strip()
                break
        
        # Remove special characters and extra spaces
        cleaned = ''.join(c for c in cleaned if c.isalnum() or c.isspace())
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        
        return cleaned

    # def load_hey_classification(self, csv_path):
    #     """
    #     Load Hey Classification data from CSV file with improved logging.

    #     Parameters:
    #     -----------
    #     csv_path : str
    #         Path to the CSV file containing Hey Classification data.

    #     Returns:
    #     --------
    #     dict
    #         Dictionary mapping mineral names to their Hey Classifications.
    #     """
    #     try:
    #         print(f"Loading Hey Classification data from: {csv_path}")
            
    #         # Check if file exists
    #         if not os.path.exists(csv_path):
    #             print(f"ERROR: Hey Classification file not found at {csv_path}")
    #             return {}
                
    #         # Read the CSV file
    #         df = pd.read_csv(csv_path)
    #         print(f"Successfully read CSV with {len(df)} rows")
            
    #         # Check required columns
    #         required_columns = ['NAME', 'HEY CLASSIFICATION']
    #         for col in required_columns:
    #             if col not in df.columns:
    #                 print(f"ERROR: Required column '{col}' not found in Hey Classification CSV")
    #                 actual_columns = ', '.join(df.columns)
    #                 print(f"Available columns: {actual_columns}")
    #                 return {}
            
    #         # Create dictionary mapping mineral names to classifications
    #         hey_classification = {}
    #         for _, row in df.iterrows():
    #             mineral_name = row['NAME']
    #             classification = row['HEY CLASSIFICATION']
    #             if pd.notna(mineral_name) and pd.notna(classification):
    #                 hey_classification[mineral_name] = classification
            
    #         print(f"Loaded {len(hey_classification)} Hey Classification entries")
            
    #         # Store the classification data
    #         self.hey_classification = hey_classification
    #         return hey_classification
            
    #     except Exception as e:
    #         print(f"ERROR loading Hey Classification data: {str(e)}")
    #         return {}

    def load_hey_classification(self, csv_path):
        """
        Load Hey Classification data from CSV file with correct column mapping.

        Parameters:
        -----------
        csv_path : str
            Path to the CSV file containing Hey Classification data.

        Returns:
        --------
        dict
            Dictionary mapping mineral names to their Hey Classifications and additional metadata.
        """
        try:
            print(f"Loading Hey Classification data from: {csv_path}")
            
            # Check if file exists
            if not os.path.exists(csv_path):
                print(f"ERROR: Hey Classification file not found at {csv_path}")
                return {}
                
            # Read the CSV file
            df = pd.read_csv(csv_path)
            print(f"Successfully read CSV with {len(df)} rows")
            
            # Print column names to help with debugging
            print(f"CSV columns: {list(df.columns)}")
            
            # Check for required columns (using the actual column names from the CSV)
            mineral_name_col = "Mineral Name"
            classification_col = "Hey Classification Name"
            
            required_columns = [mineral_name_col, classification_col]
            for col in required_columns:
                if col not in df.columns:
                    print(f"ERROR: Required column '{col}' not found in Hey Classification CSV")
                    # Try to guess column names based on partial matches
                    possible_columns = [c for c in df.columns if col.lower() in c.lower()]
                    if possible_columns:
                        print(f"Possible matches: {possible_columns}")
                    return {}
            
            # Additional metadata fields to extract
            additional_fields = [
                "IMA Number",
                "RRUFF ID",
                "Structural Groupname",
                "Crystal System",
                "Space Groups",
                "Oldest Known Age (Ma)",
                "Paragenetic Modes",
                "Chemistry Elements"
            ]
            
            # Check which additional fields are actually present in the CSV
            available_fields = [field for field in additional_fields if field in df.columns]
            if len(available_fields) < len(additional_fields):
                missing_fields = set(additional_fields) - set(available_fields)
                print(f"Note: Some requested metadata fields are not in the CSV: {missing_fields}")
            
            # Create dictionary mapping mineral names to classifications and metadata
            hey_classification = {}
            for _, row in df.iterrows():
                mineral_name = row[mineral_name_col]
                classification = row[classification_col]
                
                if pd.notna(mineral_name) and pd.notna(classification) and classification:
                    # Create metadata dictionary for this mineral
                    metadata = {"HEY CLASSIFICATION": classification}
                    
                    # Add additional metadata fields if available
                    for field in available_fields:
                        if field in df.columns and pd.notna(row[field]):
                            # Create a normalized field name for consistency
                            norm_field = field.upper()
                            metadata[norm_field] = row[field]
                    
                    # Store both the original name and a cleaned version for better matching
                    hey_classification[mineral_name] = metadata
                    
                    # Also add a cleaned version of the name for more flexible matching
                    cleaned_name = self._clean_mineral_name(mineral_name)
                    if cleaned_name != mineral_name:
                        hey_classification[cleaned_name] = metadata
            
            print(f"Loaded {len(hey_classification)} Hey Classification entries with additional metadata")
            
            # Store the classification data
            self.hey_classification = hey_classification
            return hey_classification
            
        except Exception as e:
            print(f"ERROR loading Hey Classification data: {str(e)}")
            import traceback
            traceback.print_exc()
            return {}    


    


    def baseline_als(self, y, lam=1e5, p=0.01, niter=10):
        """
        Asymmetric Least Squares Smoothing for baseline correction.
        
        Parameters:
        -----------
        y : array-like
            Input spectrum.
        lam : float
            Smoothness parameter.
        p : float
            Asymmetry parameter.
        niter : int
            Number of iterations.
            
        Returns:
        --------
        array-like
            Estimated baseline.
        """
        L = len(y)
        D = csc_matrix(np.diff(np.eye(L), 2))
        w = np.ones(L)
        
        for i in range(niter):
            W = csc_matrix((w, (np.arange(L), np.arange(L))))
            Z = W + lam * D.dot(D.transpose())
            z = spsolve(Z, w * y)
            w = p * (y > z) + (1 - p) * (y <= z)
        
        return z
    
    def subtract_background(self, lam=1e5, p=0.01, niter=10):
        """
        Subtract the background from the current spectrum.
        
        Parameters:
        -----------
        lam : float
            Smoothness parameter for baseline correction.
        p : float
            Asymmetry parameter for baseline correction.
        niter : int
            Number of iterations for baseline correction.
            
        Returns:
        --------
        tuple
            Background-subtracted spectrum and estimated background.
        """
        if self.current_spectra is None:
            raise ValueError("No spectrum loaded. Import a spectrum first.")
        
        # Compute the baseline
        baseline = self.baseline_als(self.current_spectra, lam, p, niter)
        
        # Subtract baseline from spectrum
        corrected_spectrum = self.current_spectra - baseline
        
        # Set negative values to zero (optional)
        corrected_spectrum[corrected_spectrum < 0] = 0
        
        # Store the processed spectrum and background
        self.processed_spectra = corrected_spectrum
        self.background = baseline
        
        return corrected_spectrum, baseline
    
    def find_spectrum_peaks(self, height=None, threshold=None, distance=None, prominence=None, width=None):
        """
        Find peaks in the current spectrum using scipy's find_peaks.
        
        Parameters:
        -----------
        height : float or None
            Required height of peaks.
        threshold : float or None
            Required threshold of peaks.
        distance : float or None
            Required minimal horizontal distance between peaks.
        prominence : float or None
            Required prominence of peaks.
        width : float or None
            Required width of peaks.
            
        Returns:
        --------
        dict
            Dictionary with peak indices, heights, and properties.
        """
        if self.processed_spectra is None:
            if self.current_spectra is None:
                raise ValueError("No spectrum loaded. Import a spectrum first.")
            spectrum = self.current_spectra
        else:
            spectrum = self.processed_spectra
        
        # Default parameters if none provided
        if height is None:
            height = 0.05 * np.max(spectrum)
        if distance is None:
            distance = len(spectrum) // 100  # 1% of spectrum length
        if prominence is None:
            prominence = 0.02 * np.max(spectrum)
        
        # Find peaks
        peak_indices, properties = find_peaks(
            spectrum, 
            height=height,
            threshold=threshold,
            distance=distance,
            prominence=prominence,
            width=width
        )
        
        # Get peak wavenumbers and heights
        peak_wavenumbers = self.current_wavenumbers[peak_indices]
        peak_heights = spectrum[peak_indices]
        
        # Store peaks information
        self.peaks = {
            'indices': peak_indices,
            'wavenumbers': peak_wavenumbers,
            'heights': peak_heights,
            'properties': properties
        }
        
        return self.peaks
    
    
    def match_mineral_name(self, mineral_name, threshold=0.8):
        """
        Advanced matching of mineral names with Hey Classification data.
        Uses both exact matching and fuzzy matching techniques.

        Parameters:
        -----------
        mineral_name : str
            Name of the mineral to match.
        threshold : float
            Minimum similarity score to consider a match (0.0-1.0).

        Returns:
        --------
        tuple
            (best_match_name, metadata_dict) or (None, None) if no match found.
            metadata_dict contains 'HEY CLASSIFICATION' and other available metadata.
        """
        if not mineral_name or not isinstance(mineral_name, str) or not self.hey_classification:
            return None, None

        # Clean the input name
        name_to_match = self._clean_mineral_name(mineral_name)
        if not name_to_match:
            return None, None

        # 1. Try exact match first
        if mineral_name in self.hey_classification:
            return mineral_name, self.hey_classification[mineral_name]
            
        # 2. Try with cleaned name
        if name_to_match in self.hey_classification:
            return name_to_match, self.hey_classification[name_to_match]
        
        # 3. Check if the name is contained within any key in the dictionary
        for db_name, metadata in self.hey_classification.items():
            if name_to_match in db_name.lower():
                return db_name, metadata
        
        # 4. Try fuzzy matching as a last resort
        try:
            # Import difflib for fuzzy matching
            from difflib import SequenceMatcher

            best_match = None
            best_score = 0
            best_metadata = None

            for db_name, metadata in self.hey_classification.items():
                # Calculate similarity ratio
                ratio = SequenceMatcher(None, name_to_match, db_name.lower()).ratio()

                # Check if this is the best match so far
                if ratio > best_score and ratio >= threshold:
                    best_score = ratio
                    best_match = db_name
                    best_metadata = metadata

            if best_match:
                return best_match, best_metadata

        except ImportError:
            print("Warning: difflib module not available for fuzzy matching")

        # No match found
        return None, None

    
    
    def add_to_database(self, name, metadata=None):
        """
        Add current spectrum to the database.
        
        Parameters:
        -----------
        name : str
            Name of the spectrum to add.
        metadata : dict, optional
            Metadata dictionary for the spectrum. If None, use current metadata.
        
        Returns:
        --------
        bool
            True if successful, False otherwise.
        """
        if self.current_spectra is None or self.current_wavenumbers is None:
            return False
        
        # Use passed metadata or current metadata
        meta = metadata if metadata is not None else self.metadata
        
        # Create entry
        entry = {
            'wavenumbers': self.current_wavenumbers,
            'intensities': self.current_spectra,
            'metadata': meta
        }
        
        # Add processed spectrum if available
        if self.processed_spectra is not None:
            entry['processed'] = self.processed_spectra
        
        # Add background if available
        if self.background is not None:
            entry['background'] = self.background
        
        # Add peak data if available
        if self.peaks is not None:
            entry['peaks'] = self.peaks
            
        # Add peak fitting data if available
        if hasattr(self, 'fitted_peaks') and self.fitted_peaks is not None:
            entry['fitted_peaks'] = self.fitted_peaks
            
        if hasattr(self, 'peak_fit_result') and self.peak_fit_result is not None:
            # Store peak fitting result (excluding potentially large arrays)
            fit_result_to_store = {
                'model': self.peak_fit_result.get('model', ''),
                'r_squared': self.peak_fit_result.get('r_squared', 0),
                'parameters': self.peak_fit_result.get('parameters', [])
            }
            entry['peak_fit_result'] = fit_result_to_store
        
        # Add to database
        self.database[name] = entry
        
        # Save database
        self.save_database()
        
        return True
    
    def remove_from_database(self, name):
        """
        Remove a spectrum from the database.
        
        Parameters:
        -----------
        name : str
            Name/identifier of the spectrum to remove.
            
        Returns:
        --------
        bool
            True if successful, False if spectrum not found.
        """
        if name in self.database:
            del self.database[name]
            self.save_database()
            return True
        return False
    
    def save_database(self):
        """
        Save the database to disk.
        
        Returns:
        --------
        bool
            True if successful.
        """
        try:
            with open(self.db_path, 'wb') as f:
                pickle.dump(self.database, f)
            return True
        except Exception as e:
            print(f"Error saving database: {str(e)}")
            return False
    
    def load_database(self):
        """
        Load the database from disk.
        
        Returns:
        --------
        dict
            The loaded database.
        """
        try:
            if os.path.exists(self.db_path):
                with open(self.db_path, 'rb') as f:
                    self.database = pickle.load(f)
                print(f"Successfully loaded database with {len(self.database)} entries.")
            else:
                print("No existing database found. Creating a new one.")
                self.database = {}
            return self.database
        except Exception as e:
            print(f"Warning: Could not load database: {str(e)}")
            self.database = {}
            return self.database
    
    def search_match(self, n_matches=5, correlation_threshold=0.7):
        """
        Search the database for matches to the current spectrum.
        
        Parameters:
        -----------
        n_matches : int
            Number of top matches to return.
        correlation_threshold : float
            Minimum correlation coefficient to consider a match.
            
        Returns:
        --------
        list
            List of tuples (name, score) of matching spectra.
        """
        # Store the search parameters for reporting
        self.last_search_algorithm = "Combined (Correlation + MSE + Peak Matching)"
        self.last_search_threshold = correlation_threshold
        
        if self.processed_spectra is None:
            if self.current_spectra is None:
                raise ValueError("No spectrum loaded. Import a spectrum first.")
            query_spectrum = self.current_spectra
        else:
            query_spectrum = self.processed_spectra
        
        if not self.database:
            raise ValueError("Database is empty. Add spectra to the database first.")
        
        matches = []
        
        # Normalize the query spectrum (0-1 range)
        query_min = np.min(query_spectrum)
        query_max = np.max(query_spectrum)
        if query_max > query_min:
            query_norm = (query_spectrum - query_min) / (query_max - query_min)
        else:
            query_norm = query_spectrum
        
        for name, data in self.database.items():
            # Extract database spectrum
            db_spectrum = data['intensities']
            db_wavenumbers = data['wavenumbers']
            
            # Check if wavenumbers are compatible
            if not np.array_equal(self.current_wavenumbers, db_wavenumbers):
                # Interpolate database spectrum to match query wavenumbers
                db_spectrum = np.interp(
                    self.current_wavenumbers, 
                    db_wavenumbers, 
                    db_spectrum
                )
            
            # Normalize database spectrum (0-1 range)
            db_min = np.min(db_spectrum)
            db_max = np.max(db_spectrum)
            if db_max > db_min:
                db_norm = (db_spectrum - db_min) / (db_max - db_min)
            else:
                db_norm = db_spectrum
            
            # Calculate matching metrics
            # 1. Correlation coefficient
            corr_coef = np.corrcoef(query_norm, db_norm)[0, 1]
            if np.isnan(corr_coef):  # Handle NaN values
                corr_coef = 0
                
            # 2. Mean squared error
            mse = np.mean((query_norm - db_norm) ** 2)
            mse_score = 1 / (1 + 10 * mse)  # Convert MSE to similarity score (0-1)
            
            # 3. Peak matching (if peaks are available)
            peak_score = 0
            if self.peaks is not None and 'peaks' in data and data['peaks'] is not None:
                query_peaks = set(np.round(self.peaks['wavenumbers']).astype(int))
                db_peaks = set(np.round(data['peaks']['wavenumbers']).astype(int))
                
                # Calculate Jaccard similarity for peaks
                if query_peaks or db_peaks:  # Avoid division by zero
                    intersection = len(query_peaks.intersection(db_peaks))
                    union = len(query_peaks.union(db_peaks))
                    peak_score = intersection / union
            
            # Combined score - weighted average of the metrics
            # 60% correlation, 20% MSE, 20% peak matching
            combined_score = 0.6 * corr_coef + 0.2 * mse_score + 0.2 * peak_score
            
            if combined_score >= correlation_threshold:
                matches.append((name, combined_score))
        
        # Sort matches by combined score (descending)
        matches.sort(key=lambda x: x[1], reverse=True)
        
        # Return top n matches
        return matches[:n_matches]
    
    def plot_spectrum(self, include_background=False, include_peaks=False, figsize=(10, 6)):
        """
        Plot the current spectrum with optional background and peaks.
        
        Parameters:
        -----------
        include_background : bool
            If True, plot the estimated background.
        include_peaks : bool
            If True, mark the detected peaks.
        figsize : tuple
            Figure size (width, height) in inches.
            
        Returns:
        --------
        tuple
            (fig, ax) - Matplotlib figure and axes objects.
        """
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot raw spectrum
        if self.current_spectra is not None:
            ax.plot(self.current_wavenumbers, self.current_spectra, 'b-', label='Raw Spectrum')
        
        # Plot background-subtracted spectrum
        if self.processed_spectra is not None:
            ax.plot(self.current_wavenumbers, self.processed_spectra, 'g-', label='Processed Spectrum')
        
        # Plot background
        if include_background and self.background is not None:
            ax.plot(self.current_wavenumbers, self.background, 'r--', label='Background')
        
        # Mark peaks
        if include_peaks and self.peaks is not None:
            ax.plot(self.peaks['wavenumbers'], self.peaks['heights'], 'ro', label='Peaks')
            
            # Annotate peak positions
            for i, (wn, height) in enumerate(zip(self.peaks['wavenumbers'], self.peaks['heights'])):
                ax.annotate(
                    f"{wn:.1f}",
                    xy=(wn, height),
                    xytext=(0, 5),
                    textcoords='offset points',
                    ha='center',
                    fontsize=8
                )
        
        # Set labels and title
        ax.set_xlabel('Wavenumber (cm⁻¹)')
        ax.set_ylabel('Intensity (a.u.)')
        ax.set_title('Raman Spectrum Analysis')
        ax.legend()
        
        return fig, ax
        
    def save_spectrum(self, filepath):
        """
        Save the current spectrum to a file with metadata in the header.
        
        Parameters:
        -----------
        filepath : str
            Path to save the spectrum file.
            
        Returns:
        --------
        bool
            True if successful, False otherwise.
        """
        try:
            if self.current_spectra is None or self.current_wavenumbers is None:
                return False
                
            # Determine which spectrum to save (processed if available, otherwise raw)
            spectra_to_save = self.processed_spectra if self.processed_spectra is not None else self.current_spectra
            
            # Get file extension to determine format
            _, ext = os.path.splitext(filepath)
            ext = ext.lower()
            
            if ext == '.csv':
                # CSV format with metadata in header as comments
                with open(filepath, 'w', newline='') as f:
                    # Write metadata as comments
                    if hasattr(self, 'metadata') and self.metadata:
                        f.write("# === METADATA ===\n")
                        for key, value in self.metadata.items():
                            f.write(f"# {key}: {value}\n")
                        f.write("# =================\n")
                    
                    # Add peak information if available
                    if hasattr(self, 'peaks') and self.peaks is not None:
                        f.write("# === PEAKS ===\n")
                        f.write(f"# Number of peaks: {len(self.peaks['wavenumbers'])}\n")
                        for i, (pos, height) in enumerate(zip(self.peaks['wavenumbers'], self.peaks['heights'])):
                            f.write(f"# Peak {i+1}: {pos:.2f} cm⁻¹ (height: {height:.2f})\n")
                        f.write("# =================\n")
                    
                    # Add peak fitting results if available
                    if hasattr(self, 'peak_fit_result') and self.peak_fit_result is not None:
                        f.write("# === PEAK FIT ===\n")
                        f.write(f"# Model: {self.peak_fit_result.get('model', 'Unknown')}\n")
                        f.write(f"# R-squared: {self.peak_fit_result.get('r_squared', 0):.4f}\n")
                        f.write("# =================\n")
                    
                    # Write column headers
                    f.write("Wavenumber (cm⁻¹),Intensity (a.u.)\n")
                    
                    # Write data
                    for wn, intensity in zip(self.current_wavenumbers, spectra_to_save):
                        f.write(f"{wn:.4f},{intensity:.6f}\n")
            
            elif ext == '.txt':
                # Text format with metadata in header
                with open(filepath, 'w') as f:
                    # Write metadata as comments
                    if hasattr(self, 'metadata') and self.metadata:
                        f.write("### METADATA ###\n")
                        for key, value in self.metadata.items():
                            f.write(f"{key}: {value}\n")
                        f.write("###############\n\n")
                    
                    # Add peak information if available
                    if hasattr(self, 'peaks') and self.peaks is not None:
                        f.write("### PEAKS ###\n")
                        f.write(f"Number of peaks: {len(self.peaks['wavenumbers'])}\n")
                        for i, (pos, height) in enumerate(zip(self.peaks['wavenumbers'], self.peaks['heights'])):
                            f.write(f"Peak {i+1}: {pos:.2f} cm⁻¹ (height: {height:.2f})\n")
                        f.write("##############\n\n")
                    
                    # Add peak fitting results if available
                    if hasattr(self, 'peak_fit_result') and self.peak_fit_result is not None:
                        f.write("### PEAK FIT ###\n")
                        f.write(f"Model: {self.peak_fit_result.get('model', 'Unknown')}\n")
                        f.write(f"R-squared: {self.peak_fit_result.get('r_squared', 0):.4f}\n")
                        f.write("###############\n\n")
                    
                    # Write column headers
                    f.write("Wavenumber (cm⁻¹)\tIntensity (a.u.)\n")
                    
                    # Write data
                    for wn, intensity in zip(self.current_wavenumbers, spectra_to_save):
                        f.write(f"{wn:.4f}\t{intensity:.6f}\n")
            
            else:
                # Default to tab-separated text format
                with open(filepath, 'w') as f:
                    # Write metadata as comments
                    if hasattr(self, 'metadata') and self.metadata:
                        f.write("### METADATA ###\n")
                        for key, value in self.metadata.items():
                            f.write(f"{key}: {value}\n")
                        f.write("###############\n\n")
                    
                    # Write column headers
                    f.write("Wavenumber (cm⁻¹)\tIntensity (a.u.)\n")
                    
                    # Write data
                    for wn, intensity in zip(self.current_wavenumbers, spectra_to_save):
                        f.write(f"{wn:.4f}\t{intensity:.6f}\n")
            
            return True
            
        except Exception as e:
            print(f"Error saving spectrum: {str(e)}")
            return False

    def save_analysis_state(self, filepath):
        """
        Save the current analysis state to a file.
        
        This method saves the current analysis session, including:
        - Current spectra and wavenumbers
        - Processed spectra
        - Background
        - Peak data
        - Metadata
        - Fitted peaks and fit results
        
        Parameters:
        -----------
        filepath : str
            Path where the analysis state will be saved
            
        Returns:
        --------
        bool
            True if successful, False otherwise
        """
        try:
            # Create a dictionary with all the state information
            state = {
                'timestamp': datetime.now().isoformat(),
                'current_spectra': self.current_spectra,
                'current_wavenumbers': self.current_wavenumbers,
                'processed_spectra': self.processed_spectra,
                'peaks': self.peaks,
                'background': self.background,
                'metadata': self.metadata,
                'fitted_peaks': self.fitted_peaks,
                'peak_fit_result': self.peak_fit_result
            }
            
            # Add file extension if not present
            if not filepath.endswith('.claritystate'):
                filepath += '.claritystate'
                
            # Save the state to a file
            with open(filepath, 'wb') as f:
                pickle.dump(state, f)
                
            print(f"Analysis state saved to {filepath}")
            return True
            
        except Exception as e:
            print(f"Error saving analysis state: {str(e)}")
            return False
            
    def load_analysis_state(self, filepath):
        """
        Load a previously saved analysis state from a file.
        
        Parameters:
        -----------
        filepath : str
            Path to the saved analysis state file
            
        Returns:
        --------
        bool
            True if successful, False otherwise
        """
        try:
            # Load the state from the file
            with open(filepath, 'rb') as f:
                state = pickle.load(f)
                
            # Restore the state
            self.current_spectra = state.get('current_spectra')
            self.current_wavenumbers = state.get('current_wavenumbers')
            self.processed_spectra = state.get('processed_spectra')
            self.peaks = state.get('peaks')
            self.background = state.get('background')
            self.metadata = state.get('metadata', {})
            self.fitted_peaks = state.get('fitted_peaks')
            self.peak_fit_result = state.get('peak_fit_result')
            
            print(f"Analysis state loaded from {filepath}")
            return True
            
        except Exception as e:
            print(f"Error loading analysis state: {str(e)}")
            return False