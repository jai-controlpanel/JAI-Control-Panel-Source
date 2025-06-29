# --- PUT THIS LINE AT THE VERY TOP OF THE FILE ---
print("DEBUG: main_app.py has started execution. GUI is about to initialize.")

import customtkinter
import json
import os
import sys
import requests
import time
import emoji
import traceback
import webbrowser
import subprocess
# import client_application_logic as client_logic # If this is a separate file, ensure it's used or remove
import platform
from threading import Thread, Event
from queue import Queue, Empty
from datetime import datetime, timezone 
from tkinter import filedialog, messagebox 
from PIL import Image, ImageTk 
import mimetypes

API_BASE_URL = "https://jai-controlpanel.com" 

# ======================================================
# --- UI COLOR PALETTE DEFINITIONS ---
# Define these at the very top, before any UI elements are created.
# This makes it easy to change the look globally.
# ======================================================

UI_PRIMARY_ACCENT = "#C084FC"
UI_BACKGROUND_PRIMARY = "#0F0F1A"
UI_BACKGROUND_SECONDARY_1 = "#1A1A2A"
UI_BACKGROUND_SECONDARY_2 = "#2A2A3A"

UI_TEXT_PRIMARY = "#E0E0E0"
UI_TEXT_MUTED = "#A0A0A0"

UI_BUTTON_NORMAL_FG = "#4A5A7B"
UI_BUTTON_NORMAL_HOVER = "#5D7B9D"

UI_BUTTON_DANGER_FG = "#7B0000"
UI_BUTTON_DANGER_HOVER = "#8D0000"

UI_STATUS_ACTIVE = "#3CB371"
UI_STATUS_WARNING = "#D35400"
UI_STATUS_ERROR = "#8B0000"

COLOR_API = "#00CED1"
COLOR_TELE = "#4682B4"
COLOR_REDDIT = "#D3DEDF"
COLOR_DISCORD = "#7B68EE"
COLOR_SYSTEM = UI_TEXT_MUTED
COLOR_ERROR = UI_STATUS_ERROR
COLOR_WARNING = UI_STATUS_WARNING


# ======================================================
# --- All Pop-up Window Classes ---
# ======================================================

class RegistrationWindow(customtkinter.CTkToplevel):
    def __init__(self, master=None, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.title("First-Time User Registration")
        self.geometry("400x350")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.focus_force()

        self.configure(fg_color=UI_BACKGROUND_PRIMARY)
        self.grid_columnconfigure(0, weight=1)

        self.title_label = customtkinter.CTkLabel(self, text="Create Your Account", font=("Arial", 16, "bold"), text_color=UI_TEXT_PRIMARY)
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.info_label = customtkinter.CTkLabel(self, text="Paste your code/key below to register or start a trial.", wraplength=350, text_color=UI_TEXT_MUTED)
        self.info_label.grid(row=1, column=0, padx=20, pady=(0, 10))

        self.code_entry = customtkinter.CTkEntry(self, placeholder_text="Paste Activation Code or Trial Key", text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
        self.code_entry.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        
        self.username_entry = customtkinter.CTkEntry(self, placeholder_text="Username", text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
        self.username_entry.grid(row=3, column=0, padx=20, pady=5, sticky="ew")
        
        self.password_entry = customtkinter.CTkEntry(self, placeholder_text="Password", show="*", text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
        self.password_entry.grid(row=4, column=0, padx=20, pady=5, sticky="ew")
        
        self.create_user_button = customtkinter.CTkButton(self, text="Create Account", command=self.create_user_deduced, fg_color=UI_BUTTON_NORMAL_FG, hover_color=UI_BUTTON_NORMAL_HOVER, text_color=UI_TEXT_PRIMARY)
        self.create_user_button.grid(row=5, column=0, padx=20, pady=10)
        
        self.status_label = customtkinter.CTkLabel(self, text="", text_color=UI_TEXT_PRIMARY)
        self.status_label.grid(row=6, column=0, padx=20, pady=10)

        self.registration_success = False
        self.registered_username = None
        self.is_trial_user = False
        self.trial_expiry_time = None
        self.user_data_from_api = None # NEW: To capture the full user_data payload from auto-login

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_user_deduced(self):
        code_or_key = self.code_entry.get().strip()
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not all([code_or_key, username, password]):
            self.status_label.configure(text="All fields are required.", text_color=UI_STATUS_WARNING)
            return

        endpoint = f"{API_BASE_URL}/register-deduce"
        payload = {"code_or_key": code_or_key, "username": username, "password": password}

        try:
            response = requests.post(endpoint, json=payload, timeout=10)
            response_data = response.json()
            
            if response.status_code == 201:
                self.status_label.configure(text="Account created! Attempting auto-login...", text_color=UI_STATUS_ACTIVE)
                self.registration_success = True
                self.registered_username = username
                # In this specific scenario, registration for desktop app doesn't directly return full user_data
                # The main __main__ block will perform a subsequent /login call to get it.
                self.after(1500, self.destroy) # Close after displaying message
            else:
                error_message = response_data.get('error', 'Unknown error during registration.')
                self.status_label.configure(text=f"Error: {error_message}", text_color=UI_STATUS_ERROR)
        except requests.exceptions.RequestException:
            self.status_label.configure(text="Error: Could not connect to API server.", text_color=UI_STATUS_ERROR)

    def on_closing(self):
        self.registration_success = False
        self.registered_username = None
        self.is_trial_user = False
        self.trial_expiry_time = None
        self.user_data_from_api = None
        self.destroy()

class LoginWindow(customtkinter.CTkToplevel):
    def __init__(self, master=None, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.title("Login")
        self.geometry("400x280")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.logged_in = False
        self.logged_in_username = None
        self.is_trial_user = False
        self.trial_expiry_time = None
        self.user_data_from_api = None # CRITICAL: This will store the dashboard_data from the API
        
        self.grid_columnconfigure(0, weight=1)

        self.configure(fg_color=UI_BACKGROUND_PRIMARY)
        self.title_label = customtkinter.CTkLabel(self, text="Jasmine AI Control Panel Login", font=("Arial", 16, "bold"), text_color=UI_TEXT_PRIMARY)
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.username_entry = customtkinter.CTkEntry(self, placeholder_text="Username", text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
        self.username_entry.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        
        self.password_entry = customtkinter.CTkEntry(self, placeholder_text="Password", show="*", text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
        self.password_entry.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        
        self.login_button = customtkinter.CTkButton(self, text="Login", command=self.attempt_login, fg_color=UI_BUTTON_NORMAL_FG, hover_color=UI_BUTTON_NORMAL_HOVER, text_color=UI_TEXT_PRIMARY)
        self.login_button.grid(row=3, column=0, padx=20, pady=10)
        
        self.password_entry.bind("<Return>", self.attempt_login)
        self.username_entry.bind("<Return>", lambda e: self.password_entry.focus())
        
        self.status_label = customtkinter.CTkLabel(self, text="", text_color=UI_TEXT_PRIMARY)
        self.status_label.grid(row=4, column=0, padx=20, pady=5)

        self.grab_set()
        self.focus_force()

    def attempt_login(self, event=None):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not (username and password):
            self.status_label.configure(text="Username and password are required.", text_color=UI_STATUS_WARNING)
            return

        try:
            APP_VERSION = "1.0"
            os_system = platform.system()
            os_release = platform.release()
            os_arch = platform.machine()
            custom_user_agent = f"JasmineAI-Client/{APP_VERSION} ({os_system}; {os_release}; {os_arch})"
        except Exception as e:
            custom_user_agent = "JasmineAI-Client/1.0 (UnknownOS)"
            print(f"DEBUG: Could not create detailed User-Agent. Error: {e}")

        http_headers = {'User-Agent': custom_user_agent}

        payload = {"username": username, "password": password}

        try:
            response = requests.post(f"{API_BASE_URL}/login", json=payload, timeout=10, headers=http_headers)
            response_data = response.json()
            
            if response.status_code == 200:
                self.logged_in = True
                self.logged_in_username = username
                # CRITICAL: Capture the full 'user_data' payload from the API response
                self.user_data_from_api = response_data.get("user_data", {}) 
                
                # These can now be derived directly from user_data_from_api
                self.is_trial_user = self.user_data_from_api.get("trial_status", "Permanent") != "Permanent"
                self.trial_expiry_time = self.user_data_from_api.get("expiry_date")
                
                if response_data.get("message") == "Your trial has expired. Please contact support to continue using Jasmine AI.":
                    self.status_label.configure(text=response_data.get("message"), text_color=UI_STATUS_ERROR)
                    self.is_trial_user = True
                    self.trial_expiry_time = "Expired"
                    self.after(2000, self.destroy)
                    return
                else:
                    self.status_label.configure(text="Login successful!", text_color=UI_STATUS_ACTIVE)

                self.after(1500, self.destroy)

            else:
                self.logged_in = False
                self.logged_in_username = None
                self.is_trial_user = False
                self.trial_expiry_time = None
                self.user_data_from_api = None # Clear this on failed login
                self.status_label.configure(text=response_data.get("message", "Login failed."), text_color=UI_STATUS_ERROR)
            
        except requests.exceptions.RequestException:
            self.status_label.configure(text="Cannot connect to API server.\nPlease ensure api.py is running.", text_color=UI_STATUS_ERROR)
        except Exception as e:
            self.status_label.configure(text=f"An unexpected error occurred: {e}", text_color=UI_STATUS_ERROR)

    def on_closing(self):
        self.logged_in = False
        self.logged_in_username = None
        self.is_trial_user = False
        self.trial_expiry_time = None
        self.user_data_from_api = None 
        self.destroy()

class SettingsWindow(customtkinter.CTkToplevel):
    def __init__(self, master=None, app_instance=None, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.master_app = app_instance
        self.title("Jasmine AI Settings (General)")
        self.geometry("1000x650") 
        self.resizable(True, True) 
        self.transient(master)

        self.grid_columnconfigure(0, weight=1) 
        self.grid_rowconfigure(0, weight=1) 

        self.scrollable_content_frame = customtkinter.CTkScrollableFrame(self, fg_color=UI_BACKGROUND_PRIMARY)
        self.scrollable_content_frame.grid(row=0, column=0, sticky="nsew")
        
        self.content_frame = self.scrollable_content_frame 
        self.content_frame.grid_columnconfigure(0, weight=1) 

        self.current_row_idx = 0 
        settings_font = ("Arial", 11) 
        label_pady = (3, 0) 
        entry_pady = 2 

        self.entries = {} 

        # --- Section 1: API Base URL (Spans full width) ---
        customtkinter.CTkLabel(self.content_frame, text="API Base URL:", font=("Arial", 13, "bold"), text_color=UI_TEXT_PRIMARY).grid(row=self.current_row_idx, column=0, padx=20, pady=(10, 3), sticky="w")
        self.current_row_idx += 1
        self.api_url_entry = customtkinter.CTkEntry(self.content_frame, font=settings_font, text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
        self.api_url_entry.grid(row=self.current_row_idx, column=0, padx=20, pady=entry_pady, sticky="ew")
        self.entries["api_base_url"] = self.api_url_entry
        self.current_row_idx += 1

        # --- Section 2: Core AI Info & Credentials (3-column layout) ---
        self.current_row_idx += 1 
        
        core_settings_frame = customtkinter.CTkFrame(self.content_frame, fg_color="transparent")
        core_settings_frame.grid(row=self.current_row_idx, column=0, sticky="ew", padx=10, pady=5)
        core_settings_frame.grid_columnconfigure(0, weight=0) 
        core_settings_frame.grid_columnconfigure(1, weight=1) 
        core_settings_frame.grid_columnconfigure(2, weight=0, minsize=20)
        core_settings_frame.grid_columnconfigure(3, weight=0)
        core_settings_frame.grid_columnconfigure(4, weight=1)
        core_settings_frame.grid_columnconfigure(5, weight=0, minsize=20)
        core_settings_frame.grid_columnconfigure(6, weight=0)
        core_settings_frame.grid_columnconfigure(7, weight=1)

        core_row_counter = 0

        block1_elements = [
            ("ai_name", "AI Name:"),
            ("ai_age", "AI Age:"),
            ("location", "AI Location:"),
            ("min_response_delay_seconds", "Min AI Response Delay (s):"),
            ("max_response_delay_seconds", "Max AI Response Delay (s):")
        ]
        for i, (key, text) in enumerate(block1_elements):
            label = customtkinter.CTkLabel(core_settings_frame, text=text, font=settings_font, text_color=UI_TEXT_PRIMARY)
            label.grid(row=core_row_counter + i, column=0, padx=5, pady=label_pady, sticky="w")
            entry = customtkinter.CTkEntry(core_settings_frame, font=settings_font, text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
            entry.grid(row=core_row_counter + i, column=1, padx=5, pady=entry_pady, sticky="ew")
            self.entries[key] = entry
        max_core_block_height = len(block1_elements)

        block2_elements = [
            ("phone_number", "Phone Number:"),
            ("instagram_handle", "Instagram Handle:"),
            ("telegram_handle", "Telegram Handle:"),
            ("facebook_page_link", "Facebook Page Link:"),
            ("facebook_verify_token", "Facebook Verify Token:")
        ]
        for i, (key, text) in enumerate(block2_elements):
            label = customtkinter.CTkLabel(core_settings_frame, text=text, font=settings_font, text_color=UI_TEXT_PRIMARY)
            label.grid(row=core_row_counter + i, column=3, padx=5, pady=label_pady, sticky="w")
            entry = customtkinter.CTkEntry(core_settings_frame, font=settings_font, text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
            entry.grid(row=core_row_counter + i, column=4, padx=5, pady=entry_pady, sticky="ew")
            self.entries[key] = entry
        max_core_block_height = max(max_core_block_height, len(block2_elements))

        block3_elements = [
            ("telegram_token", "Telegram Bot Token:"),
            ("discord_bot_token", "Discord Bot Token:"),
            ("facebook_page_access_token", "Facebook Page Access Token:"),
            ("reddit_username", "Reddit Bot Username:"),
            ("reddit_password", "Reddit Bot Password:")
        ]
        for i, (key, text) in enumerate(block3_elements):
            label = customtkinter.CTkLabel(core_settings_frame, text=text, font=settings_font, text_color=UI_TEXT_PRIMARY)
            label.grid(row=core_row_counter + i, column=6, padx=5, pady=label_pady, sticky="w")
            if key in ["telegram_token", "discord_bot_token", "facebook_page_access_token", "reddit_password"]:
                entry = customtkinter.CTkEntry(core_settings_frame, font=settings_font, text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED, show="*")
            else:
                entry = customtkinter.CTkEntry(core_settings_frame, font=settings_font, text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
            entry.grid(row=core_row_counter + i, column=7, padx=5, pady=entry_pady, sticky="ew")
            self.entries[key] = entry
        max_core_block_height = max(max_core_block_height, len(block3_elements))

        self.current_row_idx += max_core_block_height + 1

        # --- Section 3: Proactive Mode (Spans full width) ---
        self.current_row_idx += 1 
        proactive_mode_frame = customtkinter.CTkFrame(self.content_frame, fg_color="transparent")
        proactive_mode_frame.grid(row=self.current_row_idx, column=0, padx=10, pady=(10, 5), sticky="ew")
        proactive_mode_frame.grid_columnconfigure(0, weight=0) 
        proactive_mode_frame.grid_columnconfigure(1, weight=1) 

        self.proactive_mode_enabled_var = customtkinter.BooleanVar(value=False)
        self.proactive_mode_checkbox = customtkinter.CTkCheckBox(proactive_mode_frame, text="Enable Proactive Mode (Jasmine texts first)",
                                                                 variable=self.proactive_mode_enabled_var,
                                                                 font=settings_font, text_color=UI_TEXT_PRIMARY, fg_color=UI_BUTTON_NORMAL_FG, checkmark_color=UI_PRIMARY_ACCENT)
        self.proactive_mode_checkbox.grid(row=0, column=0, columnspan=2, pady=(0, 5), sticky="w")
        self.entries["proactive_mode_enabled"] = self.proactive_mode_enabled_var

        self.proactive_greeting_label = customtkinter.CTkLabel(proactive_mode_frame, text="Proactive Greeting Message:", font=settings_font, text_color=UI_TEXT_PRIMARY)
        self.proactive_greeting_label.grid(row=1, column=0, pady=label_pady, sticky="w")
        self.proactive_greeting_entry = customtkinter.CTkEntry(proactive_mode_frame, font=settings_font, text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
        self.proactive_greeting_entry.grid(row=1, column=1, pady=entry_pady, sticky="ew")
        self.entries["proactive_greeting_message"] = self.proactive_greeting_entry
        self.current_row_idx += 1 

        # --- Section 4: Automated Random Proactive Approach (ARPA) (2-column layout) ---
        self.current_row_idx += 1 
        arpa_settings_section_frame = customtkinter.CTkFrame(self.content_frame, fg_color="transparent")
        arpa_settings_section_frame.grid(row=self.current_row_idx, column=0, padx=10, pady=(10, 5), sticky="ew")
        arpa_settings_section_frame.grid_columnconfigure(0, weight=1)
        arpa_settings_section_frame.grid_columnconfigure(1, weight=1)

        reddit_arpa_settings_frame = customtkinter.CTkFrame(arpa_settings_section_frame, fg_color=UI_BACKGROUND_SECONDARY_1, corner_radius=8)
        reddit_arpa_settings_frame.grid(row=0, column=0, padx=3, pady=3, sticky="nsew")
        reddit_arpa_settings_frame.grid_columnconfigure(0, weight=1)

        customtkinter.CTkLabel(reddit_arpa_settings_frame, text="Reddit ARPA Settings", font=("Arial", 10, "bold"), text_color=UI_TEXT_PRIMARY).pack(pady=(5,3))
        self.entries["auto_proactive_reddit_enabled"] = customtkinter.BooleanVar(value=False)
        customtkinter.CTkCheckBox(reddit_arpa_settings_frame, text="Enable Reddit ARPA", variable=self.entries["auto_proactive_reddit_enabled"], font=("Arial", 9), text_color=UI_TEXT_PRIMARY, fg_color=UI_BUTTON_NORMAL_FG, checkmark_color=UI_PRIMARY_ACCENT).pack(anchor="w", padx=8, pady=1)
        customtkinter.CTkLabel(reddit_arpa_settings_frame, text="Target Subreddits (comma-separated):", font=("Arial", 9), text_color=UI_TEXT_MUTED).pack(anchor="w", padx=8, pady=(3,0))
        self.entries["reddit_target_subreddits"] = customtkinter.CTkEntry(reddit_arpa_settings_frame, font=("Arial", 9), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
        self.entries["reddit_target_subreddits"].pack(fill="x", padx=8, pady=1)
        customtkinter.CTkLabel(reddit_arpa_settings_frame, text="User Cooldown (hrs):", font=("Arial", 9), text_color=UI_TEXT_MUTED).pack(anchor="w", padx=8, pady=(3,0))
        self.entries["reddit_proactive_cooldown_hours_per_user"] = customtkinter.CTkEntry(reddit_arpa_settings_frame, font=("Arial", 9), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
        self.entries["reddit_proactive_cooldown_hours_per_user"].pack(fill="x", padx=8, pady=1)
        customtkinter.CTkLabel(reddit_arpa_settings_frame, text="Message Delay (s):", font=("Arial", 9), text_color=UI_TEXT_MUTED).pack(anchor="w", padx=8, pady=(3,0))
        self.entries["reddit_proactive_min_delay_seconds_per_message"] = customtkinter.CTkEntry(reddit_arpa_settings_frame, font=("Arial", 9), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
        self.entries["reddit_proactive_min_delay_seconds_per_message"].pack(fill="x", padx=8, pady=1)
        customtkinter.CTkLabel(reddit_arpa_settings_frame, text="Max Daily Messages:", font=("Arial", 9), text_color=UI_TEXT_MUTED).pack(anchor="w", padx=8, pady=(3,0))
        self.entries["reddit_proactive_max_daily_messages_total"] = customtkinter.CTkEntry(reddit_arpa_settings_frame, font=("Arial", 9), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
        self.entries["reddit_proactive_max_daily_messages_total"].pack(fill="x", padx=8, pady=1)
        customtkinter.CTkLabel(reddit_arpa_settings_frame, text="Message Template:", font=("Arial", 9), text_color=UI_TEXT_MUTED).pack(anchor="w", padx=8, pady=(3,0))
        self.entries["reddit_proactive_message_template"] = customtkinter.CTkEntry(reddit_arpa_settings_frame, font=("Arial", 9), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
        self.entries["reddit_proactive_message_template"].pack(fill="x", padx=8, pady=(1,8))

        discord_arpa_settings_frame = customtkinter.CTkFrame(arpa_settings_section_frame, fg_color=UI_BACKGROUND_SECONDARY_1, corner_radius=8)
        discord_arpa_settings_frame.grid(row=0, column=1, padx=3, pady=3, sticky="nsew")
        discord_arpa_settings_frame.grid_columnconfigure(0, weight=1)

        customtkinter.CTkLabel(discord_arpa_settings_frame, text="Discord ARPA Settings", font=("Arial", 10, "bold"), text_color=UI_TEXT_PRIMARY).pack(pady=(5,3))
        self.entries["auto_proactive_discord_enabled"] = customtkinter.BooleanVar(value=False)
        customtkinter.CTkCheckBox(discord_arpa_settings_frame, text="Enable Discord ARPA", variable=self.entries["auto_proactive_discord_enabled"], font=("Arial", 9), text_color=UI_TEXT_PRIMARY, fg_color=UI_BUTTON_NORMAL_FG, checkmark_color=UI_PRIMARY_ACCENT).pack(anchor="w", padx=8, pady=1)
        customtkinter.CTkLabel(discord_arpa_settings_frame, text="Target Channel IDs (comma-separated):", font=("Arial", 9), text_color=UI_TEXT_MUTED).pack(anchor="w", padx=8, pady=(3,0))
        self.entries["discord_target_channels"] = customtkinter.CTkEntry(discord_arpa_settings_frame, font=("Arial", 9), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
        self.entries["discord_target_channels"].pack(fill="x", padx=8, pady=1)
        customtkinter.CTkLabel(discord_arpa_settings_frame, text="User Cooldown (hrs):", font=("Arial", 9), text_color=UI_TEXT_MUTED).pack(anchor="w", padx=8, pady=(3,0))
        self.entries["discord_proactive_cooldown_hours_per_user"] = customtkinter.CTkEntry(discord_arpa_settings_frame, font=("Arial", 9), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
        self.entries["discord_proactive_cooldown_hours_per_user"].pack(fill="x", padx=8, pady=1)
        customtkinter.CTkLabel(discord_arpa_settings_frame, text="Message Delay (s):", font=("Arial", 9), text_color=UI_TEXT_MUTED).pack(anchor="w", padx=8, pady=(3,0))
        self.entries["discord_proactive_min_delay_seconds_per_message"] = customtkinter.CTkEntry(discord_arpa_settings_frame, font=("Arial", 9), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
        self.entries["discord_proactive_min_delay_seconds_per_message"].pack(fill="x", padx=8, pady=1)
        customtkinter.CTkLabel(discord_arpa_settings_frame, text="Max Daily Messages:", font=("Arial", 9), text_color=UI_TEXT_MUTED).pack(anchor="w", padx=8, pady=(3,0))
        self.entries["discord_proactive_max_daily_messages_total"] = customtkinter.CTkEntry(discord_arpa_settings_frame, font=("Arial", 9), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
        self.entries["discord_proactive_max_daily_messages_total"].pack(fill="x", padx=8, pady=1)
        customtkinter.CTkLabel(discord_arpa_settings_frame, text="Message Template:", font=("Arial", 9), text_color=UI_TEXT_MUTED).pack(anchor="w", padx=8, pady=(3,0))
        self.entries["discord_proactive_message_template"] = customtkinter.CTkEntry(discord_arpa_settings_frame, placeholder_text="Message Template", font=("Arial", 9), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
        self.entries["discord_proactive_message_template"].pack(fill="x", padx=8, pady=(1,8))

        self.current_row_idx += 1 

        # --- NEW Section: User Uploaded Images ---
        self.current_row_idx += 1 
        user_uploads_section_frame = customtkinter.CTkFrame(self.content_frame, fg_color="transparent")
        user_uploads_section_frame.grid(row=self.current_row_idx, column=0, padx=10, pady=(10, 5), sticky="ew")
        user_uploads_section_frame.grid_columnconfigure(0, weight=1)

        customtkinter.CTkLabel(user_uploads_section_frame, text="Upload Your Own Images (for Jasmine's context)", font=("Arial", 12, "bold"), text_color=UI_TEXT_PRIMARY).pack(pady=(5,10))

        # File path selection for upload
        self.user_upload_path_frame = customtkinter.CTkFrame(user_uploads_section_frame, fg_color="transparent")
        self.user_upload_path_frame.pack(fill="x", padx=10, pady=2)
        self.user_upload_path_frame.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(self.user_upload_path_frame, text="Image to Upload (from your local PC):", font=settings_font, text_color=UI_TEXT_MUTED).grid(row=0, column=0, sticky="w")
        self.user_upload_entry = customtkinter.CTkEntry(self.user_upload_path_frame, font=settings_font, text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
        self.user_upload_entry.grid(row=1, column=0, sticky="ew")
        customtkinter.CTkButton(self.user_upload_path_frame, text="Browse", width=60, command=self.browse_user_upload_file, fg_color=UI_BUTTON_NORMAL_FG, hover_color=UI_BUTTON_NORMAL_HOVER, text_color=UI_TEXT_PRIMARY, font=("Arial", 10)).grid(row=1, column=1, padx=(5,0))

        # Label/Description for the image
        self.user_upload_label_frame = customtkinter.CTkFrame(user_uploads_section_frame, fg_color="transparent")
        self.user_upload_label_frame.pack(fill="x", padx=10, pady=2)
        self.user_upload_label_frame.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(self.user_upload_label_frame, text="Optional Label/Description:", font=settings_font, text_color=UI_TEXT_MUTED).grid(row=0, column=0, sticky="w")
        self.user_upload_label_entry = customtkinter.CTkEntry(self.user_upload_label_frame, placeholder_text="e.g., My avatar, My pet, My favorite landscape", font=settings_font, text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_BACKGROUND_SECONDARY_2, placeholder_text_color=UI_TEXT_MUTED)
        self.user_upload_label_entry.grid(row=1, column=0, sticky="ew")

        # Upload Button
        self.upload_user_image_button = customtkinter.CTkButton(user_uploads_section_frame, text="Upload Image to Server", command=self.upload_selected_image, fg_color=UI_PRIMARY_ACCENT, hover_color=UI_BUTTON_NORMAL_HOVER, text_color=UI_TEXT_PRIMARY, font=("Arial", 12, "bold"))
        self.upload_user_image_button.pack(pady=10)

        # Status Label for uploads
        self.user_upload_status_label = customtkinter.CTkLabel(user_uploads_section_frame, text="", font=("Arial", 10), text_color=UI_TEXT_PRIMARY)
        self.user_upload_status_label.pack(pady=(0, 5))

        self.current_row_idx += 1 

        # --- Save Button (at Very Bottom) ---
        self.save_button = customtkinter.CTkButton(self, text="Save and Close", command=self.save_and_close,
                                                     fg_color=UI_BUTTON_NORMAL_FG, hover_color=UI_BUTTON_NORMAL_HOVER, font=("Arial", 14, "bold"), height=40, text_color=UI_TEXT_PRIMARY)
        self.save_button.grid(row=self.current_row_idx, column=0, padx=20, pady=20, sticky="ew")
        
        self.load_config()
    
    def browse_path(self, entry_name_str):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            if entry_name_str in self.entries:
                entry_widget = self.entries[entry_name_str]
                entry_widget.delete(0, 'end')
                entry_widget.insert(0, folder_selected)
                if self.master_app and hasattr(self.master_app, 'config'):
                    self.master_app.config[entry_name_str] = folder_selected
                    self.master_app._insert_console_message(f"Selected path for {entry_name_str}: {folder_selected}", prefix="[System] ", tag="system_tag")
            else:
                self.master_app._insert_console_message(f"Error: Internal entry '{entry_name_str}' not found for path Browse.", prefix="[System] ", tag="error_tag")
        else:
            self.master_app._insert_console_message(f"No path selected for {entry_name_str}.", prefix="[System] ", tag="warning_tag")

    def browse_user_upload_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Image File to Upload",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.webp")]
        )
        if file_path:
            self.user_upload_entry.delete(0, 'end')
            self.user_upload_entry.insert(0, file_path)
            self.user_upload_status_label.configure(text="")

    def upload_selected_image(self):
        local_file_path = self.user_upload_entry.get().strip()
        image_label = self.user_upload_label_entry.get().strip()
        current_username = self.master_app.logged_in_username 

        if not current_username:
            self.user_upload_status_label.configure(text="Error: Not logged in. Cannot upload.", text_color=UI_STATUS_ERROR)
            return

        if not local_file_path:
            self.user_upload_status_label.configure(text="Please select an image file first.", text_color=UI_STATUS_WARNING)
            return
        if not os.path.exists(local_file_path):
            self.user_upload_status_label.configure(text="Error: File does not exist.", text_color=UI_STATUS_ERROR)
            return

        self.user_upload_status_label.configure(text="Uploading image...", text_color=UI_TEXT_MUTED)
        self.upload_user_image_button.configure(state="disabled")

        upload_thread = Thread(target=self._perform_upload_in_thread, args=(current_username, local_file_path, image_label))
        upload_thread.start()

    def _perform_upload_in_thread(self, user_id, file_path, label):
        """Internal function to handle the actual HTTP upload to Flask API."""
        upload_url = f"{API_BASE_URL}/upload_user_image"

        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = 'application/octet-stream'

        try:
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f, mime_type)}
                data = {'user_id': user_id}
                if label:
                    data['label'] = label

                response = requests.post(upload_url, files=files, data=data, timeout=60)
                response.raise_for_status()

                response_data = response.json()
                if response_data.get("message") == "Image uploaded successfully":
                    # This is the OCI public URL now!
                    uploaded_oci_url = response_data.get("image_url") 
                    self.master_app.after(0, lambda: self.user_upload_status_label.configure(
                        text=f"Upload successful! OCI URL: {uploaded_oci_url}", text_color=UI_STATUS_ACTIVE))
                    self.master_app.after(0, lambda: self.user_upload_entry.delete(0, 'end'))
                    self.master_app.after(0, lambda: self.user_upload_label_entry.delete(0, 'end'))
                    self.master_app._insert_console_message(f"Client uploaded image for {user_id} to OCI: {uploaded_oci_url}", prefix="[Client Upload] ", tag="system_tag")
                    
                    # Force a refresh of the dashboard data to reflect new image count
                    self.master_app.after(0, self.master_app.refresh_dashboard_data) 
                else:
                    error_msg = response_data.get("error", "Unknown server error.")
                    self.master_app.after(0, lambda: self.user_upload_status_label.configure(
                        text=f"Upload failed: {error_msg}", text_color=UI_STATUS_ERROR))
                    self.master_app._insert_console_message(f"Client upload failed for {user_id}: {error_msg}", prefix="[Client Upload Error] ", tag="error_tag")

        except requests.exceptions.RequestException as e:
            error_msg = f"Network Error: {e}"
            if hasattr(e, 'response') and e.response is not None:
                error_msg += f" (Server response: {e.response.text[:100]}...)"
            self.master_app.after(0, lambda: self.user_upload_status_label.configure(
                text=f"Upload failed: {error_msg}", text_color=UI_STATUS_ERROR))
            self.master_app._insert_console_message(f"Client upload network error for {user_id}: {error_msg}", prefix="[Client Upload Error] ", tag="error_tag")
        except Exception as e:
            self.master_app.after(0, lambda: self.user_upload_status_label.configure(
                text=f"Upload failed: An unexpected error occurred: {e}", text_color=UI_STATUS_ERROR))
            self.master_app._insert_console_message(f"Client upload unexpected error for {user_id}: {e}", prefix="[Client Upload Error] ", tag="error_tag")
        finally:
            self.master_app.after(0, lambda: self.upload_user_image_button.configure(state="normal"))

    def save_and_close(self):
        current_window_settings = {}
        for key, entry_or_var in self.entries.items():
            if isinstance(entry_or_var, customtkinter.BooleanVar):
                current_window_settings[key] = entry_or_var.get()
            elif isinstance(entry_or_var, customtkinter.CTkEntry):
                if key in ["reddit_target_subreddits", "discord_target_channels"]:
                    current_window_settings[key] = [s.strip() for s in entry_or_var.get().split(',') if s.strip()]
                elif key in ["min_response_delay_seconds", "max_response_delay_seconds",
                             "reddit_proactive_cooldown_hours_per_user", "reddit_proactive_min_delay_seconds_per_message",
                             "reddit_proactive_max_daily_messages_total",
                             "discord_proactive_cooldown_hours_per_user", "discord_proactive_min_delay_seconds_per_message",
                             "discord_proactive_max_daily_messages_total"]:
                    try:
                        current_window_settings[key] = int(entry_or_var.get())
                    except ValueError:
                        current_window_settings[key] = 0
                        self.master_app._insert_console_message(f"Warning: Invalid number for '{key}'. Set to 0.", prefix="[System] ", tag="warning_tag")
                else: 
                    current_window_settings[key] = entry_or_var.get()

        full_config_to_save = {}
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                full_config_to_save = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        full_config_to_save.update(current_window_settings)

        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(full_config_to_save, f, indent=4)
            self.master_app._insert_console_message("General settings saved.", prefix="[System] ", tag="system_tag")
            self.destroy()
        except Exception as e:
            self.master_app._insert_console_message(f"Error saving settings: {e}", prefix="[System] ", tag="error_tag")

    def load_config(self):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
            for key, entry_or_var in self.entries.items():
                if isinstance(entry_or_var, customtkinter.BooleanVar):
                    entry_or_var.set(config.get(key, False))
                elif isinstance(entry_or_var, customtkinter.CTkEntry):
                    value = config.get(key, "")
                    if key in ["reddit_target_subreddits", "discord_target_channels"]:
                        if isinstance(value, list):
                            value = ", ".join(value)
                    
                    entry_or_var.delete(0, 'end')
                    entry_or_var.insert(0, str(value))
        except (FileNotFoundError, json.JSONDecodeError):
            self.master_app._insert_console_message("Warning: config.json not found or invalid for SettingsWindow. Using defaults.", prefix="[System] ", tag="warning_tag")

class DebugWindow(customtkinter.CTkToplevel):
    def __init__(self, master=None, app_instance=None, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.master_app = app_instance

        self.title("Debug Actions")
        self.geometry("300x250") 
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.focus_force()

        self.configure(fg_color=UI_BACKGROUND_PRIMARY)
        self.title_label = customtkinter.CTkLabel(self, text="Troubleshooting", font=("Arial", 16, "bold"), text_color=UI_TEXT_PRIMARY)
        self.title_label.pack(pady=(10,5))
        self.info_label = customtkinter.CTkLabel(self, text="Try these actions to resolve issues.", text_color=UI_TEXT_MUTED)
        self.info_label.pack(pady=5)
        self.server_test_button = customtkinter.CTkButton(self, text="Run Server Test", command=self.run_server_test, fg_color=UI_BUTTON_NORMAL_FG, hover_color=UI_BUTTON_NORMAL_HOVER, text_color=UI_TEXT_PRIMARY)
        self.server_test_button.pack(pady=5, padx=20, fill="x")
        self.refresh_users_button = customtkinter.CTkButton(self, text="Refresh Active Users", command=self.refresh_active_users, fg_color=UI_BUTTON_NORMAL_FG, hover_color=UI_BUTTON_NORMAL_HOVER, text_color=UI_TEXT_PRIMARY)
        self.refresh_users_button.pack(pady=5, padx=20, fill="x")
        self.restart_button = customtkinter.CTkButton(self, text="Restart Application", command=self.restart_app, fg_color=UI_BUTTON_DANGER_FG, hover_color=UI_BUTTON_DANGER_HOVER, text_color=UI_TEXT_PRIMARY)
        self.restart_button.pack(pady=5, padx=20, fill="x")

    def run_server_test(self):
        self.master_app._insert_console_message("Running server test...", prefix="[Debug] ", tag="system_tag")
        try:
            response = requests.get(f"{API_BASE_URL}/status", timeout=2)
            response.raise_for_status()
            if response.status_code == 200:
                self.master_app._insert_console_message("Server test PASSED. API is responsive.", prefix="[Debug] ", tag="system_tag")
            else:
                self.master_app._insert_console_message(f"Server test FAILED. Status Code: {response.status_code}", prefix="[Debug] ", tag="error_tag")
        except requests.exceptions.RequestException as e:
            self.master_app._insert_console_message(f"Server test FAILED. API is not reachable: {e}", prefix="[Debug] ", tag="error_tag")
        finally:
            self.destroy()

    def refresh_active_users(self):
        self.master_app._insert_console_message("Manually refreshing active user data...", prefix="[System] ", tag="system_tag")
        self.master_app.update_status() # This now triggers the overall refresh including active users
        self.master_app._repopulate_chat_display_for_current_tab() # Refresh chat logs for current user too
        self.destroy()

    def restart_app(self):
        self.master_app.on_closing()

class ConfirmationWindow(customtkinter.CTkToplevel):
    def __init__(self, master=None, app_instance=None, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.master_app = app_instance

        self.title("")
        self.geometry("350x120") 
        self.resizable(False, False)
        self.transient(master)
        self.grab_set() 
        self.focus_force()
        self.configure(fg_color=UI_BACKGROUND_PRIMARY)

        self.grid_columnconfigure((0,1), weight=1)

        self.label = customtkinter.CTkLabel(self, text="Are you sure you want to close the application?", text_color=UI_TEXT_PRIMARY)
        self.label.grid(row=0, column=0, columnspan=2, padx=20, pady=10)

        self.cancel_button = customtkinter.CTkButton(self, text="Cancel", command=self.destroy,
                                                     fg_color=UI_BUTTON_NORMAL_FG, hover_color=UI_BUTTON_NORMAL_HOVER, text_color=UI_TEXT_PRIMARY)
        self.cancel_button.grid(row=1, column=0, padx=10, pady=10)

        self.close_button = customtkinter.CTkButton(self, text="Close", command=self.master_app.on_closing, # Directly call on_closing
                                                     fg_color=UI_BUTTON_DANGER_FG, hover_color=UI_BUTTON_DANGER_HOVER, text_color=UI_TEXT_PRIMARY)
        self.close_button.grid(row=1, column=1, padx=10, pady=10)

class UserListWindow(customtkinter.CTkToplevel):
    def __init__(self, master=None, app_instance=None, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.master_app = app_instance
        self.title("Active Users")
        self.geometry("300x400") 
        self.resizable(False, False)
        self.transient(master)

        self.configure(fg_color=UI_BACKGROUND_PRIMARY)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        customtkinter.CTkLabel(self, text="Select a User:", font=("Arial", 14, "bold"), text_color=UI_TEXT_PRIMARY).grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        self.user_scroll_frame = customtkinter.CTkScrollableFrame(self, fg_color=UI_BACKGROUND_SECONDARY_1)
        self.user_scroll_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.user_scroll_frame.grid_columnconfigure(0, weight=1)

        self.user_buttons = {}

        self.load_users()

    def load_users(self):
        for widget in self.user_scroll_frame.winfo_children():
            widget.destroy()
        self.user_buttons = {}

        current_tab_name = self.master_app.chat_log_tabview.get()
        base_platform_key = current_tab_name.split(" ")[0].lower()

        # Get the full detailed user funnel status from the latest API /status call
        funnel_data = self.master_app._get_current_funnel_data().get('user_funnel_status_detailed', {})

        active_users_on_platform = []
        for user_id, user_info in funnel_data.items():
            user_platform_in_data = user_info.get('platform')
            platform_matches = False
            if user_platform_in_data == base_platform_key:
                platform_matches = True
            elif base_platform_key == "facebook" and user_platform_in_data in ["facebook", "facebook_postback"]:
                platform_matches = True
            elif base_platform_key == "web" and user_platform_in_data == "browser_autonomous":
                platform_matches = True

            if platform_matches and user_info.get('status') in ["in_progress", "funneled", "permanent_active"]: # Include 'permanent_active' users if applicable
                last_active_str = user_info.get('last_active')
                display_time = "N/A"
                if last_active_str:
                    try:
                        last_active_dt_utc = datetime.fromisoformat(last_active_str.replace('Z', '+00:00'))
                        local_last_active_dt = last_active_dt_utc.astimezone()  
                        display_time = local_last_active_dt.strftime('%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        display_time = "Invalid Time"

                manual_mode_status = " (Manual)" if user_info.get('manual_mode_active', False) else ""
                cross_platform_id = user_info.get('cross_platform_id')
                nickname_status = user_info.get('nickname_status')

                user_display_name = user_id
                if cross_platform_id:
                    user_display_name = f"{user_id} ({cross_platform_id})"

                nickname_status_text = ""
                if nickname_status == "pending_input":
                    nickname_status_text = " (Ask Name)"
                elif nickname_status == "assigned":
                    nickname_status_text = " (Name Ready)"
                elif nickname_status == "confirmed":
                    nickname_status_text = " (Name Confirmed)"

                active_users_on_platform.append({
                    'user_id': user_id,
                    'display_text': f"{user_display_name}{manual_mode_status}{nickname_status_text} (Last Active: {display_time})",
                    'platform': user_platform_in_data,
                    'last_active': last_active_str,
                    'full_user_data': user_info # Store the full user_info for direct use in select_user_and_display_chat
                })

        active_users_on_platform.sort(key=lambda x: datetime.fromisoformat(x['last_active'].replace('Z', '+00:00')) if 'last_active' in x and x['last_active'] else datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        if not active_users_on_platform:
            customtkinter.CTkLabel(self.user_scroll_frame, text="No active users on this platform.", font=("Arial", 12), text_color=UI_TEXT_MUTED).pack(pady=20)
            return

        row_idx = 0
        for user_data in active_users_on_platform:
            user_id = user_data['user_id']
            display_text = user_data['display_text']
            platform_in_data = user_data['platform']
            full_user_data_for_select = user_data['full_user_data'] # Pass the full data

            user_status_val = full_user_data_for_select.get('status', 'unknown') # Use 'status' directly
            button_text_color = UI_TEXT_PRIMARY
            if user_status_val == 'in_progress': # Check 'status' key
                button_text_color = UI_STATUS_WARNING
            elif user_status_val == 'funneled' or user_status_val == 'permanent_active': # Also check 'status' key
                button_text_color = UI_STATUS_ACTIVE
            elif user_status_val == 'expired_trial':
                button_text_color = UI_STATUS_ERROR


            button = customtkinter.CTkButton(
                self.user_scroll_frame,
                text=display_text,
                command=lambda uid=user_id, plat=platform_in_data, u_data=full_user_data_for_select: self.select_user_and_display_chat(uid, plat, u_data),
                font=("Arial", 12),
                fg_color=UI_BUTTON_NORMAL_FG,
                hover_color=UI_BUTTON_NORMAL_HOVER,
                height=30,
                anchor="w",
                text_color=button_text_color
            )
            button.grid(row=row_idx, column=0, sticky="ew", pady=2, padx=5)
            self.user_buttons[user_id] = button
            row_idx += 1

    def select_user_and_display_chat(self, user_id, platform, user_full_data):
        self.master_app.reset_platform_notifications(platform)
        self.master_app._insert_console_message(f"Selected user {user_id} on {platform} for chat view.", prefix="[System] ", tag="system_tag")
        
        # CRITICAL: Update the main app's currently selected user and its full data
        self.master_app.current_manual_mode_user_id = user_id
        self.master_app.current_manual_mode_platform = platform
        self.master_app.user_full_data = user_full_data # Pass the full data directly

        tab_mapping = {
            "web": "Web Chat",
            "telegram": "Telegram",
            "reddit": "Reddit",
            "discord": "Discord",
            "facebook": "Facebook",
            "facebook_postback": "Facebook",
            "browser_autonomous": "Web Chat"
        }
        target_tab_name = tab_mapping.get(platform, "Web Chat")
        self.master_app.chat_log_tabview.set(target_tab_name)
        
        # Now repopulate chat display and update manual mode UI
        self.master_app._repopulate_chat_display_for_current_tab()
        self.master_app._update_manual_mode_ui(user_full_data.get('manual_mode_active', False)) # Update UI based on this user's manual mode status
        
        self.destroy()

class UserHistoryWindow(customtkinter.CTkToplevel):
    def __init__(self, master=None, app_instance=None, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.master_app = app_instance
        self.title("User History")
        self.geometry("500x600") 
        self.resizable(True, True)
        self.transient(master)

        self.configure(fg_color=UI_BACKGROUND_PRIMARY)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        customtkinter.CTkLabel(header_frame, text="All Conversations", font=("Arial", 16, "bold"), text_color=UI_TEXT_PRIMARY).pack(side="left")
        
        refresh_button = customtkinter.CTkButton(header_frame, text="Refresh", width=80, command=self.load_user_history, fg_color=UI_BUTTON_NORMAL_FG, hover_color=UI_BUTTON_NORMAL_HOVER, text_color=UI_TEXT_PRIMARY)
        refresh_button.pack(side="right")

        self.history_scroll_frame = customtkinter.CTkScrollableFrame(self, fg_color=UI_BACKGROUND_SECONDARY_1)
        self.history_scroll_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.history_scroll_frame.grid_columnconfigure(0, weight=1)

        self.load_user_history()

    def load_user_history(self):
        for widget in self.history_scroll_frame.winfo_children():
            widget.destroy()

        try:
            # Fetch from the new /status endpoint for detailed user_funnel_status_detailed
            response = requests.get(f"{API_BASE_URL}/status", timeout=3)
            response.raise_for_status()
            funnel_data_detailed = response.json().get('user_funnel_status_detailed', {})
            
            if not funnel_data_detailed:
                customtkinter.CTkLabel(self.history_scroll_frame, text="No user history found.", font=("Arial", 12), text_color=UI_TEXT_MUTED).pack(pady=20)
                return

            user_list_sorted = list(funnel_data_detailed.items())
            
            # Sort by last_active timestamp
            user_list_sorted.sort(
                key=lambda item: datetime.fromisoformat(item[1].get('last_active', '1970-01-01T00:00:00.000000').replace('Z', '+00:00')) if item[1].get('last_active') else datetime.min.replace(tzinfo=timezone.utc),
                reverse=True
            )

            for user_id, user_info in user_list_sorted:
                # Use the 'funnel_state' or 'status' key for color/display logic
                status_val = user_info.get('status', 'unknown') # Legacy status
                funnel_state_val = user_info.get('funnel_state', 'none') # New funnel_state from UserDataManager

                text_color = UI_TEXT_MUTED
                if status_val == 'in_progress' or funnel_state_val != 'none': # User is active in funnel
                    text_color = UI_STATUS_WARNING
                if status_val == 'funneled' or funnel_state_val in ['funneled_to_telegram', 'funneled_to_facebook', 'initiated_website', 'final_success', 'permanent_active']:
                    text_color = UI_STATUS_ACTIVE
                if status_val == 'expired_trial':
                    text_color = UI_STATUS_ERROR


                platform = user_info.get('platform', 'N/A').capitalize()
                last_active_str = user_info.get('last_active')
                
                display_date = "N/A"
                if last_active_str:
                    try:
                        dt_obj = datetime.fromisoformat(last_active_str.replace('Z', '+00:00'))
                        display_date = dt_obj.astimezone().strftime('%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        display_date = "Invalid Date"
                
                cross_platform_id = user_info.get('cross_platform_id')
                nickname_status = user_info.get('nickname_status')

                user_display_name_history = user_id
                if cross_platform_id:
                    user_display_name_history = f"{user_id} ({cross_platform_id})"

                nickname_status_text_history = ""
                if nickname_status == "pending_input":
                    nickname_status_text_history = " (Ask Name)"
                elif nickname_status == "assigned":
                    nickname_status_text_history = " (Name Ready)"
                elif nickname_status == "confirmed":
                    nickname_status_text_history = " (Name Confirmed)"
                
                manual_mode_status_history = " (Manual)" if user_info.get('manual_mode_active', False) else ""

                display_text = f"{user_display_name_history} ({platform}){manual_mode_status_history}{nickname_status_text_history} - Last Active: {display_date}"

                label = customtkinter.CTkLabel(
                    self.history_scroll_frame,
                    text=display_text,
                    font=("Arial", 12),
                    text_color=text_color,
                    anchor="w"
                )
                label.pack(fill="x", padx=5, pady=2)

        except requests.exceptions.RequestException as e:
            error_label = customtkinter.CTkLabel(self.history_scroll_frame, text=f"Error fetching user history:\n{e}", text_color=UI_STATUS_ERROR)
            error_label.pack(pady=20)
        except Exception as e:
            error_label = customtkinter.CTkLabel(self.history_scroll_frame, text=f"An unexpected error occurred:\n{e}", text_color=UI_STATUS_ERROR)
            error_label.pack(pady=20)

class EmojiPickerWindow(customtkinter.CTkToplevel):
    def __init__(self, master, on_emoji_select_callback):
        super().__init__(master)
        self.on_emoji_select = on_emoji_select_callback
        
        self.title("Select an Emoji")
        self.geometry("300x400")
        self.after(250, lambda: self.iconbitmap(''))
        self.transient(master)
        self.lift()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        scrollable_frame = customtkinter.CTkScrollableFrame(self, label_text="Emojis")
        scrollable_frame.pack(fill="both", expand=True, padx=5, pady=5)

        emoji_list = list(emoji.EMOJI_DATA.keys())[::12]
        
        row, col = 0, 0
        for e in emoji_list:
            emoji_button = customtkinter.CTkButton(
                scrollable_frame,
                text=e,
                width=40,
                height=40,
                font=("Segoe UI Emoji", 18),
                command=lambda chosen_emoji=e: self.select_emoji(chosen_emoji)
            )
            emoji_button.grid(row=row, column=col, padx=2, pady=2)
            
            col += 1
            if col > 4:
                col = 0
                row += 1

    def select_emoji(self, emoji_char):
        self.on_emoji_select(emoji_char)
        self.destroy()

class App(customtkinter.CTk):
    
    PANEL_CLOSED_X_COMPENSATION = 109

    def __init__(self):
        super().__init__()

        self.polling_stop_event = Event()
        self.polling_thread = None  
        self.is_closing = False

        print("DEBUG: App class __init__ started. Setting up main window.")

        try:
            print("DEBUG: Setting window properties.")
            self.title("Jasmine AI Control Panel")
            self.geometry("1400x1250")
            self.minsize(1100, 1050)
            self.resizable(True, True)
            self.protocol("WM_DELETE_WINDOW", self.on_closing)
            print("DEBUG: Window properties set.")

            self.api_process = None
            self.telegram_process = None
            self.reddit_process = None
            self.discord_process = None
            self.facebook_process = None
            
            self.settings_window = None
            self.debug_window = None
            self.confirmation_window = None
            self.user_list_window = None
            self.user_history_window = None
            
            self.left_panel_visible = True
            self.is_closing = False
            
            self.config = {}
            print("DEBUG: Calling load_initial_config_file().")
            self.load_initial_config_file() 
            print("DEBUG: load_initial_config_file() completed.")

            self.api_queue, self.telegram_queue, self.reddit_queue, self.discord_queue = Queue(), Queue(), Queue(), Queue()
            self.stop_event = Event()

            self.notification_badges = {}
            self.chat_frames = {}
            self.chat_row_counters = {}
            self.last_log_entry_index = 0

            self.current_manual_mode_user_id = None
            self.current_manual_mode_platform = None
            
            self.logged_in_username = None 
            self.is_trial_user = False  
            self.trial_expiry_time = None  
            self.user_full_data = None      # CRITICAL: Store the full user_data here after login
            
            self.username_display_label = None 
            self.trial_status_label = None     
            self.expiry_date_label = None      

            self.gui_active = False 
                
            self.app_config_vars = {} 
            
            self.typing_animation_active = False
            self.typing_dots_count = 0

            print("DEBUG: Applying background color and grid configure.")
            self.configure(fg_color=UI_BACKGROUND_PRIMARY)
            self.grid_columnconfigure(1, weight=1) 
            self.grid_columnconfigure(0, weight=0) 
            self.grid_columnconfigure(2, weight=0) 
            self.grid_rowconfigure(0, weight=1) 
            self.grid_rowconfigure(1, weight=0) 
            print("DEBUG: Background and grid configured.")

            print("DEBUG: Calling UI creation methods.")
            
            self.create_left_sidebar() 
            print("DEBUG: create_left_sidebar() completed.")

            self.create_center_content() 
            print("DEBUG: create_center_content() completed.")

            self.create_right_pillar() 
            print("DEBUG: create_right_pillar() completed.")

            self.create_bottom_bar() 
            print("DEBUG: create_bottom_bar() completed.")
            
            print("DEBUG: Setting up console tags.")
            self._setup_console_tags() 
            print("DEBUG: Console tags setup completed.")

            if hasattr(self, 'manual_mode_controls_frame') and self.manual_mode_controls_frame:
                print("DEBUG: Hiding manual mode controls.")
                self.manual_mode_controls_frame.grid_forget()
                print("DEBUG: Manual mode controls hidden.")
            else:
                print("WARNING: manual_mode_controls_frame not found during init, skipping hide.")

            print("DEBUG: Populating ARPA UI from config.")
            self._populate_arpa_ui_from_config() 
            print("DEBUG: ARPA UI populated.")
            
            print("DEBUG: Initial periodic updates scheduled. (No, actually waiting for login).") 
            
            self.disable_all_gui_interaction() 
            self.hide_trial_expired_message() 
            
        except Exception as e:
            print(f"ERROR: An exception occurred during App __init__ setup: {e}")
            messagebox.showerror("Initialization Error", f"Failed to initialize main application:\n\n{e}\n\nCheck console for traceback.")
            traceback.print_exc()
            self.destroy()
            return

    def handle_login_success(self, user_data_from_api):
        """
        Processes successful login data (the dashboard_data payload) and refreshes the GUI.
        user_data_from_api should be the entire dictionary returned by /login's 'user_data' field.
        """
        self.logged_in_username = user_data_from_api.get("user_id") # 'user_id' is the new key from UDM dashboard
        self.is_trial_user = user_data_from_api.get("current_state", {}).get("trial_status", "Permanent") != "Permanent" # Assuming trial_status in current_state
        self.trial_expiry_time = user_data_from_api.get("current_state", {}).get("expiry_date") # Assuming expiry_date in current_state (or pass from login directly)
        self.user_full_data = user_data_from_api # Store the full data for later use

        print(f"GUI: Login data received by App: {self.logged_in_username}, Trial: {self.is_trial_user}")

        # Determine if trial is truly expired (API should already handle this, but re-check for GUI status)
        is_actually_expired = False
        if self.is_trial_user and self.trial_expiry_time == "Expired": # API already sends "Expired" string
            is_actually_expired = True
        elif self.is_trial_user and self.trial_expiry_time and self.trial_expiry_time != "Permanent":
            try:
                expiry_dt_utc = datetime.fromisoformat(self.trial_expiry_time.replace('Z', '+00:00'))
                if datetime.now(timezone.utc) > expiry_dt_utc:
                    is_actually_expired = True
            except ValueError:
                print(f"GUI Warning: Invalid expiry_date format: {self.trial_expiry_time}")
                is_actually_expired = True # Treat as expired if format is bad

        if is_actually_expired:
            self.show_trial_expired_message()
            print(f"GUI: Detected expired trial for {self.logged_in_username}. GUI disabled.")
        else:
            self.enable_all_gui_interaction()
            self.hide_trial_expired_message()
            print(f"GUI: {self.logged_in_username} trial active. GUI enabled.")

            self.refresh_gui_for_current_user(self.user_full_data)

            self.polling_stop_event.clear()
            self.polling_thread = Thread(target=self.poll_server_status, daemon=True)
            self.polling_thread.start()
            print("GUI: Started API status polling thread AFTER successful login.")

            self.after(100, self.process_console_queues)
            self.after(100, self.update_notification_counts)
            self.after(100, self.update_status) # Force an initial status update, now handled by poll_server_status

    def refresh_gui_for_current_user(self, user_data):
        """
        Clears all user-specific UI elements and repopulates them
        with data for the currently logged-in user.
        Called after successful login or user selection in admin view.
        """
        if not user_data:
            print("GUI Warning: refresh_gui_for_current_user called with no user_data.")
            self.clear_all_user_specific_displays()
            return

        self.clear_all_user_specific_displays()
        
        # Populate GUI elements with data from user_data
        if self.username_display_label:
            self.username_display_label.configure(text=f"User: {user_data.get('user_id', 'N/A')}")
        if self.trial_status_label:
            self.trial_status_label.configure(text=f"Status: {user_data.get('current_state',{}).get('trial_status', 'N/A')}")
        if self.expiry_date_label:
            self.expiry_date_label.configure(text=f"Expires: {user_data.get('current_state',{}).get('expiry_date', 'N/A')}")

        # Update Conversations Count (from user_data.stats.total_conversations)
        if self.active_users_count_label: # This label is currently for 'total conversations' in your GUI screenshot
            conv_count = user_data.get("stats", {}).get("total_conversations", 0)
            self.active_users_count_label.configure(text=str(conv_count))

        self.current_manual_mode_user_id = user_data.get('user_id')
        self.current_manual_mode_platform = user_data.get("current_state",{}).get("platform", "web_gui")
        
        self._repopulate_chat_display_for_current_tab()
        
        # Update Manual Mode Toggle state based on user_data
        is_manual_active = user_data.get("current_state",{}).get("manual_mode_active", False)
        self._update_manual_mode_ui(is_manual_active)

        print(f"GUI: Display refreshed for user: {user_data.get('user_id', 'N/A')}.")

    def clear_all_user_specific_displays(self):
        """Clears all UI elements that display user-specific data."""
        if self.active_users_count_label:
            self.active_users_count_label.configure(text="0")

        for platform_key in self.chat_frames:
            log_frame = self.chat_frames[platform_key]
            for widget in log_frame.winfo_children():
                widget.destroy()
            self.chat_row_counters[platform_key] = 0
        self.last_log_entry_index = 0

        if self.username_display_label:
            self.username_display_label.configure(text="User: N/A")
        if self.trial_status_label:
            self.trial_status_label.configure(text="Status: N/A")
        if self.expiry_date_label:
            self.expiry_date_label.configure(text="Expires: N/A")

        self.current_manual_mode_user_id = None
        self.current_manual_mode_platform = None
        # Ensure 'pause_resume_button' exists before configuring
        if hasattr(self, 'pause_resume_button'):
            self.pause_resume_button.configure(text="No Active User", state="disabled", fg_color=UI_BACKGROUND_SECONDARY_2, text_color=UI_TEXT_MUTED)
        if hasattr(self, 'manual_mode_controls_frame'):
            self.manual_mode_controls_frame.grid_forget() 
            self.center_panel_frame.grid_rowconfigure(1, weight=4) 
            self.center_panel_frame.grid_rowconfigure(2, weight=0)

        print("GUI: All user-specific displays cleared.")

    def disable_all_gui_interaction(self):
        """Disables all interactive elements in the main GUI."""
        self.gui_active = False
        self.web_chat_button.configure(state="disabled")
        self.stop_web_chat_button.configure(state="disabled")
        self.telegram_button.configure(state="disabled")
        self.stop_telegram_button.configure(state="disabled")
        self.reddit_button.configure(state="disabled")
        self.stop_reddit_button.configure(state="disabled")
        self.discord_button.configure(state="disabled")
        self.stop_discord_button.configure(state="disabled")
        self.kill_all_button.configure(state="disabled")
        
        if hasattr(self, 'manual_message_entry'):
            self.manual_message_entry.configure(state="disabled")
        if hasattr(self, 'send_manual_button'):
            self.send_manual_button.configure(state="disabled")
        if hasattr(self, 'send_file_button'):
            self.send_file_button.configure(state="disabled")
        if hasattr(self, 'emoji_button'): # Disable emoji button too
            self.emoji_button.configure(state="disabled")

        if hasattr(self, 'save_arpa_settings_button'):
            self.save_arpa_settings_button.configure(state="disabled")
        
        if hasattr(self, 'send_manual_proactive_button_pillar'):
            self.send_manual_proactive_button_pillar.configure(state="disabled")

        # Disable all entry widgets in SettingsWindow if it's open
        if self.settings_window and self.settings_window.winfo_exists():
            for key, entry_or_var in self.settings_window.entries.items():
                if isinstance(entry_or_var, customtkinter.CTkEntry):
                    entry_or_var.configure(state="disabled")
                elif isinstance(entry_or_var, customtkinter.CTkCheckBox):
                    entry_or_var.configure(state="disabled")
            self.settings_window.save_button.configure(state="disabled")
            self.settings_window.upload_user_image_button.configure(state="disabled")


    def enable_all_gui_interaction(self):
        """Enables all interactive elements in the main GUI."""
        self.gui_active = True
        self.web_chat_button.configure(state="normal")
        self.telegram_button.configure(state="normal")
        self.reddit_button.configure(state="normal")
        self.discord_button.configure(state="normal")
        self.kill_all_button.configure(state="normal")
        
        if hasattr(self, 'manual_message_entry'):
            self.manual_message_entry.configure(state="normal")
        if hasattr(self, 'send_manual_button'):
            self.send_manual_button.configure(state="normal")
        if hasattr(self, 'send_file_button'):
            self.send_file_button.configure(state="normal")
        if hasattr(self, 'emoji_button'):
            self.emoji_button.configure(state="normal")

        if hasattr(self, 'save_arpa_settings_button'):
            self.save_arpa_settings_button.configure(state="normal")

        if hasattr(self, 'send_manual_proactive_button_pillar'):
            self.send_manual_proactive_button_pillar.configure(state="normal")
        
        # Enable all entry widgets in SettingsWindow if it's open
        if self.settings_window and self.settings_window.winfo_exists():
            for key, entry_or_var in self.settings_window.entries.items():
                if isinstance(entry_or_var, customtkinter.CTkEntry):
                    entry_or_var.configure(state="normal")
                elif isinstance(entry_or_var, customtkinter.CTkCheckBox):
                    entry_or_var.configure(state="normal")
            self.settings_window.save_button.configure(state="normal")
            self.settings_window.upload_user_image_button.configure(state="normal")


    def show_trial_expired_message(self):
        """Displays the trial expired message and disables GUI."""
        self.disable_all_gui_interaction()
        if hasattr(self, 'status_label_bottom'): # Ensure this widget exists
            self.status_label_bottom.configure(text="Trial key expired. Join the Discord for activation key.", text_color=UI_STATUS_ERROR) 
        self.join_discord_button.configure(state="normal")
        self.join_telegram_button.configure(state="normal")

    def hide_trial_expired_message(self):
        """Hides the trial expired message."""
        if hasattr(self, 'status_label_bottom'):
            self.status_label_bottom.configure(text="")

    def poll_server_status(self):
        """Polls the API server periodically for overall status, and if logged in, for user-specific trial expiry."""
        print("GUI: Started API status polling thread.")
        while not self.polling_stop_event.is_set():
            if not (hasattr(self, 'server_status_indicator') and self.server_status_indicator.winfo_exists()):
                self.polling_stop_event.wait(1)
                continue
            
            try:
                response = requests.get(f"{API_BASE_URL}/status", timeout=5)
                response.raise_for_status()
                status_data = response.json()

                self.after(0, lambda: self.server_status_indicator.configure(fg_color=UI_STATUS_ACTIVE))
                
                # Fetch detailed user funnel status
                user_funnel_status_detailed = status_data.get('user_funnel_status_detailed', {})
                
                # Check current logged-in user's trial status based on the detailed data
                if self.logged_in_username and self.user_full_data: # Ensure full_data is loaded
                    current_user_dashboard_data = user_funnel_status_detailed.get(self.logged_in_username, {})
                    
                    if current_user_dashboard_data.get('current_state', {}).get('status') == "expired_trial":
                        if self.gui_active:
                            self.after(0, self.show_trial_expired_message)
                            print(f"GUI: Detected expired trial for {self.logged_in_username}. GUI disabled.")
                    elif not self.gui_active: # If GUI was disabled and is now active again (e.g., re-enabled trial)
                        self.after(0, self.enable_all_gui_interaction)
                        self.after(0, self.hide_trial_expired_message)
                        print(f"GUI: {self.logged_in_username} trial re-activated. GUI enabled.")
                        # Force a full refresh for this user after re-enabling GUI
                        # Fetch the latest user data again in case other fields changed
                        re_fetch_response = requests.get(f"{API_BASE_URL}/api/user/{self.logged_in_username}/dashboard", timeout=5)
                        re_fetch_response.raise_for_status()
                        self.user_full_data = re_fetch_response.json() # Update stored full user data
                        self.after(0, lambda: self.refresh_gui_for_current_user(self.user_full_data))
                
                # Update global counts (In Progress, Funneled) based on /status endpoint
                self.after(0, lambda: self.in_progress_label.configure(text=f"In Progress: {status_data.get('in_progress_funnel_count', 0)}"))
                self.after(0, lambda: self.funneled_label.configure(text=f"Funneled: {status_data.get('funneled_users_count', 0)}"))
                # "Conversations" label is for total active sessions
                self.after(0, lambda: self.active_users_count_label.configure(text=str(status_data.get('total_active_sessions', 0))))

                arpa_status_details = status_data.get('arpa_status_details', {})
                arpa_overall_status = "Off"
                arpa_current_action = "Idle"
                arpa_target = "N/A"
                arpa_last_user = "None"
                arpa_session_msgs = 0
                arpa_next_run = "N/A"
                arpa_overall_enabled = False

                for platform_name, p_arpa_data in arpa_status_details.items():
                    if p_arpa_data.get("overall_status") == "On":
                        arpa_overall_enabled = True
                    
                    if p_arpa_data.get("current_action") != "Idle":
                        arpa_current_action = p_arpa_data.get("current_action", "Running")
                        arpa_target = p_arpa_data.get("current_target", "N/A")
                        arpa_last_user = p_arpa_data.get("last_proactive_user", "None")
                        arpa_session_msgs += p_arpa_data.get("session_messages_sent", 0)
                        arpa_next_run = p_arpa_data.get("next_run_time", "N/A")

                self.after(0, lambda: self.arpa_overall_status_label.configure(text=f"Overall Status: {'On' if arpa_overall_enabled else 'Off'}",
                                                                                text_color=UI_STATUS_ACTIVE if arpa_overall_enabled else UI_TEXT_MUTED))
                self.after(0, lambda: self.arpa_current_action_label.configure(text=f"Action: {arpa_current_action}"))
                self.after(0, lambda: self.arpa_target_label.configure(text=f"Target: {arpa_target}"))
                self.after(0, lambda: self.arpa_last_user_label.configure(text=f"Last User: {arpa_last_user}"))
                self.after(0, lambda: self.arpa_session_msgs_label.configure(text=f"Msgs Sent (Session): {arpa_session_msgs}"))

                if arpa_next_run != 'N/A':
                    try:
                        next_run_dt_utc = datetime.fromisoformat(arpa_next_run.replace('Z', '+00:00'))
                        local_next_run_dt = next_run_dt_utc.astimezone()
                        self.after(0, lambda: self.arpa_next_run_label.configure(text=f"Next Run: {local_next_run_dt.strftime('%H:%M:%S')}"))
                    except ValueError:
                        self.after(0, lambda: self.arpa_next_run_label.configure(text="Next Run: Invalid Time"))
                else:
                    self.after(0, lambda: self.arpa_next_run_label.configure(text="Next Run: N/A"))
                
                # Update manual mode button for the selected user, if any
                if self.current_manual_mode_user_id:
                    selected_user_data = user_funnel_status_detailed.get(self.current_manual_mode_user_id, {})
                    current_manual_mode_status = selected_user_data.get("current_state", {}).get("manual_mode_active", False)
                    self.after(0, lambda: self._update_manual_mode_ui(current_manual_mode_status))

            except requests.exceptions.ConnectionError:
                self.after(0, lambda: self._insert_console_message("API Server Offline. Please launch 'api.py'.", prefix="[API Status] ", tag="error_tag"))
                self.after(0, lambda: self.server_status_indicator.configure(fg_color=UI_STATUS_ERROR))
                self.after(0, lambda: self.in_progress_label.configure(text="In Progress: N/A"))
                self.after(0, lambda: self.funneled_label.configure(text="Funneled: N/A"))
                self.after(0, lambda: self.active_users_count_label.configure(text="N/A"))
                self.after(0, lambda: self.arpa_overall_status_label.configure(text="Overall Status: Offline", text_color=UI_STATUS_ERROR))
                self.after(0, lambda: self.arpa_current_action_label.configure(text="Action: Offline"))
                self.after(0, lambda: self.arpa_target_label.configure(text="Target: Offline"))
                self.after(0, lambda: self.arpa_last_user_label.configure(text="Last User: Offline"))
                self.after(0, lambda: self.arpa_session_msgs_label.configure(text="Msgs Sent (Session): N/A"))
                self.after(0, lambda: self.arpa_next_run_label.configure(text="Next Run: Offline"))
                self.after(0, lambda: self.pause_resume_button.configure(state="disabled", text="Server Offline", fg_color=UI_BACKGROUND_SECONDARY_2, text_color=UI_TEXT_MUTED))

            except requests.exceptions.Timeout:
                self.after(0, lambda: self._insert_console_message("API Server Timeout. Check server load or network.", prefix="[API Status] ", tag="warning_tag"))
                self.after(0, lambda: self.server_status_indicator.configure(fg_color=UI_STATUS_WARNING))
            except Exception as e:
                self.after(0, lambda: self._insert_console_message(f"Error fetching API status: {e}", prefix="[API Status] ", tag="error_tag"))
                self.after(0, lambda: self.server_status_indicator.configure(fg_color=UI_STATUS_ERROR))
            finally:
                if not self.is_closing:
                    self.after(2000, self.poll_server_status)

    def load_initial_config_file(self):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                self.config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.config = {}
            print("Warning: config.json not found or invalid. Using empty config.")
    
    def _get_current_funnel_data(self):
        try:
            # THIS IS THE CORRECT ENDPOINT TO GET ALL DETAILED USER STATUSES
            response = requests.get(f"{API_BASE_URL}/status", timeout=1) 
            response.raise_for_status()
            return response.json() # Return the entire response, which contains user_funnel_status_detailed
        except requests.exceptions.RequestException as e:
            print(f"DEBUG: Error fetching current funnel data from API: {e}")
            return {}

    def _insert_console_message(self, message, prefix="", tag=None):
        if hasattr(self, 'console_output_textbox') and self.console_output_textbox:
            self.console_output_textbox.configure(state="normal")
            full_message = prefix + message + "\n"
            if tag:
                self.console_output_textbox.insert("end", full_message, tag)
            else:
                self.console_output_textbox.insert("end", full_message)
            self.console_output_textbox.see("end")
            self.console_output_textbox.configure(state="disabled")
        else:
            print(f"{prefix}{message}") 

    def create_left_sidebar(self):
        self.sidebar_frame = customtkinter.CTkFrame(self, width=250, corner_radius=0, fg_color=UI_BACKGROUND_SECONDARY_1)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(0, weight=1)

        self.bot_control_panel = customtkinter.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.bot_control_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.bot_control_panel.grid_columnconfigure(0, weight=1)
        self.bot_control_panel.grid_rowconfigure(10, weight=1)

        button_font = ("Arial", 13, "bold")
        button_pady_tight, button_height = 4, 28
        
        launch_color, stop_color = UI_BUTTON_NORMAL_FG, UI_BUTTON_DANGER_FG
        hover_launch_color, hover_stop_color = UI_BUTTON_NORMAL_HOVER, UI_BUTTON_DANGER_HOVER

        self.web_chat_button = customtkinter.CTkButton(self.bot_control_panel, text="Launch Web Chat", command=self.launch_web_chat, font=button_font, fg_color=launch_color, hover_color=hover_launch_color, height=button_height, text_color=UI_TEXT_PRIMARY)
        self.web_chat_button.grid(row=0, column=0, pady=button_pady_tight, sticky="ew")
        self.stop_web_chat_button = customtkinter.CTkButton(self.bot_control_panel, text="Stop Web Server", command=self.stop_web_chat, fg_color=stop_color, hover_color=hover_stop_color, font=button_font, height=button_height, state="disabled", text_color=UI_TEXT_PRIMARY)
        self.stop_web_chat_button.grid(row=1, column=0, pady=button_pady_tight, sticky="ew")
        self.telegram_button = customtkinter.CTkButton(self.bot_control_panel, text="Launch Telegram Bot", command=self.launch_telegram_bot, font=button_font, fg_color=launch_color, hover_color=hover_launch_color, height=button_height, text_color=UI_TEXT_PRIMARY)
        self.telegram_button.grid(row=2, column=0, pady=button_pady_tight, sticky="ew")
        self.stop_telegram_button = customtkinter.CTkButton(self.bot_control_panel, text="Stop Telegram Bot", command=self.stop_telegram_bot, fg_color=stop_color, hover_color=hover_stop_color, font=button_font, height=button_height, state="disabled", text_color=UI_TEXT_PRIMARY)
        self.stop_telegram_button.grid(row=3, column=0, pady=button_pady_tight, sticky="ew")
        self.reddit_button = customtkinter.CTkButton(self.bot_control_panel, text="Launch Reddit Bot", command=self.launch_reddit_bot, font=button_font, fg_color=launch_color, hover_color=hover_launch_color, height=button_height, text_color=UI_TEXT_PRIMARY)
        self.reddit_button.grid(row=4, column=0, pady=button_pady_tight, sticky="ew")
        self.stop_reddit_button = customtkinter.CTkButton(self.bot_control_panel, text="Stop Reddit Bot", command=self.stop_reddit_bot, fg_color=stop_color, hover_color=hover_stop_color, font=button_font, height=button_height, state="disabled", text_color=UI_TEXT_PRIMARY)
        self.stop_reddit_button.grid(row=5, column=0, pady=button_pady_tight, sticky="ew")
        self.discord_button = customtkinter.CTkButton(self.bot_control_panel, text="Launch Discord Bot", command=self.launch_discord_bot, font=button_font, fg_color=launch_color, hover_color=hover_launch_color, height=button_height, text_color=UI_TEXT_PRIMARY)
        self.discord_button.grid(row=6, column=0, pady=button_pady_tight, sticky="ew")
        self.stop_discord_button = customtkinter.CTkButton(self.bot_control_panel, text="Stop Discord Bot", command=self.stop_discord_bot, fg_color=stop_color, hover_color=hover_stop_color, font=button_font, height=button_height, state="disabled", text_color=UI_TEXT_PRIMARY)
        self.stop_discord_button.grid(row=7, column=0, pady=button_pady_tight, sticky="ew")
        self.facebook_button = customtkinter.CTkButton(self.bot_control_panel, text="Facebook Webhook Info", command=self.launch_facebook_setup_guide, font=button_font, fg_color=launch_color, hover_color=hover_launch_color, height=button_height, text_color=UI_TEXT_PRIMARY)
        self.facebook_button.grid(row=8, column=0, pady=button_pady_tight, sticky="ew")

        self.kill_all_button = customtkinter.CTkButton(self.bot_control_panel, text="STOP ALL BOTS", command=self.stop_all_processes, font=button_font, fg_color=UI_BUTTON_DANGER_FG, hover_color=UI_BUTTON_DANGER_HOVER, height=button_height + 5, text_color=UI_TEXT_PRIMARY)
        self.kill_all_button.grid(row=9, column=0, sticky="ew", pady=(button_pady_tight * 2, button_pady_tight))

        customtkinter.CTkFrame(self.bot_control_panel, fg_color="transparent", height=20).grid(row=10, column=0, pady=5)

        self.settings_button = customtkinter.CTkButton(self.bot_control_panel, text="Settings", command=self.open_settings, font=button_font, fg_color=launch_color, hover_color=hover_launch_color, height=button_height, text_color=UI_TEXT_PRIMARY)
        self.settings_button.grid(row=11, column=0, pady=button_pady_tight, sticky="ew")

        self.debug_button = customtkinter.CTkButton(self.bot_control_panel, text="Debug", command=self.open_debug_window, font=button_font, fg_color=launch_color, hover_color=hover_launch_color, height=button_height, text_color=UI_TEXT_PRIMARY)
        self.debug_button.grid(row=12, column=0, pady=button_pady_tight, sticky="ew")

        self.close_app_button = customtkinter.CTkButton(self.bot_control_panel, text="CLOSE APP", command=self.open_close_confirmation,
                                                         font=button_font, fg_color=UI_BUTTON_DANGER_FG, hover_color=UI_BUTTON_DANGER_HOVER, height=button_height, text_color=UI_TEXT_PRIMARY)
        self.close_app_button.grid(row=13, column=0, pady=button_pady_tight, sticky="ew")

        self.bot_control_panel.grid_rowconfigure(14, weight=1)

        self.toggle_panel_button = customtkinter.CTkButton(self, text="H\nI\nD\nE", width=25, height=70,
                                                             font=("Arial", 12, "bold"),
                                                             fg_color=UI_BACKGROUND_SECONDARY_1,
                                                             hover_color=UI_BUTTON_NORMAL_HOVER,
                                                             command=self.toggle_left_panel, corner_radius=8,
                                                             text_color=UI_TEXT_PRIMARY)
        self.toggle_panel_button.place(x=242, rely=0.5, anchor="e")

    def toggle_left_panel(self):
        if self.left_panel_visible:
            # Hide the panel
            self.sidebar_frame.grid_forget()
            self.toggle_panel_button.configure(text="S\nH\nO\nW")
            # Adjust button position when panel is hidden
            self.toggle_panel_button.place(x=5, rely=0.5, anchor="w")
            self.left_panel_visible = False
        else:
            # Show the panel
            self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
            self.toggle_panel_button.configure(text="H\nI\nD\nE")
            # Restore button position
            self.toggle_panel_button.place(x=242, rely=0.5, anchor="e")
            self.left_panel_visible = True

    def open_user_list_window(self):
        if self.user_list_window is None or not self.user_list_window.winfo_exists():
            self.user_list_window = UserListWindow(master=self, app_instance=self)
            self.user_list_window.grab_set() # It makes sense for this to be modal if it blocks interaction
        else:
            self.user_list_window.lift()

    def create_center_content(self):
        self.center_panel_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.center_panel_frame.grid(row=0, column=1, sticky="nsew", padx=(20, 2))
        self.center_panel_frame.grid_columnconfigure(0, weight=1)
        self.center_panel_frame.grid_rowconfigure(0, weight=0)
        self.center_panel_frame.grid_rowconfigure(1, weight=4) 
        self.center_panel_frame.grid_rowconfigure(2, weight=0) 
        self.center_panel_frame.grid_rowconfigure(3, weight=2) 

        header_frame = customtkinter.CTkFrame(self.center_panel_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(2,0))
        header_frame.grid_columnconfigure(1, weight=1)

        self.in_progress_bubble_frame = customtkinter.CTkFrame(header_frame, fg_color=UI_BACKGROUND_SECONDARY_2, corner_radius=8)
        self.in_progress_bubble_frame.grid(row=0, column=0, sticky="w", padx=5)
        self.in_progress_label = customtkinter.CTkLabel(self.in_progress_bubble_frame, text="In Progress: 0", font=("Arial", 15, "bold"), text_color=UI_TEXT_PRIMARY)
        self.in_progress_label.pack(padx=10, pady=5)

        title_frame = customtkinter.CTkFrame(header_frame, fg_color="transparent")
        title_frame.grid(row=0, column=1, sticky="nsew") 
        title_frame.grid_columnconfigure(0, weight=1) 

        GLOW_COLOR = "#70509E"  
        self.jai_title_underglow_frame = customtkinter.CTkFrame(title_frame, fg_color=GLOW_COLOR, width=280, height=100) 

        self.jai_title_label = customtkinter.CTkLabel(title_frame, text="J.A.I.", font=("Arial", 90, "bold"), text_color=UI_PRIMARY_ACCENT)
        self.jai_title_label.pack(fill="x", expand=True) 
        
        self.jai_title_underglow_frame.place(in_=self.jai_title_label, relx=0.5, rely=0.5, anchor="center", relwidth=1.05, relheight=0.7)
        self.jai_title_underglow_frame.lower(self.jai_title_label)  

        self.funneled_bubble_frame = customtkinter.CTkFrame(header_frame, fg_color=UI_BACKGROUND_SECONDARY_2, corner_radius=8)
        self.funneled_bubble_frame.grid(row=0, column=2, sticky="e", padx=5)
        self.funneled_label = customtkinter.CTkLabel(self.funneled_bubble_frame, text="Funneled: 0", font=("Arial", 15, "bold"), text_color=UI_TEXT_PRIMARY)
        self.funneled_label.pack(padx=10, pady=5)


        self.chat_log_tabview = customtkinter.CTkTabview(self.center_panel_frame, 
                                                         fg_color=UI_BACKGROUND_SECONDARY_1,
                                                         border_width=2, 
                                                         border_color=UI_PRIMARY_ACCENT,
                                                         segmented_button_selected_color=UI_PRIMARY_ACCENT,
                                                         segmented_button_unselected_color=UI_BACKGROUND_SECONDARY_2,
                                                         text_color=UI_TEXT_PRIMARY,
                                                         command=self._on_tab_change)
        self.chat_log_tabview.grid(row=1, column=0, sticky="nsew", pady=(0, 0))

        self.web_chat_tab = self.chat_log_tabview.add("Web Chat")
        self.telegram_chat_tab = self.chat_log_tabview.add("Telegram")
        self.reddit_chat_tab = self.chat_log_tabview.add("Reddit")
        self.discord_chat_tab = self.chat_log_tabview.add("Discord")
        self.facebook_chat_tab = self.chat_log_tabview.add("Facebook")

        self.chat_frames["web"] = self._create_log_frame(self.web_chat_tab)
        self.chat_frames["telegram"] = self._create_log_frame(self.telegram_chat_tab)
        self.chat_frames["reddit"] = self._create_log_frame(self.reddit_chat_tab)
        self.chat_frames["discord"] = self._create_log_frame(self.discord_chat_tab)
        self.chat_frames["facebook"] = self._create_log_frame(self.facebook_chat_tab)    
        
        self.chat_log_watermark = customtkinter.CTkLabel(self.chat_log_tabview, text="Chat Log",
                                                         text_color=UI_TEXT_MUTED, font=("Arial", 12))
        self.chat_log_watermark.place(relx=0.99, rely=0.99, anchor="se")

        self.manual_mode_controls_frame = customtkinter.CTkFrame(self.center_panel_frame, fg_color=UI_BACKGROUND_SECONDARY_2, corner_radius=10)
        self.manual_mode_controls_frame.grid(row=2, column=0, sticky="ew", pady=(5,0))

        self.manual_message_entry = customtkinter.CTkEntry(self.manual_mode_controls_frame, placeholder_text="Send a manual message...", width=400, text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_1, border_color=UI_BACKGROUND_SECONDARY_1, placeholder_text_color=UI_TEXT_MUTED)
        self.manual_message_entry.pack(side="left", fill="x", expand=True, padx=(10, 5), pady=10)
        self.manual_message_entry.bind("<Return>", lambda event: self.send_manual_message())

        self.emoji_button = customtkinter.CTkButton(
            self.manual_mode_controls_frame, 
            text="😊", 
            command=self.open_emoji_picker,
            width=35, 
            height=35,
            font=("Segoe UI Emoji", 18)
        )
        self.emoji_button.pack(side="left", padx=(0, 5), pady=10)

        self.send_manual_button = customtkinter.CTkButton(self.manual_mode_controls_frame, text="Send", command=self.send_manual_message, fg_color=UI_BUTTON_NORMAL_FG, hover_color=UI_BUTTON_NORMAL_HOVER, text_color=UI_TEXT_PRIMARY)
        self.send_manual_button.pack(side="left", padx=(0, 5), pady=10)

        self.send_file_button = customtkinter.CTkButton(self.manual_mode_controls_frame, text="Send File", command=self.send_manual_file, fg_color=UI_BUTTON_NORMAL_FG, hover_color=UI_BUTTON_NORMAL_HOVER, text_color=UI_TEXT_PRIMARY)
        self.send_file_button.pack(side="left", padx=(0, 10), pady=10)


        self.pause_resume_button = customtkinter.CTkButton(
            self.chat_log_tabview, 
            text="Pause AI",
            command=self.toggle_manual_mode,
            fg_color=UI_STATUS_WARNING,
            hover_color=UI_BUTTON_NORMAL_HOVER,
            font=("Arial", 12, "bold"),
            width=80,
            height=25,
            state="disabled",
            text_color=UI_TEXT_PRIMARY
        )
        self.pause_resume_button.place(relx=0.98, rely=0.01, anchor="ne")

        self.users_list_button = customtkinter.CTkButton(
            self.chat_log_tabview, 
            text="Users List",
            command=self.open_user_list_window,
            fg_color=UI_BUTTON_NORMAL_FG, hover_color=UI_BUTTON_NORMAL_HOVER,
            font=("Arial", 12), width=80, height=25, text_color=UI_TEXT_PRIMARY
        )
        self.users_list_button.place(relx=0.025, rely=0.01, anchor="nw")
        
        self.user_history_button = customtkinter.CTkButton(
            self.chat_log_tabview, 
            text="User History",
            command=self.open_user_history_window,
            fg_color=UI_BUTTON_NORMAL_FG, hover_color=UI_BUTTON_NORMAL_HOVER,
            font=("Arial", 12), width=100, height=25, text_color=UI_TEXT_PRIMARY
        )
        self.user_history_button.place(relx=0.13, rely=0.01, anchor="nw")


        self.console_output_textbox = customtkinter.CTkTextbox(self.center_panel_frame, wrap="word", state="disabled", 
                                                               fg_color=UI_BACKGROUND_SECONDARY_1,
                                                               text_color=UI_TEXT_PRIMARY, font=("Consolas", 12), 
                                                               border_width=2, border_color=UI_PRIMARY_ACCENT)
        self.console_output_textbox.grid(row=3, column=0, sticky="nsew", pady=(10,0))

        self.console_output_watermark = customtkinter.CTkLabel(self.console_output_textbox, text="Console Output",
                                                               text_color=UI_TEXT_MUTED, font=("Arial", 12))
        self.console_output_watermark.place(relx=0.99, rely=0.99, anchor="se")

        self.typing_indicator_frame = customtkinter.CTkFrame(self.chat_log_tabview, fg_color="transparent")
        self.typing_indicator_label = customtkinter.CTkLabel(self.typing_indicator_frame, text="",
                                                             font=("Arial", 14), text_color=UI_TEXT_MUTED)
        self.typing_indicator_label.pack(side="left", padx=5, pady=2)

    def create_right_pillar(self):
        self.pillar_frame = customtkinter.CTkFrame(self, width=150, corner_radius=0, fg_color=UI_BACKGROUND_SECONDARY_1, border_width=0)
        self.pillar_frame.grid(row=0, column=2, rowspan=2, sticky="nsew", padx=(2,0))
        self.pillar_frame.grid_columnconfigure(0, weight=1)

        pillar_row_counter = 0

        server_status_bubble = customtkinter.CTkFrame(self.pillar_frame, fg_color=UI_BACKGROUND_SECONDARY_2, corner_radius=12, border_width=0)
        server_status_bubble.grid(row=pillar_row_counter, column=0, sticky="ew", padx=10, pady=(0,0))
        pillar_row_counter += 1

        server_status_title = customtkinter.CTkLabel(server_status_bubble, text="Server Status", font=("Arial", 12, "bold"), text_color=UI_TEXT_PRIMARY)
        server_status_title.pack(padx=15, pady=(1,0))

        self.server_status_indicator = customtkinter.CTkFrame(server_status_bubble, fg_color=UI_STATUS_ERROR, height=8, width=50, corner_radius=5, border_width=0)
        self.server_status_indicator.pack(pady=(0,1), padx=40)

        conversations_title = customtkinter.CTkLabel(server_status_bubble, text="Conversations", font=("Arial", 12, "bold"), text_color=UI_TEXT_PRIMARY)
        conversations_title.pack(padx=15, pady=(1,0))
        
        self.active_users_counter_frame = customtkinter.CTkFrame(server_status_bubble, fg_color=UI_BACKGROUND_SECONDARY_2, border_color=UI_TEXT_MUTED, border_width=1, height=24, corner_radius=5)
        self.active_users_counter_frame.pack(padx=15, pady=(0,1), fill="x")
        
        self.active_users_count_label = customtkinter.CTkLabel(
            self.active_users_counter_frame,
            text="0",
            font=("Arial", 16, "bold"), 
            text_color=UI_TEXT_PRIMARY
        )
        self.active_users_count_label.pack(expand=True, fill="both", padx=5, pady=0)

        self.manual_proactive_outreach_pillar_frame = customtkinter.CTkFrame(self.pillar_frame, fg_color=UI_BACKGROUND_SECONDARY_2, corner_radius=10, border_width=0)
        self.manual_proactive_outreach_pillar_frame.grid(row=pillar_row_counter, column=0, sticky="ew", padx=0, pady=(3,0))
        self.manual_proactive_outreach_pillar_frame.grid_columnconfigure(0, weight=1)
        self.manual_proactive_outreach_pillar_frame.grid_columnconfigure(1, weight=1)

        self.manual_proactive_outreach_label_pillar = customtkinter.CTkLabel(self.manual_proactive_outreach_pillar_frame, text="Manual Proactive Outreach", font=("Arial", 11, "bold"), text_color=UI_TEXT_PRIMARY)
        self.manual_proactive_outreach_label_pillar.grid(row=0, column=0, columnspan=2, padx=10, pady=(5,2), sticky="w")
        self.manual_proactive_user_id_entry_pillar = customtkinter.CTkEntry(self.manual_proactive_outreach_pillar_frame, placeholder_text="User ID", width=70, font=("Arial", 10), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_1, placeholder_text_color=UI_TEXT_MUTED)
        self.manual_proactive_user_id_entry_pillar.grid(row=1, column=0, padx=(10, 5), pady=3, sticky="ew")
        self.manual_proactive_platform_entry_pillar = customtkinter.CTkEntry(self.manual_proactive_outreach_pillar_frame, placeholder_text="Platform", width=60, font=("Arial", 10), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_1, placeholder_text_color=UI_TEXT_MUTED)
        self.manual_proactive_platform_entry_pillar.grid(row=1, column=1, padx=(0, 10), pady=3, sticky="ew")
        self.send_manual_proactive_button_pillar = customtkinter.CTkButton(self.manual_proactive_outreach_pillar_frame, text="Send Proactive", command=self._send_proactive_from_pillar, fg_color=UI_STATUS_ACTIVE, hover_color=UI_BUTTON_NORMAL_HOVER, font=("Arial", 10, "bold"), height=22, text_color=UI_TEXT_PRIMARY)
        self.send_manual_proactive_button_pillar.grid(row=2, column=0, columnspan=2, padx=10, pady=(3, 3), sticky="ew")
        self.manual_proactive_info_label_pillar = customtkinter.CTkLabel(self.manual_proactive_outreach_pillar_frame, text="*Telegram requires previous contact.", wraplength=130, font=("Arial", 8), text_color=UI_TEXT_MUTED)
        self.manual_proactive_info_label_pillar.grid(row=3, column=0, columnspan=2, padx=10, pady=(0,1), sticky="w")
        pillar_row_counter += 1

        self.arpa_main_frame = customtkinter.CTkFrame(self.pillar_frame, fg_color=UI_BACKGROUND_SECONDARY_2, corner_radius=10, border_width=0)
        self.arpa_main_frame.grid(row=pillar_row_counter, column=0, sticky="ew", padx=0, pady=(2,0))
        self.arpa_main_frame.grid_columnconfigure(0, weight=1)
        self.arpa_main_frame.grid_columnconfigure(1, weight=1)

        customtkinter.CTkLabel(self.arpa_main_frame, text="Automated Proactive Outreach (ARPA)", font=("Arial", 11, "bold"), text_color=UI_TEXT_PRIMARY).grid(row=0, column=0, columnspan=2, padx=10, pady=(2,1), sticky="w")

        self.app_config_vars["arpa_enabled"] = customtkinter.BooleanVar(value=False)
        customtkinter.CTkCheckBox(self.arpa_main_frame, text="Enable ARPA Globally",
                                  variable=self.app_config_vars["arpa_enabled"],
                                  font=("Arial", 8), text_color=UI_TEXT_PRIMARY, fg_color=UI_BUTTON_NORMAL_FG).grid(row=1, column=0, columnspan=2, padx=10, pady=(1,1), sticky="w")

        reddit_arpa_inner_frame = customtkinter.CTkFrame(self.arpa_main_frame, fg_color="transparent")
        reddit_arpa_inner_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=0)
        reddit_arpa_inner_frame.grid_columnconfigure(0, weight=1)

        customtkinter.CTkLabel(reddit_arpa_inner_frame, text="Reddit ARPA:", font=("Arial", 10, "underline"), text_color=UI_TEXT_PRIMARY).grid(row=0, column=0, padx=5, pady=(1,0), sticky="w")
        self.app_config_vars["auto_proactive_reddit_enabled"] = customtkinter.BooleanVar(value=False)
        customtkinter.CTkCheckBox(reddit_arpa_inner_frame, text="Enable", variable=self.app_config_vars["auto_proactive_reddit_enabled"], font=("Arial", 8), text_color=UI_TEXT_PRIMARY, fg_color=UI_BUTTON_NORMAL_FG).grid(row=1, column=0, padx=5, pady=0, sticky="w")
        self.app_config_vars["reddit_target_subreddits"] = customtkinter.CTkEntry(reddit_arpa_inner_frame, placeholder_text="Subreddits (comma)", font=("Arial", 8), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_1, placeholder_text_color=UI_TEXT_MUTED)
        self.app_config_vars["reddit_target_subreddits"].grid(row=2, column=0, padx=5, pady=0, sticky="ew")
        self.app_config_vars["reddit_proactive_cooldown_hours_per_user"] = customtkinter.CTkEntry(reddit_arpa_inner_frame, placeholder_text="Cooldown (hrs)", font=("Arial", 8), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_1, placeholder_text_color=UI_TEXT_MUTED)
        self.app_config_vars["reddit_proactive_cooldown_hours_per_user"].grid(row=3, column=0, padx=5, pady=0, sticky="ew")
        self.app_config_vars["reddit_proactive_min_delay_seconds_per_message"] = customtkinter.CTkEntry(reddit_arpa_inner_frame, placeholder_text="Min Delay (s)", font=("Arial", 8), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_1, placeholder_text_color=UI_TEXT_MUTED)
        self.app_config_vars["reddit_proactive_min_delay_seconds_per_message"].grid(row=4, column=0, padx=5, pady=0, sticky="ew")
        self.app_config_vars["reddit_proactive_max_daily_messages_total"] = customtkinter.CTkEntry(reddit_arpa_inner_frame, placeholder_text="Max Daily Msgs", font=("Arial", 8), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_1, placeholder_text_color=UI_TEXT_MUTED)
        self.app_config_vars["reddit_proactive_max_daily_messages_total"].grid(row=5, column=0, padx=5, pady=0, sticky="ew")
        self.app_config_vars["reddit_proactive_message_template"] = customtkinter.CTkEntry(reddit_arpa_inner_frame, placeholder_text="Message Template", font=("Arial", 8), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_1, placeholder_text_color=UI_TEXT_MUTED)
        self.app_config_vars["reddit_proactive_message_template"].grid(row=6, column=0, padx=5, pady=(0,1), sticky="ew")


        discord_arpa_inner_frame = customtkinter.CTkFrame(self.arpa_main_frame, fg_color="transparent")
        discord_arpa_inner_frame.grid(row=2, column=1, sticky="nsew", padx=5, pady=0)
        discord_arpa_inner_frame.grid_columnconfigure(0, weight=1)

        customtkinter.CTkLabel(discord_arpa_inner_frame, text="Discord ARPA:", font=("Arial", 10, "underline"), text_color=UI_TEXT_PRIMARY).grid(row=0, column=0, padx=5, pady=(1,0), sticky="w")
        self.app_config_vars["auto_proactive_discord_enabled"] = customtkinter.BooleanVar(value=False)
        customtkinter.CTkCheckBox(discord_arpa_inner_frame, text="Enable", variable=self.app_config_vars["auto_proactive_discord_enabled"], font=("Arial", 8), text_color=UI_TEXT_PRIMARY, fg_color=UI_BUTTON_NORMAL_FG).grid(row=1, column=0, padx=5, pady=0, sticky="w")
        self.app_config_vars["discord_target_channels"] = customtkinter.CTkEntry(discord_arpa_inner_frame, placeholder_text="Channels (comma)", font=("Arial", 8), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_1, placeholder_text_color=UI_TEXT_MUTED)
        self.app_config_vars["discord_target_channels"].grid(row=2, column=0, padx=5, pady=0, sticky="ew")
        self.app_config_vars["discord_proactive_cooldown_hours_per_user"] = customtkinter.CTkEntry(discord_arpa_inner_frame, placeholder_text="Cooldown (hrs)", font=("Arial", 8), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_1, placeholder_text_color=UI_TEXT_MUTED)
        self.app_config_vars["discord_proactive_cooldown_hours_per_user"].grid(row=3, column=0, padx=5, pady=0, sticky="ew")
        self.app_config_vars["discord_proactive_min_delay_seconds_per_message"] = customtkinter.CTkEntry(discord_arpa_inner_frame, placeholder_text="Min Delay (s)", font=("Arial", 8), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_1, placeholder_text_color=UI_TEXT_MUTED)
        self.app_config_vars["discord_proactive_min_delay_seconds_per_message"].grid(row=4, column=0, padx=5, pady=0, sticky="ew")
        self.app_config_vars["discord_proactive_max_daily_messages_total"] = customtkinter.CTkEntry(discord_arpa_inner_frame, placeholder_text="Max Daily Msgs", font=("Arial", 8), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_1, placeholder_text_color=UI_TEXT_MUTED)
        self.app_config_vars["discord_proactive_max_daily_messages_total"].grid(row=5, column=0, padx=5, pady=0, sticky="ew")
        self.app_config_vars["discord_proactive_message_template"] = customtkinter.CTkEntry(discord_arpa_inner_frame, placeholder_text="Message Template", font=("Arial", 8), text_color=UI_TEXT_PRIMARY, fg_color=UI_BACKGROUND_SECONDARY_1, placeholder_text_color=UI_TEXT_MUTED)
        self.app_config_vars["discord_proactive_message_template"].grid(row=6, column=0, padx=5, pady=(0,1), sticky="ew")

        self.save_arpa_settings_button = customtkinter.CTkButton(self.arpa_main_frame, text="Save ARPA Settings", command=self.save_arpa_settings,
                                                                  fg_color=UI_STATUS_ACTIVE, hover_color=UI_BUTTON_NORMAL_HOVER, font=("Arial", 10, "bold"), height=22, text_color=UI_TEXT_PRIMARY)
        self.save_arpa_settings_button.grid(row=7, column=0, columnspan=2, padx=10, pady=(2,4), sticky="ew")

        pillar_row_counter += 1
        
        self.arpa_activity_frame = customtkinter.CTkFrame(self.pillar_frame, fg_color=UI_BACKGROUND_SECONDARY_2, corner_radius=10, border_width=0)
        self.arpa_activity_frame.grid(row=pillar_row_counter, column=0, sticky="nsew", padx=0, pady=(3,0))
        self.arpa_activity_frame.grid_columnconfigure(0, weight=1)

        self.arpa_activity_frame.grid_rowconfigure(1, weight=1) 

        customtkinter.CTkLabel(self.arpa_activity_frame, text="ARPA Activity Monitoring", font=("Arial", 11, "bold"), text_color=UI_TEXT_PRIMARY).grid(row=0, column=0, padx=10, pady=(3,1), sticky="w")

        self.arpa_display_screen_frame = customtkinter.CTkFrame(self.arpa_activity_frame, fg_color=UI_BACKGROUND_SECONDARY_1, corner_radius=8, border_width=0)
        self.arpa_display_screen_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=(1, 5))
        self.arpa_display_screen_frame.grid_columnconfigure((0, 1), weight=1)
        self.arpa_display_screen_frame.grid_rowconfigure(0, weight=1)
        self.arpa_display_screen_frame.grid_rowconfigure(4, weight=1)

        self.pillar_frame.grid_rowconfigure(pillar_row_counter, weight=1)
                
        self.arpa_overall_status_label = customtkinter.CTkLabel(self.arpa_display_screen_frame, text="Overall Status: Off", font=("Arial", 10), text_color=UI_TEXT_PRIMARY, justify="center")
        self.arpa_overall_status_label.grid(row=1, column=0, padx=8, pady=(5,5), sticky="ew")

        self.arpa_current_action_label = customtkinter.CTkLabel(self.arpa_display_screen_frame, text="Action: Idle", font=("Arial", 9), wraplength=65, justify="center", text_color=UI_TEXT_PRIMARY)
        self.arpa_current_action_label.grid(row=1, column=1, padx=8, pady=(5,5), sticky="ew")

        self.arpa_target_label = customtkinter.CTkLabel(self.arpa_display_screen_frame, text="Target: N/A", font=("Arial", 9), wraplength=65, justify="center", text_color=UI_TEXT_PRIMARY)
        self.arpa_target_label.grid(row=2, column=0, padx=8, pady=(5,5), sticky="ew")

        self.arpa_last_user_label = customtkinter.CTkLabel(self.arpa_display_screen_frame, text="Last User: None", font=("Arial", 9), wraplength=65, justify="center", text_color=UI_TEXT_PRIMARY)
        self.arpa_last_user_label.grid(row=2, column=1, padx=8, pady=(5,5), sticky="ew")

        self.arpa_session_msgs_label = customtkinter.CTkLabel(self.arpa_display_screen_frame, text="Msgs Sent (Session): 0", font=("Arial", 9), text_color=UI_TEXT_PRIMARY, justify="center")
        self.arpa_session_msgs_label.grid(row=3, column=0, padx=8, pady=(5,5), sticky="ew")

        self.arpa_next_run_label = customtkinter.CTkLabel(self.arpa_display_screen_frame, text="Next Run: N/A", font=("Arial", 9), text_color=UI_TEXT_PRIMARY, justify="center")
        self.arpa_next_run_label.grid(row=3, column=1, padx=8, pady=(5,5), sticky="ew")
        self.pillar_frame.grid_rowconfigure(3, weight=1)
        
    def update_notification_counts(self):
        """Periodically fetches unread counts and displays them as red notification badges
        with dynamically calculated positions to stick to the tabs."""
        try:
            if self.chat_log_tabview.winfo_width() < 100:
                self.after(200, self.update_notification_counts)
                return

            response = requests.get(f"{API_BASE_URL}/get_unread_counts", timeout=2)
            if response.status_code != 200:
                if not self.is_closing:
                    self.after(3000, self.update_notification_counts)
                return

            unread_counts = response.json()

            TABS_CONFIG = {
                "web":      ("Web Chat", 72),
                "telegram": ("Telegram", 65),
                "reddit":   ("Reddit", 50),
                "discord":  ("Discord", 58),
                "facebook": ("Facebook", 70)
            }
            PLATFORM_ORDER = ["web", "telegram", "reddit", "discord", "facebook"]

            badge_positions = {}
            current_x_offset = 0
            X_ADJUSTMENT = 240
            Y_ADJUSTMENT = -3   

            for platform in PLATFORM_ORDER:
                tab_width = TABS_CONFIG.get(platform, ("Unknown", 90))[1]
                current_x_offset += tab_width
                
                compensation = 0
                if not self.left_panel_visible:
                    compensation = self.PANEL_CLOSED_X_COMPENSATION
                
                badge_positions[platform] = {
                    "x": current_x_offset + X_ADJUSTMENT + compensation,
                    "y": Y_ADJUSTMENT
                }
            
            tabview_x = self.chat_log_tabview.winfo_x()
            tabview_y = self.chat_log_tabview.winfo_y()
            for platform, pos in badge_positions.items():
                count = unread_counts.get(platform, 0)

                if count > 0:
                    if platform not in self.notification_badges:
                        badge = customtkinter.CTkLabel(
                            self.center_panel_frame, # Parent to center_panel_frame (correct)
                            text=str(count),
                            fg_color="red",
                            text_color="white",
                            font=("Arial", 10, "bold"),
                            width=13,
                            height=13,
                            corner_radius=8,
                            padx=0,
                            pady=0,
                        )
                        self.notification_badges[platform] = badge
                    else:
                        badge = self.notification_badges[platform]

                    badge.configure(text=str(count))
                    final_x = tabview_x + pos['x']
                    final_y = tabview_y + pos['y']

                    badge.place(x=final_x, y=final_y, anchor="ne")
                                            
                    badge.lift() 

                elif count == 0 and platform in self.notification_badges:
                    self.notification_badges[platform].destroy()
                    del self.notification_badges[platform]

        except requests.exceptions.RequestException:
            pass 
        except Exception as e:
            print(f"Error in update_notification_counts: {e}")
        finally:
            if not self.is_closing:
                self.after(3000, self.update_notification_counts)

    def reset_platform_notifications(self, platform):
        try:
            requests.post(f"{API_BASE_URL}/reset_unread_count", json={"platform": platform}, timeout=2)
            print(f"GUI: Resetting unread count for platform '{platform}'")
        except requests.exceptions.RequestException as e:
            self._insert_console_message(f"Could not reset unread count for {platform}: {e}", tag="error_tag")

    def open_emoji_picker(self):
        if hasattr(self, 'emoji_picker') and self.emoji_picker is not None and self.emoji_picker.winfo_exists():
            self.emoji_picker.destroy()

        def on_emoji_select(emoji_char):
            self.manual_message_entry.insert(self.manual_message_entry.index("insert"), emoji_char)

        self.emoji_picker = EmojiPickerWindow(self, on_emoji_select_callback=on_emoji_select)
        self.emoji_picker.grab_set()

    def _send_proactive_from_pillar(self):
        user_id = self.manual_proactive_user_id_entry_pillar.get().strip()
        platform = self.manual_proactive_platform_entry_pillar.get().strip().lower()
        self.send_proactive_first_message_internal(user_id, platform) # Call internal helper
        self.manual_proactive_user_id_entry_pillar.delete(0, 'end')
        self.manual_proactive_platform_entry_pillar.delete(0, 'end')

    def _populate_arpa_ui_from_config(self):
        default_arpa_settings = {
            "arpa_enabled": False, "auto_proactive_reddit_enabled": False, "reddit_target_subreddits": [],
            "reddit_proactive_cooldown_hours_per_user": 0, "reddit_proactive_min_delay_seconds_per_message": 0,
            "reddit_proactive_max_daily_messages_total": 0, "reddit_proactive_message_template": "",
            "auto_proactive_discord_enabled": False, "discord_target_channels": [],
            "discord_proactive_cooldown_hours_per_user": 0, "discord_proactive_min_delay_seconds_per_message": 0,
            "discord_proactive_max_daily_messages_total": 0, "discord_proactive_message_template": "",
            "chat_pic_path": "", "random_update_pic_path": "", "funnel_pic_path": ""
        }
        for key, default_value in default_arpa_settings.items():
            if key not in self.config:
                self.config[key] = default_value

        for key, widget_ref in self.app_config_vars.items():
            if isinstance(widget_ref, customtkinter.BooleanVar):
                widget_ref.set(self.config.get(key, False))
            elif isinstance(widget_ref, customtkinter.CTkEntry):
                value = self.config.get(key, "")
                if key in ["reddit_target_subreddits", "discord_target_channels"]:
                    if isinstance(value, list):
                        value = ", ".join(value)
                
                widget_ref.delete(0, 'end')
                widget_ref.insert(0, str(value))
            
        # These fields are in SettingsWindow, not directly in main App's pillar frame
        # They are loaded/saved by SettingsWindow's own methods
        # if hasattr(self, 'chat_pic_path_entry') and "chat_pic_path" in self.config:
        #     self.chat_pic_path_entry.delete(0, 'end')
        #     self.chat_pic_path_entry.insert(0, self.config["chat_pic_path"])
        # if hasattr(self, 'random_update_pic_path_entry') and "random_update_pic_path" in self.config:
        #     self.random_update_pic_path_entry.delete(0, 'end')
        #     self.random_update_pic_path_entry.insert(0, self.config["random_update_pic_path"])
        # if hasattr(self, 'funnel_pic_path_entry') and "funnel_pic_path" in self.config:
        #     self.funnel_pic_path_entry.delete(0, 'end')
        #     self.funnel_pic_path_entry.insert(0, self.config["funnel_pic_path"])

    def _setup_console_tags(self):
        if hasattr(self, 'console_output_textbox') and self.console_output_textbox:
            self.console_output_textbox.tag_config("api_tag", foreground=COLOR_API)
            self.console_output_textbox.tag_config("tele_tag", foreground=COLOR_TELE)
            self.console_output_textbox.tag_config("red_tag", foreground=COLOR_REDDIT)
            self.console_output_textbox.tag_config("disc_tag", foreground=COLOR_DISCORD)
            self.console_output_textbox.tag_config("system_tag", foreground=COLOR_SYSTEM)
            self.console_output_textbox.tag_config("error_tag", foreground=COLOR_ERROR)
            self.console_output_textbox.tag_config("warning_tag", foreground=COLOR_WARNING)
            self.console_output_textbox.tag_config("normal_tag", foreground=UI_TEXT_PRIMARY)
            
            self._insert_console_message("\n" +
                                         " _______ __   _______ ______ _______ _______ \n" +
                                         "|       _ |   |       _    _       _       |\n" +
                                         "|   1   | |___   |   1   |   < 1       |   1   |\n" +
                                         "|_______|_______| |_______|______/_______|_______|\n" +
                                         "         J.A.I. Control Panel\n",
                                         prefix="", tag="system_tag")
            self._insert_console_message("Welcome to Jasmine AI Control Panel.", prefix="[System] ", tag="system_tag")
            self._insert_console_message("Monitoring and control features are active.", prefix="[System] ", tag="system_tag")
            self._insert_console_message("--------------------------------------------------", prefix="", tag="system_tag")
        else:
            print("Warning: console_output_textbox not found for tag setup.")

    def create_bottom_bar(self):
        self.bottom_frame = customtkinter.CTkFrame(self, fg_color="transparent", height=40)
        self.bottom_frame.grid(row=1, column=1, sticky="nsew", padx=(20, 2), pady=5)
        
        self.bottom_frame.grid_columnconfigure(0, weight=0)
        self.bottom_frame.grid_columnconfigure(1, weight=1)
        self.bottom_frame.grid_columnconfigure(2, weight=0)

        social_frame = customtkinter.CTkFrame(self.bottom_frame, fg_color="transparent")
        social_frame.grid(row=0, column=0, sticky="w")

        social_button_font = ("Arial", 12)
        social_button_height = 25
        social_button_fg_color = UI_BUTTON_NORMAL_FG
        social_button_hover_color = UI_BUTTON_NORMAL_HOVER

        self.join_telegram_button = customtkinter.CTkButton(social_frame, text="Join Telegram", command=self.open_telegram_link,
                                                            font=social_button_font, fg_color=social_button_fg_color, hover_color=social_button_hover_color, height=social_button_height, text_color=UI_TEXT_PRIMARY)
        self.join_telegram_button.pack(side="left", padx=(0,5))
        self.join_discord_button = customtkinter.CTkButton(social_frame, text="Join Discord", command=self.open_discord_link,
                                                            font=social_button_font, fg_color=social_button_fg_color, hover_color=social_button_hover_color, height=social_button_height, text_color=UI_TEXT_PRIMARY)
        self.join_discord_button.pack(side="left")

        self.status_label_bottom = customtkinter.CTkLabel(self.bottom_frame, text="", font=("Arial", 12, "bold"), text_color=UI_STATUS_ERROR)
        self.status_label_bottom.grid(row=0, column=1, sticky="nsew", padx=10, pady=5)

        self.copyright_label = customtkinter.CTkLabel(self.bottom_frame, text="J.A.I. by Daniel N. All Rights Reserved. Patent Pending.™",
                                                         font=("Arial", 10), text_color=UI_TEXT_MUTED)
        self.copyright_label.grid(row=0, column=2, sticky="e", padx=0, pady=0)

    def _create_log_frame(self, tab):
        scrollable_frame = customtkinter.CTkScrollableFrame(tab, fg_color=UI_BACKGROUND_PRIMARY)
        scrollable_frame.pack(fill="both", expand=True)
        scrollable_frame.grid_columnconfigure(0, weight=1) 
        scrollable_frame.grid_columnconfigure(1, weight=1) 
        return scrollable_frame

    def _add_chat_bubble(self, platform, sender, message):
        log_frame = self.chat_frames.get(platform)
        if not log_frame:
            log_frame = self.chat_frames.get("web") # Fallback to web chat
            if not log_frame: return

        current_row = self.chat_row_counters.get(platform, 0)
        self.chat_row_counters[platform] = current_row + 1

        is_user = sender.lower() == 'user'
        is_manual_agent = sender.lower() == 'manual_agent'

        column = 0 if is_user else 1
        sticky = "w" if is_user else "e"
        
        user_bubble_color = UI_BACKGROUND_SECONDARY_2
        bot_bubble_color = UI_BUTTON_NORMAL_FG
        agent_bubble_color = UI_BUTTON_NORMAL_HOVER

        bubble_color = user_bubble_color if is_user else (bot_bubble_color if not is_manual_agent else agent_bubble_color)

        bubble = customtkinter.CTkLabel(
            master=log_frame,
            text=message,
            font=("Arial", 13),
            text_color=UI_TEXT_PRIMARY,
            fg_color=bubble_color,
            corner_radius=12,
            wraplength=int(self.chat_log_tabview.winfo_width() * 0.45),
            justify="left",
            padx=12,
            pady=7
        )
        bubble.grid(row=current_row, column=column, sticky=sticky, padx=10, pady=4)

        self.after(50, lambda: log_frame._parent_canvas.yview_moveto(1.0))

    def update_chat_logs(self):
        if self.is_closing: return

        if self.current_manual_mode_user_id is None:
            self.after(3000, self.update_chat_logs) 
            return

        try:
            # Fetch specific user's chat logs
            response = requests.get(f"{API_BASE_URL}/api/user/{self.current_manual_mode_user_id}/chat_history?limit=500", timeout=3)
            response.raise_for_status()
            all_log_entries = response.json().get('chat_history', []) # Get 'chat_history' key

            current_tab_name = self.chat_log_tabview.get()
            base_platform_key = current_tab_name.split(" ")[0].lower()

            filtered_entries = []
            for entry in all_log_entries:
                entry_platform = entry['platform']
                user_id_in_log = str(entry['user_id'])

                platform_matches_tab = False
                if entry_platform == base_platform_key:
                    platform_matches_tab = True
                elif base_platform_key == "facebook" and entry_platform in ["facebook", "facebook_postback"]:
                    platform_matches_tab = True
                elif base_platform_key == "web" and entry_platform == "browser_autonomous":
                    platform_matches_tab = True

                if platform_matches_tab and user_id_in_log == str(self.current_manual_mode_user_id):
                    filtered_entries.append(entry)

            if len(filtered_entries) > self.last_log_entry_index:
                new_entries = filtered_entries[self.last_log_entry_index:]
                for entry in new_entries:
                    self._add_chat_bubble(entry['platform'], entry['sender'], entry['message'])
                self.last_log_entry_index = len(filtered_entries)

            # Re-fetch funnel data to ensure manual mode button updates
            funnel_data = self._get_current_funnel_data()
            self._update_pause_resume_button_state(funnel_data)

        except requests.exceptions.RequestException as e:
            if e.response and e.response.status_code == 404:
                self._insert_console_message(f"API Error 404: No chat logs found for user {self.current_manual_mode_user_id} (or endpoint mismatch).", prefix="[Chat Log] ", tag="error_tag")
            else:
                self._insert_console_message(f"Network/API Error fetching chat logs: {e}", prefix="[Chat Log] ", tag="error_tag")
        except (json.JSONDecodeError, KeyError) as e:
            self._insert_console_message(f"Error decoding chat logs or missing key: {e}", prefix="[Chat Log] ", tag="error_tag")
        finally:
            if not self.is_closing:
                self.after(3000, self.update_chat_logs)

    def _repopulate_chat_display_for_current_tab(self):
        current_tab_name = self.chat_log_tabview.get()
        base_platform_key = current_tab_name.split(" ")[0].lower()
        log_frame = self.chat_frames.get(base_platform_key)

        if not log_frame: return

        for widget in log_frame.winfo_children():
            widget.destroy()
        self.chat_row_counters[base_platform_key] = 0
        self.last_log_entry_index = 0

        if self.current_manual_mode_user_id is None:
            no_user_label = customtkinter.CTkLabel(log_frame, text="Select a user from the 'Users List' to view their chat.",
                                                   font=("Arial", 14), text_color=UI_TEXT_MUTED)
            no_user_label.grid(row=0, column=0, columnspan=2, pady=50, padx=20, sticky="ew")
            return

        all_log_entries = []
        try:
            response = requests.get(f"{API_BASE_URL}/api/user/{self.current_manual_mode_user_id}/chat_history?limit=500", timeout=3)
            response.raise_for_status()
            all_log_entries = response.json().get('chat_history', [])
        except requests.exceptions.RequestException as e:
            self._insert_console_message(f"Error fetching chat logs for display refresh: {e}", prefix="[System] ", tag="error_tag")
            customtkinter.CTkLabel(log_frame, text=f"Error loading chat: {e}", font=("Arial", 14), text_color=UI_STATUS_ERROR).grid(row=0, column=0, columnspan=2, pady=50)
            return
        except (json.JSONDecodeError, KeyError) as e:
            self._insert_console_message(f"Error decoding chat logs for display refresh: {e}", prefix="[System] ", tag="error_tag")
            customtkinter.CTkLabel(log_frame, text=f"Error loading chat: {e}", font=("Arial", 14), text_color=UI_STATUS_ERROR).grid(row=0, column=0, columnspan=2, pady=50)
            return

        new_log_count = 0
        for entry in all_log_entries:
            entry_platform = entry['platform']
            user_id_in_log = str(entry['user_id'])

            platform_match_for_tab = False
            if entry_platform == base_platform_key:
                platform_match_for_tab = True
            elif base_platform_key == "facebook" and entry_platform in ["facebook", "facebook_postback"]:
                platform_match_for_tab = True
            elif base_platform_key == "web" and entry_platform == "browser_autonomous":
                platform_match_for_tab = True

            if platform_match_for_tab and user_id_in_log == str(self.current_manual_mode_user_id):
                self._add_chat_bubble(entry['platform'], entry['sender'], entry['message'])
                new_log_count +=1
            
        self.last_log_entry_index = new_log_count

        funnel_data = self._get_current_funnel_data()
        self._update_pause_resume_button_state(funnel_data)

    def refresh_chat_logs_and_status(self):
        self._insert_console_message("Manually refreshing chat logs and status...", prefix="[System] ", tag="system_tag")
        self.update_status()
        self.update_chat_logs()

    def _on_tab_change(self):
        current_tab_name_with_count = self.chat_log_tabview.get()
        
        platform_key = current_tab_name_with_count.split(" ")[0].lower()

        if platform_key in self.notification_badges:
            self.notification_badges[platform_key].destroy()
            del self.notification_badges[platform_key]
        
        try:
            requests.post(f"{API_BASE_URL}/reset_unread_count", json={"platform": platform_key}, timeout=2)
        except requests.exceptions.RequestException as e:
            self._insert_console_message(f"Could not reset unread count for {platform_key}: {e}", tag="error_tag")
        
        self._insert_console_message(f"Tab changed to: {current_tab_name_with_count}", prefix="[System] ", tag="system_tag")
        
        self.current_manual_mode_user_id = None # Clear selected user when changing tabs
        self.current_manual_mode_platform = None
        self._repopulate_chat_display_for_current_tab()
        self._update_pause_resume_button_state(self._get_current_funnel_data())

    def _update_pause_resume_button_state(self, status_data):
        """
        Updates the pause/resume button state based on the selected user's manual_mode_active flag.
        `status_data` should be the full response from /status containing 'user_funnel_status_detailed'.
        """
        if self.current_manual_mode_user_id is None:
            self.pause_resume_button.configure(text="No Active User", state="disabled", fg_color=UI_BACKGROUND_SECONDARY_2, hover_color=UI_BACKGROUND_SECONDARY_2, text_color=UI_TEXT_MUTED)
            self.manual_mode_controls_frame.grid_forget()
            self.center_panel_frame.grid_rowconfigure(1, weight=4)
            self.center_panel_frame.grid_rowconfigure(2, weight=0)
            return

        user_funnel_status_detailed = status_data.get('user_funnel_status_detailed', {})
        selected_user_info = user_funnel_status_detailed.get(self.current_manual_mode_user_id, {})
        
        is_manual_mode_active = selected_user_info.get('current_state', {}).get('manual_mode_active', False)

        if selected_user_info: # Only enable if a valid user is selected
            self.pause_resume_button.configure(state="normal")
            self._update_manual_mode_ui(is_manual_mode_active)
        else: # If selected user is no longer in funnel_status_detailed
            self.pause_resume_button.configure(text="User Not Found", state="disabled", fg_color=UI_BACKGROUND_SECONDARY_2, hover_color=UI_BACKGROUND_SECONDARY_2, text_color=UI_TEXT_MUTED)
            self.manual_mode_controls_frame.grid_forget()
            self.center_panel_frame.grid_rowconfigure(1, weight=4)
            self.center_panel_frame.grid_rowconfigure(2, weight=0)


    def show_notification(self, message, user_id, platform):
        if hasattr(self, 'notification_box') and self.notification_box and self.notification_box.winfo_exists():
            self.notification_box.destroy()
            self.notification_box = None
            if hasattr(self, 'notification_hide_timer') and self.notification_hide_timer:
                self.after_cancel(self.notification_hide_timer)
                self.notification_hide_timer = None

        self.current_notification_user_id = user_id
        self.current_notification_platform = platform

        self.notification_box = customtkinter.CTkFrame(self, fg_color=UI_PRIMARY_ACCENT, corner_radius=10, border_width=2, border_color=UI_TEXT_PRIMARY)
        self.notification_box.place(relx=0.5, rely=0.01, anchor="n") 
        
        notification_text = f"New message from {user_id} on {platform}!"
        notification_label = customtkinter.CTkLabel(self.notification_box, text=notification_text, font=("Arial", 14, "bold"), text_color=UI_TEXT_PRIMARY)
        notification_label.pack(padx=15, pady=10)

        self.notification_box.bind("<Button-1>", lambda event: self.go_to_conversation())
        notification_label.bind("<Button-1>", lambda event: self.go_to_conversation())

        self.notification_hide_timer = self.after(5000, self.hide_notification_popup)

        self._insert_console_message(f"NOTIFICATION: {message} (User: {user_id}, Platform: {platform})", prefix="[Notification] ", tag="warning_tag")

    def hide_notification_popup(self):
        if hasattr(self, 'notification_box') and self.notification_box and self.notification_box.winfo_exists():
            self.notification_box.destroy()
        self.notification_box = None
        if hasattr(self, 'notification_hide_timer') and self.notification_hide_timer:
            self.after_cancel(self.notification_hide_timer)
            self.notification_hide_timer = None

    def on_closing(self):
        if self.is_closing:
            return 
            
        print("GUI: Closing application...")
        self.is_closing = True 

        if self.polling_stop_event:
            self.polling_stop_event.set()
        
        if self.polling_thread and self.polling_thread.is_alive():
            print("GUI: Waiting for polling thread to stop...")
            self.polling_thread.join(timeout=2)
            if self.polling_thread.is_alive():
                print("GUI: Warning - Polling thread did not terminate gracefully.")

        self.stop_all_processes()
        self.destroy()
        sys.exit(0)

    def open_debug_window(self):
        if not hasattr(self, 'debug_window') or self.debug_window is None or not self.debug_window.winfo_exists():
            self.debug_window = DebugWindow(master=self, app_instance=self)
            self.update_idletasks()
            master_x = self.winfo_x()
            master_y = self.winfo_y()
            master_width = self.winfo_width()
            master_height = self.winfo_height()
            initial_x = master_x + (master_width // 2) - (300 // 2)
            initial_y = master_y + (master_height // 2) - (250 // 2)
            self.debug_window.geometry(f"300x250+{initial_x}+{initial_y}")
            self.debug_window.lift()
            self.debug_window.focus_force()
        else:
            self.debug_window.deiconify()
            self.debug_window.lift()
            self.debug_window.focus_force()

    def open_close_confirmation(self):
        if not hasattr(self, 'confirmation_window') or self.confirmation_window is None or not self.confirmation_window.winfo_exists():
            self.confirmation_window = ConfirmationWindow(master=self, app_instance=self)
            self.update_idletasks()
            master_x = self.winfo_x()
            master_y = self.winfo_y()
            master_width = self.winfo_width()
            master_height = self.winfo_height()
            initial_x = master_x + (master_width // 2) - (350 // 2)
            initial_y = master_y + (master_height // 2) - (120 // 2)
            self.confirmation_window.geometry(f"350x120+{initial_x}+{initial_y}")
            self.confirmation_window.lift()
            self.confirmation_window.focus_force()
        else:
            self.confirmation_window.deiconify()
            self.confirmation_window.lift()
            self.confirmation_window.focus_force()

    def open_settings(self):
        if not hasattr(self, 'settings_window') or self.settings_window is None or not self.settings_window.winfo_exists():
            self.settings_window = SettingsWindow(master=self, app_instance=self)
            self.update_idletasks()
            master_x = self.winfo_x()
            master_y = self.winfo_y()
            master_width = self.winfo_width()
            master_height = self.winfo_height()
            initial_x = master_x + (master_width // 2) - (1000 // 2)
            initial_y = master_y + (master_height // 2) - (650 // 2)
            self.settings_window.geometry(f"1000x650+{initial_x}+{initial_y}")
            self.settings_window.lift()
            self.settings_window.focus_force()
        else:
            self.settings_window.deiconify()
            self.settings_window.lift()
            self.settings_window.focus_force()
            self.settings_window.load_config() 
    
    def open_user_history_window(self):
        if not hasattr(self, 'user_history_window') or self.user_history_window is None or not self.user_history_window.winfo_exists():
            self.user_history_window = UserHistoryWindow(master=self, app_instance=self) 
            self.update_idletasks()
            master_x = self.winfo_x()
            master_y = self.winfo_y()
            master_width = self.winfo_width()
            master_height = self.winfo_height()
            initial_x = master_x + (master_width // 2) - (500 // 2)
            initial_y = master_y + (master_height // 2) - (600 // 2)
            self.user_history_window.geometry(f"500x600+{initial_x}+{initial_y}")
            self.user_history_window.lift()
        else:
            self.user_history_window.deiconify()
            self.user_history_window.lift()
            self.user_history_window.focus_force()
            self.user_history_window.load_user_history() 
    
    def go_to_conversation(self):
        if not self.current_notification_user_id or not self.current_notification_platform:
            self._insert_console_message("No active notification to go to conversation.", prefix="[System] ", tag="warning_tag")
            return

        if hasattr(self, 'notification_box') and self.notification_box and self.notification_box.winfo_exists():
            self.notification_box.destroy()
            self.notification_box = None
            if hasattr(self, 'notification_hide_timer') and self.notification_hide_timer:
                self.after_cancel(self.notification_hide_timer)
                self.notification_hide_timer = None

        target_platform_display_name = self.current_notification_platform.capitalize()
        if target_platform_display_name == "Web": target_platform_display_name = "Web Chat"
        
        self.chat_log_tabview.set(target_platform_display_name)

        self.current_manual_mode_user_id = self.current_notification_user_id
        self.current_manual_mode_platform = self.current_notification_platform.lower()

        self._repopulate_chat_display_for_current_tab()
        self._insert_console_message(f"Navigated to conversation with {self.current_manual_mode_user_id} on {self.current_manual_mode_platform}.", prefix="[System] ", tag="system_tag")
        
        funnel_data = self._get_current_funnel_data()
        self._update_pause_resume_button_state(funnel_data)

        self.current_notification_user_id = None
        self.current_notification_platform = None

    def stop_all_processes(self):
        self._insert_console_message("\nInitiating STOP ALL BOTS (Kill Switch)...", prefix="[System] ", tag="system_tag")
        processes_to_stop = [
            (self.api_process, "api_process", "API Server"),
            (self.telegram_process, "telegram_process", "Telegram Bot"),
            (self.reddit_process, "reddit_process", "Reddit Bot"),
            (self.discord_process, "discord_process", "Discord Bot"),
            (self.facebook_process, "facebook_process", "Facebook Setup Guide")
        ]
        for process_obj, attr_name, name in processes_to_stop:
            if process_obj and process_obj.poll() is None:
                try:
                    process_obj.terminate()
                    process_obj.wait(timeout=2)
                    if process_obj.poll() is None:
                        process_obj.kill()
                        self._insert_console_message(f"Force killed {name}.", prefix="[System] ", tag="error_tag")
                    else:
                        self._insert_console_message(f"Stopped {name}.", prefix="[System] ", tag="system_tag")
                except Exception as e:
                    self._insert_console_message(f"Error stopping {name}: {e}", prefix="[System] ", tag="error_tag")
                finally:
                    setattr(self, attr_name, None)
            else:
                self._insert_console_message(f"{name} was not running.", prefix="[System] ", tag="system_tag")

        self._insert_console_message("All identified processes stopped.", prefix="[System] ", tag="system_tag")
        self.web_chat_button.configure(state="normal", fg_color=UI_BUTTON_NORMAL_FG, hover_color=UI_BUTTON_NORMAL_HOVER, text_color=UI_TEXT_PRIMARY)
        self.stop_web_chat_button.configure(state="disabled", fg_color=UI_BACKGROUND_SECONDARY_2, text_color=UI_TEXT_MUTED)
        self.telegram_button.configure(state="normal", fg_color=UI_BUTTON_NORMAL_FG, hover_color=UI_BUTTON_NORMAL_HOVER, text_color=UI_TEXT_PRIMARY)
        self.stop_telegram_button.configure(state="disabled", fg_color=UI_BACKGROUND_SECONDARY_2, text_color=UI_TEXT_MUTED)
        self.reddit_button.configure(state="normal", fg_color=UI_BUTTON_NORMAL_FG, hover_color=UI_BUTTON_NORMAL_HOVER, text_color=UI_TEXT_PRIMARY)
        self.stop_reddit_button.configure(state="disabled", fg_color=UI_BACKGROUND_SECONDARY_2, text_color=UI_TEXT_MUTED)
        self.discord_button.configure(state="normal", fg_color=UI_BUTTON_NORMAL_FG, hover_color=UI_BUTTON_NORMAL_HOVER, text_color=UI_TEXT_PRIMARY)
        self.stop_discord_button.configure(state="disabled", fg_color=UI_BACKGROUND_SECONDARY_2, text_color=UI_TEXT_MUTED)

    def _launch_script(self, script_base_name, process_attr_name, queue, launch_button, stop_button):
        process = getattr(self, process_attr_name)
        if process and process.poll() is None:
            self._insert_console_message(f"{script_base_name} is already running.", prefix="[System] ", tag="warning_tag")
            return
        try:
            command = [sys.executable, f"{script_base_name}.py"]
            creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            
            new_process = subprocess.Popen(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                text=True, 
                encoding='utf-8', 
                bufsize=1, 
                creationflags=creation_flags
            )
            setattr(self, process_attr_name, new_process)

            reader_thread = Thread(target=self._enqueue_output, args=(new_process.stdout, queue, self.stop_event))
            reader_thread.daemon = True
            reader_thread.start()

            launch_button.configure(state="disabled", fg_color=UI_BACKGROUND_SECONDARY_2, text_color=UI_TEXT_MUTED)
            stop_button.configure(state="normal", fg_color=UI_BUTTON_DANGER_FG, hover_color=UI_BUTTON_DANGER_HOVER, text_color=UI_TEXT_PRIMARY)

            self._insert_console_message(f"Launched {script_base_name} successfully! Output will appear below.", prefix="[System] ", tag="system_tag")

        except Exception as e:
            self._insert_console_message(f"Failed to launch {script_base_name}: {e}", prefix="[System] ", tag="error_tag")
            traceback.print_exc()

    def _stop_script(self, script_display_name, process_attr_name, launch_button, stop_button):
        process = getattr(self, process_attr_name)
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=2)
                if process.poll() is None:
                    process.kill()
                    self._insert_console_message(f"Force killed {script_display_name}.", prefix="[System] ", tag="error_tag")
                else:
                    self._insert_console_message(f"Stopped {script_display_name}.", prefix="[System] ", tag="system_tag")
            except Exception as e:
                self._insert_console_message(f"Error stopping {script_display_name}: {e}", prefix="[System] ", tag="error_tag")
            finally:
                setattr(self, process_attr_name, None)
                launch_button.configure(state="normal", fg_color=UI_BUTTON_NORMAL_FG, hover_color=UI_BUTTON_NORMAL_HOVER, text_color=UI_TEXT_PRIMARY)
                stop_button.configure(state="disabled", fg_color=UI_BACKGROUND_SECONDARY_2, text_color=UI_TEXT_MUTED)
        else:
            self._insert_console_message(f"{script_display_name} is not running.", prefix="[System] ", tag="system_tag")
            launch_button.configure(state="normal", fg_color=UI_BUTTON_NORMAL_FG, hover_color=UI_BUTTON_NORMAL_HOVER, text_color=UI_TEXT_PRIMARY)
            stop_button.configure(state="disabled", fg_color=UI_BACKGROUND_SECONDARY_2, text_color=UI_TEXT_MUTED)

    def launch_web_chat(self):
        self._insert_console_message("Checking API server status...", prefix="[System] ", tag="system_tag")
        try:
            response = requests.get(f"{API_BASE_URL}/status", timeout=2)
            if response.status_code == 200:
                self._insert_console_message("API server is active. Opening web chat...", prefix="[System] ", tag="system_tag")
                webbrowser.open_new_tab(f"{API_BASE_URL}/web_chat")
                self.web_chat_button.configure(state="disabled")
                self.stop_web_chat_button.configure(state="normal")
            else:
                self._insert_console_message(f"API server responded with status {response.status_code}. Cannot open web chat.", prefix="[System] ", tag="error_tag")
        except requests.exceptions.RequestException:
            self._insert_console_message("API server is not reachable. Please ensure it was started with launch.py.", prefix="[System] ", tag="error_tag")

    def stop_web_chat(self):
        self._insert_console_message("Attempting to shut down API server...", prefix="[System] ", tag="warning_tag")
        try:
            response = requests.post(f"{API_BASE_URL}/shutdown", timeout=2)
            if response.status_code == 200:
                self._insert_console_message("API server shutdown command sent successfully.", prefix="[System] ", tag="system_tag")
            else:
                self._insert_console_message(f"API server responded with status {response.status_code} to shutdown command.", prefix="[System] ", tag="error_tag")
        except requests.exceptions.RequestException:
            self._insert_console_message("API server has been shut down.", prefix="[System] ", tag="system_tag")
        finally:
            self.web_chat_button.configure(state="normal")
            self.stop_web_chat_button.configure(state="disabled")
            self.api_process = None

    def launch_telegram_bot(self):
        self._launch_script("telegram_bot", "telegram_process", self.telegram_queue, self.telegram_button, self.stop_telegram_button)

    def stop_telegram_bot(self):
        self._stop_script("Telegram Bot", "telegram_process", self.telegram_button, self.stop_telegram_button)

    def launch_reddit_bot(self):
        self._launch_script("reddit_bot", "reddit_process", self.reddit_queue, self.reddit_button, self.stop_reddit_button)

    def stop_reddit_bot(self):
        self._stop_script("Reddit Bot", "reddit_process", self.reddit_button, self.stop_reddit_button)

    def launch_discord_bot(self):
        self._launch_script("discord_bot", "discord_process", self.discord_queue, self.discord_button, self.stop_discord_button)

    def stop_discord_bot(self):
        self._stop_script("Discord Bot", "discord_process", self.discord_button, self.stop_discord_button)

    def launch_facebook_setup_guide(self):
        self._insert_console_message("Opening Facebook Webhook Info Guide (in new console)...", prefix="[System] ", tag="system_tag")
        try:
            command = [sys.executable, "facebook_bot.py"]
            # CREATE_NEW_CONSOLE is Windows-specific, for cross-platform, you might need a different approach
            # or simply run it as a regular subprocess and let its output go to the current console.
            creation_flags = subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
            self.facebook_process = subprocess.Popen(command, creationflags=creation_flags)
        except Exception as e:
            self._insert_console_message(f"Failed to open Facebook Setup Guide: {e}", prefix="[System] ", tag="error_tag")

    def toggle_manual_mode(self):
        if self.current_manual_mode_user_id is None or self.current_manual_mode_platform is None:
            self._insert_console_message("No active user selected to toggle manual mode. Select a chat tab with an active user.", prefix="[System] ", tag="warning_tag")
            return

        user_id = self.current_manual_mode_user_id
        platform = self.current_manual_mode_platform

        try:
            response = requests.get(f"{API_BASE_URL}/api/user/{user_id}/dashboard", timeout=1) # Fetch dashboard for specific user
            response.raise_for_status()
            user_dashboard_data = response.json()
            current_manual_mode = user_dashboard_data.get('current_state', {}).get('manual_mode_active', False)
            new_manual_mode = not current_manual_mode

            payload = {
                "user_id": user_id,
                "platform": platform, 
                "manual_mode_active": new_manual_mode
            }
            set_response = requests.post(f"{API_BASE_URL}/set_manual_mode", json=payload, timeout=5)
            set_response.raise_for_status()

            self._insert_console_message(f"Manual mode for {user_id} on {platform} toggled to {new_manual_mode}.", prefix="[System] ", tag="system_tag")

            # Force UI update after toggle
            self._update_manual_mode_ui(new_manual_mode)

            if not new_manual_mode and self.config.get("proactive_mode_enabled", False):
                proactive_msg = self.config.get("proactive_greeting_message", "Hello again! How can I help?")
                proactive_payload = {
                    "user_id": user_id,
                    "message": proactive_msg,
                    "platform": platform
                }
                requests.post(f"{API_BASE_URL}/send_manual_message", json=proactive_payload, timeout=10)
                self._insert_console_message(f"Proactive message sent to {user_id} on {platform} after resuming AI.", prefix="[System] ", tag="system_tag")

        except requests.exceptions.RequestException as e:
            self._insert_console_message(f"Error toggling manual mode: {e}", prefix="[System] ", tag="error_tag")

    def _update_manual_mode_ui(self, is_manual_mode_active):
        if is_manual_mode_active:
            self.pause_resume_button.configure(text="Resume AI", fg_color="#27AE60", hover_color="#2ECC71", state="normal")
            self.manual_mode_controls_frame.grid(row=2, column=0, sticky="ew", pady=(5, 0))
            self.center_panel_frame.grid_rowconfigure(1, weight=3)
            self.center_panel_frame.grid_rowconfigure(2, weight=1)
            self.manual_message_entry.focus_set()
        else:
            self.pause_resume_button.configure(text="Pause AI", fg_color="#F39C12", hover_color="#E67E22", state="normal")
            self.manual_mode_controls_frame.grid_forget()
            self.center_panel_frame.grid_rowconfigure(1, weight=4)
            self.center_panel_frame.grid_rowconfigure(2, weight=0)

    def send_manual_message(self):
        message = self.manual_message_entry.get().strip()
        if not message:
            return

        if self.current_manual_mode_user_id is None or self.current_manual_mode_platform is None:
            self._insert_console_message("No active user selected to send manual message.", prefix="[System] ", tag="warning_tag")
            return
        user_id = self.current_manual_mode_user_id
        platform = self.current_manual_mode_platform

        try:
            payload = {
                "user_id": user_id,
                "message": message,
                "platform": platform
            }
            send_response = requests.post(f"{API_BASE_URL}/send_manual_message", json=payload, timeout=10)
            send_response.raise_for_status()

            if send_response.status_code == 200:
                self._insert_console_message(f"Manual message sent to {user_id} on {platform}.", prefix="[System] ", tag="system_tag")
                self.manual_message_entry.delete(0, 'end')
            else:
                self._insert_console_message(f"Error sending manual message: {send_response.json().get('error', 'Unknown error')}", prefix="[System] ", tag="error_tag")
        except requests.exceptions.RequestException as e:
            self._insert_console_message(f"Connection error sending manual message: {e}", prefix="[System] ", tag="error_tag")

    def send_manual_file(self):
        file_path = customtkinter.filedialog.askopenfilename(
            title="Select File to Send",
            filetypes=[("All files", "*.*")]
        )
        if not file_path:
            return

        if self.current_manual_mode_user_id is None or self.current_manual_mode_platform is None:
            self._insert_console_message("No active user selected to send file.", prefix="[System] ", tag="warning_tag")
            return

        user_id = self.current_manual_mode_user_id
        platform = self.current_manual_mode_platform

        try:
            payload = {
                "user_id": user_id,
                "file_path": file_path, 
                "platform": platform
            }
            send_response = requests.post(f"{API_BASE_URL}/send_manual_message", json=payload, timeout=30)
            send_response.raise_for_status()

            if send_response.status_code == 200:
                self._insert_console_message(f"Manual file '{os.path.basename(file_path)}' logged for {user_id} on {platform}.", prefix="[System] ", tag="system_tag")
            else:
                self._insert_console_message(f"Error sending manual file: {send_response.json().get('error', 'Unknown error')}", prefix="[System] ", tag="error_tag")
        except requests.exceptions.RequestException as e:
            self._insert_console_message(f"Connection error sending manual file: {e}", prefix="[System] ", tag="error_tag")

    def send_proactive_first_message_internal(self, user_id, platform):
        # Renamed to avoid confusion with the API endpoint directly in settings window
        if not user_id:
            self._insert_console_message("Please enter a User ID for Proactive Outreach.", prefix="[System] ", tag="warning_tag")
            return

        if not platform or platform not in ["discord", "reddit", "telegram", "web", "facebook"]:
            self._insert_console_message(f"Please select a valid platform for Proactive Outreach: {platform} is not valid.", prefix="[System] ", tag="warning_tag")
            return
            
        if platform == "telegram":
            self._insert_console_message("WARNING: Telegram requires user to have messaged bot first. Unsolicited messages will fail.", prefix="[System] ", tag="warning_tag")
            
        self._insert_console_message(f"Attempting to send proactive first message to {user_id} on {platform}...", prefix="[System] ", tag="system_tag")

        try:
            response = requests.post(
                f"{API_BASE_URL}/send_proactive_initial_message",
                json={"user_id": user_id, "platform": platform},
                timeout=10
            )
            response.raise_for_status()
            response_data = response.json()

            if response.status_code == 200:
                self._insert_console_message(f"Proactive message status: {response_data.get('message')}", prefix="[System] ", tag="system_tag")
            else:
                self._insert_console_message(f"Proactive message error: {response_data.get('error', 'Unknown error')}", prefix="[System] ", tag="error_tag")
        except requests.exceptions.RequestException as e:
            self._insert_console_message(f"Connection error sending proactive message: {e}", prefix="[System] ", tag="error_tag")

    def _enqueue_output(self, out, queue, stop_event):
        for line in iter(out.readline, ''):
            if stop_event.is_set():
                break
            queue.put(line.strip())
        out.close()

    def process_console_queues(self):
        if self.is_closing: return
        queues_map = {
            self.api_queue: "api_tag",
            self.telegram_queue: "tele_tag",
            self.reddit_queue: "red_tag",
            self.discord_queue: "disc_tag"
        }
        for q, tag_name in queues_map.items():
            try:
                while True:
                    line = q.get_nowait()
                    line_lower = line.lower()
                    if "error" in line_lower or "failed" in line_lower or "critical" in line_lower:
                        final_tag = "error_tag"
                    elif "warning" in line_lower:
                        final_tag = "warning_tag"
                    else:
                        final_tag = tag_name
                    
                    self._insert_console_message(line, tag=final_tag)
            except Empty:
                pass
        if not self.is_closing:
            self.after(100, self.process_console_queues)

    def _insert_console_message(self, message, prefix="", tag=None):
        if hasattr(self, 'console_output_textbox') and self.console_output_textbox: # Ensure textbox exists
            self.console_output_textbox.configure(state="normal")
            full_message = prefix + message + "\n"
            if tag:
                self.console_output_textbox.insert("end", full_message, tag)
            else:
                self.console_output_textbox.insert("end", full_message)
            self.console_output_textbox.see("end")
            self.console_output_textbox.configure(state="disabled")
        else:
            # Fallback if console_output_textbox not yet created (e.g., during _setup_console_tags)
            print(f"{prefix}{message}")

    # --- NEW: Imgur Upload Method for App class ---
    def upload_to_imgur(self, file_path):
        imgur_client_id = self.config.get("imgur_client_id") # Access config from self.config
        if not imgur_client_id:
            self._insert_console_message("ERROR: Imgur Client ID not found in config. Cannot upload image.", tag="error_tag")
            return None

        headers = {"Authorization": f"Client-ID {imgur_client_id}"}
        url = "https://api.imgur.com/3/image"

        try:
            with open(file_path, 'rb') as image_file:
                files = {'image': image_file}
                self._insert_console_message(f"Uploading {os.path.basename(file_path)} to Imgur...", tag="system_tag")
                response = requests.post(url, headers=headers, files=files, timeout=30) # Added timeout
                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

                data = response.json()
                if data and data['success']:
                    image_url = data['data']['link']
                    self._insert_console_message(f"Image uploaded successfully: {image_url}", tag="system_tag")
                    return image_url
                else:
                    error_msg = data.get('data', {}).get('error', 'Unknown error')
                    self._insert_console_message(f"Imgur upload failed: {error_msg}", tag="error_tag")
                    return None
        except requests.exceptions.RequestException as e:
            self._insert_console_message(f"Network or API error during Imgur upload: {e}", tag="error_tag")
            return None
        except FileNotFoundError:
            self._insert_console_message(f"File not found: {file_path}", tag="error_tag")
            return None
        except Exception as e:
            self._insert_console_message(f"An unexpected error occurred during Imgur upload: {e}", tag="error_tag")
            traceback.print_exc() # Print full traceback for unexpected errors
            return None


    def update_status(self):
        if self.is_closing:
            return

        try:
            response = requests.get(f"{API_BASE_URL}/status", timeout=1)
            response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            status_data = response.json()

            # Update server status indicator
            self.server_status_indicator.configure(fg_color=UI_STATUS_ACTIVE)

            # Update conversation counts
            user_funnel_status = status_data.get('user_funnel_status', {})
            in_progress_count = sum(1 for user_info in user_funnel_status.values() if user_info.get('status') == 'in_progress')
            funneled_count = sum(1 for user_info in user_funnel_status.values() if user_info.get('status') == 'funneled')

            self.in_progress_label.configure(text=f"In Progress: {in_progress_count}")
            self.funneled_label.configure(text=f"Funneled: {funneled_count}")
            self.active_users_count_label.configure(text=str(in_progress_count + funneled_count))

            # Update ARPA status
            arpa_status = status_data.get('arpa_status', {})
            arpa_overall_enabled = arpa_status.get('arpa_enabled', False)
            arpa_last_run = arpa_status.get('last_run_time', 'N/A')
            arpa_next_run = arpa_status.get('next_run_time', 'N/A')
            arpa_current_action = arpa_status.get('current_action', 'Idle')
            arpa_target = arpa_status.get('current_target', 'N/A')
            arpa_last_user = arpa_status.get('last_proactive_user', 'None')
            arpa_session_msgs = arpa_status.get('session_messages_sent', 0)

            self.arpa_overall_status_label.configure(text=f"Overall Status: {'On' if arpa_overall_enabled else 'Off'}",
                                                     text_color=UI_STATUS_ACTIVE if arpa_overall_enabled else UI_TEXT_MUTED)
            self.arpa_current_action_label.configure(text=f"Action: {arpa_current_action}")
            self.arpa_target_label.configure(text=f"Target: {arpa_target}")
            self.arpa_last_user_label.configure(text=f"Last User: {arpa_last_user}")
            self.arpa_session_msgs_label.configure(text=f"Msgs Sent (Session): {arpa_session_msgs}")

            # Format next run time for display
            if arpa_next_run != 'N/A':
                try:
                    # Assuming arpa_next_run is an ISO format string, possibly UTC
                    next_run_dt_utc = datetime.fromisoformat(arpa_next_run.replace('Z', '+00:00'))
                    local_next_run_dt = next_run_dt_utc.astimezone() # Convert to local timezone
                    self.arpa_next_run_label.configure(text=f"Next Run: {local_next_run_dt.strftime('%H:%M:%S')}")
                except ValueError:
                    self.arpa_next_run_label.configure(text="Next Run: Invalid Time")
            else:
                self.arpa_next_run_label.configure(text="Next Run: N/A")

            # Update the pause/resume button state if a user is selected
            self._update_pause_resume_button_state(user_funnel_status)


        except requests.exceptions.ConnectionError:
            self._insert_console_message("API Server Offline. Please launch 'api.py'.", prefix="[API Status] ", tag="error_tag")
            self.server_status_indicator.configure(fg_color=UI_STATUS_ERROR)
            self.in_progress_label.configure(text="In Progress: N/A")
            self.funneled_label.configure(text="Funneled: N/A")
            self.active_users_count_label.configure(text="N/A")
            self.arpa_overall_status_label.configure(text="Overall Status: Offline", text_color=UI_STATUS_ERROR)
            self.arpa_current_action_label.configure(text="Action: Offline")
            self.arpa_target_label.configure(text="Target: Offline")
            self.arpa_last_user_label.configure(text="Last User: Offline")
            self.arpa_session_msgs_label.configure(text="Msgs Sent (Session): N/A")
            self.arpa_next_run_label.configure(text="Next Run: Offline")
            self.pause_resume_button.configure(state="disabled", text="Server Offline", fg_color=UI_BACKGROUND_SECONDARY_2, text_color=UI_TEXT_MUTED)

        except requests.exceptions.Timeout:
            self._insert_console_message("API Server Timeout. Check server load or network.", prefix="[API Status] ", tag="warning_tag")
            self.server_status_indicator.configure(fg_color=UI_STATUS_WARNING)
            # Retain last known values or set to 'N/A' as appropriate
        except Exception as e:
            self._insert_console_message(f"Error fetching API status: {e}", prefix="[API Status] ", tag="error_tag")
            self.server_status_indicator.configure(fg_color=UI_STATUS_ERROR)
        finally:
            # Schedule the next update
            if not self.is_closing:
                self.after(2000, self.update_status) # Poll every 2 seconds

    
    
    def open_telegram_link(self):
        telegram_handle_from_config = self.config.get("telegram_handle", "")
        if telegram_handle_from_config:
            telegram_link = f"https://t.me/+49eBTz33XJ9iYjQx"
            webbrowser.open_new_tab(telegram_link)
            self._insert_console_message(f"Opened Telegram link: {telegram_link}", prefix="[System] ", tag="system_tag")
        else:
            self._insert_console_message("Telegram handle not configured in config.json.", prefix="[System] ", tag="warning_tag")

    def open_discord_link(self):
        discord_invite_from_config = self.config.get("discord_invite_link", "")
        if discord_invite_from_config:
            # Ensure it's a valid invite code, not a full URL
            if "discord.gg/" in discord_invite_from_config:
                discord_invite_from_config = discord_invite_from_config.split("discord.gg/")[1]
            discord_link = f"https://discord.gg/NvQwB2ZH"
            webbrowser.open_new_tab(discord_link)
            self._insert_console_message(f"Opened Discord link: {discord_link}", prefix="[System] ", tag="system_tag")
        else:
            self._insert_console_message("Discord invite link not configured in config.json.", prefix="[System] ", tag="warning_tag")

    def save_arpa_settings(self):
        self._insert_console_message("Saving ARPA settings (functional)...", prefix="[System] ", tag="system_tag")
        
        # Collect data from app_config_vars (which are linked to GUI widgets)
        arpa_settings_to_save = {}
        for key, var_or_entry in self.app_config_vars.items():
            if isinstance(var_or_entry, customtkinter.BooleanVar):
                arpa_settings_to_save[key] = var_or_entry.get()
            elif isinstance(var_or_entry, customtkinter.CTkEntry):
                value = var_or_entry.get()
                if key in ["reddit_target_subreddits", "discord_target_channels"]:
                    # Split comma-separated string into a list of stripped strings
                    arpa_settings_to_save[key] = [s.strip() for s in value.split(',') if s.strip()]
                elif key.endswith(("_cooldown_hours_per_user", "_min_delay_seconds_per_message", "_max_daily_messages_total")):
                    try:
                        arpa_settings_to_save[key] = int(value)
                    except ValueError:
                        arpa_settings_to_save[key] = 0 # Default to 0 on invalid input
                        self._insert_console_message(f"Warning: Invalid number for {key}. Set to 0.", prefix="[System] ", tag="warning_tag")
                else:
                    arpa_settings_to_save[key] = value

        # Update the main self.config for runtime
        self.config.update(arpa_settings_to_save)

        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            self._insert_console_message("ARPA Configuration saved to config.json.", prefix="[System] ", tag="system_tag")
            self.save_arpa_settings_button.configure(text="Saved!", fg_color=UI_STATUS_ACTIVE) # Green feedback
            self.after(2000, lambda: self.save_arpa_settings_button.configure(text="Save ARPA Settings", fg_color=UI_BUTTON_NORMAL_FG)) # Reset after 2s
            self.update_status() # Force a status update to reflect new ARPA config
        except Exception as e:
            self._insert_console_message(f"Error saving ARPA config: {e}", prefix="[System] ", tag="error_tag")
            self.save_arpa_settings_button.configure(text="Error!", fg_color=UI_STATUS_ERROR) # Red feedback on error
            self.after(2000, lambda: self.save_arpa_settings_button.configure(text="Save ARPA Settings", fg_color=UI_BUTTON_NORMAL_FG)) # Reset after 2s
            self.update_status()

    # This method is for the "Save Image Paths" button in the pillar frame
    def save_image_paths_pillar(self):
        image_paths_to_save = {
            "chat_pic_path": self.chat_pic_path_entry.get(),
            "random_update_pic_path": self.random_update_pic_path_entry.get(),
            "funnel_pic_path": self.funnel_pic_path_entry.get()
        }
        
        # Update the main self.config for runtime
        self.config.update(image_paths_to_save)

        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            self._insert_console_message("Image paths saved to config.json.", prefix="[System] ", tag="system_tag")
            self.save_image_paths_button.configure(text="Saved!", fg_color=UI_STATUS_ACTIVE) # Green feedback
            self.after(2000, lambda: self.save_image_paths_button.configure(text="Save Image Paths", fg_color=UI_BUTTON_NORMAL_FG)) # Reset after 2s
        except Exception as e:
            self._insert_console_message(f"Error saving image paths: {e}", prefix="[System] ", tag="error_tag")
            self.save_image_paths_button.configure(text="Error!", fg_color=UI_STATUS_ERROR) # Red feedback on error
            self.after(2000, lambda: self.save_image_paths_button.configure(text="Save Image Paths", fg_color=UI_BUTTON_NORMAL_FG)) # Reset after 2s


    # This method is for the "Browse" buttons within the pillar frame (right side)
    def browse_path_pillar(self, entry_name_str):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            if entry_name_str == "chat_pic_path":
                entry_widget = self.chat_pic_path_entry
            elif entry_name_str == "random_update_pic_path":
                entry_widget = self.random_update_pic_path_entry
            elif entry_name_str == "funnel_pic_path":
                entry_widget = self.funnel_pic_path_entry
            else:
                self._insert_console_message(f"Error: Unknown entry name '{entry_name_str}' for path Browse.", prefix="[System] ", tag="error_tag")
                return

            entry_widget.delete(0, 'end')
            entry_widget.insert(0, folder_selected)
            # Update the config in memory for consistency
            self.config[entry_name_str] = folder_selected
            self._insert_console_message(f"Selected path for {entry_name_str}: {folder_selected}", prefix="[System] ", tag="system_tag")
        else:
            self._insert_console_message(f"No path selected for {entry_name_str}.", prefix="[System] ", tag="warning_tag")

if __name__ == "__main__":
    print("DEBUG: main_app.py script executed as main. Starting initial checks.")
    
    customtkinter.set_appearance_mode("dark")  # Modes: "system", "dark", "light"
    customtkinter.set_default_color_theme("blue")  # Themes: "blue", "green", "dark-blue"

    temp_pop_up_root = customtkinter.CTk()
    temp_pop_up_root.withdraw()

    temp_pop_up_root.update_idletasks()
    screen_width = temp_pop_up_root.winfo_screenwidth()
    screen_height = temp_pop_up_root.winfo_screenheight()

    api_running = False
    try:
        # PING THE API TO CHECK CONNECTIVITY
        requests.get(f"{API_BASE_URL}/status", timeout=2)
        api_running = True
        print("DEBUG: API server is reachable.")
    except requests.exceptions.RequestException:
        messagebox.showerror("API Connection Error", 
                             f"Cannot connect to the API server at {API_BASE_URL}.\n"
                             "Please ensure 'api.py' is running and accessible (check IP/Firewall).\n"
                             "Application will exit.")
        temp_pop_up_root.destroy()
        sys.exit()

    server_has_users = False
    if api_running:
        try:
            print("DEBUG: Querying API for existing registered users via /has_registered_users...")
            users_exist_response = requests.get(f"{API_BASE_URL}/has_registered_users", timeout=3)
            users_exist_response.raise_for_status()
            users_exist_data = users_exist_response.json()
            server_has_users = users_exist_data.get('users_exist', False)
            
            if server_has_users:
                print(f"DEBUG: API reports existing users: {server_has_users}. Preparing Login Window.")
            else:
                print(f"DEBUG: API reports existing users: {server_has_users}. Preparing Registration Window.")

        except requests.exceptions.RequestException as e:
            print(f"WARNING: Could not check for existing users on API server via /has_registered_users: {e}. Proceeding as if no users exist.")
            server_has_users = False
    else:
        print("DEBUG: API not running, skipping user existence check. Assuming no users exist.")
        server_has_users = False

    login_successful = False
    logged_in_user_data = None 

    if not server_has_users:
        print("GUI: No users found on server. Launching First-Time Registration...")
        setup_window = RegistrationWindow(master=temp_pop_up_root)
        
        window_width_reg = 400
        window_height_reg = 350
        x_reg = (screen_width // 2) - (window_width_reg // 2)
        y_reg = (screen_height // 2) - (window_height_reg // 2)
        setup_window.geometry(f"{window_width_reg}x{window_height_reg}+{x_reg}+{y_reg}")
        setup_window.wait_window()

        if setup_window.registration_success:
            print("GUI: Registration successful. Attempting immediate login with new credentials.")
            auto_login_payload = {
                "username": setup_window.registered_username, 
                "password": setup_window.password_entry.get().strip(),
                "auto_login_attempt": True 
            }
            try:
                response = requests.post(f"{API_BASE_URL}/login", json=auto_login_payload, timeout=10)
                response_data = response.json()
                if response.status_code == 200:
                    login_successful = True
                    # CRITICAL: Capture the full 'user_data' payload from auto-login
                    logged_in_user_data = response_data.get("user_data") 
                    print(f"DEBUG: Auto-login after registration succeeded for {logged_in_user_data.get('user_id', 'N/A')}.")
                else:
                    print(f"ERROR: Auto-login after registration failed: {response_data.get('message', 'Unknown error')}")
            except requests.exceptions.RequestException as e:
                print(f"ERROR: Network error during auto-login after registration: {e}")
            
        if not login_successful:
            print("GUI: Registration or auto-login failed. Exiting application.")
            temp_pop_up_root.destroy()
            sys.exit()

    else: # Server has users, so launch Login Window
        print("GUI: Server has existing users. Launching Login Window...")
        login_window = LoginWindow(master=temp_pop_up_root)
        
        window_width_login = 400
        window_height_login = 280
        x_login = (screen_width // 2) - (window_width_login // 2)
        y_login = (screen_height // 2) - (window_height_login // 2)
        login_window.geometry(f"{window_width_login}x{window_height_login}+{x_login}+{y_login}")
        login_window.wait_window()
        
        login_successful = login_window.logged_in
        logged_in_user_data = login_window.user_data_from_api 

        if login_successful and logged_in_user_data:
            print("GUI: Final check passed. Instantiating main application window.")
            main_app = App()

            # Defer the login handling until after the mainloop has started.
            # A small delay (e.g., 10ms) is enough to allow the window to initialize.
            main_app.after(10, lambda: main_app.handle_login_success(logged_in_user_data))

            main_app.mainloop()
            print("GUI DEBUG: mainloop exited. App is closing.")
        
        else:
            print("GUI: No successful login. Exiting application.")
        if temp_pop_up_root: 
            temp_pop_up_root.destroy()
        sys.exit()
