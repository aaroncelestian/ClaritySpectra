#!/usr/bin/env python3
"""
RamanLab Qt6 Version - Main Application Window
"""

import os
import sys
from pathlib import Path
import numpy as np

# Fix matplotlib backend for Qt6/PySide6
import matplotlib
matplotlib.use("QtAgg")  # Use QtAgg backend which works with PySide6
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

# Import Qt6-compatible matplotlib backends and UI toolbar
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from ui.matplotlib_config import CompactNavigationToolbar as NavigationToolbar
except ImportError:
    # Fallback for older matplotlib versions
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from ui.matplotlib_config import CompactNavigationToolbar as NavigationToolbar

from ui.matplotlib_config import configure_compact_ui, apply_theme

from scipy.signal import find_peaks, savgol_filter
import pandas as pd

# Qt6 imports
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QLineEdit, QTextEdit, QSlider, QCheckBox, QComboBox,
    QGroupBox, QSplitter, QFileDialog, QMessageBox, QProgressBar,
    QStatusBar, QMenuBar, QApplication, QSpinBox, QDoubleSpinBox,
    QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox, QListWidget,
    QListWidgetItem, QInputDialog, QFrame, QScrollArea, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressDialog
)
from PySide6.QtCore import Qt, QTimer, QStandardPaths, QUrl, QThread, Signal
from PySide6.QtGui import QAction, QDesktopServices, QPixmap, QFont

# Version info
from version import __version__, __author__, __copyright__

# Import batch peak fitting module
try:
    from batch_peak_fitting_qt6 import launch_batch_peak_fitting
    BATCH_AVAILABLE = True
except ImportError:
    BATCH_AVAILABLE = False

# Import the RamanSpectraQt6 class for database functionality
try:
    from raman_spectra_qt6 import RamanSpectraQt6
    RAMAN_SPECTRA_AVAILABLE = True
except ImportError:
    RAMAN_SPECTRA_AVAILABLE = False

# Additional imports for data handling
import pickle
from scipy.interpolate import griddata


class RamanAnalysisAppQt6(QMainWindow):
    """RamanLab Qt6: Main application window for Raman spectrum analysis."""

    def __init__(self):
        """Initialize the Qt6 application."""
        super().__init__()
        
        # Apply compact UI configuration for consistent toolbar sizing
        apply_theme('compact')
        
        # Initialize components
        self.current_wavenumbers = None
        self.current_intensities = None
        self.processed_intensities = None
        self.original_wavenumbers = None
        self.original_intensities = None
        self.metadata = {}
        self.spectrum_file_path = None
        
        # Spectrum database
        self.database = {}
        
        # Initialize RamanSpectraQt6 for database functionality
        if RAMAN_SPECTRA_AVAILABLE:
            self.raman_db = RamanSpectraQt6(parent_widget=self)
        else:
            self.raman_db = None
            print("Warning: RamanSpectraQt6 not available, database functionality will be limited")
        
        # Background subtraction state
        self.background_preview = None
        self.smoothing_preview = None
        
        # Processing state
        self.detected_peaks = None
        self.background_preview_active = False
        self.smoothing_preview_active = False
        self.preview_background = None
        self.preview_corrected = None
        self.preview_smoothed = None
        
        # Set window properties
        self.setWindowTitle("RamanLab")
        self.setMinimumSize(1400, 900)
        self.resize(1600, 1000)
        
        # Set up the UI
        self.setup_ui()
        self.setup_menu_bar()
        self.setup_status_bar()
        self.center_on_screen()
        
        # Load database
        self.load_database()
        
        # Show startup message
        self.show_startup_message()

    def load_database(self):
        """Load the database using RamanSpectraQt6."""
        if self.raman_db:
            try:
                self.raman_db.load_database()
                print(f"✓ Database loaded with {len(self.raman_db.database)} spectra")
            except Exception as e:
                print(f"Warning: Could not load database: {e}")
        else:
            print("Warning: Database functionality not available")

    def setup_ui(self):
        """Set up the main user interface."""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout (horizontal splitter)
        main_layout = QHBoxLayout(central_widget)
        main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(main_splitter)
        
        # Left panel - visualization
        self.setup_visualization_panel(main_splitter)
        
        # Right panel - controls
        self.setup_control_panel(main_splitter)
        
        # Set splitter proportions (70% left, 30% right)
        main_splitter.setSizes([1000, 400])

    def setup_visualization_panel(self, parent):
        """Set up the spectrum visualization panel."""
        viz_frame = QFrame()
        viz_layout = QVBoxLayout(viz_frame)
        
        # Create matplotlib figure and canvas
        self.figure = Figure(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, viz_frame)
        
        # Create the main plot
        self.ax = self.figure.add_subplot(111)
        self.ax.set_xlabel("Wavenumber (cm⁻¹)")
        self.ax.set_ylabel("Intensity (a.u.)")
        self.ax.set_title("Raman Spectrum")
        self.ax.grid(True, alpha=0.3)
        
        # Add to layout
        viz_layout.addWidget(self.toolbar)
        viz_layout.addWidget(self.canvas)
        
        parent.addWidget(viz_frame)

    def setup_control_panel(self, parent):
        """Set up the control panel with tabs."""
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Create tabs
        self.file_tab = self.create_file_tab()
        self.process_tab = self.create_process_tab()
        self.search_tab = self.create_search_tab()
        self.database_tab = self.create_database_tab()
        self.advanced_tab = self.create_advanced_tab()
        
        # Add tabs to widget
        self.tab_widget.addTab(self.file_tab, "File")
        self.tab_widget.addTab(self.process_tab, "Process")
        self.tab_widget.addTab(self.search_tab, "Search")
        self.tab_widget.addTab(self.database_tab, "Database")
        self.tab_widget.addTab(self.advanced_tab, "Advanced")
        
        # Set a reasonable maximum width for the tab widget
        self.tab_widget.setMaximumWidth(450)
        
        parent.addWidget(self.tab_widget)

    def create_file_tab(self):
        """Create the file operations tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # File operations group
        file_group = QGroupBox("File Operations")
        file_layout = QVBoxLayout(file_group)
        
        # Import button
        import_btn = QPushButton("Import Spectrum")
        import_btn.clicked.connect(self.import_spectrum)
        file_layout.addWidget(import_btn)
        
        # Save button
        save_btn = QPushButton("Save Spectrum")
        save_btn.clicked.connect(self.save_spectrum)
        file_layout.addWidget(save_btn)
        
        # Multi-spectrum manager button
        multi_btn = QPushButton("Multi-Spectrum Manager")
        multi_btn.clicked.connect(self.launch_multi_spectrum_manager)
        file_layout.addWidget(multi_btn)
        
        layout.addWidget(file_group)
        
        # Spectrum info group
        info_group = QGroupBox("Spectrum Information")
        info_layout = QVBoxLayout(info_group)
        
        # Info display
        self.info_text = QTextEdit()
        self.info_text.setMaximumHeight(200)
        self.info_text.setPlainText("No spectrum loaded")
        info_layout.addWidget(self.info_text)
        
        layout.addWidget(info_group)
        layout.addStretch()
        
        return tab

    def create_process_tab(self):
        """Create the processing operations tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Background subtraction group
        bg_group = QGroupBox("Background Subtraction")
        bg_layout = QVBoxLayout(bg_group)
        
        # Background method selection
        bg_method_layout = QHBoxLayout()
        bg_method_layout.addWidget(QLabel("Method:"))
        self.bg_method_combo = QComboBox()
        self.bg_method_combo.addItems(["ALS (Asymmetric Least Squares)", "Linear", "Polynomial", "Moving Average"])
        self.bg_method_combo.currentTextChanged.connect(self.on_bg_method_changed)
        self.bg_method_combo.currentTextChanged.connect(self.preview_background_subtraction)
        bg_method_layout.addWidget(self.bg_method_combo)
        bg_layout.addLayout(bg_method_layout)
        
        # ALS parameters (visible by default)
        self.als_params_widget = QWidget()
        als_params_layout = QVBoxLayout(self.als_params_widget)
        als_params_layout.setContentsMargins(0, 0, 0, 0)
        
        # Lambda parameter
        lambda_layout = QHBoxLayout()
        lambda_layout.addWidget(QLabel("λ (Smoothness):"))
        self.lambda_slider = QSlider(Qt.Horizontal)
        self.lambda_slider.setRange(3, 7)  # 10^3 to 10^7
        self.lambda_slider.setValue(5)  # 10^5 (default)
        lambda_layout.addWidget(self.lambda_slider)
        self.lambda_label = QLabel("1e5")
        lambda_layout.addWidget(self.lambda_label)
        als_params_layout.addLayout(lambda_layout)
        
        # p parameter
        p_layout = QHBoxLayout()
        p_layout.addWidget(QLabel("p (Asymmetry):"))
        self.p_slider = QSlider(Qt.Horizontal)
        self.p_slider.setRange(1, 50)  # 0.001 to 0.05
        self.p_slider.setValue(10)  # 0.01 (default)
        p_layout.addWidget(self.p_slider)
        self.p_label = QLabel("0.01")
        p_layout.addWidget(self.p_label)
        als_params_layout.addLayout(p_layout)
        
        # Connect sliders to update labels
        self.lambda_slider.valueChanged.connect(self.update_lambda_label)
        self.p_slider.valueChanged.connect(self.update_p_label)
        
        # Connect sliders to live preview
        self.lambda_slider.valueChanged.connect(self.preview_background_subtraction)
        self.p_slider.valueChanged.connect(self.preview_background_subtraction)
        
        bg_layout.addWidget(self.als_params_widget)
        
        # Background subtraction buttons
        button_layout = QHBoxLayout()
        
        subtract_btn = QPushButton("Apply Background Subtraction")
        subtract_btn.clicked.connect(self.apply_background_subtraction)
        button_layout.addWidget(subtract_btn)
        
        preview_btn = QPushButton("Clear Preview")
        preview_btn.clicked.connect(self.clear_background_preview)
        button_layout.addWidget(preview_btn)
        
        bg_layout.addLayout(button_layout)
        
        reset_btn = QPushButton("Reset Spectrum")
        reset_btn.clicked.connect(self.reset_spectrum)
        bg_layout.addWidget(reset_btn)
        
        layout.addWidget(bg_group)
        
        # Peak detection group with real-time sliders
        peak_group = QGroupBox("Peak Detection")
        peak_layout = QVBoxLayout(peak_group)
        
        # Height parameter
        height_layout = QHBoxLayout()
        height_layout.addWidget(QLabel("Min Height:"))
        self.height_slider = QSlider(Qt.Horizontal)
        self.height_slider.setRange(0, 100)
        self.height_slider.setValue(10)
        self.height_slider.valueChanged.connect(self.update_peak_detection)
        height_layout.addWidget(self.height_slider)
        self.height_label = QLabel("10%")
        height_layout.addWidget(self.height_label)
        peak_layout.addLayout(height_layout)
        
        # Distance parameter
        distance_layout = QHBoxLayout()
        distance_layout.addWidget(QLabel("Min Distance:"))
        self.distance_slider = QSlider(Qt.Horizontal)
        self.distance_slider.setRange(1, 50)
        self.distance_slider.setValue(10)
        self.distance_slider.valueChanged.connect(self.update_peak_detection)
        distance_layout.addWidget(self.distance_slider)
        self.distance_label = QLabel("10")
        distance_layout.addWidget(self.distance_label)
        peak_layout.addLayout(distance_layout)
        
        # Prominence parameter
        prominence_layout = QHBoxLayout()
        prominence_layout.addWidget(QLabel("Prominence:"))
        self.prominence_slider = QSlider(Qt.Horizontal)
        self.prominence_slider.setRange(0, 50)
        self.prominence_slider.setValue(5)
        self.prominence_slider.valueChanged.connect(self.update_peak_detection)
        prominence_layout.addWidget(self.prominence_slider)
        self.prominence_label = QLabel("5%")
        prominence_layout.addWidget(self.prominence_label)
        peak_layout.addLayout(prominence_layout)
        
        # Manual peak detection button
        detect_btn = QPushButton("Detect Peaks")
        detect_btn.clicked.connect(self.find_peaks)
        peak_layout.addWidget(detect_btn)
        
        # Peak count display
        self.peak_count_label = QLabel("Peaks found: 0")
        peak_layout.addWidget(self.peak_count_label)
        
        layout.addWidget(peak_group)
        
        # Smoothing group
        smooth_group = QGroupBox("Spectral Smoothing")
        smooth_layout = QVBoxLayout(smooth_group)
        
        # Savitzky-Golay parameters
        sg_layout = QHBoxLayout()
        sg_layout.addWidget(QLabel("Window Length:"))
        self.sg_window_spin = QSpinBox()
        self.sg_window_spin.setRange(3, 51)
        self.sg_window_spin.setValue(5)
        self.sg_window_spin.setSingleStep(2)  # Only odd numbers
        self.sg_window_spin.valueChanged.connect(self.preview_smoothing)
        sg_layout.addWidget(self.sg_window_spin)
        
        sg_layout.addWidget(QLabel("Poly Order:"))
        self.sg_order_spin = QSpinBox()
        self.sg_order_spin.setRange(1, 5)
        self.sg_order_spin.setValue(2)
        self.sg_order_spin.valueChanged.connect(self.preview_smoothing)
        sg_layout.addWidget(self.sg_order_spin)
        smooth_layout.addLayout(sg_layout)
        
        # Smoothing buttons
        smooth_button_layout = QHBoxLayout()
        
        smooth_btn = QPushButton("Apply Savitzky-Golay Smoothing")
        smooth_btn.clicked.connect(self.apply_smoothing)
        smooth_button_layout.addWidget(smooth_btn)
        
        clear_smooth_btn = QPushButton("Clear Preview")
        clear_smooth_btn.clicked.connect(self.clear_smoothing_preview)
        smooth_button_layout.addWidget(clear_smooth_btn)
        
        smooth_layout.addLayout(smooth_button_layout)
        
        layout.addWidget(smooth_group)
        layout.addStretch()
        
        return tab

    def create_database_tab(self):
        """Create the database management tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Measured Raman Database group
        db_ops_group = QGroupBox("Measured Raman Database")
        db_ops_layout = QVBoxLayout(db_ops_group)
        
        # View Raman database button (removed Add button, renamed and styled to match mineral button)
        view_btn = QPushButton("View/Edit Measured Raman Database")
        view_btn.clicked.connect(self.view_database)
        view_btn.setStyleSheet("""
            QPushButton {
                background-color: #673AB7;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5E35B1;
            }
            QPushButton:pressed {
                background-color: #512DA8;
            }
        """)
        db_ops_layout.addWidget(view_btn)
        
        layout.addWidget(db_ops_group)
        
        # Calculated Raman Database group
        mineral_db_group = QGroupBox("Calculated Raman Database")
        mineral_db_layout = QVBoxLayout(mineral_db_group)
        
        # Mineral modes database button
        mineral_modes_btn = QPushButton("View/Edit Calculated Raman Character Info")
        mineral_modes_btn.clicked.connect(self.launch_mineral_modes_browser)
        mineral_modes_btn.setStyleSheet("""
            QPushButton {
                background-color: #673AB7;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5E35B1;
            }
            QPushButton:pressed {
                background-color: #512DA8;
            }
        """)
        mineral_db_layout.addWidget(mineral_modes_btn)
        
        layout.addWidget(mineral_db_group)
        
        # Database stats group
        stats_group = QGroupBox("Database Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        self.db_stats_text = QTextEdit()
        self.db_stats_text.setMaximumHeight(100)
        self.db_stats_text.setPlainText("Database statistics will appear here...")
        stats_layout.addWidget(self.db_stats_text)
        
        # Refresh stats button
        refresh_btn = QPushButton("Refresh Statistics")
        refresh_btn.clicked.connect(self.update_database_stats)
        stats_layout.addWidget(refresh_btn)
        
        layout.addWidget(stats_group)
        layout.addStretch()
        
        return tab

    def create_search_tab(self):
        """Create the comprehensive search functionality tab with basic and advanced search subtabs."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Create search subtabs
        search_tab_widget = QTabWidget()
        
        # Create basic search subtab
        basic_search_tab = self.create_basic_search_subtab()
        search_tab_widget.addTab(basic_search_tab, "Basic Search")
        
        # Create advanced search subtab
        advanced_search_tab = self.create_advanced_search_subtab()
        search_tab_widget.addTab(advanced_search_tab, "Advanced Search")
        
        layout.addWidget(search_tab_widget)
        
        # Mixed Mineral Analysis section at bottom
        mixed_mineral_group = QGroupBox("Mixed Mineral Analysis")
        mixed_mineral_layout = QVBoxLayout(mixed_mineral_group)
        
        # Description
        desc_label = QLabel("Analyze spectra that may contain multiple mineral phases:")
        desc_label.setWordWrap(True)
        mixed_mineral_layout.addWidget(desc_label)
        
        # Mixed mineral analysis button
        mixed_mineral_btn = QPushButton("Launch Mixed Mineral Analysis")
        mixed_mineral_btn.clicked.connect(self.analyze_mixed_minerals)
        mixed_mineral_btn.setStyleSheet("""
            QPushButton {
                background-color: #4A90E2;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
            QPushButton:pressed {
                background-color: #2E6DA4;
            }
        """)
        mixed_mineral_layout.addWidget(mixed_mineral_btn)
        
        layout.addWidget(mixed_mineral_group)
        
        return tab

    def create_basic_search_subtab(self):
        """Create the basic search subtab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Algorithm selection
        algorithm_group = QGroupBox("Search Algorithm")
        algorithm_layout = QVBoxLayout(algorithm_group)
        
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems([
            "correlation", "peak", "combined", "DTW"
        ])
        self.algorithm_combo.setCurrentText("correlation")
        # Remove the redundant "Algorithm:" label since groupbox already says "Search Algorithm"
        algorithm_layout.addWidget(self.algorithm_combo)
        
        # Algorithm descriptions
        desc_text = QTextEdit()
        desc_text.setMaximumHeight(80)
        desc_text.setPlainText(
            "Correlation: Compare spectral shapes using cross-correlation\n"
            "Peak: Match based on peak positions and intensities\n"
            "Combined: Hybrid approach using both correlation and DTW\n"
            "DTW: Dynamic Time Warping for optimal spectral alignment"
        )
        desc_text.setReadOnly(True)
        algorithm_layout.addWidget(desc_text)
        
        layout.addWidget(algorithm_group)
        
        # Search parameters
        params_group = QGroupBox("Search Parameters")
        params_layout = QFormLayout(params_group)
        
        # Number of matches
        self.n_matches_spin = QSpinBox()
        self.n_matches_spin.setRange(1, 50)
        self.n_matches_spin.setValue(10)
        params_layout.addRow("Number of matches:", self.n_matches_spin)
        
        # Correlation threshold
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.0, 1.0)
        self.threshold_spin.setSingleStep(0.1)
        self.threshold_spin.setValue(0.7)  # More reasonable default threshold
        params_layout.addRow("Similarity threshold:", self.threshold_spin)
        
        layout.addWidget(params_group)
        
        # Search button
        search_btn = QPushButton("Search Database")
        search_btn.clicked.connect(self.perform_basic_search)
        search_btn.setStyleSheet("""
            QPushButton {
                background-color: #5CB85C;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #449D44;
            }
            QPushButton:pressed {
                background-color: #398439;
            }
        """)
        layout.addWidget(search_btn)
        
        # Search results
        results_group = QGroupBox("Search Results")
        results_layout = QVBoxLayout(results_group)
        
        self.search_results_text = QTextEdit()
        self.search_results_text.setPlainText("Search results will appear here...")
        results_layout.addWidget(self.search_results_text)
        
        layout.addWidget(results_group)
        
        return tab

    def create_advanced_search_subtab(self):
        """Create the advanced search subtab with all filtering options."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Show which algorithm will be used (from basic search tab)
        algorithm_info_group = QGroupBox("Search Algorithm")
        algorithm_info_layout = QVBoxLayout(algorithm_info_group)
        
        algorithm_note = QLabel("Uses algorithm selected in Basic Search tab")
        algorithm_note.setStyleSheet("font-style: italic; color: #666; font-size: 10px;")
        algorithm_info_layout.addWidget(algorithm_note)
        
        # Add current algorithm display
        self.current_algorithm_label = QLabel("Current: correlation")
        self.current_algorithm_label.setStyleSheet("font-weight: bold; color: #333; font-size: 11px;")
        algorithm_info_layout.addWidget(self.current_algorithm_label)
        
        # Connect to update when algorithm changes
        self.algorithm_combo.currentTextChanged.connect(self.update_advanced_algorithm_display)
        
        layout.addWidget(algorithm_info_group)
        
        # Create scrollable area for all the controls - make it more compact
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Peak-based search filter - more compact layout
        peak_group = QGroupBox("Peak-Based Search Filter")
        peak_layout = QVBoxLayout(peak_group)
        
        peak_layout.addWidget(QLabel("Search by specific peak positions:"))
        self.peak_positions_edit = QLineEdit()
        self.peak_positions_edit.setPlaceholderText("e.g., 1050, 1350, 1580")
        peak_layout.addWidget(self.peak_positions_edit)
        
        hint_label = QLabel("Comma-separated wavenumber values. Results must contain ALL peaks.")
        hint_label.setStyleSheet("font-size: 9px; color: gray;")
        peak_layout.addWidget(hint_label)
        
        # Add important note about peak detection
        note_label = QLabel("⚠️ Note: Database spectra must have detected peaks for this filter to work.")
        note_label.setStyleSheet("font-size: 9px; color: #FF6B00; font-weight: bold;")
        note_label.setWordWrap(True)
        peak_layout.addWidget(note_label)
        
        # Make tolerance layout more compact
        tolerance_layout = QHBoxLayout()
        tolerance_layout.addWidget(QLabel("Tolerance (cm⁻¹):"))
        self.peak_tolerance_spin = QDoubleSpinBox()
        self.peak_tolerance_spin.setRange(1.0, 100.0)
        self.peak_tolerance_spin.setValue(10.0)
        self.peak_tolerance_spin.setMaximumWidth(80)  # Limit width
        tolerance_layout.addWidget(self.peak_tolerance_spin)
        tolerance_layout.addStretch()
        peak_layout.addLayout(tolerance_layout)
        
        # Add peak-only search mode explanation
        peak_only_note = QLabel("✨ Peak-Only Search: When peak positions are specified above, all spectra with matching peaks will be returned, regardless of overall spectral similarity.")
        peak_only_note.setStyleSheet("font-size: 9px; color: #0066CC; font-weight: bold; background-color: #E6F3FF; padding: 5px; border-radius: 3px;")
        peak_only_note.setWordWrap(True)
        peak_layout.addWidget(peak_only_note)
        
        scroll_layout.addWidget(peak_group)
        
        # Metadata filter options - more compact
        filter_group = QGroupBox("Metadata Filters")
        filter_layout = QFormLayout(filter_group)  # Use QFormLayout for compactness
        
        # Chemical family filter
        self.chemical_family_combo = QComboBox()
        self.chemical_family_combo.setEditable(True)
        self.chemical_family_combo.setMaximumWidth(200)
        filter_layout.addRow("Chemical Family:", self.chemical_family_combo)
        
        # Hey classification filter
        self.hey_classification_combo = QComboBox()
        self.hey_classification_combo.setEditable(True)
        self.hey_classification_combo.setMaximumWidth(200)
        filter_layout.addRow("Hey Classification:", self.hey_classification_combo)
        
        scroll_layout.addWidget(filter_group)
        
        # Chemistry elements filters - more compact
        elements_group = QGroupBox("Chemistry Element Filters")
        elements_layout = QFormLayout(elements_group)
        
        self.only_elements_edit = QLineEdit()
        self.only_elements_edit.setPlaceholderText("e.g., Si, O, Al")
        self.only_elements_edit.setMaximumWidth(200)
        elements_layout.addRow("Only elements:", self.only_elements_edit)
        
        self.required_elements_edit = QLineEdit()
        self.required_elements_edit.setPlaceholderText("e.g., Ca, C")
        self.required_elements_edit.setMaximumWidth(200)
        elements_layout.addRow("Required elements:", self.required_elements_edit)
        
        self.exclude_elements_edit = QLineEdit()
        self.exclude_elements_edit.setPlaceholderText("e.g., Fe, Mg")
        self.exclude_elements_edit.setMaximumWidth(200)
        elements_layout.addRow("Exclude elements:", self.exclude_elements_edit)
        
        scroll_layout.addWidget(elements_group)
        
        # Similarity threshold for advanced search - compact
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("Similarity Threshold:"))
        self.adv_threshold_spin = QDoubleSpinBox()
        self.adv_threshold_spin.setRange(0.0, 1.0)
        self.adv_threshold_spin.setSingleStep(0.1)
        self.adv_threshold_spin.setValue(0.3)
        self.adv_threshold_spin.setMaximumWidth(80)
        threshold_layout.addWidget(self.adv_threshold_spin)
        threshold_hint = QLabel("(Applied after filtering)")
        threshold_hint.setStyleSheet("font-size: 9px; color: gray;")
        threshold_layout.addWidget(threshold_hint)
        threshold_layout.addStretch()
        scroll_layout.addLayout(threshold_layout)
        
        # Advanced search button
        adv_search_btn = QPushButton("Advanced Search")
        adv_search_btn.clicked.connect(self.perform_advanced_search)
        adv_search_btn.setStyleSheet("""
            QPushButton {
                background-color: #F0AD4E;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #EC971F;
            }
            QPushButton:pressed {
                background-color: #D58512;
            }
        """)
        scroll_layout.addWidget(adv_search_btn)
        
        # Add stretch at the end
        scroll_layout.addStretch()
        
        # Set up scroll area with more compact settings
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Add scroll area to tab
        layout.addWidget(scroll_area)
        
        # Update filter options when tab loads
        self.update_metadata_filter_options()
        
        return tab

    def setup_menu_bar(self):
        """Set up the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        import_action = QAction("Import Spectrum", self)
        import_action.triggered.connect(self.import_spectrum)
        file_menu.addAction(import_action)
        
        # Import Data submenu
        import_data_menu = file_menu.addMenu("Import Data")
        
        import_raman_map_action = QAction("Raman Spectral Map", self)
        import_raman_map_action.triggered.connect(self.import_raman_spectral_map)
        import_data_menu.addAction(import_raman_map_action)
        
        import_line_scan_action = QAction("Line Scan Data", self)
        import_line_scan_action.triggered.connect(self.import_line_scan_data)
        import_data_menu.addAction(import_line_scan_action)
        
        import_point_data_action = QAction("Point Measurement Data", self)
        import_point_data_action.triggered.connect(self.import_point_data)
        import_data_menu.addAction(import_point_data_action)
        
        import_data_menu.addSeparator()
        
        test_map_import_action = QAction("Test Raman Map Import", self)
        test_map_import_action.triggered.connect(self.test_raman_map_import)
        import_data_menu.addAction(test_map_import_action)
        
        file_menu.addSeparator()
        
        save_action = QAction("Save Current Spectrum", self)
        save_action.triggered.connect(self.save_spectrum)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Database menu
        database_menu = menubar.addMenu("Database")
        
        view_db_action = QAction("View Database", self)
        view_db_action.triggered.connect(self.view_database)
        database_menu.addAction(view_db_action)
        
        database_menu.addSeparator()
        
        migrate_action = QAction("Migrate Legacy Database", self)
        migrate_action.triggered.connect(self.migrate_legacy_database)
        database_menu.addAction(migrate_action)
        
        browse_pkl_action = QAction("Browse for PKL File", self)
        browse_pkl_action.triggered.connect(self.browse_pkl_file)
        database_menu.addAction(browse_pkl_action)
        
        database_menu.addSeparator()
        
        export_db_action = QAction("Export Database", self)
        export_db_action.triggered.connect(self.export_database_file)
        database_menu.addAction(export_db_action)
        
        import_db_action = QAction("Import Database", self)
        import_db_action.triggered.connect(self.import_database_file)
        database_menu.addAction(import_db_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def setup_status_bar(self):
        """Set up the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("RamanLab Qt6 - Ready (Cross-platform file operations enabled!)")

    def center_on_screen(self):
        """Center the window on the screen."""
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def show_startup_message(self):
        """Show startup message in the plot area."""
        self.ax.text(0.5, 0.5, 
                     'RamanLab Qt6\n\n'
                     'Enhanced File Loading Capabilities:\n'
                     '• CSV, TXT (tab/space delimited)\n'
                     '• Headers and metadata (# lines)\n'
                     '• Auto-format detection\n\n'
                     'Import a spectrum to get started\n',
                     
                     ha='center', va='center', fontsize=11, fontweight='bold',
                     transform=self.ax.transAxes)
        self.ax.set_xlim(0, 1)
        self.ax.set_ylim(0, 1)
        self.canvas.draw()

    # Cross-platform file operations (replacing your platform-specific code!)
    def import_spectrum(self):
        """Import a Raman spectrum file using Qt6 file dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Raman Spectrum",
            QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation),
            "Spectrum files (*.txt *.csv *.dat *.spc *.xy *.asc);;Text files (*.txt);;CSV files (*.csv);;Data files (*.dat);;All files (*.*)"
        )
        
        if file_path:
            try:
                self.load_spectrum_file(file_path)
                self.status_bar.showMessage(f"Loaded: {Path(file_path).name} with enhanced format detection")
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to import spectrum:\n{str(e)}")

    def load_spectrum_file(self, file_path):
        """Load spectrum data from file with enhanced header and format handling."""
        try:
            # Parse the file with enhanced handling
            wavenumbers, intensities, metadata = self.parse_spectrum_file(file_path)
            
            if len(wavenumbers) == 0 or len(intensities) == 0:
                raise ValueError("No valid data found in file")
            
            if len(wavenumbers) != len(intensities):
                raise ValueError("Wavenumber and intensity arrays have different lengths")
            
            # Store the data
            self.current_wavenumbers = wavenumbers
            self.current_intensities = intensities
            self.processed_intensities = self.current_intensities.copy()
            
            # Store metadata from file
            self.current_spectrum_metadata = metadata
            
            # Clear any active previews
            self.background_preview_active = False
            self.smoothing_preview_active = False
            self.preview_background = None
            self.preview_corrected = None
            self.preview_smoothed = None
            
            self.update_plot()
            self.update_info_display(file_path)
            
        except Exception as e:
            raise Exception(f"Error reading file: {str(e)}")

    def parse_spectrum_file(self, file_path):
        """Enhanced spectrum file parser that handles headers, metadata, and various formats."""
        import csv
        import re
        from pathlib import Path
        
        wavenumbers = []
        intensities = []
        metadata = {}
        
        file_extension = Path(file_path).suffix.lower()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(file_path, 'r', encoding='latin-1') as file:
                lines = file.readlines()
        
        # First pass: extract metadata and find data start
        data_start_line = 0
        delimiter = None
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Handle metadata lines starting with #
            if line.startswith('#'):
                self.parse_metadata_line(line, metadata)
                data_start_line = i + 1
                continue
            
            # Check if this looks like a header line (non-numeric first column)
            if self.is_header_line(line):
                data_start_line = i + 1
                continue
            
            # This should be the first data line - detect delimiter
            if delimiter is None:
                delimiter = self.detect_delimiter(line, file_extension)
                break
        
        # Second pass: read the actual data
        for i in range(data_start_line, len(lines)):
            line = lines[i].strip()
            
            # Skip empty lines and comment lines
            if not line or line.startswith('#'):
                continue
            
            try:
                # Parse the data line
                values = self.parse_data_line(line, delimiter)
                
                if len(values) >= 2:
                    # Convert to float
                    wavenumber = float(values[0])
                    intensity = float(values[1])
                    
                    wavenumbers.append(wavenumber)
                    intensities.append(intensity)
                    
            except (ValueError, IndexError) as e:
                # Skip lines that can't be parsed as numeric data
                print(f"Skipping line {i+1}: {line[:50]}... (Error: {e})")
                continue
        
        # Convert to numpy arrays
        wavenumbers = np.array(wavenumbers)
        intensities = np.array(intensities)
        
        # Add file information to metadata
        metadata['file_path'] = str(file_path)
        metadata['file_name'] = Path(file_path).name
        metadata['data_points'] = len(wavenumbers)
        if len(wavenumbers) > 0:
            metadata['wavenumber_range'] = f"{wavenumbers.min():.1f} - {wavenumbers.max():.1f} cm⁻¹"
        
        return wavenumbers, intensities, metadata

    def parse_metadata_line(self, line, metadata):
        """Parse a metadata line starting with #."""
        # Remove the # and strip whitespace
        content = line[1:].strip()
        
        if not content:
            return
        
        # Try to parse as key: value or key = value
        for separator in [':', '=']:
            if separator in content:
                parts = content.split(separator, 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    metadata[key] = value
                    return
        
        # If no separator found, store as a general comment
        if 'comments' not in metadata:
            metadata['comments'] = []
        metadata['comments'].append(content)

    def is_header_line(self, line):
        """Check if a line looks like a header (contains non-numeric data in first column)."""
        # Split the line using common delimiters
        for delimiter in [',', '\t', ' ']:
            parts = [part.strip() for part in line.split(delimiter) if part.strip()]
            if len(parts) >= 2:
                try:
                    # Try to convert first two parts to float
                    float(parts[0])
                    float(parts[1])
                    return False  # Successfully parsed as numbers, not a header
                except ValueError:
                    return True  # Can't parse as numbers, likely a header
        
        return False

    def detect_delimiter(self, line, file_extension):
        """Detect the delimiter used in the data file."""
        # For CSV files, prefer comma
        if file_extension == '.csv':
            if ',' in line:
                return ','
        
        # Count occurrences of different delimiters
        comma_count = line.count(',')
        tab_count = line.count('\t')
        space_count = len([x for x in line.split(' ') if x.strip()]) - 1
        
        # Choose delimiter with highest count
        if comma_count > 0 and comma_count >= tab_count and comma_count >= space_count:
            return ','
        elif tab_count > 0 and tab_count >= space_count:
            return '\t'
        else:
            return None  # Will use split() for whitespace

    def parse_data_line(self, line, delimiter):
        """Parse a data line using the detected delimiter."""
        if delimiter == ',':
            # Use CSV reader for proper comma handling
            import csv
            reader = csv.reader([line])
            values = next(reader)
        elif delimiter == '\t':
            values = line.split('\t')
        else:
            # Default to whitespace splitting
            values = line.split()
        
        # Strip whitespace from each value
        return [value.strip() for value in values if value.strip()]

    def update_plot(self):
        """Update the main spectrum plot with optional previews."""
        self.ax.clear()
        
        if self.current_wavenumbers is not None and self.processed_intensities is not None:
            # Plot the main processed spectrum
            self.ax.plot(self.current_wavenumbers, self.processed_intensities, 'b-', linewidth=1.5, 
                        label='Current Spectrum', alpha=0.9)
            
            # Plot background preview if active
            if self.background_preview_active and self.preview_background is not None:
                self.ax.plot(self.current_wavenumbers, self.preview_background, 'r--', linewidth=1, 
                            label='Background (Preview)', alpha=0.7)
                
                # Show corrected spectrum preview
                if self.preview_corrected is not None:
                    self.ax.plot(self.current_wavenumbers, self.preview_corrected, 'g-', linewidth=1, 
                                label='Corrected (Preview)', alpha=0.7)
            
            # Plot smoothing preview if active
            if self.smoothing_preview_active and self.preview_smoothed is not None:
                self.ax.plot(self.current_wavenumbers, self.preview_smoothed, 'm-', linewidth=1.5, 
                            label='Smoothed (Preview)', alpha=0.8)
            
            # Plot peaks if detected
            if self.detected_peaks is not None:
                peak_positions = self.current_wavenumbers[self.detected_peaks]
                peak_intensities = self.processed_intensities[self.detected_peaks]
                self.ax.plot(peak_positions, peak_intensities, 'ro', markersize=6, 
                            label='Detected Peaks')
            
            self.ax.set_xlabel("Wavenumber (cm⁻¹)")
            self.ax.set_ylabel("Intensity (a.u.)")
            self.ax.set_title("Raman Spectrum")
            self.ax.grid(True, alpha=0.3)
            
            # Add legend if there are previews
            if self.background_preview_active or self.smoothing_preview_active or self.detected_peaks is not None:
                self.ax.legend(loc='upper right', fontsize=9)
        
        self.canvas.draw()

    def update_info_display(self, file_path):
        """Update the spectrum information display."""
        if self.current_wavenumbers is not None:
            info = f"File: {Path(file_path).name}\n"
            info += f"Data points: {len(self.current_wavenumbers)}\n"
            info += f"Wavenumber range: {self.current_wavenumbers.min():.1f} - {self.current_wavenumbers.max():.1f} cm⁻¹\n"
            info += f"Intensity range: {self.current_intensities.min():.1e} - {self.current_intensities.max():.1e}\n"
            
            # Add metadata from file if available
            if hasattr(self, 'current_spectrum_metadata') and self.current_spectrum_metadata:
                info += "\n--- File Metadata ---\n"
                
                # Show important metadata first
                important_keys = ['Instrument', 'Laser Wavelength', 'Laser Power', 'Integration Time', 
                                'Accumulations', 'Temperature', 'Sample', 'Operator']
                
                for key in important_keys:
                    if key in self.current_spectrum_metadata:
                        info += f"{key}: {self.current_spectrum_metadata[key]}\n"
                
                # Show other metadata (excluding file info we already show)
                exclude_keys = ['file_path', 'file_name', 'data_points', 'wavenumber_range'] + important_keys
                other_metadata = {k: v for k, v in self.current_spectrum_metadata.items() 
                                if k not in exclude_keys and not k.startswith('_')}
                
                if other_metadata:
                    for key, value in other_metadata.items():
                        if key == 'comments' and isinstance(value, list):
                            for comment in value:
                                info += f"Comment: {comment}\n"
                        else:
                            info += f"{key}: {value}\n"
            
            self.info_text.setPlainText(info)

    # Basic processing methods
    def save_spectrum(self):
        """Save the current spectrum using cross-platform dialog."""
        if self.current_wavenumbers is None:
            QMessageBox.warning(self, "No Data", "No spectrum to save.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Spectrum",
            QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation),
            "Text files (*.txt);;CSV files (*.csv);;All files (*.*)"
        )
        
        if file_path:
            try:
                data = np.column_stack([self.current_wavenumbers, self.processed_intensities])
                np.savetxt(file_path, data, delimiter='\t', header='Wavenumber\tIntensity')
                self.status_bar.showMessage(f"Saved: {Path(file_path).name}")
                QMessageBox.information(self, "Success", f"Spectrum saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save spectrum:\n{str(e)}")

    def subtract_background(self):
        """Enhanced background subtraction with multiple methods including ALS."""
        if self.processed_intensities is None:
            QMessageBox.warning(self, "No Data", "No spectrum loaded for background subtraction.")
            return
            
        try:
            method = self.bg_method_combo.currentText()
            
            if method.startswith("ALS"):
                # ALS background subtraction
                lambda_value = 10 ** self.lambda_slider.value()
                p_value = self.p_slider.value() / 1000.0
                
                corrected_intensities, baseline = self.raman_db.subtract_background_als(
                    self.current_wavenumbers,
                    self.processed_intensities,
                    lam=lambda_value,
                    p=p_value,
                    niter=10
                )
                
                self.processed_intensities = corrected_intensities
                
            elif method == "Linear":
                # Linear background subtraction
                x = np.arange(len(self.processed_intensities))
                background = np.linspace(
                    self.processed_intensities[0],
                    self.processed_intensities[-1],
                    len(self.processed_intensities)
                )
                self.processed_intensities -= background
                
            elif method == "Polynomial":
                # Polynomial background fitting (order 2)
                x = np.arange(len(self.processed_intensities))
                coeffs = np.polyfit(x, self.processed_intensities, 2)
                background = np.polyval(coeffs, x)
                self.processed_intensities -= background
                
            elif method == "Moving Average":
                # Moving average background
                window_size = max(len(self.processed_intensities) // 20, 5)  # Adaptive window size
                background = np.convolve(
                    self.processed_intensities, 
                    np.ones(window_size)/window_size, 
                    mode='same'
                )
                self.processed_intensities -= background
            
            # Update plot
            self.update_plot()
            
            self.status_bar.showMessage(f"Applied {method.lower()} background subtraction")
            
        except Exception as e:
            QMessageBox.critical(self, "Background Subtraction Error", f"Failed to subtract background:\n{str(e)}")

    def preview_background_subtraction(self):
        """Preview background subtraction with current slider values."""
        if self.processed_intensities is None:
            return
            
        try:
            method = self.bg_method_combo.currentText()
            
            if method.startswith("ALS"):
                # ALS background subtraction preview
                lambda_value = 10 ** self.lambda_slider.value()
                p_value = self.p_slider.value() / 1000.0
                
                corrected_intensities, baseline = self.raman_db.subtract_background_als(
                    self.current_wavenumbers,
                    self.processed_intensities,
                    lam=lambda_value,
                    p=p_value,
                    niter=10
                )
                
                self.preview_background = baseline
                self.preview_corrected = corrected_intensities
                
            elif method == "Linear":
                # Linear background subtraction preview
                background = np.linspace(
                    self.processed_intensities[0],
                    self.processed_intensities[-1],
                    len(self.processed_intensities)
                )
                self.preview_background = background
                self.preview_corrected = self.processed_intensities - background
                
            elif method == "Polynomial":
                # Polynomial background fitting preview (order 2)
                x = np.arange(len(self.processed_intensities))
                coeffs = np.polyfit(x, self.processed_intensities, 2)
                background = np.polyval(coeffs, x)
                self.preview_background = background
                self.preview_corrected = self.processed_intensities - background
                
            elif method == "Moving Average":
                # Moving average background preview
                window_size = max(len(self.processed_intensities) // 20, 5)
                background = np.convolve(
                    self.processed_intensities, 
                    np.ones(window_size)/window_size, 
                    mode='same'
                )
                self.preview_background = background
                self.preview_corrected = self.processed_intensities - background
            
            # Enable background preview
            self.background_preview_active = True
            self.update_plot()
            
            # Update status
            self.status_bar.showMessage(f"Previewing {method.lower()} background subtraction")
            
        except Exception as e:
            self.status_bar.showMessage(f"Preview error: {str(e)}")

    def apply_background_subtraction(self):
        """Apply the current background subtraction preview."""
        if not self.background_preview_active or self.preview_corrected is None:
            # No preview active, run the old method
            self.subtract_background()
            return
            
        # Apply the previewed correction
        self.processed_intensities = self.preview_corrected.copy()
        
        # Clear preview
        self.clear_background_preview()
        
        # Update plot
        self.update_plot()
        
        method = self.bg_method_combo.currentText()
        self.status_bar.showMessage(f"Applied {method.lower()} background subtraction")

    def clear_background_preview(self):
        """Clear the background subtraction preview."""
        self.background_preview_active = False
        self.preview_background = None
        self.preview_corrected = None
        self.update_plot()
        self.status_bar.showMessage("Background preview cleared")

    def reset_spectrum(self):
        """Reset spectrum to original."""
        if self.current_intensities is not None:
            self.processed_intensities = self.current_intensities.copy()
            self.detected_peaks = None
            
            # Clear any active previews
            if self.background_preview_active:
                self.clear_background_preview()
            if self.smoothing_preview_active:
                self.clear_smoothing_preview()
            
            self.update_plot()
            self.status_bar.showMessage("Spectrum reset to original")

    def find_peaks(self):
        """Manual peak detection using current slider values."""
        if self.processed_intensities is not None:
            self.update_peak_detection()  # Use the real-time method
            self.status_bar.showMessage(f"Found {len(self.detected_peaks)} peaks")
        else:
            QMessageBox.warning(self, "No Data", "No spectrum loaded for peak detection.")

    def show_about(self):
        """Show about dialog."""
        about_text = f"""
        RamanLab Qt6 Version
        
        Version: {__version__}
        Author: {__author__}
        
        Qt6 conversion of the Raman Spectrum Analysis Tool.
        
        Key Benefits:
        • Cross-platform compatibility (macOS, Windows, Linux)
        • No more platform-specific code
        • Modern, professional interface
        • Better matplotlib integration
        
        This is the beginning of your cross-platform journey!
        """
        QMessageBox.about(self, "About RamanLab Qt6", about_text)

    def closeEvent(self, event):
        """Handle application close event."""
        reply = QMessageBox.question(
            self,
            "Confirm Exit",
            "Are you sure you want to exit RamanLab Qt6?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

    # Database functionality methods
    def add_to_database(self):
        """Add current spectrum to database with metadata editing."""
        if self.current_wavenumbers is None or self.current_intensities is None:
            QMessageBox.warning(self, "No Data", "No spectrum loaded to add to database.")
            return
        
        # Create a metadata input dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Spectrum to Database")
        dialog.setMinimumSize(400, 500)
        
        layout = QVBoxLayout(dialog)
        
        # Form for basic metadata
        form_layout = QFormLayout()
        
        # Spectrum name
        name_edit = QLineEdit()
        name_edit.setText(f"Spectrum_{len(self.raman_db.database) + 1}")
        form_layout.addRow("Spectrum Name:", name_edit)
        
        # Mineral name
        mineral_edit = QLineEdit()
        form_layout.addRow("Mineral Name:", mineral_edit)
        
        # Sample description
        description_edit = QTextEdit()
        description_edit.setMaximumHeight(80)
        form_layout.addRow("Description:", description_edit)
        
        # Experimental conditions
        laser_edit = QLineEdit()
        laser_edit.setPlaceholderText("e.g., 532 nm")
        form_layout.addRow("Laser Wavelength:", laser_edit)
        
        power_edit = QLineEdit()
        power_edit.setPlaceholderText("e.g., 10 mW")
        form_layout.addRow("Laser Power:", power_edit)
        
        exposure_edit = QLineEdit()
        exposure_edit.setPlaceholderText("e.g., 30 s")
        form_layout.addRow("Exposure Time:", exposure_edit)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec() == QDialog.Accepted:
            # Collect metadata
            metadata = {
                'mineral_name': mineral_edit.text(),
                'description': description_edit.toPlainText(),
                'laser_wavelength': laser_edit.text(),
                'laser_power': power_edit.text(),
                'exposure_time': exposure_edit.text(),
                'data_points': len(self.current_wavenumbers),
                'wavenumber_range': f"{self.current_wavenumbers.min():.1f} - {self.current_wavenumbers.max():.1f} cm⁻¹"
            }
            
            # Add file metadata if available
            if hasattr(self, 'current_spectrum_metadata') and self.current_spectrum_metadata:
                # Merge file metadata, giving priority to user-entered metadata
                file_metadata = self.current_spectrum_metadata.copy()
                # Remove file system specific metadata
                for key in ['file_path', 'file_name']:
                    file_metadata.pop(key, None)
                
                # Merge, with user metadata taking precedence
                merged_metadata = file_metadata.copy()
                merged_metadata.update(metadata)
                metadata = merged_metadata
            
            # Add to database
            # Convert peak indices to wavenumber values before storing
            peak_wavenumbers = None
            if self.detected_peaks is not None and len(self.detected_peaks) > 0:
                # Convert indices to actual wavenumber values
                peak_wavenumbers = self.current_wavenumbers[self.detected_peaks].tolist()

            success = self.raman_db.add_to_database(
                name=name_edit.text(),
                wavenumbers=self.current_wavenumbers,
                intensities=self.processed_intensities,
                metadata=metadata,
                peaks=peak_wavenumbers
            )
            
            if success:
                QMessageBox.information(
                    self,
                    "Success",
                    f"Spectrum '{name_edit.text()}' added to database!\n\n"
                    f"Database location:\n{self.raman_db.db_path}\n\n"
                    "This database is persistent and cross-platform!"
                )
                # Update database stats
                self.update_database_stats()

    def view_database(self):
        """Launch the comprehensive database browser window."""
        # Import and launch the database browser
        from database_browser_qt6 import DatabaseBrowserQt6
        
        self.database_browser = DatabaseBrowserQt6(self.raman_db, parent=self)
        self.database_browser.show()  # Show as modeless dialog so user can work with both windows

    def update_database_stats(self):
        """Update database statistics display using real database."""
        if hasattr(self, 'db_stats_text') and self.db_stats_text is not None:
            stats = self.raman_db.get_database_stats()
            
            # Count spectra with peaks for peak filtering information
            spectra_with_peaks = 0
            total_peaks = 0
            for data in self.raman_db.database.values():
                peaks_data = data.get('peaks', [])
                if peaks_data and len(peaks_data) > 0:
                    spectra_with_peaks += 1
                    if isinstance(peaks_data, (list, tuple)):
                        total_peaks += len(peaks_data)
            
            stats_text = f"Database Statistics:\n\n"
            stats_text += f"Total spectra: {stats['total_spectra']}\n"
            stats_text += f"Average data points: {stats['avg_data_points']:.0f}\n"
            stats_text += f"Average peaks per spectrum: {stats['avg_peaks']:.1f}\n"
            stats_text += f"Spectra with detected peaks: {spectra_with_peaks}\n"
            stats_text += f"Total peaks in database: {total_peaks}\n"
            stats_text += f"Database file size: {stats['database_size']}\n\n"
            stats_text += f"Location: {self.raman_db.db_path}\n\n"
            stats_text += "✅ Cross-platform persistent storage\n"
            stats_text += "✅ Automatic backup on every save\n\n"
            
            # Add peak filtering guidance
            if spectra_with_peaks == 0:
                stats_text += "⚠️  No spectra have detected peaks.\n"
                stats_text += "Peak-based filtering will not work.\n"
                stats_text += "Detect peaks before adding spectra to database."
            elif spectra_with_peaks < stats['total_spectra']:
                stats_text += f"ℹ️  {stats['total_spectra'] - spectra_with_peaks} spectra lack detected peaks.\n"
                stats_text += "These will be excluded from peak-based searches."
            else:
                stats_text += "✅ All spectra have detected peaks.\n"
                stats_text += "Peak-based filtering is available."
            
            self.db_stats_text.setPlainText(stats_text)

    def migrate_legacy_database(self):
        """Migrate legacy database from menu."""
        from database_browser_qt6 import DatabaseBrowserQt6
        
        # Create a temporary browser instance just for migration
        temp_browser = DatabaseBrowserQt6(self.raman_db, parent=self)
        temp_browser.migrate_legacy_database()
        
        # Update our database stats after migration
        self.update_database_stats()

    def browse_pkl_file(self):
        """Browse for PKL file to migrate from menu."""
        from database_browser_qt6 import DatabaseBrowserQt6
        
        # Create a temporary browser instance just for migration
        temp_browser = DatabaseBrowserQt6(self.raman_db, parent=self)
        temp_browser.browse_pkl_file()
        
        # Update our database stats after migration
        self.update_database_stats()

    def update_peak_detection(self):
        """Update peak detection in real-time based on slider values."""
        if self.processed_intensities is None:
            return
            
        # Get current slider values
        height_percent = self.height_slider.value()
        distance = self.distance_slider.value()
        prominence_percent = self.prominence_slider.value()
        
        # Update labels
        self.height_label.setText(f"{height_percent}%")
        self.distance_label.setText(str(distance))
        self.prominence_label.setText(f"{prominence_percent}%")
        
        # Calculate actual values
        max_intensity = np.max(self.processed_intensities)
        height_threshold = (height_percent / 100.0) * max_intensity if height_percent > 0 else None
        prominence_threshold = (prominence_percent / 100.0) * max_intensity if prominence_percent > 0 else None
        
        # Find peaks with current parameters
        try:
            self.detected_peaks, properties = find_peaks(
                self.processed_intensities,
                height=height_threshold,
                distance=distance,
                prominence=prominence_threshold
            )
            
            # Update peak count
            self.peak_count_label.setText(f"Peaks found: {len(self.detected_peaks)}")
            
            # Debug: Print detected peak positions to console
            if len(self.detected_peaks) > 0:
                peak_positions = self.current_wavenumbers[self.detected_peaks]
                print(f"DEBUG: Detected {len(self.detected_peaks)} peaks at wavenumbers: {peak_positions}")
            else:
                print("DEBUG: No peaks detected with current parameters")
            
            # Update plot
            self.update_plot()
            
        except Exception as e:
            self.peak_count_label.setText(f"Peak detection error: {str(e)}")
            print(f"DEBUG: Peak detection error: {str(e)}")

    def apply_smoothing(self):
        """Apply Savitzky-Golay smoothing to the spectrum."""
        if self.processed_intensities is None:
            QMessageBox.warning(self, "No Data", "No spectrum loaded for smoothing.")
            return
            
        try:
            # If there's a preview, use it
            if self.smoothing_preview_active and self.preview_smoothed is not None:
                self.processed_intensities = self.preview_smoothed.copy()
                window_length = self.sg_window_spin.value()
                poly_order = self.sg_order_spin.value()
                
                # Clear preview
                self.clear_smoothing_preview()
                
                # Update plot
                self.update_plot()
                
                self.status_bar.showMessage(f"Applied Savitzky-Golay smoothing (window={window_length}, order={poly_order})")
                return
            
            # No preview, apply directly
            window_length = self.sg_window_spin.value()
            poly_order = self.sg_order_spin.value()
            
            # Ensure window length is odd and greater than poly_order
            if window_length % 2 == 0:
                window_length += 1
                self.sg_window_spin.setValue(window_length)
                
            if window_length <= poly_order:
                QMessageBox.warning(
                    self, 
                    "Invalid Parameters", 
                    f"Window length ({window_length}) must be greater than polynomial order ({poly_order})."
                )
                return
                
            # Apply Savitzky-Golay filter
            smoothed = savgol_filter(self.processed_intensities, window_length, poly_order)
            self.processed_intensities = smoothed
            
            # Update plot
            self.update_plot()
            
            self.status_bar.showMessage(f"Applied Savitzky-Golay smoothing (window={window_length}, order={poly_order})")
            
        except Exception as e:
            QMessageBox.critical(self, "Smoothing Error", f"Failed to apply smoothing:\n{str(e)}")

    def preview_smoothing(self):
        """Preview Savitzky-Golay smoothing with current parameters."""
        if self.processed_intensities is None:
            return
            
        try:
            window_length = self.sg_window_spin.value()
            poly_order = self.sg_order_spin.value()
            
            # Ensure window length is odd and greater than poly_order
            if window_length % 2 == 0:
                window_length += 1
                self.sg_window_spin.setValue(window_length)
                
            if window_length <= poly_order:
                self.status_bar.showMessage(f"Window length ({window_length}) must be greater than polynomial order ({poly_order})")
                return
                
            # Apply Savitzky-Golay filter for preview
            smoothed = savgol_filter(self.processed_intensities, window_length, poly_order)
            self.preview_smoothed = smoothed
            
            # Enable smoothing preview
            self.smoothing_preview_active = True
            self.update_plot()
            
            # Update status
            self.status_bar.showMessage(f"Previewing Savitzky-Golay smoothing (window={window_length}, order={poly_order})")
            
        except Exception as e:
            self.status_bar.showMessage(f"Smoothing preview error: {str(e)}")

    def clear_smoothing_preview(self):
        """Clear the smoothing preview."""
        self.smoothing_preview_active = False
        self.preview_smoothed = None
        self.update_plot()
        self.status_bar.showMessage("Smoothing preview cleared")

    def launch_multi_spectrum_manager(self):
        """Launch the multi-spectrum manager window."""
        from multi_spectrum_manager_qt6 import MultiSpectrumManagerQt6
        
        self.multi_spectrum_window = MultiSpectrumManagerQt6(parent=self, raman_db=self.raman_db)
        self.multi_spectrum_window.show()
        
        # If there's a current spectrum loaded, offer to add it
        if self.current_wavenumbers is not None and self.current_intensities is not None:
            reply = QMessageBox.question(
                self,
                "Add Current Spectrum?",
                "Would you like to add the currently loaded spectrum to the multi-spectrum manager?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                self.multi_spectrum_window.add_current_spectrum()

    def on_bg_method_changed(self):
        """Handle change in background method."""
        method = self.bg_method_combo.currentText()
        # Show ALS parameters only when ALS is selected
        self.als_params_widget.setVisible(method.startswith("ALS"))
        
        # Clear any active background preview when method changes
        if self.background_preview_active:
            self.clear_background_preview()

    def update_lambda_label(self):
        """Update the lambda label based on the slider value."""
        value = self.lambda_slider.value()
        lambda_value = 10 ** value
        self.lambda_label.setText(f"1e{value}")

    def update_p_label(self):
        """Update the p label based on the slider value."""
        value = self.p_slider.value()
        p_value = value / 1000.0  # Convert to 0.001-0.05 range
        self.p_label.setText(f"{p_value:.3f}")

    def perform_basic_search(self):
        """Perform basic database search using current spectrum."""
        if self.current_wavenumbers is None or self.current_intensities is None:
            QMessageBox.warning(self, "No Data", "Load a spectrum first to search for matches.")
            return
            
        if not self.raman_db.database:
            QMessageBox.information(self, "Empty Database", "No spectra in database to search.\nAdd some spectra first!")
            return
        
        # Show progress indication
        self.search_results_text.setPlainText("Searching database, please wait...")
        QApplication.processEvents()  # Update UI
        
        try:
            # Get search parameters
            algorithm = self.algorithm_combo.currentText()
            n_matches = self.n_matches_spin.value()
            threshold = self.threshold_spin.value()
            
            # Update status
            algorithm_name = "DTW (Dynamic Time Warping)" if algorithm == "DTW" else algorithm.title()
            self.status_bar.showMessage(f"Searching {len(self.raman_db.database)} spectra with {algorithm_name} algorithm...")
            
            # Perform search based on algorithm
            matches = []
            for name, data in self.raman_db.database.items():
                try:
                    # Get spectrum data
                    wavenumbers = data.get('wavenumbers', [])
                    intensities = data.get('intensities', [])
                    
                    # Ensure we have data - check length instead of boolean
                    if len(wavenumbers) == 0 or len(intensities) == 0:
                        continue
                    
                    # Calculate similarity score based on algorithm
                    if algorithm == "correlation":
                        score = self.calculate_correlation_score(wavenumbers, intensities)
                    elif algorithm == "peak":
                        score = self.calculate_peak_score(wavenumbers, intensities)
                    elif algorithm == "combined":
                        score = self.calculate_combined_score(wavenumbers, intensities)
                    elif algorithm == "DTW":
                        # DTW algorithm uses Dynamic Time Warping
                        score = self.calculate_dtw_score(wavenumbers, intensities)
                    else:
                        # Fallback to correlation
                        score = self.calculate_correlation_score(wavenumbers, intensities)
                    
                    if score >= threshold:
                        matches.append({
                            'name': name,
                            'score': score,
                            'metadata': data.get('metadata', {}),
                            'peaks': data.get('peaks', []),
                            'timestamp': data.get('timestamp', '')
                        })
                        
                except Exception as e:
                    print(f"Error processing spectrum {name}: {e}")
                    continue
            
            # Sort by score and limit results
            matches.sort(key=lambda x: x['score'], reverse=True)
            matches = matches[:n_matches]
            
            # Display results
            self.display_search_results(matches, f"Basic Search ({algorithm.title()})")
            
            # Update status
            self.status_bar.showMessage(f"Search completed - found {len(matches)} matches")
            
        except Exception as e:
            QMessageBox.critical(self, "Search Error", f"Search failed:\n{str(e)}")
            self.status_bar.showMessage("Search failed")
            self.search_results_text.setPlainText("Search failed. Please check your data and try again.")

    def perform_advanced_search(self):
        """Perform advanced database search with filters."""
        if self.current_wavenumbers is None or self.current_intensities is None:
            QMessageBox.warning(self, "No Data", "Load a spectrum first to search for matches.")
            return
            
        if not self.raman_db.database:
            QMessageBox.information(self, "Empty Database", "No spectra in database to search.\nAdd some spectra first!")
            return
        
        # Show progress indication
        self.search_results_text.setPlainText("Applying filters and searching database, please wait...")
        QApplication.processEvents()  # Update UI
        
        try:
            # Get basic search parameters
            algorithm = self.algorithm_combo.currentText()
            n_matches = self.n_matches_spin.value()
            threshold = self.adv_threshold_spin.value()
            
            # Parse filter criteria
            filters = self.parse_advanced_filters()
            
            # Check if this is a peak-only search
            is_peak_only_search = 'peak_positions' in filters and len(filters['peak_positions']) > 0
            
            # Show filter information for peak-based searches
            if 'peak_positions' in filters:
                peak_info = f"Peak Filter: Looking for peaks at {filters['peak_positions']} cm⁻¹ (±{filters.get('peak_tolerance', 10)} cm⁻¹)"
                print(f"Debug: {peak_info}")
                if is_peak_only_search:
                    self.status_bar.showMessage(f"Peak-Only Search: {peak_info}")
                else:
                    self.status_bar.showMessage(peak_info)
                QApplication.processEvents()
            
            # Update status
            if not is_peak_only_search:
                self.status_bar.showMessage("Applying metadata filters...")
                QApplication.processEvents()
            
            # Apply filters to database first
            filtered_candidates = self.apply_metadata_filters(filters)
            
            if not filtered_candidates:
                # Provide specific feedback for peak filters
                if 'peak_positions' in filters:
                    no_results_msg = (
                        f"No spectra found with peaks at {filters['peak_positions']} cm⁻¹.\n\n"
                        f"Tolerance: ±{filters.get('peak_tolerance', 10)} cm⁻¹\n\n"
                        "Tips:\n"
                        "• Try increasing the tolerance\n"
                        "• Check that peak positions are reasonable (e.g., 100-4000 cm⁻¹)\n"
                        "• Ensure database spectra have detected peaks"
                    )
                else:
                    no_results_msg = "No spectra match the specified filters."
                
                QMessageBox.information(self, "No Results", no_results_msg)
                self.search_results_text.setPlainText(no_results_msg)
                self.status_bar.showMessage("No matches found after filtering")
                return
            
            # Update status
            peak_filter_info = ""
            if 'peak_positions' in filters:
                peak_filter_info = f" (peak filter: {len(filtered_candidates)} candidates found)"
            
            if is_peak_only_search:
                # Peak-only search: return all candidates that passed the peak filter
                self.status_bar.showMessage(f"Peak-Only Search: Found {len(filtered_candidates)} spectra with matching peaks{peak_filter_info}")
                QApplication.processEvents()
                
                # Convert candidates directly to matches without similarity scoring
                matches = []
                for name, data in filtered_candidates:
                    matches.append({
                        'name': name,
                        'score': 1.0,  # Set score to 1.0 for peak-only matches
                        'metadata': data.get('metadata', {}),
                        'peaks': data.get('peaks', []),
                        'timestamp': data.get('timestamp', '')
                    })
                
                # Sort by name for consistent ordering
                matches.sort(key=lambda x: x['name'])
                
                # Limit results to n_matches
                matches = matches[:n_matches] if n_matches < len(matches) else matches
                
            else:
                # Regular advanced search with similarity scoring
                self.status_bar.showMessage(f"Searching {len(filtered_candidates)} filtered candidates{peak_filter_info}...")
                QApplication.processEvents()
                
                # Perform search on filtered candidates
                matches = self.search_filtered_candidates(filtered_candidates, algorithm, n_matches, threshold)
            
            # Display results
            filter_summary = self.create_filter_summary(filters)
            if is_peak_only_search:
                algorithm_name = "Peak-Only Search"
                additional_info = f"Peak-Only Search Mode: Returned all spectra with matching peaks.\nApplied filters: {filter_summary}\nFiltered database from {len(self.raman_db.database)} to {len(filtered_candidates)} candidates."
            else:
                algorithm_name = "DTW (Dynamic Time Warping)" if algorithm == "DTW" else algorithm.title()
                additional_info = f"Applied filters: {filter_summary}\nFiltered database from {len(self.raman_db.database)} to {len(filtered_candidates)} candidates."
            
            if 'peak_positions' in filters:
                additional_info += f"\n\nPeak Filter Details:\n• Required peaks: {filters['peak_positions']} cm⁻¹\n• Tolerance: ±{filters.get('peak_tolerance', 10)} cm⁻¹"
                if is_peak_only_search:
                    additional_info += f"\n• Peak-Only Mode: Similarity scoring bypassed"
            
            self.display_search_results(
                matches, 
                f"Advanced Search ({algorithm_name})",
                additional_info=additional_info
            )
            
            # Update status
            if is_peak_only_search:
                self.status_bar.showMessage(f"Peak-Only search completed - found {len(matches)} spectra with matching peaks")
            else:
                self.status_bar.showMessage(f"Advanced search completed - found {len(matches)} matches")
            
        except Exception as e:
            QMessageBox.critical(self, "Advanced Search Error", f"Advanced search failed:\n{str(e)}")
            self.status_bar.showMessage("Advanced search failed")
            self.search_results_text.setPlainText("Advanced search failed. Please check your filters and try again.")

    def parse_advanced_filters(self):
        """Parse the advanced search filter criteria."""
        filters = {}
        
        # Peak positions
        peak_str = self.peak_positions_edit.text().strip()
        if peak_str:
            try:
                filters['peak_positions'] = [float(x.strip()) for x in peak_str.split(",")]
                filters['peak_tolerance'] = self.peak_tolerance_spin.value()
            except ValueError:
                raise ValueError("Invalid peak positions format. Use comma-separated numbers.")
        
        # Chemical family
        chem_family = self.chemical_family_combo.currentText().strip()
        if chem_family:
            filters['chemical_family'] = chem_family
        
        # Hey classification
        hey_class = self.hey_classification_combo.currentText().strip()
        if hey_class:
            filters['hey_classification'] = hey_class
        
        # Element filters
        for filter_name, widget in [
            ('only_elements', self.only_elements_edit),
            ('required_elements', self.required_elements_edit),
            ('exclude_elements', self.exclude_elements_edit)
        ]:
            elements_str = widget.text().strip()
            if elements_str:
                filters[filter_name] = [elem.strip().upper() for elem in elements_str.split(",")]
        
        return filters

    def apply_metadata_filters(self, filters):
        """Apply metadata filters to the database and return matching candidates."""
        candidates = []
        
        for name, data in self.raman_db.database.items():
            # Check if this spectrum passes all filters
            if self.spectrum_passes_filters(name, data, filters):
                candidates.append((name, data))
        
        return candidates

    def spectrum_passes_filters(self, name, data, filters):
        """Check if a spectrum passes all the specified filters."""
        metadata = data.get('metadata', {})
        
        # Peak position filter - match original app behavior exactly
        if 'peak_positions' in filters:
            spectrum_peaks_data = data.get('peaks', [])
            required_peaks = filters['peak_positions']
            tolerance = filters.get('peak_tolerance', 10)
            
            # Original app format: {"peaks": {"wavenumbers": numpy_array}}
            if isinstance(spectrum_peaks_data, dict) and spectrum_peaks_data.get("wavenumbers") is not None:
                # This matches the original app format
                db_peaks = spectrum_peaks_data["wavenumbers"]
                
                # Check if it's a numpy array with data
                if hasattr(db_peaks, 'size') and db_peaks.size > 0:
                    valid_spectrum_peaks = db_peaks.tolist() if hasattr(db_peaks, 'tolist') else list(db_peaks)
                else:
                    return False
                    
            elif isinstance(spectrum_peaks_data, (list, tuple)) and len(spectrum_peaks_data) > 0:
                # Fallback: handle other formats
                spectrum_wavenumbers = data.get('wavenumbers', [])
                
                # If we have wavenumbers and peak values look like indices (small integers)
                if (len(spectrum_wavenumbers) > 0 and 
                    all(isinstance(p, (int, float)) and 0 <= p < len(spectrum_wavenumbers) for p in spectrum_peaks_data if p is not None)):
                    # Legacy format: indices that need to be converted to wavenumbers
                    try:
                        spectrum_wavenumbers = np.array(spectrum_wavenumbers)
                        valid_spectrum_peaks = []
                        for peak_idx in spectrum_peaks_data:
                            if peak_idx is not None and 0 <= int(peak_idx) < len(spectrum_wavenumbers):
                                peak_wavenumber = float(spectrum_wavenumbers[int(peak_idx)])
                                valid_spectrum_peaks.append(peak_wavenumber)
                    except (ValueError, TypeError, IndexError):
                        return False
                else:
                    # Direct wavenumber values
                    valid_spectrum_peaks = []
                    for peak in spectrum_peaks_data:
                        try:
                            peak_value = float(peak)
                            # Sanity check: wavenumber values should be reasonable (> 50 cm⁻¹)
                            if peak_value > 50:
                                valid_spectrum_peaks.append(peak_value)
                        except (ValueError, TypeError):
                            continue
            else:
                # No valid peak data found
                return False
            
            # Check if all required peaks are found within tolerance
            for required_peak in required_peaks:
                found = False
                for peak in valid_spectrum_peaks:
                    if abs(peak - required_peak) <= tolerance:
                        found = True
                        break
                if not found:
                    return False
        
        # Chemical family filter
        if 'chemical_family' in filters:
            spectrum_family = metadata.get('CHEMICAL FAMILY') or metadata.get('Chemical Family', '')
            if not spectrum_family or filters['chemical_family'].lower() not in spectrum_family.lower():
                return False
        
        # Hey classification filter
        if 'hey_classification' in filters:
            spectrum_hey = metadata.get('HEY CLASSIFICATION', '')
            if not spectrum_hey or filters['hey_classification'].lower() not in spectrum_hey.lower():
                return False
        
        # Element filters - match original app behavior
        # Original app used "CHEMISTRY ELEMENTS" field, not "FORMULA"
        chemistry_elements = metadata.get('CHEMISTRY ELEMENTS', '') or metadata.get('Chemistry Elements', '')
        formula = metadata.get('FORMULA', '') or metadata.get('Formula', '')
        
        # Try chemistry elements field first (original app format), then formula as fallback
        elements_source = chemistry_elements if chemistry_elements else formula
        
        # If any element filters are specified, we need element data to check against
        has_element_filters = any(key in filters for key in ['only_elements', 'required_elements', 'exclude_elements'])
        
        if has_element_filters:
            if not elements_source:
                # No element data available but element filters are specified - spectrum fails
                return False
            
            # Parse elements from either chemistry elements or formula
            if chemistry_elements:
                # Original app format: comma-separated elements (e.g., "Al, Si, O")
                elements_in_spectrum = set([elem.strip().upper() for elem in chemistry_elements.split(",")])
            else:
                # Fallback: extract elements from formula (simplified parsing)
                import re
                elements_in_spectrum = set(re.findall(r'[A-Z][a-z]?', formula))
            
            # Only elements filter
            if 'only_elements' in filters:
                allowed_elements = set(filters['only_elements'])
                if not elements_in_spectrum.issubset(allowed_elements):
                    return False
            
            # Required elements filter
            if 'required_elements' in filters:
                required_elements = set(filters['required_elements'])
                if not required_elements.issubset(elements_in_spectrum):
                    return False
            
            # Exclude elements filter
            if 'exclude_elements' in filters:
                excluded_elements = set(filters['exclude_elements'])
                if elements_in_spectrum.intersection(excluded_elements):
                    return False
        
        return True

    def search_filtered_candidates(self, candidates, algorithm, n_matches, threshold):
        """Perform search algorithm on filtered candidate set."""
        matches = []
        
        for name, data in candidates:
            try:
                wavenumbers = data.get('wavenumbers', [])
                intensities = data.get('intensities', [])
                
                # Ensure we have data - check length instead of boolean
                if len(wavenumbers) == 0 or len(intensities) == 0:
                    continue
                
                # Calculate similarity score based on algorithm
                if algorithm == "correlation" and len(wavenumbers) > 0 and len(intensities) > 0:
                    score = self.calculate_correlation_score(wavenumbers, intensities)
                elif algorithm == "peak" and len(wavenumbers) > 0 and len(intensities) > 0:
                    score = self.calculate_peak_score(wavenumbers, intensities)
                elif algorithm == "combined" and len(wavenumbers) > 0 and len(intensities) > 0:
                    score = self.calculate_combined_score(wavenumbers, intensities)
                elif algorithm == "DTW" and len(wavenumbers) > 0 and len(intensities) > 0:
                    # DTW algorithm uses Dynamic Time Warping
                    score = self.calculate_dtw_score(wavenumbers, intensities)
                else:
                    # Fallback to correlation
                    if len(wavenumbers) > 0 and len(intensities) > 0:
                        score = self.calculate_correlation_score(wavenumbers, intensities)
                    else:
                        score = 0.0
                
                if score >= threshold:
                    matches.append({
                        'name': name,
                        'score': score,
                        'metadata': data.get('metadata', {}),
                        'peaks': data.get('peaks', []),
                        'timestamp': data.get('timestamp', '')
                    })
                    
            except Exception as e:
                # Log error but continue processing other candidates
                continue
        
        # Sort by score
        matches.sort(key=lambda x: x['score'], reverse=True)
        return matches[:n_matches]

    def calculate_correlation_score(self, db_wavenumbers, db_intensities):
        """Calculate correlation score between current spectrum and database spectrum."""
        try:
            # Convert to numpy arrays with explicit float conversion
            db_wavenumbers = np.array(db_wavenumbers, dtype=float)
            db_intensities = np.array(db_intensities, dtype=float)
            
            # Check for empty or invalid data
            if len(db_wavenumbers) == 0 or len(db_intensities) == 0:
                return 0.0
            
            # Interpolate to common wavenumber grid
            common_wavenumbers = np.linspace(
                max(self.current_wavenumbers.min(), db_wavenumbers.min()),
                min(self.current_wavenumbers.max(), db_wavenumbers.max()),
                min(len(self.current_wavenumbers), len(db_wavenumbers))
            )
            
            query_interp = np.interp(common_wavenumbers, self.current_wavenumbers, self.processed_intensities)
            db_interp = np.interp(common_wavenumbers, db_wavenumbers, db_intensities)
            
            # Check for zero variance (constant spectra)
            query_std = np.std(query_interp)
            db_std = np.std(db_interp)
            
            if query_std == 0 or db_std == 0:
                return 0.0
            
            # Normalize to zero mean, unit variance
            query_norm = (query_interp - np.mean(query_interp)) / query_std
            db_norm = (db_interp - np.mean(db_interp)) / db_std
            
            # Calculate correlation
            correlation = np.corrcoef(query_norm, db_norm)[0, 1]
            
            # Convert correlation (-1 to 1) to similarity score (0 to 1)
            # Use absolute correlation for spectral matching (shape similarity)
            similarity = abs(correlation)
            
            return max(0, min(1, similarity))  # Ensure [0, 1] range
            
        except Exception as e:
            print(f"Error in correlation score calculation: {e}")
            return 0.0

    def calculate_dtw_score(self, db_wavenumbers, db_intensities):
        """Calculate DTW (Dynamic Time Warping) similarity score between current spectrum and database spectrum."""
        try:
            # Import fastdtw
            from fastdtw import fastdtw
            
            # Convert to numpy arrays with explicit float conversion
            db_wavenumbers = np.array(db_wavenumbers, dtype=float)
            db_intensities = np.array(db_intensities, dtype=float)
            
            # Check for empty or invalid data
            if len(db_wavenumbers) == 0 or len(db_intensities) == 0:
                return 0.0
            
            # Find overlapping wavenumber region
            overlap_start = max(self.current_wavenumbers.min(), db_wavenumbers.min())
            overlap_end = min(self.current_wavenumbers.max(), db_wavenumbers.max())
            
            # Check for sufficient overlap (at least 50% of either spectrum)
            query_range = self.current_wavenumbers.max() - self.current_wavenumbers.min()
            db_range = db_wavenumbers.max() - db_wavenumbers.min()
            overlap_range = overlap_end - overlap_start
            
            if overlap_range < 0.3 * min(query_range, db_range):
                return 0.0  # Insufficient overlap
            
            # Create common wavenumber grid with reasonable density
            # Use fewer points for DTW to reduce computation time
            n_points = min(200, len(self.current_wavenumbers), len(db_wavenumbers))
            common_wavenumbers = np.linspace(overlap_start, overlap_end, n_points)
            
            # Interpolate both spectra to common grid
            query_interp = np.interp(common_wavenumbers, self.current_wavenumbers, self.processed_intensities)
            db_interp = np.interp(common_wavenumbers, db_wavenumbers, db_intensities)
            
            # Check for zero variance
            if np.std(query_interp) == 0 or np.std(db_interp) == 0:
                return 0.0
            
            # Normalize both spectra to [0, 1] range
            query_min, query_max = np.min(query_interp), np.max(query_interp)
            db_min, db_max = np.min(db_interp), np.max(db_interp)
            
            if query_max > query_min:
                query_norm = (query_interp - query_min) / (query_max - query_min)
            else:
                query_norm = query_interp
                
            if db_max > db_min:
                db_norm = (db_interp - db_min) / (db_max - db_min)
            else:
                db_norm = db_interp
            
            # Convert to lists for fastdtw (it expects sequences, not numpy arrays)
            query_list = query_norm.tolist()
            db_list = db_norm.tolist()
            
            # Define scalar distance function for spectral intensities
            def spectral_distance(a, b):
                return abs(float(a) - float(b))
            
            # Apply DTW with scalar distance
            distance, path = fastdtw(query_list, db_list, dist=spectral_distance)
            
            # Convert distance to similarity score
            # Normalize distance by path length to account for different spectrum lengths
            if len(path) > 0:
                normalized_distance = distance / len(path)
                
                # Convert to similarity using exponential decay
                # Scale the distance to get reasonable similarity values
                scaled_distance = normalized_distance * 2.0  # Adjust scaling factor
                similarity = np.exp(-scaled_distance)
                
                return max(0, min(1, similarity))  # Ensure [0, 1] range
            else:
                return 0.0
            
        except ImportError:
            # Fallback to correlation if fastdtw is not available
            return self.calculate_correlation_score(db_wavenumbers, db_intensities)
        except Exception as e:
            print(f"Error in DTW score calculation: {e}")
            return 0.0

    def calculate_peak_score(self, db_wavenumbers, db_intensities):
        """Calculate peak-based similarity score between current spectrum and database spectrum."""
        try:
            # Get peaks from current spectrum
            if self.detected_peaks is None or len(self.detected_peaks) == 0:
                return 0.0
            
            current_peak_positions = self.current_wavenumbers[self.detected_peaks]
            current_peak_intensities = self.processed_intensities[self.detected_peaks]
            
            # Find peaks in database spectrum with explicit float conversion
            db_wavenumbers = np.array(db_wavenumbers, dtype=float)
            db_intensities = np.array(db_intensities, dtype=float)
            
            # Check for empty or invalid data
            if len(db_wavenumbers) == 0 or len(db_intensities) == 0:
                return 0.0
            
            db_peaks, _ = find_peaks(db_intensities, height=np.max(db_intensities) * 0.1)
            
            if len(db_peaks) == 0:
                return 0.0
            
            db_peak_positions = db_wavenumbers[db_peaks]
            db_peak_intensities = db_intensities[db_peaks]
            
            # Calculate peak matching score
            tolerance = 20  # cm⁻¹ tolerance for peak matching
            matched_peaks = 0
            total_intensity_diff = 0
            
            for curr_pos, curr_int in zip(current_peak_positions, current_peak_intensities):
                # Find closest peak in database spectrum
                distances = np.abs(db_peak_positions - curr_pos)
                min_dist_idx = np.argmin(distances)
                min_distance = distances[min_dist_idx]
                
                if min_distance <= tolerance:
                    matched_peaks += 1
                    # Calculate intensity similarity (normalized)
                    db_int = db_peak_intensities[min_dist_idx]
                    curr_norm = curr_int / np.max(current_peak_intensities)
                    db_norm = db_int / np.max(db_peak_intensities)
                    intensity_diff = abs(curr_norm - db_norm)
                    total_intensity_diff += intensity_diff
            
            if matched_peaks == 0:
                return 0.0
            
            # Calculate score based on percentage of matched peaks and intensity similarity
            peak_match_ratio = matched_peaks / len(current_peak_positions)
            avg_intensity_similarity = 1 - (total_intensity_diff / matched_peaks)
            
            # Combined score (weighted average)
            score = 0.7 * peak_match_ratio + 0.3 * avg_intensity_similarity
            return max(0, min(1, score))
            
        except Exception:
            return 0.0

    def calculate_combined_score(self, db_wavenumbers, db_intensities):
        """Calculate combined similarity score using both correlation and DTW."""
        try:
            # Get individual scores
            correlation_score = self.calculate_correlation_score(db_wavenumbers, db_intensities)
            dtw_score = self.calculate_dtw_score(db_wavenumbers, db_intensities)
            
            # Combined score (weighted average)
            # Give more weight to DTW as it's more sophisticated for spectral matching
            combined_score = 0.3 * correlation_score + 0.7 * dtw_score
            
            return max(0, min(1, combined_score))
            
        except Exception as e:
            print(f"Error in combined score calculation: {e}")
            return 0.0

    def create_filter_summary(self, filters):
        """Create a summary string of applied filters."""
        summary_parts = []
        
        if 'peak_positions' in filters:
            summary_parts.append(f"Peaks: {', '.join(map(str, filters['peak_positions']))}")
        if 'chemical_family' in filters:
            summary_parts.append(f"Family: {filters['chemical_family']}")
        if 'hey_classification' in filters:
            summary_parts.append(f"Hey: {filters['hey_classification']}")
        if 'only_elements' in filters:
            summary_parts.append(f"Only: {', '.join(filters['only_elements'])}")
        if 'required_elements' in filters:
            summary_parts.append(f"Required: {', '.join(filters['required_elements'])}")
        if 'exclude_elements' in filters:
            summary_parts.append(f"Exclude: {', '.join(filters['exclude_elements'])}")
        
        return "; ".join(summary_parts) if summary_parts else "None"

    def display_search_results(self, matches, search_type, additional_info=""):
        """Display search results in the comprehensive results window."""
        if not matches:
            # Show simple message for no results
            result_text = f"{search_type} Results\n{'='*40}\n\n"
            result_text += "No matches found above threshold.\n"
            if additional_info:
                result_text += f"\n{additional_info}\n"
            result_text += "\nTry lowering the similarity threshold or adding more spectra to the database."
            self.search_results_text.setPlainText(result_text)
            return
        
        # Enhance matches with actual spectrum data from database
        enhanced_matches = []
        for match in matches:
            match_name = match.get('name')
            if match_name in self.raman_db.database:
                db_entry = self.raman_db.database[match_name]
                enhanced_match = match.copy()
                enhanced_match['wavenumbers'] = db_entry.get('wavenumbers', [])
                enhanced_match['intensities'] = db_entry.get('intensities', [])
                enhanced_matches.append(enhanced_match)
            else:
                # Add empty spectrum data if not found
                enhanced_match = match.copy()
                enhanced_match['wavenumbers'] = []
                enhanced_match['intensities'] = []
                enhanced_matches.append(enhanced_match)
        
        # Show brief summary in the search tab
        result_text = f"{search_type} Results\n{'='*40}\n\n"
        if additional_info:
            result_text += f"{additional_info}\n\n"
        
        result_text += f"Found {len(enhanced_matches)} matches. Opening detailed results window...\n\n"
        result_text += "Top 3 matches:\n"
        
        for i, match in enumerate(enhanced_matches[:3], 1):
            result_text += f"{i}. {match['name']} (Score: {match['score']:.3f})\n"
            metadata = match.get('metadata', {})
            if metadata.get('NAME'):
                result_text += f"   Mineral: {metadata['NAME']}\n"
        
        self.search_results_text.setPlainText(result_text)
        
        # Launch the comprehensive search results window
        try:
            self.search_results_window = SearchResultsWindow(
                enhanced_matches,
                self.current_wavenumbers,
                self.processed_intensities,
                search_type,
                parent=self
            )
            self.search_results_window.show()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open search results window:\n{str(e)}"
            )

    def update_metadata_filter_options(self):
        """Update the dropdown options for chemical family and Hey classification."""
        # Get unique values from database
        chemical_families = set()
        hey_classifications = set()
        
        for data in self.raman_db.database.values():
            metadata = data.get('metadata', {})
            
            # Chemical family
            family = metadata.get('CHEMICAL FAMILY') or metadata.get('Chemical Family')
            if family and isinstance(family, str):
                chemical_families.add(family.strip())
            
            # Hey classification
            hey_class = metadata.get('HEY CLASSIFICATION')
            if hey_class and isinstance(hey_class, str):
                hey_classifications.add(hey_class.strip())
        
        # Update comboboxes
        if hasattr(self, 'chemical_family_combo'):
            self.chemical_family_combo.clear()
            self.chemical_family_combo.addItem("")  # Empty option
            self.chemical_family_combo.addItems(sorted(chemical_families))
        
        if hasattr(self, 'hey_classification_combo'):
            self.hey_classification_combo.clear()
            self.hey_classification_combo.addItem("")  # Empty option
            self.hey_classification_combo.addItems(sorted(hey_classifications))

    def update_advanced_algorithm_display(self):
        """Update the algorithm display in the advanced search tab."""
        if hasattr(self, 'current_algorithm_label'):
            current_algo = self.algorithm_combo.currentText()
            self.current_algorithm_label.setText(f"Current: {current_algo}")

    def analyze_mixed_minerals(self):
        """Launch the mixed mineral analysis window."""
        if self.current_wavenumbers is None or self.current_intensities is None:
            QMessageBox.warning(
                self, 
                "No Data", 
                "Please load a spectrum first before running mixed mineral analysis."
            )
            return
        
        try:
            # Try to import and launch the Qt6 version of mixed mineral analysis
            from mixed_mineral_enhancement import EnhancedMixedMineralAnalysis
            
            # Create a wrapper object that mimics the expected interface
            class Qt6AppWrapper:
                def __init__(self, qt6_app):
                    self.qt6_app = qt6_app
                    self.root = None  # Will be set by mixed mineral analysis
                    
                    # Create a wrapper for the raman database to match expected interface
                    class RamanWrapper:
                        def __init__(self, raman_db, qt6_app):
                            self.database = raman_db.database
                            self.current_wavenumbers = qt6_app.current_wavenumbers
                            self.current_spectra = qt6_app.current_intensities
                            self.processed_spectra = qt6_app.processed_intensities
                    
                    # Set the raman attribute directly (not as a property)
                    self.raman = RamanWrapper(self.qt6_app.raman_db, self.qt6_app)
            
            # Create wrapper and launch analysis
            wrapper = Qt6AppWrapper(self)
            analysis = EnhancedMixedMineralAnalysis(wrapper)
            
            # Show info dialog first
            QMessageBox.information(
                self,
                "Mixed Mineral Analysis",
                "Launching Enhanced Mixed Mineral Analysis...\n\n"
                "This will open a new window for interactive mineral component analysis.\n"
                "For best results, it's recommended to:\n\n"
                "1. Load and process your spectrum\n"
                "2. Perform background subtraction\n"
                "3. Apply any necessary smoothing\n"
                "4. Then run Mixed Mineral Analysis"
            )
            
            # Launch the analysis
            analysis.launch_analysis()
            
        except ImportError:
            QMessageBox.warning(
                self,
                "Mixed Mineral Analysis",
                "Mixed mineral analysis module not available.\n\n"
                "This feature requires the enhanced mixed mineral analysis module."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error launching mixed mineral analysis:\n{str(e)}\n\n"
                "Please ensure all required dependencies are installed."
            )

    def create_advanced_tab(self):
        """Create the advanced analysis tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Primary Analysis Tools group (dark blue buttons)
        primary_group = QGroupBox("Primary Analysis Tools")
        primary_layout = QVBoxLayout(primary_group)
        
        # Dark blue button style
        dark_blue_style = """
            QPushButton {
                background-color: #1E3A8A;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1E40AF;
            }
            QPushButton:pressed {
                background-color: #1D4ED8;
            }
        """
        
        # Multi-spectrum comparison
        multi_spectrum_btn = QPushButton("Multi-Spectrum Comparison")
        multi_spectrum_btn.clicked.connect(self.launch_multi_spectrum_manager)
        multi_spectrum_btn.setStyleSheet(dark_blue_style)
        primary_layout.addWidget(multi_spectrum_btn)
        
        # Spectral deconvolution
        deconvolution_btn = QPushButton("Spectral Deconvolution")
        deconvolution_btn.clicked.connect(self.launch_deconvolution)
        deconvolution_btn.setStyleSheet(dark_blue_style)
        primary_layout.addWidget(deconvolution_btn)
        
        # Batch peak fitting (if available)
        if BATCH_AVAILABLE:
            batch_peak_fitting_btn = QPushButton("Batch Peak Fitting")
            batch_peak_fitting_btn.clicked.connect(self.launch_batch_peak_fitting)
            batch_peak_fitting_btn.setStyleSheet(dark_blue_style)
            primary_layout.addWidget(batch_peak_fitting_btn)
        else:
            # Show info about missing batch capabilities
            missing_label = QLabel("Batch Peak Fitting: Module not available")
            missing_label.setStyleSheet("color: orange; font-style: italic; padding: 8px; background-color: #FFF3E0; border-radius: 4px;")
            primary_layout.addWidget(missing_label)
        
        layout.addWidget(primary_group)
        
        # Spatial Analysis Tools group
        spatial_group = QGroupBox("Spatial Analysis Tools")
        spatial_layout = QVBoxLayout(spatial_group)
        
        # Spatial analysis button style (teal/green)
        spatial_style = """
            QPushButton {
                background-color: #0D9488;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0F766E;
            }
            QPushButton:pressed {
                background-color: #115E59;
            }
        """
        
        # Map analysis
        map_analysis_btn = QPushButton("Map Analysis")
        map_analysis_btn.clicked.connect(self.launch_map_analysis)
        map_analysis_btn.setStyleSheet(spatial_style)
        spatial_layout.addWidget(map_analysis_btn)
        
        # Cluster analysis
        cluster_analysis_btn = QPushButton("Cluster Analysis")
        cluster_analysis_btn.clicked.connect(self.launch_cluster_analysis)
        cluster_analysis_btn.setStyleSheet(spatial_style)
        spatial_layout.addWidget(cluster_analysis_btn)
        
        # Polarization analysis
        polarization_analysis_btn = QPushButton("Polarization Analysis")
        polarization_analysis_btn.clicked.connect(self.launch_polarization_analysis)
        polarization_analysis_btn.setStyleSheet(spatial_style)
        spatial_layout.addWidget(polarization_analysis_btn)
        
        layout.addWidget(spatial_group)
        
        # Mechanical Analysis Tools group
        mechanical_group = QGroupBox("Mechanical Analysis Tools")
        mechanical_layout = QVBoxLayout(mechanical_group)
        
        # Mechanical analysis button style (purple)
        mechanical_style = """
            QPushButton {
                background-color: #7C3AED;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #8B5CF6;
            }
            QPushButton:pressed {
                background-color: #6D28D9;
            }
        """
        
        # Stress/Strain analysis
        stress_strain_btn = QPushButton("Stress/Strain Analysis")
        stress_strain_btn.clicked.connect(self.launch_stress_strain_analysis)
        stress_strain_btn.setStyleSheet(mechanical_style)
        mechanical_layout.addWidget(stress_strain_btn)
        
        # Chemical strain analysis
        chemical_strain_btn = QPushButton("Chemical Strain Analysis")
        chemical_strain_btn.clicked.connect(self.launch_chemical_strain_analysis)
        chemical_strain_btn.setStyleSheet(mechanical_style)
        mechanical_layout.addWidget(chemical_strain_btn)
        
        layout.addWidget(mechanical_group)
        
        # Additional Processing Tools group
        processing_group = QGroupBox("Additional Processing Tools")
        processing_layout = QVBoxLayout(processing_group)
        
        # Additional tools button style (orange)
        additional_style = """
            QPushButton {
                background-color: #EA580C;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #DC2626;
            }
            QPushButton:pressed {
                background-color: #B91C1C;
            }
        """
        
        # Peak fitting analysis
        peak_fitting_btn = QPushButton("Peak Fitting Analysis")
        peak_fitting_btn.clicked.connect(self.launch_peak_fitting)
        peak_fitting_btn.setStyleSheet(additional_style)
        processing_layout.addWidget(peak_fitting_btn)
        
        # Baseline correction tools
        baseline_btn = QPushButton("Advanced Baseline Correction")
        baseline_btn.clicked.connect(self.launch_baseline_tools)
        baseline_btn.setStyleSheet(additional_style)
        processing_layout.addWidget(baseline_btn)
        
        # Normalization tools
        normalization_btn = QPushButton("Advanced Normalization")
        normalization_btn.clicked.connect(self.launch_normalization_tools)
        normalization_btn.setStyleSheet(additional_style)
        processing_layout.addWidget(normalization_btn)
        
        layout.addWidget(processing_group)
        
        # Export and Reporting group
        export_group = QGroupBox("Export and Reporting")
        export_layout = QVBoxLayout(export_group)
        
        # Export tools button style (gray)
        export_style = """
            QPushButton {
                background-color: #6B7280;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #4B5563;
            }
            QPushButton:pressed {
                background-color: #374151;
            }
        """
        
        # Batch export
        batch_export_btn = QPushButton("Batch Export Tools")
        batch_export_btn.clicked.connect(self.launch_batch_export)
        batch_export_btn.setStyleSheet(export_style)
        export_layout.addWidget(batch_export_btn)
        
        # Report generation
        report_btn = QPushButton("Generate Analysis Report")
        report_btn.clicked.connect(self.generate_analysis_report)
        report_btn.setStyleSheet(export_style)
        export_layout.addWidget(report_btn)
        
        layout.addWidget(export_group)
        
        layout.addStretch()
        
        return tab

    def launch_peak_fitting(self):
        """Launch peak fitting analysis tool."""
        QMessageBox.information(
            self,
            "Peak Fitting",
            "Peak fitting analysis tool will be implemented.\n\n"
            "This will provide:\n"
            "• Gaussian and Lorentzian peak fitting\n"
            "• Multi-peak deconvolution\n"
            "• Peak parameter analysis\n"
            "• Goodness of fit statistics"
        )

    def launch_baseline_tools(self):
        """Launch advanced baseline correction tools."""
        QMessageBox.information(
            self,
            "Baseline Correction",
            "Advanced baseline correction tools will be implemented.\n\n"
            "This will provide:\n"
            "• Additional baseline algorithms\n"
            "• Interactive baseline selection\n"
            "• Baseline parameter optimization\n"
            "• Preview and comparison modes"
        )

    def launch_normalization_tools(self):
        """Launch advanced normalization tools."""
        QMessageBox.information(
            self,
            "Normalization Tools",
            "Advanced normalization tools will be implemented.\n\n"
            "This will provide:\n"
            "• Vector normalization\n"
            "• Area under curve normalization\n"
            "• Standard normal variate (SNV)\n"
            "• Multiple scatter correction (MSC)"
        )

    def launch_deconvolution(self):
        """Launch spectral deconvolution tool."""
        if self.current_wavenumbers is None or self.current_intensities is None:
            QMessageBox.warning(self, "No Data", "Load a spectrum first to perform deconvolution.")
            return
            
        try:
            # Import and launch the Qt6 spectral deconvolution module
            from peak_fitting_qt6 import launch_spectral_deconvolution
            
            # Launch with current spectrum data
            launch_spectral_deconvolution(
                self, 
                self.current_wavenumbers, 
                self.processed_intensities
            )
            
        except ImportError as e:
            QMessageBox.critical(
                self,
                "Module Error",
                f"Failed to import spectral deconvolution module:\n{str(e)}\n\n"
                "Make sure peak_fitting_qt6.py is available."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Launch Error", 
                f"Failed to launch spectral deconvolution:\n{str(e)}"
            )

    def launch_batch_export(self):
        """Launch batch export tools."""
        QMessageBox.information(
            self,
            "Batch Export",
            "Batch export tools will be implemented.\n\n"
            "This will provide:\n"
            "• Batch processing of multiple files\n"
            "• Format conversion utilities\n"
            "• Automated analysis workflows\n"
            "• Bulk data export options"
        )

    def generate_analysis_report(self):
        """Generate comprehensive analysis report."""
        if self.current_wavenumbers is None:
            QMessageBox.warning(self, "No Data", "Load a spectrum first to generate a report.")
            return
            
        QMessageBox.information(
            self,
            "Analysis Report",
            "Analysis report generation will be implemented.\n\n"
            "This will provide:\n"
            "• Comprehensive spectrum analysis\n"
            "• Peak identification and characterization\n"
            "• Search results and matches\n"
            "• Exportable PDF and HTML reports"
        )

    def launch_batch_peak_fitting(self):
        """Launch batch peak fitting processing."""
        if not BATCH_AVAILABLE:
            QMessageBox.warning(self, "Not Available", 
                              "Batch processing module is not available.")
            return
        
        try:
            # Launch batch peak fitting with current spectrum data if available
            if self.current_wavenumbers is not None and self.current_intensities is not None:
                launch_batch_peak_fitting(self, self.current_wavenumbers, 
                                         self.processed_intensities if self.processed_intensities is not None 
                                         else self.current_intensities)
            else:
                # Launch without initial data - user can load files in the batch interface
                launch_batch_peak_fitting(self)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", 
                               f"Failed to launch batch processing: {str(e)}")

    def launch_map_analysis(self):
        """Launch Raman mapping analysis tool."""
        try:
            # Import and launch the Qt6 map analysis module
            from map_analysis_2d_qt6 import TwoDMapAnalysisQt6
            
            # Create and show the map analysis window
            self.map_analysis_window = TwoDMapAnalysisQt6()
            self.map_analysis_window.show()
            
            # Show success message
            self.statusBar().showMessage("Map Analysis tool launched successfully")
            
        except ImportError as e:
            QMessageBox.critical(
                self,
                "Map Analysis Error",
                f"Failed to import map analysis module:\n{str(e)}\n\n"
                "Please ensure map_analysis_2d_qt6.py is in the same directory."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Map Analysis Error",
                f"Failed to launch map analysis:\n{str(e)}"
            )

    def launch_cluster_analysis(self):
        """Launch cluster analysis tool."""
        try:
            # Import and launch the cluster analysis module
            from raman_cluster_analysis_qt6 import launch_cluster_analysis
            
            # Launch the cluster analysis window - pass self as both parent and raman_app
            self.cluster_analysis_window = launch_cluster_analysis(self, self)
            
            # Show success message in status bar
            self.statusBar().showMessage("Cluster Analysis window launched successfully")
            
        except ImportError as e:
            QMessageBox.critical(
                self,
                "Import Error",
                f"Failed to import cluster analysis module:\n{str(e)}\n\n"
                "Please ensure raman_cluster_analysis_qt6.py is in the same directory."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Cluster Analysis Error",
                f"Failed to launch cluster analysis:\n{str(e)}"
            )

    def launch_polarization_analysis(self):
        """Launch polarization analysis tool."""
        if self.current_wavenumbers is None or self.current_intensities is None:
            QMessageBox.warning(self, "No Data", "Load a spectrum first to perform polarization analysis.")
            return
            
        try:
            # Import and launch the polarization analysis module
            QMessageBox.information(
                self,
                "Polarization Analysis",
                "Launching Polarization Analysis...\n\n"
                "This feature provides:\n"
                "• Polarized Raman spectroscopy analysis\n"
                "• Angular dependence measurements\n"
                "• Crystal orientation determination\n"
                "• Tensor component analysis"
            )
            
            # TODO: Replace with actual polarization analysis module
            # from polarization_analysis_qt6 import launch_polarization_analysis
            # launch_polarization_analysis(self, self.current_wavenumbers, self.processed_intensities)
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Polarization Analysis Error",
                f"Failed to launch polarization analysis:\n{str(e)}"
            )

    def launch_stress_strain_analysis(self):
        """Launch stress/strain analysis tool."""
        if self.current_wavenumbers is None or self.current_intensities is None:
            QMessageBox.warning(self, "No Data", "Load a spectrum first to perform stress/strain analysis.")
            return
            
        try:
            # Import and launch the stress/strain analysis module
            QMessageBox.information(
                self,
                "Stress/Strain Analysis",
                "Launching Stress/Strain Analysis...\n\n"
                "This feature provides:\n"
                "• Peak shift analysis for stress determination\n"
                "• Strain calculation from lattice deformation\n"
                "• Pressure coefficient analysis\n"
                "• Mechanical property evaluation"
            )
            
            # TODO: Replace with actual stress/strain analysis module
            # from stress_strain_analysis_qt6 import launch_stress_strain_analysis
            # launch_stress_strain_analysis(self, self.current_wavenumbers, self.processed_intensities)
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Stress/Strain Analysis Error",
                f"Failed to launch stress/strain analysis:\n{str(e)}"
            )

    def launch_chemical_strain_analysis(self):
        """Launch chemical strain analysis tool."""
        if self.current_wavenumbers is None or self.current_intensities is None:
            QMessageBox.warning(self, "No Data", "Load a spectrum first to perform chemical strain analysis.")
            return
            
        try:
            # Import and launch the chemical strain analysis module
            QMessageBox.information(
                self,
                "Chemical Strain Analysis",
                "Launching Chemical Strain Analysis...\n\n"
                "This feature provides:\n"
                "• Chemical composition-induced strain analysis\n"
                "• Lattice parameter variation studies\n"
                "• Solid solution strain effects\n"
                "• Compositional gradient analysis"
            )
            
            # TODO: Replace with actual chemical strain analysis module
            # from chemical_strain_analysis_qt6 import launch_chemical_strain_analysis
            # launch_chemical_strain_analysis(self, self.current_wavenumbers, self.processed_intensities)
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Chemical Strain Analysis Error",
                f"Failed to launch chemical strain analysis:\n{str(e)}"
            )

    def export_database_file(self):
        """Export the database to a file."""
        from database_browser_qt6 import DatabaseBrowserQt6
        
        # Create a temporary browser instance just for export
        temp_browser = DatabaseBrowserQt6(self.raman_db, parent=self)
        temp_browser.export_database()
        
        # Update our database stats after export (in case anything changed)
        self.update_database_stats()

    def import_database_file(self):
        """Import the database from a file."""
        from database_browser_qt6 import DatabaseBrowserQt6
        
        # Create a temporary browser instance just for import
        temp_browser = DatabaseBrowserQt6(self.raman_db, parent=self)
        temp_browser.import_database()
        
        # Update our database stats after import
        self.update_database_stats()

    def launch_mineral_modes_browser(self):
        """Launch the mineral modes database browser."""
        try:
            from mineral_modes_browser_qt6 import MineralModesDatabaseQt6
            
            # Create and show the mineral modes browser window
            self.mineral_modes_browser = MineralModesDatabaseQt6(parent=self)
            self.mineral_modes_browser.show()
            
            # Show success message
            self.statusBar().showMessage("Mineral Modes Database browser launched successfully")
            
        except ImportError as e:
            QMessageBox.critical(
                self,
                "Import Error",
                f"Failed to import mineral modes browser module:\n{str(e)}\n\n"
                "Please ensure mineral_modes_browser_qt6.py is in the same directory."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Launch Error",
                f"Failed to launch mineral modes browser:\n{str(e)}"
            )

    def update_window_title(self, filename=None):
        if filename:
            self.setWindowTitle(f"RamanLab: Raman Spectrum Analysis - {filename}")
        else:
            self.setWindowTitle("RamanLab: Raman Spectrum Analysis")

    # Import Data Methods
    def import_raman_spectral_map(self):
        """Import Raman spectral map data and convert to pkl format for mapping and clustering."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Raman Spectral Map",
            QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation),
            "Text files (*.txt);;CSV files (*.csv);;Data files (*.dat);;All files (*.*)"
        )
        
        if file_path:
            # Create and show progress dialog
            self.progress_dialog = QProgressDialog("Processing Raman spectral map data...", "Cancel", 0, 100, self)
            self.progress_dialog.setWindowTitle("Importing Raman Map")
            self.progress_dialog.setModal(True)
            self.progress_dialog.setMinimumDuration(0)
            self.progress_dialog.setValue(0)
            self.progress_dialog.show()
            
            # Create worker thread
            self.import_worker = RamanMapImportWorker(file_path)
            self.import_worker.progress.connect(self.progress_dialog.setValue)
            self.import_worker.status_update.connect(self.progress_dialog.setLabelText)
            self.import_worker.finished.connect(self.on_import_finished)
            self.import_worker.error.connect(self.on_import_error)
            self.progress_dialog.canceled.connect(self.import_worker.cancel)
            
            # Start the worker
            self.import_worker.start()

    def on_import_finished(self, map_data):
        """Handle successful completion of import."""
        self.progress_dialog.close()
        
        try:
            # Save as PKL file
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Raman Map Data as PKL",
                str(Path(self.import_worker.file_path).with_suffix('.pkl')),
                "Pickle files (*.pkl);;All files (*.*)"
            )
            
            if save_path:
                # Show progress for saving
                save_progress = QProgressDialog("Saving PKL file...", None, 0, 0, self)
                save_progress.setWindowTitle("Saving")
                save_progress.setModal(True)
                save_progress.show()
                
                # Process events to show the dialog
                QApplication.processEvents()
                
                with open(save_path, 'wb') as f:
                    pickle.dump(map_data, f)
                
                save_progress.close()
                
                # Display summary
                self.display_map_data_summary(map_data, save_path)
                self.status_bar.showMessage(f"Converted and saved: {Path(save_path).name}")
                
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save map data:\n{str(e)}")

    def on_import_error(self, error_message):
        """Handle import error."""
        self.progress_dialog.close()
        QMessageBox.critical(self, "Import Error", f"Failed to import Raman spectral map:\n{error_message}")

    def parse_raman_spectral_map(self, file_path, progress_callback=None, status_callback=None):
        """Parse Raman spectral map data where first row is Raman shifts and first two columns are X,Y positions."""
        try:
            if status_callback:
                status_callback("Reading file...")
            
            # Read the file line by line to handle inconsistent column counts
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            if len(lines) < 2:
                raise ValueError("File must have at least 2 lines (header + data)")
            
            total_lines = len(lines) - 1  # Exclude header
            
            if status_callback:
                status_callback("Parsing header...")
            if progress_callback:
                progress_callback(5)
            
            # Parse the first line to get Raman shifts
            first_line = lines[0].strip().split()
            print(f"First line has {len(first_line)} columns")
            
            # Extract Raman shifts from first row (skip first two cells which should be X,Y labels)
            if len(first_line) < 3:
                raise ValueError("First line must have at least 3 columns (X, Y, and Raman shifts)")
            
            raman_shifts = np.array([float(x) for x in first_line[2:]])
            print(f"Extracted {len(raman_shifts)} Raman shifts from header")
            
            # Process spatial data and spectra
            spatial_data = []
            spectra_data = []
            skipped_lines = 0
            
            if status_callback:
                status_callback(f"Processing {total_lines} spectra...")
            
            for i, line in enumerate(lines[1:], 1):  # Start from line 1 (skip header)
                # Update progress every 1000 lines or for small datasets, every 100 lines
                update_frequency = 1000 if total_lines > 10000 else max(100, total_lines // 100)
                
                if i % update_frequency == 0 and progress_callback:
                    progress_percent = 5 + int((i / total_lines) * 60)  # 5-65% for line processing
                    progress_callback(progress_percent)
                    if status_callback:
                        status_callback(f"Processing spectra: {i}/{total_lines} ({progress_percent-5}%)")
                
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                    
                try:
                    parts = line.split()
                    
                    # Check if we have enough columns
                    if len(parts) < 3:
                        skipped_lines += 1
                        if skipped_lines <= 5:  # Only print first few warnings
                            print(f"Skipping line {i+1}: insufficient columns ({len(parts)})")
                        continue
                    
                    x_pos = float(parts[0])  # X position in microns
                    y_pos = float(parts[1])  # Y position in microns
                    
                    # Extract spectrum intensities - handle variable column counts
                    # Take only as many intensity values as we have Raman shifts
                    spectrum_parts = parts[2:]
                    n_to_take = min(len(spectrum_parts), len(raman_shifts))
                    
                    if n_to_take < len(raman_shifts):
                        # Pad with zeros if we have fewer intensities than expected
                        spectrum = np.zeros(len(raman_shifts))
                        spectrum[:n_to_take] = [float(x) for x in spectrum_parts[:n_to_take]]
                        if skipped_lines <= 5:
                            print(f"Line {i+1}: Padded spectrum from {n_to_take} to {len(raman_shifts)} values")
                    else:
                        # Take only the number of intensities we need
                        spectrum = np.array([float(x) for x in spectrum_parts[:len(raman_shifts)]])
                        if len(spectrum_parts) > len(raman_shifts) and skipped_lines <= 5:
                            print(f"Line {i+1}: Truncated spectrum from {len(spectrum_parts)} to {len(raman_shifts)} values")
                    
                    spatial_data.append([x_pos, y_pos])
                    spectra_data.append(spectrum)
                    
                except (ValueError, IndexError) as e:
                    skipped_lines += 1
                    if skipped_lines <= 5:  # Only print first few errors
                        print(f"Skipping line {i+1}: {e}")
                    continue
            
            if skipped_lines > 5:
                print(f"... and {skipped_lines - 5} more lines were skipped")
            
            if len(spatial_data) == 0:
                raise ValueError("No valid data rows found in file")
            
            if status_callback:
                status_callback("Converting to arrays...")
            if progress_callback:
                progress_callback(70)
            
            spatial_data = np.array(spatial_data)
            spectra_data = np.array(spectra_data)
            
            print(f"Successfully processed {len(spatial_data)} positions")
            print(f"Spatial X range: {spatial_data[:, 0].min():.1f} to {spatial_data[:, 0].max():.1f}")
            print(f"Spatial Y range: {spatial_data[:, 1].min():.1f} to {spatial_data[:, 1].max():.1f}")
            print(f"Spectrum intensity range: {spectra_data.min():.2e} to {spectra_data.max():.2e}")
            
            # Create organized map data structure
            if status_callback:
                status_callback("Creating map data structure...")
            if progress_callback:
                progress_callback(75)
                
            map_data = {
                'raman_shifts': raman_shifts,
                'spatial_coordinates': spatial_data,
                'spectra': spectra_data,
                'metadata': {
                    'source_file': str(file_path),
                    'n_positions': len(spatial_data),
                    'n_wavenumbers': len(raman_shifts),
                    'spatial_range_x': [spatial_data[:, 0].min(), spatial_data[:, 0].max()],
                    'spatial_range_y': [spatial_data[:, 1].min(), spatial_data[:, 1].max()],
                    'wavenumber_range': [raman_shifts.min(), raman_shifts.max()],
                    'skipped_lines': skipped_lines,
                    'units': {
                        'spatial': 'microns',
                        'wavenumber': 'cm⁻¹',
                        'intensity': 'a.u.'
                    }
                }
            }
            
            # Create gridded data for easier mapping
            x_unique = np.unique(spatial_data[:, 0])
            y_unique = np.unique(spatial_data[:, 1])
            
            if len(x_unique) > 1 and len(y_unique) > 1:
                try:
                    if status_callback:
                        status_callback("Creating gridded data for mapping...")
                    if progress_callback:
                        progress_callback(80)
                    
                    # Create interpolated grid for mapping
                    xi, yi = np.meshgrid(
                        np.linspace(spatial_data[:, 0].min(), spatial_data[:, 0].max(), len(x_unique)),
                        np.linspace(spatial_data[:, 1].min(), spatial_data[:, 1].max(), len(y_unique))
                    )
                    
                    # Interpolate each wavenumber onto the grid
                    gridded_spectra = np.zeros((len(y_unique), len(x_unique), len(raman_shifts)))
                    
                    for i, wavenumber in enumerate(raman_shifts):
                        # Update progress for interpolation
                        if i % max(1, len(raman_shifts) // 10) == 0 and progress_callback:
                            interpolation_progress = 80 + int((i / len(raman_shifts)) * 15)  # 80-95%
                            progress_callback(interpolation_progress)
                            if status_callback:
                                status_callback(f"Interpolating wavenumber {i+1}/{len(raman_shifts)}...")
                        
                        intensities = spectra_data[:, i]
                        gridded_intensities = griddata(
                            spatial_data, intensities, (xi, yi), method='linear', fill_value=0
                        )
                        gridded_spectra[:, :, i] = gridded_intensities
                    
                    map_data['gridded_data'] = {
                        'x_grid': xi,
                        'y_grid': yi,
                        'spectra_grid': gridded_spectra
                    }
                    print("✓ Created gridded data for mapping")
                    
                except Exception as e:
                    print(f"Warning: Could not create gridded data: {e}")
            
            if status_callback:
                status_callback("Import complete!")
            if progress_callback:
                progress_callback(100)
            
            return map_data
            
        except Exception as e:
            raise Exception(f"Error parsing Raman spectral map: {str(e)}")

    def display_map_data_summary(self, map_data, save_path):
        """Display a summary of the imported map data."""
        metadata = map_data['metadata']
        
        summary = f"""Raman Spectral Map Import Summary
        
Source File: {Path(metadata['source_file']).name}
Saved to: {Path(save_path).name}

Data Dimensions:
• Number of positions: {metadata['n_positions']}
• Number of wavenumbers: {metadata['n_wavenumbers']}

Spatial Coverage:
• X range: {metadata['spatial_range_x'][0]:.1f} to {metadata['spatial_range_x'][1]:.1f} {metadata['units']['spatial']}
• Y range: {metadata['spatial_range_y'][0]:.1f} to {metadata['spatial_range_y'][1]:.1f} {metadata['units']['spatial']}

Spectral Coverage:
• Wavenumber range: {metadata['wavenumber_range'][0]:.1f} to {metadata['wavenumber_range'][1]:.1f} {metadata['units']['wavenumber']}

Gridded Data: {'Available' if 'gridded_data' in map_data else 'Not available'}

This data is now ready for:
• 2D mapping analysis
• Cluster analysis
• Principal component analysis
• Spatial correlation studies
"""
        
        QMessageBox.information(self, "Import Complete", summary)

    def import_line_scan_data(self):
        """Import line scan data and convert to pkl format."""
        QMessageBox.information(self, "Feature Coming Soon", 
                               "Line scan data import will be implemented next.\n"
                               "This will handle 1D spatial Raman data.")

    def import_point_data(self):
        """Import point measurement data and convert to pkl format."""
        QMessageBox.information(self, "Feature Coming Soon", 
                               "Point measurement data import will be implemented next.\n"
                               "This will handle individual spectrum collections.")

    def test_raman_map_import(self):
        """Test Raman map import functionality."""
        # Select file to test
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Raman Map File to Test",
            QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation),
            "Text files (*.txt);;CSV files (*.csv);;Data files (*.dat);;All files (*.*)"
        )
        
        if not file_path:
            return
            
        try:
            self.status_bar.showMessage("Testing Raman map import...")
            
            # Test the parsing function
            result = self.run_raman_map_test(file_path)
            
            if result:
                QMessageBox.information(
                    self,
                    "Test Successful",
                    f"Raman map import test completed successfully!\n\n"
                    f"✓ Processed {result['n_positions']} positions\n"
                    f"✓ {result['n_wavenumbers']} wavenumbers\n"
                    f"✓ Test PKL file saved\n"
                    f"✓ Visualization created\n\n"
                    f"Check the output files in the same directory as your input file."
                )
                self.status_bar.showMessage("Test completed successfully")
            else:
                QMessageBox.warning(
                    self,
                    "Test Failed",
                    "The Raman map import test failed. Check the console for error details."
                )
                self.status_bar.showMessage("Test failed")
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Test Error",
                f"Error during test:\n{str(e)}"
            )
            self.status_bar.showMessage("Test error")
    
    def run_raman_map_test(self, file_path):
        """Run the actual Raman map import test."""
        try:
            print(f"Testing with file: {file_path}")
            
            # Read the file line by line to handle inconsistent column counts
            print("Reading data...")
            
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            print(f"File has {len(lines)} lines")
            
            if len(lines) < 2:
                raise ValueError("File must have at least 2 lines (header + data)")
            
            # Parse the first line to get Raman shifts
            first_line = lines[0].strip().split()
            print(f"First line has {len(first_line)} columns")
            
            # Extract Raman shifts (skip first two columns which should be position labels)
            if len(first_line) < 3:
                raise ValueError("First line must have at least 3 columns (X, Y, and Raman shifts)")
            
            raman_shifts = np.array([float(x) for x in first_line[2:]])
            print(f"Extracted {len(raman_shifts)} Raman shifts")
            print(f"Raman shift range: {raman_shifts.min():.1f} to {raman_shifts.max():.1f} cm⁻¹")
            
            # Process a sample of the spatial data (first 100 lines to test)
            spatial_data = []
            spectra_data = []
            skipped_lines = 0
            
            for i, line in enumerate(lines[1:101]):  # Test with first 100 data lines
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                    
                try:
                    parts = line.split()
                    
                    # Check if we have enough columns
                    if len(parts) < 3:
                        skipped_lines += 1
                        if skipped_lines <= 5:
                            print(f"Skipping line {i+2}: insufficient columns ({len(parts)})")
                        continue
                    
                    x_pos = float(parts[0])
                    y_pos = float(parts[1])
                    
                    # Extract spectrum intensities - handle variable column counts
                    spectrum_parts = parts[2:]
                    n_to_take = min(len(spectrum_parts), len(raman_shifts))
                    
                    if n_to_take < len(raman_shifts):
                        # Pad with zeros if we have fewer intensities than expected
                        spectrum = np.zeros(len(raman_shifts))
                        spectrum[:n_to_take] = [float(x) for x in spectrum_parts[:n_to_take]]
                        if skipped_lines <= 5:
                            print(f"Line {i+2}: Padded spectrum from {n_to_take} to {len(raman_shifts)} values")
                    else:
                        # Take only the number of intensities we need
                        spectrum = np.array([float(x) for x in spectrum_parts[:len(raman_shifts)]])
                        if len(spectrum_parts) > len(raman_shifts) and skipped_lines <= 3:
                            print(f"Line {i+2}: Using {len(raman_shifts)} of {len(spectrum_parts)} available values")
                    
                    spatial_data.append([x_pos, y_pos])
                    spectra_data.append(spectrum)
                    
                    if i < 5:  # Print first few for verification
                        print(f"Position {i+1}: X={x_pos:.1f}, Y={y_pos:.1f}, Spectrum shape: {spectrum.shape}")
                        
                except (ValueError, IndexError) as e:
                    skipped_lines += 1
                    if skipped_lines <= 5:
                        print(f"Skipping line {i+2}: {e}")
                    continue
            
            if skipped_lines > 5:
                print(f"... and {skipped_lines - 5} more lines were skipped")
            
            if len(spatial_data) == 0:
                raise ValueError("No valid data rows found in test sample")
            
            spatial_data = np.array(spatial_data)
            spectra_data = np.array(spectra_data)
            
            print(f"\nProcessed {len(spatial_data)} positions")
            print(f"Spatial X range: {spatial_data[:, 0].min():.1f} to {spatial_data[:, 0].max():.1f}")
            print(f"Spatial Y range: {spatial_data[:, 1].min():.1f} to {spatial_data[:, 1].max():.1f}")
            print(f"Spectrum intensity range: {spectra_data.min():.1f} to {spectra_data.max():.1f}")
            
            # Create the map data structure
            map_data = {
                'raman_shifts': raman_shifts,
                'spatial_coordinates': spatial_data,
                'spectra': spectra_data,
                'metadata': {
                    'source_file': str(file_path),
                    'n_positions': len(spatial_data),
                    'n_wavenumbers': len(raman_shifts),
                    'spatial_range_x': [spatial_data[:, 0].min(), spatial_data[:, 0].max()],
                    'spatial_range_y': [spatial_data[:, 1].min(), spatial_data[:, 1].max()],
                    'wavenumber_range': [raman_shifts.min(), raman_shifts.max()],
                    'skipped_lines': skipped_lines,
                    'units': {
                        'spatial': 'microns',
                        'wavenumber': 'cm⁻¹',
                        'intensity': 'a.u.'
                    }
                }
            }
            
            # Save test PKL file
            test_pkl_path = Path(file_path).with_suffix('_test.pkl')
            with open(test_pkl_path, 'wb') as f:
                pickle.dump(map_data, f)
            
            print(f"\nTest PKL file saved: {test_pkl_path}")
            
            # Create a simple visualization
            plt.figure(figsize=(12, 4))
            
            # Plot 1: Spatial distribution
            plt.subplot(1, 3, 1)
            plt.scatter(spatial_data[:, 0], spatial_data[:, 1], c=range(len(spatial_data)), 
                       cmap='viridis', s=20)
            plt.xlabel('X position (μm)')
            plt.ylabel('Y position (μm)')
            plt.title('Spatial Distribution')
            plt.colorbar(label='Point index')
            
            # Plot 2: Sample spectrum
            plt.subplot(1, 3, 2)
            plt.plot(raman_shifts, spectra_data[len(spectra_data)//2])
            plt.xlabel('Raman Shift (cm⁻¹)')
            plt.ylabel('Intensity (a.u.)')
            plt.title('Sample Spectrum (middle point)')
            plt.grid(True, alpha=0.3)
            
            # Plot 3: Intensity map at a specific wavenumber
            plt.subplot(1, 3, 3)
            # Find index closest to 1000 cm⁻¹
            idx_1000 = np.argmin(np.abs(raman_shifts - 1000))
            intensities_1000 = spectra_data[:, idx_1000]
            scatter = plt.scatter(spatial_data[:, 0], spatial_data[:, 1], 
                                c=intensities_1000, cmap='hot', s=30)
            plt.xlabel('X position (μm)')
            plt.ylabel('Y position (μm)')
            plt.title(f'Intensity Map at {raman_shifts[idx_1000]:.1f} cm⁻¹')
            plt.colorbar(scatter, label='Intensity')
            
            plt.tight_layout()
            
            # Save the plot
            plot_path = Path(file_path).with_suffix('_test_visualization.png')
            plt.savefig(plot_path, dpi=150, bbox_inches='tight')
            print(f"Visualization saved: {plot_path}")
            
            plt.show()
            
            print("\nTest completed successfully!")
            
            return {
                'n_positions': len(spatial_data),
                'n_wavenumbers': len(raman_shifts),
                'pkl_path': test_pkl_path,
                'plot_path': plot_path
            }
            
        except Exception as e:
            print(f"Error in test: {e}")
            import traceback
            traceback.print_exc()
            return None


class SearchResultsWindow(QDialog):
    """Interactive search results window with spectrum comparison and metadata viewing."""
    
    def __init__(self, matches, query_wavenumbers, query_intensities, search_type, parent=None):
        super().__init__(parent)
        self.matches = matches
        self.query_wavenumbers = query_wavenumbers
        self.query_intensities = query_intensities
        self.search_type = search_type
        self.selected_match = None
        
        self.setWindowTitle(f"{search_type} Results - {len(matches)} matches found")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        self.setup_ui()
        
        # Select first match by default
        if self.matches:
            self.results_table.selectRow(0)
            self.on_match_selected()
    
    def setup_ui(self):
        """Set up the search results UI."""
        layout = QHBoxLayout(self)
        
        # Left panel - results list and controls
        left_panel = QWidget()
        left_panel.setMaximumWidth(400)
        left_layout = QVBoxLayout(left_panel)
        
        # Results table
        results_group = QGroupBox(f"Search Results ({len(self.matches)} matches)")
        results_layout = QVBoxLayout(results_group)
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["Mineral", "Score", "Formula"])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setAlternatingRowColors(True)
        
        # Populate results table
        self.populate_results_table()
        
        # Connect selection change
        self.results_table.selectionModel().selectionChanged.connect(self.on_match_selected)
        
        results_layout.addWidget(self.results_table)
        left_layout.addWidget(results_group)
        
        # Control buttons
        controls_group = QGroupBox("Actions")
        controls_layout = QVBoxLayout(controls_group)
        
        self.metadata_btn = QPushButton("View Metadata")
        self.metadata_btn.clicked.connect(self.show_metadata)
        self.metadata_btn.setStyleSheet("""
            QPushButton {
                background-color: #5BC0DE;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #46B8DA;
            }
        """)
        controls_layout.addWidget(self.metadata_btn)
        
        # Normalization options
        norm_group = QGroupBox("Normalization")
        norm_layout = QVBoxLayout(norm_group)
        
        self.norm_combo = QComboBox()
        self.norm_combo.addItems([
            "Max Intensity", "Area Under Curve", "Standard Score (Z-score)", "Min-Max"
        ])
        self.norm_combo.currentTextChanged.connect(self.update_comparison_plot)
        norm_layout.addWidget(self.norm_combo)
        
        controls_layout.addWidget(norm_group)
        controls_layout.addStretch()
        
        left_layout.addWidget(controls_group)
        layout.addWidget(left_panel)
        
        # Right panel - spectrum comparison with three plots
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Create matplotlib figure with two subplots
        self.figure = Figure(figsize=(12, 10))
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, right_panel)
        
        # Create two subplots with adjusted height ratios
        # Comparison plot (60%) and vibration analysis (40%)
        gs = self.figure.add_gridspec(2, 1, height_ratios=[3, 2], hspace=0.3)
        self.ax_comparison = self.figure.add_subplot(gs[0])
        self.ax_vibration = self.figure.add_subplot(gs[1])
        
        # Adjust subplot spacing 
        self.figure.subplots_adjust(left=0.08, right=0.98, top=0.95, bottom=0.08)
        
        right_layout.addWidget(self.toolbar)
        right_layout.addWidget(self.canvas)
        
        layout.addWidget(right_panel)
        
        # Initialize tooltip variables
        self.tooltip_data = []
        self.tooltip = None
        self.comparison_overlay = None
        
        # Metadata window (initially hidden)
        self.metadata_window = None
    
    def populate_results_table(self):
        """Populate the results table with match data."""
        self.results_table.setRowCount(len(self.matches))
        
        for i, match in enumerate(self.matches):
            # Mineral name
            name = match.get('name', 'Unknown')
            metadata = match.get('metadata', {})
            display_name = metadata.get('NAME') or metadata.get('mineral_name') or name
            
            name_item = QTableWidgetItem(display_name)
            name_item.setToolTip(f"Database entry: {name}")
            self.results_table.setItem(i, 0, name_item)
            
            # Score
            score = match.get('score', 0.0)
            score_item = QTableWidgetItem(f"{score:.3f}")
            score_item.setTextAlignment(Qt.AlignCenter)
            self.results_table.setItem(i, 1, score_item)
            
            # Formula
            formula = metadata.get('IDEAL CHEMISTRY') or metadata.get('FORMULA') or metadata.get('Formula') or 'N/A'
            formula_item = QTableWidgetItem(formula)
            self.results_table.setItem(i, 2, formula_item)
        
        # Resize columns
        self.results_table.resizeColumnsToContents()
    
    def on_match_selected(self):
        """Handle match selection change."""
        selected_rows = self.results_table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            self.selected_match = self.matches[row]
            self.update_comparison_plot()
            
            # Update metadata window if it's open
            if self.metadata_window and self.metadata_window.isVisible():
                self.show_metadata()
    
    def update_comparison_plot(self):
        """Update the spectrum comparison plot with vibrational analysis."""
        if not self.selected_match:
            return
        
        # Clear all plots
        self.ax_comparison.clear()
        self.ax_vibration.clear()
        
        # Get database spectrum data
        db_wavenumbers = self.selected_match.get('wavenumbers', [])
        db_intensities = self.selected_match.get('intensities', [])
        
        if len(db_wavenumbers) == 0 or len(db_intensities) == 0:
            self.ax_comparison.text(0.5, 0.5, 'No spectrum data available for this match',
                                   ha='center', va='center', transform=self.ax_comparison.transAxes)
            self.canvas.draw()
            return
        
        # Convert to numpy arrays
        db_wavenumbers = np.array(db_wavenumbers)
        db_intensities = np.array(db_intensities)
        
        # Interpolate to common wavenumber grid
        common_wavenumbers = np.linspace(
            max(self.query_wavenumbers.min(), db_wavenumbers.min()),
            min(self.query_wavenumbers.max(), db_wavenumbers.max()),
            min(len(self.query_wavenumbers), len(db_wavenumbers))
        )
        
        query_interp = np.interp(common_wavenumbers, self.query_wavenumbers, self.query_intensities)
        db_interp = np.interp(common_wavenumbers, db_wavenumbers, db_intensities)
        
        # Apply normalization
        norm_method = self.norm_combo.currentText()
        query_norm, db_norm = self.normalize_spectra(query_interp, db_interp, norm_method)
        
        # === COMPARISON PLOT ===
        self.ax_comparison.plot(common_wavenumbers, query_norm, 'b-', linewidth=1.5, 
                               label='Query Spectrum', alpha=0.8)
        self.ax_comparison.plot(common_wavenumbers, db_norm, 'r-', linewidth=1.5, 
                               label=f'Match: {self.get_display_name()}', alpha=0.8)
        
        # Calculate residual and add as overlay at top of plot
        residual = query_norm - db_norm
        
        # Scale residual to be smaller and position at top of comparison plot
        y_min, y_max = self.ax_comparison.get_ylim() if hasattr(self.ax_comparison, '_current_ylim') else (0, 1)
        y_range = max(np.max(query_norm), np.max(db_norm)) - min(np.min(query_norm), np.min(db_norm))
        if y_range == 0:
            y_range = 1
            
        # Scale residual to be 15% of the main plot height and position at 85% of the plot height
        residual_scaled = (residual / np.max(np.abs(residual)) if np.max(np.abs(residual)) > 0 else residual) * (0.15 * y_range)
        residual_offset = 0.85 * y_range + min(np.min(query_norm), np.min(db_norm))
        residual_positioned = residual_scaled + residual_offset
        
        # Plot small residual overlay
        self.ax_comparison.plot(common_wavenumbers, residual_positioned, 'g-', linewidth=0.8, 
                               label='Residual (scaled)', alpha=0.6)
        self.ax_comparison.axhline(y=residual_offset, color='k', linestyle=':', alpha=0.4, linewidth=0.5)
        
        # Calculate and display statistics in comparison plot
        correlation = np.corrcoef(query_norm, db_norm)[0, 1]
        rmse = np.sqrt(np.mean(residual**2))
        
        # Add statistics text to comparison plot
        stats_text = f'Correlation: {correlation:.3f}\nRMSE: {rmse:.3f}'
        self.ax_comparison.text(0.02, 0.98, stats_text, transform=self.ax_comparison.transAxes,
                               verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        self.ax_comparison.set_xlabel('Wavenumber (cm⁻¹)')
        self.ax_comparison.set_ylabel('Normalized Intensity')
        self.ax_comparison.set_title(f'Spectrum Comparison (Score: {self.selected_match.get("score", 0):.3f})')
        self.ax_comparison.legend()
        self.ax_comparison.grid(True, alpha=0.3)
        
        # === VIBRATIONAL CORRELATION PLOT ===
        self.plot_vibrational_analysis(common_wavenumbers, query_norm, db_norm)
        
        self.canvas.draw()
    
    def plot_vibrational_analysis(self, wavenumbers, query_spectrum, match_spectrum):
        """Plot vibrational correlation analysis showing mineral group correlations."""
        # Define specific mineral vibration regions with group categories
        mineral_regions = [
            # Silicate vibrations
            ("Silicate", 450, 550, "Si-O-Si 3MR Stretch"),
            ("Silicate", 600, 680, "Si-O-Si"),
            ("Silicate", 850, 1000, "Si-O Stretch Q²,Q³"),
            ("Silicate", 1050, 1200, "Si-O-Si Stretch Q⁰"),
            # Carbonate vibrations
            ("Carbonate", 700, 740, "CO₃ Bend ν₂"),
            ("Carbonate", 1050, 1090, "CO₃ Stretch ν₄"),
            # Phosphate vibrations
            ("Phosphate", 550, 620, "PO₄ Bend ν₄"),
            ("Phosphate", 950, 970, "PO₄ Stretch ν₁"),
            ("Phosphate", 1030, 1080, "PO₄ Asym"),
            # Arsenate vibrations
            ("Arsenate", 420, 460, "AsO₄ Bend ν₂"),
            ("Arsenate", 810, 855, "AsO₄ Stretch ν₁"),
            ("Arsenate", 780, 880, "AsO₃ Stretch ν₃"),
            # Sulfate vibrations
            ("Sulfate", 450, 500, "SO₄ Bend ν₂"),
            ("Sulfate", 975, 1010, "SO₄ Stretch ν₁"),
            ("Sulfate", 1100, 1150, "SO₄ Asym ν₃"),
            # Oxide vibrations
            ("Oxide", 300, 350, "Metal-O Stretch"),
            ("Oxide", 400, 450, "Metal-O-Metal Bend"),
            ("Oxide", 500, 600, "M-O Lattice"),
            # Hydroxide vibrations
            ("Hydroxide", 3500, 3650, "OH Stretch"),
            ("Hydroxide", 600, 900, "M-OH Bend"),
            ("Hydroxide", 1600, 1650, "HOH Bend"),
            # Sulfide vibrations
            ("Sulfide", 300, 400, "Metal-S Stretch"),
            ("Sulfide", 200, 280, "S-S Stretch"),
            ("Sulfide", 350, 420, "M-S-M Bend"),
            # Sulfosalt vibrations
            ("Sulfosalt", 300, 360, "Sb-S Stretch"),
            ("Sulfosalt", 330, 380, "As-S Stretch"),
            ("Sulfosalt", 250, 290, "S-S Stretch"),
            # Vanadate vibrations
            ("Vanadate", 800, 860, "V-O Stretch ν₁"),
            ("Vanadate", 780, 820, "V-O-V Asym ν₃"),
            ("Vanadate", 400, 450, "V-O Bend ν₄"),
            # Borate vibrations
            ("Borate", 650, 700, "BO₃ Bend"),
            ("Borate", 880, 950, "BO₃ Stretch"),
            ("Borate", 1300, 1400, "BO₃ Asym"),
            # Water vibrations
            ("OH/H₂O", 3200, 3500, "H₂O Stretch"),
            ("OH/H₂O", 1600, 1650, "H₂O Bend"),
            ("OH/H₂O", 500, 800, "H₂O Libration"),
            # Oxalate vibrations
            ("Oxalate", 1455, 1490, "C-O Stretch"),
            ("Oxalate", 900, 920, "C-C Stretch"),
            ("Oxalate", 850, 870, "O-C-O Bend"),
        ]
        
        # Filter regions to only those within our spectral range
        filtered_regions = [region for region in mineral_regions 
                           if region[1] <= wavenumbers.max() and region[2] >= wavenumbers.min()]
        
        # Calculate correlation for each region
        region_data = []
        group_correlations = {}
        group_weights = {}
        
        # Define region importance factors
        region_importance = {
            "Carbonate": 1.0, "Sulfate": 1.0, "Phosphate": 1.0, "Silicate": 1.0,
            "OH/H₂O": 0.5, "Vanadate": 1.0, "Borate": 1.0, "Oxalate": 1.0,
            "Arsenate": 1.0, "Oxide": 1.0, "Hydroxide": 0.8, "Sulfide": 1.0, "Sulfosalt": 1.0
        }
        
        for group, start, end, label in filtered_regions:
            indices = np.where((wavenumbers >= start) & (wavenumbers <= end))[0]
            if len(indices) > 1:
                region_query = query_spectrum[indices]
                region_match = match_spectrum[indices]
                
                # Calculate correlation coefficient
                try:
                    if np.all(region_query == region_query[0]) or np.all(region_match == region_match[0]):
                        corr = 0.0
                    else:
                        corr = np.corrcoef(region_query, region_match)[0, 1]
                    if np.isnan(corr):
                        corr = 0.0
                except Exception:
                    corr = 0.0
            else:
                corr = 0.0
            
            region_data.append((group, start, end, label, corr))
            
            # Track group correlations
            if group not in group_correlations:
                group_correlations[group] = []
                group_weights[group] = []
            
            group_correlations[group].append(corr)
            width = end - start
            weight = (width / 2000.0) * region_importance.get(group, 1.0)
            group_weights[group].append(weight)
        
        # Calculate weighted group correlations
        weighted_group_scores = {}
        for group in group_correlations:
            if len(group_correlations[group]) > 0:
                weighted_corr = np.average(group_correlations[group], weights=group_weights[group])
                weighted_group_scores[group] = weighted_corr
        
        # Set up the vibrational plot
        x_min, x_max = wavenumbers.min(), wavenumbers.max()
        x_range = x_max - x_min
        x_min = max(0, x_min - 0.05 * x_range)
        x_max = x_max + 0.05 * x_range
        
        self.ax_vibration.set_xlim(x_min, x_max)
        self.ax_vibration.set_ylim(0, 1)
        self.ax_vibration.grid(True, axis='x', linestyle=':', color='gray', alpha=0.6)
        
        # Define y-positions for each group
        group_positions = {
            "Silicate": 0.94, "Carbonate": 0.86, "Phosphate": 0.78, "Arsenate": 0.70,
            "Sulfate": 0.62, "Oxide": 0.54, "Hydroxide": 0.46, "Sulfide": 0.38,
            "Sulfosalt": 0.30, "Vanadate": 0.22, "Borate": 0.14, "OH/H₂O": 0.06
        }
        
        bar_height = 0.06
        
        # Group by mineral types
        groups = {}
        for item in region_data:
            group = item[0]
            if group not in groups:
                groups[group] = []
            groups[group].append(item)
        
        # Use colormap for correlation values
        import matplotlib.cm as cm
        cmap = cm.RdYlGn
        
        # Clear tooltip data
        self.tooltip_data = []
        
        # Plot each group
        for group_name, group_items in groups.items():
            y_pos = group_positions.get(group_name, 0.5)
            avg_corr = weighted_group_scores.get(group_name, 0.0)
            
            # Add group label
            group_label = f"{group_name} (Avg: {avg_corr:.2f})"
            self.ax_vibration.text(
                x_min - 0.03 * (x_max - x_min), y_pos, group_label,
                fontsize=8, ha='left', va='center',
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1)
            )
            
            # Plot bars for each region in the group
            for _, start, end, label, corr in group_items:
                if end < x_min or start > x_max:
                    continue
                
                width = end - start
                color = cmap(corr)
                
                # Create rectangle
                from matplotlib.patches import Rectangle
                rect = Rectangle(
                    (start, y_pos - bar_height/2), width, bar_height,
                    facecolor=color, edgecolor='black', alpha=0.8
                )
                self.ax_vibration.add_patch(rect)
                
                # Add correlation value for wider bars
                if width > 70:
                    text_color = 'black' if 0.3 <= corr <= 0.7 else 'white'
                    self.ax_vibration.text(
                        start + width/2, y_pos, f"{corr:.2f}",
                        ha='center', va='center', fontsize=7, fontweight='bold',
                        color=text_color
                    )
                
                # Store tooltip data
                tooltip_info = f"{group_name}: {label}\nRange: {start}-{end} cm⁻¹\nCorrelation: {corr:.2f}"
                self.tooltip_data.append((rect, tooltip_info, color, start, end))
        
        # Add color gradient reference
        gradient_width = (x_max - x_min) * 0.6
        gradient_x = x_min + (x_max - x_min) * 0.2
        gradient_y = -0.05
        gradient_height = 0.02
        
        gradient = np.linspace(0, 1, 100).reshape(1, -1)
        self.ax_vibration.imshow(
            gradient, aspect='auto', 
            extent=[gradient_x, gradient_x + gradient_width, 
                   gradient_y - gradient_height/2, gradient_y + gradient_height/2],
            cmap=cmap
        )
        
        # Add gradient labels
        self.ax_vibration.text(gradient_x, gradient_y + gradient_height/2 + 0.02,
                              "Low Correlation (0.0)", ha='left', va='bottom', fontsize=7, color='dimgray')
        self.ax_vibration.text(gradient_x + gradient_width, gradient_y + gradient_height/2 + 0.02,
                              "High Correlation (1.0)", ha='right', va='bottom', fontsize=7, color='dimgray')
        
        # Set labels and title
        self.ax_vibration.set_xlabel('Wavenumber (cm⁻¹)')
        self.ax_vibration.set_title(f'Mineral Vibration Correlation: Query vs. {self.get_display_name()}')
        self.ax_vibration.set_yticks([])
        self.ax_vibration.set_ylabel('')  # Remove y-axis label
        
        # Setup tooltips
        self.setup_vibrational_tooltips()
    
    def setup_vibrational_tooltips(self):
        """Set up interactive tooltips and overlays for the vibrational correlation plot."""
        # Create tooltip annotation if it doesn't exist
        if self.tooltip is None:
            self.tooltip = self.ax_vibration.annotate(
                "", xy=(0, 0), xytext=(0, -70),
                textcoords="offset points",
                bbox=dict(boxstyle="round,pad=0.5", fc="white", alpha=0.9, edgecolor="black"),
                arrowprops=dict(arrowstyle="->"),
                visible=False,
                fontsize=9,
                color="navy"
            )
        
        def on_hover(event):
            """Handle mouse hover events for tooltips and overlays."""
            if not hasattr(self, 'tooltip_data') or not self.tooltip_data:
                return
            
            # Check if mouse is over the vibrational plot
            if event.inaxes != self.ax_vibration:
                self.tooltip.set_visible(False)
                self.canvas.draw_idle()
                # Remove overlay from comparison plot
                if hasattr(self, 'comparison_overlay') and self.comparison_overlay is not None:
                    self.comparison_overlay.remove()
                    self.comparison_overlay = None
                    self.canvas.draw_idle()
                return
            
            # Check if mouse is over any vibrational region rectangle
            for rect, tooltip_text, color, start, end in self.tooltip_data:
                contains, _ = rect.contains(event)
                if contains:
                    # Update tooltip
                    self.tooltip.set_text(tooltip_text)
                    self.tooltip.xy = (event.xdata, event.ydata)
                    self.tooltip.xyann = (0, -70)
                    
                    # Set tooltip background color to match rectangle
                    r, g, b, _ = color
                    lighter_r = 0.7 * r + 0.3
                    lighter_g = 0.7 * g + 0.3
                    lighter_b = 0.7 * b + 0.3
                    
                    self.tooltip.get_bbox_patch().set(
                        fc=(lighter_r, lighter_g, lighter_b, 0.9), ec=color
                    )
                    
                    # Show tooltip
                    self.tooltip.set_visible(True)
                    
                    # Add overlay to comparison plot
                    if hasattr(self, 'comparison_overlay') and self.comparison_overlay is not None:
                        self.comparison_overlay.remove()
                    
                    self.comparison_overlay = self.ax_comparison.axvspan(
                        start, end, color=color, alpha=0.3, zorder=0
                    )
                    
                    self.canvas.draw_idle()
                    return
            
            # If not over any rectangle, hide tooltip and overlay
            self.tooltip.set_visible(False)
            if hasattr(self, 'comparison_overlay') and self.comparison_overlay is not None:
                self.comparison_overlay.remove()
                self.comparison_overlay = None
            self.canvas.draw_idle()
        
        # Connect the hover event
        self.canvas.mpl_connect('motion_notify_event', on_hover)
    
    def normalize_spectra(self, spectrum1, spectrum2, method):
        """Normalize two spectra using the specified method."""
        spec1 = spectrum1.copy()
        spec2 = spectrum2.copy()
        
        if method == "Max Intensity":
            spec1 = spec1 / np.max(spec1) if np.max(spec1) > 0 else spec1
            spec2 = spec2 / np.max(spec2) if np.max(spec2) > 0 else spec2
            
        elif method == "Area Under Curve":
            area1 = np.trapz(np.abs(spec1))
            area2 = np.trapz(np.abs(spec2))
            spec1 = spec1 / area1 if area1 > 0 else spec1
            spec2 = spec2 / area2 if area2 > 0 else spec2
            
        elif method == "Standard Score (Z-score)":
            spec1 = (spec1 - np.mean(spec1)) / np.std(spec1) if np.std(spec1) > 0 else spec1
            spec2 = (spec2 - np.mean(spec2)) / np.std(spec2) if np.std(spec2) > 0 else spec2
            
        elif method == "Min-Max":
            min1, max1 = np.min(spec1), np.max(spec1)
            min2, max2 = np.min(spec2), np.max(spec2)
            spec1 = (spec1 - min1) / (max1 - min1) if (max1 - min1) > 0 else spec1
            spec2 = (spec2 - min2) / (max2 - min2) if (max2 - min2) > 0 else spec2
        
        return spec1, spec2
    
    def get_display_name(self):
        """Get display name for the selected match."""
        if not self.selected_match:
            return "No selection"
        
        metadata = self.selected_match.get('metadata', {})
        name = metadata.get('NAME') or metadata.get('mineral_name') or self.selected_match.get('name', 'Unknown')
        return name
    
    def show_metadata(self):
        """Show metadata window for the selected match."""
        if not self.selected_match:
            QMessageBox.warning(self, "No Selection", "Please select a match to view metadata.")
            return
        
        # Create or update metadata window
        if self.metadata_window is None:
            self.metadata_window = MetadataViewerWindow(self)
        
        self.metadata_window.update_metadata(self.selected_match)
        self.metadata_window.show()
        self.metadata_window.raise_()
        self.metadata_window.activateWindow()


class MetadataViewerWindow(QDialog):
    """Window for viewing detailed metadata of selected spectrum."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Spectrum Metadata")
        self.setMinimumSize(500, 600)
        self.resize(600, 700)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the metadata viewer UI."""
        layout = QVBoxLayout(self)
        
        # Title
        self.title_label = QLabel("Spectrum Metadata")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(self.title_label)
        
        # Metadata table
        self.metadata_table = QTableWidget()
        self.metadata_table.setColumnCount(2)
        self.metadata_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.metadata_table.horizontalHeader().setStretchLastSection(True)
        self.metadata_table.verticalHeader().setVisible(False)
        self.metadata_table.setAlternatingRowColors(True)
        
        # Make the table read-only
        self.metadata_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        layout.addWidget(self.metadata_table)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
    
    def update_metadata(self, match_data):
        """Update the metadata display with new match data."""
        metadata = match_data.get('metadata', {})
        name = match_data.get('name', 'Unknown')
        
        # Update title
        display_name = metadata.get('NAME') or metadata.get('mineral_name') or name
        self.title_label.setText(f"Metadata: {display_name}")
        
        # Collect all metadata
        all_metadata = {
            'Database Entry': name,
            'Score': f"{match_data.get('score', 0):.3f}",
            'Timestamp': match_data.get('timestamp', 'N/A')[:19] if match_data.get('timestamp') else 'N/A',
            'Number of Peaks': str(len(match_data.get('peaks', [])))
        }
        
        # Add all metadata fields
        for key, value in metadata.items():
            if value is not None and str(value).strip():
                all_metadata[key] = str(value)
        
        # Populate table
        self.metadata_table.setRowCount(len(all_metadata))
        
        for i, (key, value) in enumerate(all_metadata.items()):
            # Property name
            key_item = QTableWidgetItem(key)
            key_item.setFont(QFont("Arial", 9, QFont.Bold))
            self.metadata_table.setItem(i, 0, key_item)
            
            # Property value
            value_item = QTableWidgetItem(str(value))
            value_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.metadata_table.setItem(i, 1, value_item)
        
        # Resize columns
        self.metadata_table.resizeColumnsToContents()
        self.metadata_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.metadata_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)


class RamanMapImportWorker(QThread):
    """Worker thread for importing Raman spectral map data in the background."""
    
    # Define signals
    progress = Signal(int)           # Progress percentage (0-100)
    status_update = Signal(str)      # Status message
    finished = Signal(object)       # Finished with map_data result
    error = Signal(str)             # Error with error message
    
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.cancelled = False
    
    def cancel(self):
        """Cancel the import operation."""
        self.cancelled = True
    
    def run(self):
        """Run the import operation in the background thread."""
        try:
            # Run the parsing with progress callbacks
            map_data = self.parse_raman_spectral_map_static(
                self.file_path,
                progress_callback=self.emit_progress,
                status_callback=self.emit_status
            )
            
            if not self.cancelled:
                self.finished.emit(map_data)
                
        except Exception as e:
            if not self.cancelled:
                self.error.emit(str(e))
    
    def emit_progress(self, value):
        """Emit progress signal if not cancelled."""
        if not self.cancelled:
            self.progress.emit(value)
    
    def emit_status(self, message):
        """Emit status signal if not cancelled."""
        if not self.cancelled:
            self.status_update.emit(message)
    
    def parse_raman_spectral_map_static(self, file_path, progress_callback=None, status_callback=None):
        """Static version of parse_raman_spectral_map for use in worker thread."""
        try:
            if status_callback:
                status_callback("Reading file...")
            
            # Read the file line by line to handle inconsistent column counts
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            if len(lines) < 2:
                raise ValueError("File must have at least 2 lines (header + data)")
            
            total_lines = len(lines) - 1  # Exclude header
            
            if status_callback:
                status_callback("Parsing header...")
            if progress_callback:
                progress_callback(5)
            
            # Parse the first line to get Raman shifts
            first_line = lines[0].strip().split()
            print(f"First line has {len(first_line)} columns")
            
            # Extract Raman shifts from first row (skip first two cells which should be X,Y labels)
            if len(first_line) < 3:
                raise ValueError("First line must have at least 3 columns (X, Y, and Raman shifts)")
            
            raman_shifts = np.array([float(x) for x in first_line[2:]])
            print(f"Extracted {len(raman_shifts)} Raman shifts from header")
            
            # Process spatial data and spectra
            spatial_data = []
            spectra_data = []
            skipped_lines = 0
            
            if status_callback:
                status_callback(f"Processing {total_lines} spectra...")
            
            for i, line in enumerate(lines[1:], 1):  # Start from line 1 (skip header)
                # Check for cancellation
                if self.cancelled:
                    return None
                
                # Update progress every 1000 lines or for small datasets, every 100 lines
                update_frequency = 1000 if total_lines > 10000 else max(100, total_lines // 100)
                
                if i % update_frequency == 0 and progress_callback:
                    progress_percent = 5 + int((i / total_lines) * 60)  # 5-65% for line processing
                    progress_callback(progress_percent)
                    if status_callback:
                        status_callback(f"Processing spectra: {i}/{total_lines} ({progress_percent-5}%)")
                
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                    
                try:
                    parts = line.split()
                    
                    # Check if we have enough columns
                    if len(parts) < 3:
                        skipped_lines += 1
                        if skipped_lines <= 5:  # Only print first few warnings
                            print(f"Skipping line {i+1}: insufficient columns ({len(parts)})")
                        continue
                    
                    x_pos = float(parts[0])  # X position in microns
                    y_pos = float(parts[1])  # Y position in microns
                    
                    # Extract spectrum intensities - handle variable column counts
                    # Take only as many intensity values as we have Raman shifts
                    spectrum_parts = parts[2:]
                    n_to_take = min(len(spectrum_parts), len(raman_shifts))
                    
                    if n_to_take < len(raman_shifts):
                        # Pad with zeros if we have fewer intensities than expected
                        spectrum = np.zeros(len(raman_shifts))
                        spectrum[:n_to_take] = [float(x) for x in spectrum_parts[:n_to_take]]
                        if skipped_lines <= 5:
                            print(f"Line {i+1}: Padded spectrum from {n_to_take} to {len(raman_shifts)} values")
                    else:
                        # Take only the number of intensities we need
                        spectrum = np.array([float(x) for x in spectrum_parts[:len(raman_shifts)]])
                        if len(spectrum_parts) > len(raman_shifts) and skipped_lines <= 5:
                            print(f"Line {i+1}: Truncated spectrum from {len(spectrum_parts)} to {len(raman_shifts)} values")
                    
                    spatial_data.append([x_pos, y_pos])
                    spectra_data.append(spectrum)
                    
                except (ValueError, IndexError) as e:
                    skipped_lines += 1
                    if skipped_lines <= 5:  # Only print first few errors
                        print(f"Skipping line {i+1}: {e}")
                    continue
            
            if self.cancelled:
                return None
            
            if skipped_lines > 5:
                print(f"... and {skipped_lines - 5} more lines were skipped")
            
            if len(spatial_data) == 0:
                raise ValueError("No valid data rows found in file")
            
            if status_callback:
                status_callback("Converting to arrays...")
            if progress_callback:
                progress_callback(70)
            
            spatial_data = np.array(spatial_data)
            spectra_data = np.array(spectra_data)
            
            print(f"Successfully processed {len(spatial_data)} positions")
            print(f"Spatial X range: {spatial_data[:, 0].min():.1f} to {spatial_data[:, 0].max():.1f}")
            print(f"Spatial Y range: {spatial_data[:, 1].min():.1f} to {spatial_data[:, 1].max():.1f}")
            print(f"Spectrum intensity range: {spectra_data.min():.2e} to {spectra_data.max():.2e}")
            
            # Create organized map data structure
            if status_callback:
                status_callback("Creating map data structure...")
            if progress_callback:
                progress_callback(75)
                
            map_data = {
                'raman_shifts': raman_shifts,
                'spatial_coordinates': spatial_data,
                'spectra': spectra_data,
                'metadata': {
                    'source_file': str(file_path),
                    'n_positions': len(spatial_data),
                    'n_wavenumbers': len(raman_shifts),
                    'spatial_range_x': [spatial_data[:, 0].min(), spatial_data[:, 0].max()],
                    'spatial_range_y': [spatial_data[:, 1].min(), spatial_data[:, 1].max()],
                    'wavenumber_range': [raman_shifts.min(), raman_shifts.max()],
                    'skipped_lines': skipped_lines,
                    'units': {
                        'spatial': 'microns',
                        'wavenumber': 'cm⁻¹',
                        'intensity': 'a.u.'
                    }
                }
            }
            
            if self.cancelled:
                return None
            
            # Create gridded data for easier mapping
            x_unique = np.unique(spatial_data[:, 0])
            y_unique = np.unique(spatial_data[:, 1])
            
            if len(x_unique) > 1 and len(y_unique) > 1:
                try:
                    if status_callback:
                        status_callback("Creating gridded data for mapping...")
                    if progress_callback:
                        progress_callback(80)
                    
                    # Create interpolated grid for mapping
                    xi, yi = np.meshgrid(
                        np.linspace(spatial_data[:, 0].min(), spatial_data[:, 0].max(), len(x_unique)),
                        np.linspace(spatial_data[:, 1].min(), spatial_data[:, 1].max(), len(y_unique))
                    )
                    
                    # Interpolate each wavenumber onto the grid
                    gridded_spectra = np.zeros((len(y_unique), len(x_unique), len(raman_shifts)))
                    
                    for i, wavenumber in enumerate(raman_shifts):
                        # Check for cancellation during interpolation
                        if self.cancelled:
                            return None
                        
                        # Update progress for interpolation
                        if i % max(1, len(raman_shifts) // 10) == 0 and progress_callback:
                            interpolation_progress = 80 + int((i / len(raman_shifts)) * 15)  # 80-95%
                            progress_callback(interpolation_progress)
                            if status_callback:
                                status_callback(f"Interpolating wavenumber {i+1}/{len(raman_shifts)}...")
                        
                        intensities = spectra_data[:, i]
                        gridded_intensities = griddata(
                            spatial_data, intensities, (xi, yi), method='linear', fill_value=0
                        )
                        gridded_spectra[:, :, i] = gridded_intensities
                    
                    if not self.cancelled:
                        map_data['gridded_data'] = {
                            'x_grid': xi,
                            'y_grid': yi,
                            'spectra_grid': gridded_spectra
                        }
                        print("✓ Created gridded data for mapping")
                    
                except Exception as e:
                    print(f"Warning: Could not create gridded data: {e}")
            
            if self.cancelled:
                return None
            
            if status_callback:
                status_callback("Import complete!")
            if progress_callback:
                progress_callback(100)
            
            return map_data
            
        except Exception as e:
            raise Exception(f"Error parsing Raman spectral map: {str(e)}")