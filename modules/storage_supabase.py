"""
Storage module for Supabase Storage
Handles PDF file uploads and downloads
"""

import os
from supabase import create_client, Client
import uuid
from typing import Optional, Tuple
import re


class SupabaseStorage:
    def __init__(self, url: str = None, key: str = None):
        """Initialize Supabase Storage client"""
        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_KEY")
        
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        
        self.client: Client = create_client(self.url, self.key)
        self.bucket_name = "policy-pdfs"
        self.ensure_bucket_exists()
    
    def ensure_bucket_exists(self):
        """Ensure the storage bucket exists"""
        try:
            # Try to get bucket info
            self.client.storage.get_bucket(self.bucket_name)
        except Exception:
            # Bucket doesn't exist, create it
            try:
                self.client.storage.create_bucket(
                    self.bucket_name,
                    options={"public": False}  # Private bucket
                )
            except Exception as e:
                print(f"Note: Could not create bucket (may already exist): {e}")
    
    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to remove problematic characters
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename safe for storage
        """
        # Remove or replace problematic characters
        # Keep only alphanumeric, Hebrew letters, hyphens, underscores, and dots
        sanitized = re.sub(r'[^\w\u0590-\u05FF._-]', '_', filename)
        # Remove multiple consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        return sanitized
    
    def upload_pdf(self, file_bytes: bytes, investigation_id: str, company: str, 
                   original_filename: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Upload PDF to Supabase Storage
        
        Returns:
            (file_path, error_message)
        """
        try:
            # Generate unique filename with sanitized company name
            file_extension = os.path.splitext(original_filename)[1]
            unique_id = str(uuid.uuid4())[:8]
            
            # Sanitize company name to avoid problematic characters
            safe_company = self.sanitize_filename(company)
            
            # Create file path
            file_name = f"{investigation_id}/{safe_company}_{unique_id}{file_extension}"
            
            # Upload file
            result = self.client.storage.from_(self.bucket_name).upload(
                file_name,
                file_bytes,
                file_options={"content-type": "application/pdf"}
            )
            
            return file_name, None
            
        except Exception as e:
            return None, f"שגיאה בהעלאת קובץ: {str(e)}"
    
    def download_pdf(self, file_path: str) -> Optional[bytes]:
        """
        Download PDF from Supabase Storage
        
        Returns:
            File bytes or None if error
        """
        try:
            response = self.client.storage.from_(self.bucket_name).download(file_path)
            return response
        except Exception as e:
            print(f"Error downloading file: {e}")
            return None
    
    def delete_pdf(self, file_path: str) -> bool:
        """
        Delete PDF from Supabase Storage
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.storage.from_(self.bucket_name).remove([file_path])
            return True
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False
    
    def get_public_url(self, file_path: str) -> Optional[str]:
        """
        Get public URL for a file (requires public bucket)
        For private buckets, use signed URLs instead
        """
        try:
            result = self.client.storage.from_(self.bucket_name).get_public_url(file_path)
            return result
        except Exception as e:
            print(f"Error getting public URL: {e}")
            return None
    
    def create_signed_url(self, file_path: str, expires_in: int = 3600) -> Optional[str]:
        """
        Create signed URL for temporary access to private file
        
        Args:
            file_path: Path to file in storage
            expires_in: Expiration time in seconds (default 1 hour)
        
        Returns:
            Signed URL or None if error
        """
        try:
            result = self.client.storage.from_(self.bucket_name).create_signed_url(
                file_path,
                expires_in
            )
            return result.get('signedURL')
        except Exception as e:
            print(f"Error creating signed URL: {e}")
            return None
    
    def list_files(self, investigation_id: str) -> list:
        """
        List all files for an investigation
        
        Returns:
            List of file objects
        """
        try:
            result = self.client.storage.from_(self.bucket_name).list(investigation_id)
            return result
        except Exception as e:
            print(f"Error listing files: {e}")
            return []
    
    def delete_investigation_files(self, investigation_id: str) -> bool:
        """
        Delete all files for an investigation
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # List all files in the investigation folder
            files = self.list_files(investigation_id)
            
            if files:
                # Delete all files
                file_paths = [f"{investigation_id}/{file['name']}" for file in files]
                self.client.storage.from_(self.bucket_name).remove(file_paths)
            
            return True
        except Exception as e:
            print(f"Error deleting investigation files: {e}")
            return False
