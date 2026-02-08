#!/usr/bin/env python3
"""
Telegram File Downloader Application

This application provides a GUI interface for connecting to Telegram,
scanning channels for specific file types, and downloading them.
"""

import asyncio
import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import MessageMediaDocument, Document, Photo, InputPeerChannel
from telethon.tl.functions.channels import GetMessagesRequest


@dataclass
class DownloadStats:
    """Class to track download statistics"""
    total_files: int = 0
    downloaded_files: int = 0
    failed_files: int = 0
    bytes_downloaded: int = 0
    total_bytes: int = 0


class TelegramFileDownloader:
    """
    Main class for handling Telegram file downloads with GUI
    """
    
    def __init__(self):
        # Initialize default values
        self.client: Optional[TelegramClient] = None
        self.phone_number: str = ""
        self.api_id: int = 0
        self.api_hash: str = ""
        
        # File categories with their extensions
        self.file_categories = {
            "Documents": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".xls", ".xlsx", ".ppt", ".pptx"},
            "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
            "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"},
            "Videos": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"},
            "Audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"},
            "Programs": {".exe", ".msi", ".deb", ".rpm", ".app", ".dmg", ".apk"},
            "Data": {".csv", ".json", ".xml", ".sql", ".db", ".sqlite"},
            "Code": {".py", ".js", ".html", ".css", ".java", ".cpp", ".c", ".h", ".php", ".rb", ".go", ".rs"}
        }
        
        # Currently selected categories
        self.selected_categories: Set[str] = set()
        self.download_folder: str = str(Path.home() / "Downloads")
        
        # Statistics
        self.stats = DownloadStats()
        
        # Files to download
        self.files_to_download: List[Dict] = []
        self.current_operation_task: Optional[asyncio.Task] = None
        
        # Create download folder if it doesn't exist
        os.makedirs(self.download_folder, exist_ok=True)
    
    async def connect_to_telegram(self, phone_number: str, api_id: int, api_hash: str) -> bool:
        """
        Connect to Telegram using phone number authentication
        
        Args:
            phone_number: User's phone number
            api_id: Telegram API ID
            api_hash: Telegram API hash
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.phone_number = phone_number
            self.api_id = api_id
            self.api_hash = api_hash
            
            # Create client with session file based on phone number
            session_name = f"session_{phone_number.replace('+', '')}"
            self.client = TelegramClient(session_name, api_id, api_hash)
            
            # Start the client
            await self.client.start(phone=phone_number)
            
            if not await self.client.is_user_authorized():
                raise Exception("User not authorized. Please check credentials.")
            
            return True
            
        except SessionPasswordNeededError:
            # Handle 2FA if needed
            print("Two-factor authentication required")
            return False
        except Exception as e:
            print(f"Connection error: {e}")
            return False
    
    def get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename"""
        return os.path.splitext(filename)[1].lower()
    
    def is_file_in_selected_category(self, filename: str) -> bool:
        """Check if file belongs to any selected category"""
        ext = self.get_file_extension(filename)
        
        for category in self.selected_categories:
            if category in self.file_categories:
                if ext in self.file_categories[category]:
                    return True
        return False
    
    async def scan_channel_for_files(self, channel_username: str, progress_callback=None) -> List[Dict]:
        """
        Scan a Telegram channel for files matching selected categories
        
        Args:
            channel_username: Username or ID of the channel to scan
            progress_callback: Optional callback to report progress
            
        Returns:
            List of file information dictionaries
        """
        if not self.client:
            raise Exception("Not connected to Telegram")
        
        files_found = []
        
        try:
            # Get channel entity
            channel_entity = await self.client.get_entity(channel_username)
            
            # Get total message count to calculate progress
            total_messages = 0
            async for _ in self.client.iter_messages(channel_entity):
                total_messages += 1
                break  # Just counting, we'll iterate again properly
            
            processed_count = 0
            
            # Iterate through messages in the channel
            async for message in self.client.iter_messages(channel_entity):
                processed_count += 1
                
                # Update progress if callback provided
                if progress_callback:
                    progress = (processed_count / max(total_messages, 1)) * 100
                    progress_callback(f"Scanning: {progress:.1f}% ({processed_count}/{total_messages})")
                
                # Check if message has media (document/photo)
                if hasattr(message, 'media') and message.media:
                    file_info = self.extract_file_info(message)
                    
                    if file_info and self.is_file_in_selected_category(file_info['filename']):
                        files_found.append(file_info)
        
        except Exception as e:
            print(f"Error scanning channel: {e}")
            raise
        
        return files_found
    
    def extract_file_info(self, message) -> Optional[Dict]:
        """
        Extract file information from a Telegram message
        
        Args:
            message: Telegram message object
            
        Returns:
            Dictionary with file information or None if no file found
        """
        if not hasattr(message, 'media'):
            return None
        
        if isinstance(message.media, MessageMediaDocument):
            doc: Document = message.media.document
            if doc and hasattr(doc, 'attributes'):
                # Find filename attribute
                filename = "unknown"
                for attr in doc.attributes:
                    if hasattr(attr, 'file_name'):
                        filename = attr.file_name
                        break
                
                return {
                    'id': doc.id,
                    'filename': filename,
                    'size': getattr(doc, 'size', 0),
                    'date': message.date,
                    'message_id': message.id,
                    'channel_id': message.chat_id,
                    'extension': self.get_file_extension(filename)
                }
        
        elif isinstance(message, Photo):
            # Handle photos
            photo = message.photo
            if photo:
                filename = f"photo_{photo.id}.jpg"
                size = 0
                if hasattr(photo, 'sizes') and photo.sizes:
                    largest_size = photo.sizes[-1]
                    if hasattr(largest_size, 'size'):
                        size = largest_size.size
                
                return {
                    'id': photo.id,
                    'filename': filename,
                    'size': size,
                    'date': message.date,
                    'message_id': message.id,
                    'channel_id': message.chat_id,
                    'extension': '.jpg'
                }
        
        return None
    
    async def download_file(self, file_info: Dict, progress_callback=None) -> bool:
        """
        Download a single file from Telegram
        
        Args:
            file_info: Dictionary containing file information
            progress_callback: Optional callback to report progress
            
        Returns:
            True if download successful, False otherwise
        """
        if not self.client:
            return False
        
        try:
            # Construct file path
            filepath = os.path.join(self.download_folder, file_info['filename'])
            
            # Add numeric suffix if file already exists
            counter = 1
            original_filepath = filepath
            while os.path.exists(filepath):
                name, ext = os.path.splitext(original_filepath)
                filepath = f"{name}_{counter}{ext}"
                counter += 1
            
            # Download the file with progress callback
            def progress_hook(current, total):
                if progress_callback:
                    progress = (current / total) * 100 if total > 0 else 0
                    progress_callback(f"Downloading: {progress:.1f}% ({current}/{total}) bytes")
            
            # Get the message containing the document
            channel_entity = await self.client.get_entity(
                InputPeerChannel(file_info['channel_id'], 0)
            )
            
            messages = await self.client(GetMessagesRequest(
                channel_entity,
                [file_info['message_id']]
            ))
            
            if messages and len(messages) > 0:
                message = messages[0]
                if hasattr(message, 'media') and message.media:
                    await self.client.download_media(
                        message.media,
                        file=filepath,
                        progress_callback=progress_hook
                    )
                    
                    # Update statistics
                    self.stats.downloaded_files += 1
                    self.stats.bytes_downloaded += file_info['size']
                    
                    return True
            
            return False
            
        except Exception as e:
            print(f"Download error: {e}")
            self.stats.failed_files += 1
            return False
    
    async def download_all_files(self, progress_callback=None) -> None:
        """
        Download all files in the files_to_download list
        
        Args:
            progress_callback: Optional callback to report progress
        """
        if not self.files_to_download:
            return
        
        total_files = len(self.files_to_download)
        
        for i, file_info in enumerate(self.files_to_download):
            if progress_callback:
                progress_callback(f"Downloading file {i+1} of {total_files}: {file_info['filename']}")
            
            success = await self.download_file(file_info)
            
            if not success:
                print(f"Failed to download: {file_info['filename']}")
    
    def stop_current_operation(self) -> None:
        """Stop the currently running operation"""
        if self.current_operation_task and not self.current_operation_task.done():
            self.current_operation_task.cancel()


class TelegramDownloaderGUI:
    """GUI Class for the Telegram File Downloader"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Telegram File Downloader")
        self.root.geometry("800x600")
        
        # Create main application instance
        self.app = TelegramFileDownloader()
        
        # Variables
        self.phone_var = tk.StringVar()
        self.api_id_var = tk.IntVar()
        self.api_hash_var = tk.StringVar()
        self.channel_var = tk.StringVar()
        self.progress_var = tk.StringVar(value="Ready")
        self.status_var = tk.StringVar(value="Disconnected")
        
        # Setup GUI
        self.setup_gui()
        
        # Start GUI update timer
        self.update_timer()
    
    def setup_gui(self):
        """Setup the main GUI layout"""
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Connection Frame
        conn_frame = ttk.LabelFrame(main_frame, text="Connection", padding="10")
        conn_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(conn_frame, text="Phone Number:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Entry(conn_frame, textvariable=self.phone_var, width=20).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        ttk.Label(conn_frame, text="API ID:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        ttk.Entry(conn_frame, textvariable=self.api_id_var, width=15).grid(row=0, column=3, sticky=(tk.W, tk.E), padx=(0, 10))
        
        ttk.Label(conn_frame, text="API Hash:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        ttk.Entry(conn_frame, textvariable=self.api_hash_var, width=40).grid(row=1, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0))
        
        ttk.Button(conn_frame, text="Connect", command=self.connect_to_telegram).grid(row=0, column=4, rowspan=2, padx=(10, 0))
        
        # Status label
        ttk.Label(conn_frame, textvariable=self.status_var).grid(row=0, column=5, padx=(20, 0), sticky=tk.W)
        
        # Categories Frame
        cats_frame = ttk.LabelFrame(main_frame, text="File Categories", padding="10")
        cats_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        cats_frame.columnconfigure(0, weight=1)
        
        # Create checkboxes for each category
        self.category_vars = {}
        row = 0
        for category in self.app.file_categories.keys():
            var = tk.BooleanVar()
            checkbox = ttk.Checkbutton(cats_frame, text=category, variable=var)
            checkbox.grid(row=row, column=0, sticky=tk.W)
            self.category_vars[category] = var
            row += 1
        
        # Channel and Actions Frame
        actions_frame = ttk.LabelFrame(main_frame, text="Actions", padding="10")
        actions_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10), padx=(10, 0))
        actions_frame.columnconfigure(0, weight=1)
        
        ttk.Label(actions_frame, text="Channel:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(actions_frame, textvariable=self.channel_var, width=30).grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(actions_frame, text="Scan Channel", command=self.scan_channel).grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        ttk.Button(actions_frame, text="Download Selected", command=self.download_files).grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        ttk.Button(actions_frame, text="Select Download Folder", command=self.select_download_folder).grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        ttk.Button(actions_frame, text="Stop Operation", command=self.stop_operation).grid(row=5, column=0, sticky=(tk.W, tk.E))
        
        # Progress Frame
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        progress_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)
        
        ttk.Label(progress_frame, textvariable=self.progress_var).grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Results Treeview
        tree_frame = ttk.Frame(main_frame)
        tree_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Create treeview for showing files
        columns = ('filename', 'size', 'date')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=10)
        
        # Define headings
        self.tree.heading('filename', text='Filename')
        self.tree.heading('size', text='Size')
        self.tree.heading('date', text='Date')
        
        # Configure column widths
        self.tree.column('filename', width=300)
        self.tree.column('size', width=100)
        self.tree.column('date', width=150)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    
    def connect_to_telegram(self):
        """Connect to Telegram in a separate thread"""
        def connect_thread():
            try:
                phone = self.phone_var.get().strip()
                api_id = self.api_id_var.get()
                api_hash = self.api_hash_var.get().strip()
                
                if not phone or not api_id or not api_hash:
                    self.show_error("Please fill all connection fields")
                    return
                
                async def connect_async():
                    success = await self.app.connect_to_telegram(phone, api_id, api_hash)
                    return success
                
                # Run the async connection
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success = loop.run_until_complete(connect_async())
                loop.close()
                
                if success:
                    self.status_var.set("Connected")
                    self.progress_var.set("Successfully connected to Telegram")
                else:
                    self.show_error("Failed to connect to Telegram")
                    
            except Exception as e:
                self.show_error(f"Connection error: {e}")
        
        # Run connection in separate thread to avoid blocking UI
        threading.Thread(target=connect_thread, daemon=True).start()
    
    def scan_channel(self):
        """Scan channel for files in a separate thread"""
        def scan_thread():
            try:
                channel = self.channel_var.get().strip()
                if not channel:
                    self.show_error("Please enter a channel username")
                    return
                
                # Update selected categories
                self.app.selected_categories = {
                    cat for cat, var in self.category_vars.items() if var.get()
                }
                
                if not self.app.selected_categories:
                    self.show_error("Please select at least one file category")
                    return
                
                async def scan_async():
                    files = await self.app.scan_channel_for_files(
                        channel, 
                        progress_callback=lambda msg: self.progress_var.set(msg)
                    )
                    return files
                
                # Run the async scan
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                files = loop.run_until_complete(scan_async())
                loop.close()
                
                # Update GUI with found files
                self.app.files_to_download = files
                self.update_file_list(files)
                self.progress_var.set(f"Found {len(files)} files matching selected categories")
                
            except Exception as e:
                self.show_error(f"Scan error: {e}")
        
        # Run scan in separate thread to avoid blocking UI
        threading.Thread(target=scan_thread, daemon=True).start()
    
    def download_files(self):
        """Download selected files in a separate thread"""
        if not self.app.files_to_download:
            self.show_error("No files to download. Please scan a channel first.")
            return
        
        def download_thread():
            try:
                async def download_async():
                    await self.app.download_all_files(
                        progress_callback=lambda msg: self.progress_var.set(msg)
                    )
                
                # Run the async download
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(download_async())
                loop.close()
                
                self.progress_var.set("Download completed!")
                
            except Exception as e:
                self.show_error(f"Download error: {e}")
        
        # Run download in separate thread to avoid blocking UI
        threading.Thread(target=download_thread, daemon=True).start()
    
    def select_download_folder(self):
        """Open dialog to select download folder"""
        folder = filedialog.askdirectory(initialdir=self.app.download_folder)
        if folder:
            self.app.download_folder = folder
            self.progress_var.set(f"Download folder set to: {folder}")
    
    def stop_operation(self):
        """Stop current operation"""
        self.app.stop_current_operation()
        self.progress_var.set("Operation stopped")
    
    def update_file_list(self, files):
        """Update the file list in the GUI"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add new files
        for file_info in files:
            size_str = self.format_file_size(file_info['size'])
            date_str = file_info['date'].strftime('%Y-%m-%d %H:%M') if file_info['date'] else 'Unknown'
            
            self.tree.insert('', tk.END, values=(
                file_info['filename'],
                size_str,
                date_str
            ))
    
    def format_file_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        size = float(size_bytes)
        
        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1
        
        return f"{size:.1f} {size_names[i]}"
    
    def show_error(self, message):
        """Show error message in both GUI and console"""
        print(f"Error: {message}")
        messagebox.showerror("Error", message)
    
    def update_timer(self):
        """Periodic updates to GUI"""
        # Schedule next update
        self.root.after(100, self.update_timer)
    
    def run(self):
        """Start the GUI application"""
        self.root.mainloop()


def main():
    """Main entry point"""
    try:
        gui = TelegramDownloaderGUI()
        gui.run()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
    except Exception as e:
        print(f"Application error: {e}")


if __name__ == "__main__":
    main()