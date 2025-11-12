"""
Database module using Supabase (PostgreSQL)
Replaces SQLite with persistent cloud database
"""

import os
from supabase import create_client, Client
import hashlib
import uuid
import json
from datetime import datetime, timedelta
import random


def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()


class SupabaseDatabase:
    def __init__(self, url: str = None, key: str = None):
        """Initialize Supabase client"""
        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_KEY")
        
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        
        self.client: Client = create_client(self.url, self.key)
        self.create_tables()
    
    def create_tables(self):
        """
        Create tables in Supabase
        Note: This should be run once manually via SQL editor in Supabase dashboard
        or via migration script
        """
        # Tables are created via SQL migrations in Supabase
        # See migration_sql.sql file
        pass
    
    # ==================== USER MANAGEMENT ====================
    
    def create_user(self, username, email, password):
        """Create new user"""
        try:
            user_id = str(uuid.uuid4())
            password_hash = hash_password(password)
            
            data = {
                "id": user_id,
                "username": username,
                "email": email,
                "password_hash": password_hash,
                "created_at": datetime.now().isoformat()
            }
            
            result = self.client.table("users").insert(data).execute()
            return user_id, None
            
        except Exception as e:
            error_msg = str(e).lower()
            if 'username' in error_msg or 'unique' in error_msg:
                return None, "שם משתמש או אימייל כבר קיים"
            return None, f"שגיאה ביצירת משתמש: {str(e)}"
    
    def verify_user(self, username, password):
        """Verify user credentials"""
        try:
            password_hash = hash_password(password)
            
            result = self.client.table("users").select("id, username").eq(
                "username", username
            ).eq("password_hash", password_hash).execute()
            
            if result.data and len(result.data) > 0:
                return {"id": result.data[0]["id"], "username": result.data[0]["username"]}
            return None
            
        except Exception as e:
            print(f"Error verifying user: {e}")
            return None
    
    def get_user_by_email(self, email):
        """Get user by email"""
        try:
            result = self.client.table("users").select("*").eq("email", email).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            print(f"Error getting user by email: {e}")
            return None
    
    def get_user_by_id(self, user_id):
        """Get user by ID"""
        try:
            result = self.client.table("users").select("*").eq("id", user_id).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            print(f"Error getting user by ID: {e}")
            return None
    
    # ==================== PASSWORD RESET ====================
    
    def create_password_reset(self, email):
        """Create password reset code"""
        user = self.get_user_by_email(email)
        if not user:
            return None, "אימייל לא נמצא במערכת"
        
        # Generate 6-digit code
        reset_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        # Set expiration (15 minutes from now)
        expires_at = (datetime.now() + timedelta(minutes=15)).isoformat()
        
        try:
            data = {
                "user_id": user['id'],
                "reset_code": reset_code,
                "expires_at": expires_at,
                "used": False
            }
            
            self.client.table("password_resets").insert(data).execute()
            return reset_code, None
            
        except Exception as e:
            return None, f"שגיאה ביצירת קוד איפוס: {str(e)}"
    
    def verify_reset_code(self, email, code):
        """Verify reset code is valid"""
        user = self.get_user_by_email(email)
        if not user:
            return False, "אימייל לא נמצא"
        
        try:
            result = self.client.table("password_resets").select("*").eq(
                "user_id", user['id']
            ).eq("reset_code", code).eq("used", False).gt(
                "expires_at", datetime.now().isoformat()
            ).order("created_at", desc=True).limit(1).execute()
            
            if result.data and len(result.data) > 0:
                return True, user['id']
            return False, "קוד שגוי או פג תוקף"
            
        except Exception as e:
            return False, f"שגיאה בבדיקת קוד: {str(e)}"
    
    def reset_password(self, user_id, new_password, reset_code):
        """Reset user password"""
        try:
            # Mark code as used
            self.client.table("password_resets").update({"used": True}).eq(
                "reset_code", reset_code
            ).execute()
            
            # Update password
            password_hash = hash_password(new_password)
            self.client.table("users").update({"password_hash": password_hash}).eq(
                "id", user_id
            ).execute()
            
            return True
            
        except Exception as e:
            print(f"Error resetting password: {e}")
            return False
    
    # ==================== INVESTIGATION MANAGEMENT ====================
    
    def create_investigation(self, user_id, client_name, description=None):
        """Create new investigation - NO try/except to see real errors"""
        inv_id = str(uuid.uuid4())
        data = {
            "id": inv_id,
            "user_id": user_id,
            "client_name": client_name,
            "description": description,
            "created_at": datetime.now().isoformat()
        }
        
        self.client.table("investigations").insert(data).execute()
        return inv_id
    
    def get_all_investigations(self, user_id):
        """Get all investigations for a user"""
        try:
            result = self.client.table("investigations").select("*").eq(
                "user_id", user_id
            ).order("created_at", desc=True).execute()
            
            investigations = []
            for inv in result.data:
                # Get policy count
                policy_result = self.client.table("policies").select(
                    "id", count="exact"
                ).eq("investigation_id", inv['id']).execute()
                policy_count = policy_result.count or 0
                
                # Get question count
                qa_result = self.client.table("qa_history").select(
                    "id", count="exact"
                ).eq("investigation_id", inv['id']).execute()
                question_count = qa_result.count or 0
                
                investigations.append({
                    'id': inv['id'],
                    'client_name': inv['client_name'],
                    'description': inv.get('description'),
                    'created_at': inv['created_at'],
                    'policy_count': policy_count,
                    'question_count': question_count
                })
            
            return investigations
            
        except Exception as e:
            print(f"Error getting investigations: {e}")
            return []
    
    def get_investigation(self, inv_id):
        """Get single investigation"""
        try:
            result = self.client.table("investigations").select("*").eq("id", inv_id).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            print(f"Error getting investigation: {e}")
            return None
    
    def delete_investigation(self, inv_id):
        """Delete investigation (cascades to policies and chunks)"""
        try:
            # Note: Files in storage need to be deleted separately
            # This is handled in the app layer
            self.client.table("investigations").delete().eq("id", inv_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting investigation: {e}")
            return False
    
    # ==================== POLICY MANAGEMENT ====================
    
    def get_company_count(self, inv_id, company):
        """Get count of policies for a company in an investigation"""
        try:
            result = self.client.table("policies").select(
                "id", count="exact"
            ).eq("investigation_id", inv_id).eq("company", company).execute()
            return result.count or 0
        except Exception as e:
            print(f"Error getting company count: {e}")
            return 0
    
    def insert_policy(self, inv_id, company, file_name, custom_name, file_path, total_pages):
        """Insert new policy"""
        try:
            policy_id = str(uuid.uuid4())
            data = {
                "id": policy_id,
                "investigation_id": inv_id,
                "company": company,
                "file_name": file_name,
                "custom_name": custom_name,
                "file_path": file_path,
                "total_pages": total_pages,
                "created_at": datetime.now().isoformat()
            }
            
            self.client.table("policies").insert(data).execute()
            return policy_id
            
        except Exception as e:
            print(f"Error inserting policy: {e}")
            return None
    
    def get_policies(self, inv_id):
        """Get all policies for an investigation"""
        try:
            result = self.client.table("policies").select("*").eq(
                "investigation_id", inv_id
            ).order("created_at", desc=True).execute()
            return result.data
        except Exception as e:
            print(f"Error getting policies: {e}")
            return []
    
    def delete_policy(self, policy_id):
        """Delete policy (cascades to chunks)"""
        try:
            # Get file path before deleting
            result = self.client.table("policies").select("file_path").eq("id", policy_id).execute()
            file_path = result.data[0]['file_path'] if result.data else None
            
            # Delete from database
            self.client.table("policies").delete().eq("id", policy_id).execute()
            
            return file_path  # Return file_path so it can be deleted from storage
        except Exception as e:
            print(f"Error deleting policy: {e}")
            return None
    
    # ==================== POLICY CHUNKS ====================
    
    def insert_chunks(self, policy_id, chunks):
        """Insert text chunks for a policy"""
        try:
            data = [{"policy_id": policy_id, "chunk_text": chunk} for chunk in chunks]
            self.client.table("policy_chunks").insert(data).execute()
            return True
        except Exception as e:
            print(f"Error inserting chunks: {e}")
            return False
    
    def get_all_text(self, policy_id):
        """Get all text for a policy"""
        try:
            result = self.client.table("policy_chunks").select("chunk_text").eq(
                "policy_id", policy_id
            ).execute()
            return "\n\n".join([row['chunk_text'] for row in result.data])
        except Exception as e:
            print(f"Error getting all text: {e}")
            return ""
    
    def search_chunks(self, policy_id, query, top_k=10):
        """Search chunks for a policy (simple keyword search)"""
        try:
            result = self.client.table("policy_chunks").select("chunk_text").eq(
                "policy_id", policy_id
            ).execute()
            
            query_lower = query.lower()
            scored = []
            
            for row in result.data:
                text = row['chunk_text']
                score = 0
                
                # Boost for price-related queries
                if 'מחיר' in query_lower or 'עלות' in query_lower or 'פרמיה' in query_lower:
                    if 'גיל' in text.lower() or 'מחיר' in text.lower() or 'פרמיה' in text.lower():
                        score += 10
                
                # Count keyword matches
                score += sum(1 for word in query_lower.split() if word in text.lower())
                
                if score > 0:
                    scored.append({'text': text, 'score': score})
            
            scored.sort(key=lambda x: x['score'], reverse=True)
            return scored[:top_k]
            
        except Exception as e:
            print(f"Error searching chunks: {e}")
            return []
    
    # ==================== Q&A HISTORY ====================
    
    def save_qa(self, inv_id, question, answer, policy_names):
        """Save Q&A to history"""
        try:
            data = {
                "investigation_id": inv_id,
                "question": question,
                "answer": answer,
                "policy_names": json.dumps(policy_names),
                "created_at": datetime.now().isoformat()
            }
            
            self.client.table("qa_history").insert(data).execute()
            return True
        except Exception as e:
            print(f"Error saving Q&A: {e}")
            return False
    
    def get_qa_history(self, inv_id):
        """Get Q&A history for an investigation"""
        try:
            result = self.client.table("qa_history").select("*").eq(
                "investigation_id", inv_id
            ).order("created_at", desc=True).execute()
            
            return [{
                'question': row['question'],
                'answer': row['answer'],
                'policy_names': row['policy_names'],
                'created_at': row['created_at']
            } for row in result.data]
            
        except Exception as e:
            print(f"Error getting Q&A history: {e}")
            return []
