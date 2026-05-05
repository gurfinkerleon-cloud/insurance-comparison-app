"""
InsuranceClientDB — Supabase client for BituachBot landing page.

Tables used:
  agents           (id, agent_code, full_name, admin_password, email)
  profiles         (id, phone_number, full_name, teudat_zehut, agent_id)
  master_annexes   (id, annex_code, annex_name, company_id, full_text)
  user_policies    (id, user_id, annex_id)
  insurance_companies (id, name)
"""

import os
import random
import re
from datetime import datetime, timedelta

import requests
from supabase import create_client, Client


def _load_secret(key: str) -> str | None:
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val:
            return val
    except Exception:
        pass
    return os.getenv(key)


class InsuranceClientDB:
    def __init__(self):
        url = _load_secret("SUPABASE_URL")
        key = _load_secret("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be configured")
        self.client: Client = create_client(url, key)
        self._green_instance = _load_secret("GREEN_API_INSTANCE")
        self._green_token = _load_secret("GREEN_API_TOKEN")

    # ── AGENTS ────────────────────────────────────────────────────────────────

    def get_agent_by_code(self, code: str) -> dict | None:
        try:
            res = (
                self.client.table("agents")
                .select("id, agent_code, full_name, admin_password, email")
                .eq("agent_code", code.upper())
                .limit(1)
                .execute()
            )
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[InsuranceClientDB] get_agent_by_code: {e}")
            return None

    def get_agent_by_email_and_password(self, email: str, password: str) -> dict | None:
        try:
            res = (
                self.client.table("agents")
                .select("id, agent_code, full_name, admin_password, email")
                .eq("email", email.lower().strip())
                .limit(1)
                .execute()
            )
            if not res.data:
                return None
            agent = res.data[0]
            return agent if agent.get("admin_password") == password else None
        except Exception as e:
            print(f"[InsuranceClientDB] get_agent_by_email_and_password: {e}")
            return None

    def get_all_agents(self) -> list[dict]:
        try:
            res = self.client.table("agents").select("id, agent_code, full_name").execute()
            return res.data or []
        except Exception as e:
            print(f"[InsuranceClientDB] get_all_agents: {e}")
            return []

    def reset_agent_password(self, email: str, full_name: str, new_password: str) -> bool:
        """Reset password after verifying email + full name match."""
        try:
            res = (
                self.client.table("agents")
                .select("id, full_name")
                .eq("email", email.lower().strip())
                .limit(1)
                .execute()
            )
            if not res.data:
                return False
            agent = res.data[0]
            if agent["full_name"].strip().lower() != full_name.strip().lower():
                return False
            self.client.table("agents").update(
                {"admin_password": new_password}
            ).eq("id", agent["id"]).execute()
            return True
        except Exception as e:
            print(f"[InsuranceClientDB] reset_agent_password: {e}")
            return False

    def create_agent(self, agent_code: str, full_name: str, admin_password: str, email: str = "") -> tuple[bool, str]:
        try:
            existing = self.get_agent_by_code(agent_code)
            if existing:
                return False, "agent_exists"
            res = self.client.table("agents").insert({
                "agent_code": agent_code.upper(),
                "full_name": full_name,
                "admin_password": admin_password,
                "email": email,
            }).execute()
            return (True, res.data[0]["id"]) if res.data else (False, "שגיאה ביצירת הסוכן")
        except Exception as e:
            print(f"[InsuranceClientDB] create_agent: {e}")
            return False, str(e)

    # ── PROFILES ──────────────────────────────────────────────────────────────

    def get_profile_by_phone(self, phone: str) -> dict | None:
        try:
            res = self.client.table("profiles").select("*").eq("phone_number", phone).limit(1).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[InsuranceClientDB] get_profile_by_phone: {e}")
            return None

    def register_user_with_policies(
        self, phone: str, name: str, annex_codes: list[str], tz: str, agent_id: str = ""
    ) -> tuple[bool, str]:
        """
        Creates a new profile and links annex codes.
        Returns (True, user_id) on success.
        Returns (False, "already_registered") if phone exists.
        Returns (False, error_message) on failure.
        """
        try:
            existing = self.get_profile_by_phone(phone)
            if existing:
                return False, "already_registered"

            # Insert profile — try with teudat_zehut, fall back without it
            profile_data: dict = {"phone_number": phone, "full_name": name}
            if tz:
                profile_data["teudat_zehut"] = tz
            if agent_id:
                profile_data["agent_id"] = agent_id

            try:
                res = self.client.table("profiles").insert(profile_data).execute()
            except Exception:
                profile_data.pop("teudat_zehut", None)
                res = self.client.table("profiles").insert(profile_data).execute()

            if not res.data:
                return False, "שגיאה ביצירת הפרופיל"

            user_id: str = res.data[0]["id"]

            for code in annex_codes:
                self._save_annex_code(user_id, code)

            return True, user_id

        except Exception as e:
            print(f"[InsuranceClientDB] register_user_with_policies: {e}")
            return False, f"שגיאה: {str(e)}"

    def _save_annex_code(self, user_id: str, code: str) -> None:
        """Save annex code to user_policies. Links annex_id if found in master_annexes."""
        try:
            # Check already saved
            existing = (
                self.client.table("user_policies")
                .select("id, annex_id")
                .eq("user_id", user_id)
                .eq("annex_code", code)
                .limit(1)
                .execute()
            )
            annex = (
                self.client.table("master_annexes")
                .select("id")
                .eq("annex_code", code)
                .limit(1)
                .execute()
            )
            annex_id = annex.data[0]["id"] if annex.data else None

            if existing.data:
                # Update annex_id if it was missing and now we have it
                if annex_id and not existing.data[0].get("annex_id"):
                    self.client.table("user_policies").update(
                        {"annex_id": annex_id}
                    ).eq("id", existing.data[0]["id"]).execute()
            else:
                row = {"user_id": user_id, "annex_code": code}
                if annex_id:
                    row["annex_id"] = annex_id
                self.client.table("user_policies").insert(row).execute()
        except Exception as e:
            print(f"[InsuranceClientDB] _save_annex_code {code}: {e}")

    def resolve_pending_codes(self, annex_code: str, annex_id: str) -> int:
        """After a nispaj is added to master_annexes, link all pending user_policies."""
        try:
            res = (
                self.client.table("user_policies")
                .update({"annex_id": annex_id})
                .eq("annex_code", annex_code)
                .is_("annex_id", "null")
                .execute()
            )
            return len(res.data) if res.data else 0
        except Exception as e:
            print(f"[InsuranceClientDB] resolve_pending_codes {annex_code}: {e}")
            return 0

    def upsert_master_annex(self, annex_code: str, annex_name: str, full_text: str, company_id: str = None) -> tuple[bool, str]:
        """Add or update a nispaj in master_annexes. Returns (ok, annex_id)."""
        try:
            existing = (
                self.client.table("master_annexes")
                .select("id")
                .eq("annex_code", annex_code)
                .limit(1)
                .execute()
            )
            data = {"annex_code": annex_code, "annex_name": annex_name, "full_text": full_text}
            if company_id:
                data["company_id"] = company_id

            if existing.data:
                annex_id = existing.data[0]["id"]
                self.client.table("master_annexes").update(data).eq("id", annex_id).execute()
            else:
                res = self.client.table("master_annexes").insert(data).execute()
                if not res.data:
                    return False, "שגיאה בהוספת הנספח"
                annex_id = res.data[0]["id"]

            updated = self.resolve_pending_codes(annex_code, annex_id)
            return True, annex_id
        except Exception as e:
            print(f"[InsuranceClientDB] upsert_master_annex {annex_code}: {e}")
            return False, str(e)

    def get_profiles_without_policies(self, agent_id: str = "") -> list[dict]:
        """Returns profiles with no linked user_policies, optionally filtered by agent."""
        try:
            q = self.client.table("profiles").select("id, phone_number, full_name, created_at")
            if agent_id:
                q = q.eq("agent_id", agent_id)
            all_profiles = q.execute()
            if not all_profiles.data:
                return []
            result = []
            for profile in all_profiles.data:
                policies = (
                    self.client.table("user_policies")
                    .select("id")
                    .eq("user_id", profile["id"])
                    .limit(1)
                    .execute()
                )
                if not policies.data:
                    result.append(profile)
            return result
        except Exception as e:
            print(f"[InsuranceClientDB] get_profiles_without_policies: {e}")
            return []

    def link_annex_codes(self, user_id: str, annex_codes: list[str]) -> tuple[int, list[str]]:
        """Save all annex codes to user profile. Returns (saved_count, already_existed)."""
        saved = 0
        existed: list[str] = []
        for code in annex_codes:
            existing = (
                self.client.table("user_policies")
                .select("id")
                .eq("user_id", user_id)
                .eq("annex_code", code)
                .limit(1)
                .execute()
            )
            if existing.data:
                existed.append(code)
            else:
                self._save_annex_code(user_id, code)
                saved += 1
        return saved, existed

    # ── POLICIES ──────────────────────────────────────────────────────────────

    def get_user_policies(self, user_id: str) -> list[dict]:
        """Returns all annex codes for a user with availability flag."""
        try:
            res = (
                self.client.table("user_policies")
                .select("id, annex_code, annex_id, master_annexes(annex_code, annex_name, full_text, insurance_companies(name))")
                .eq("user_id", user_id)
                .execute()
            )
            if not res.data:
                return []
            result = []
            for row in res.data:
                annex = row.get("master_annexes") or {}
                code = annex.get("annex_code") or row.get("annex_code", "")
                has_data = bool(annex.get("full_text"))
                result.append({
                    "annex_code": code,
                    "annex_name": annex.get("annex_name", f"נספח {code}"),
                    "company": (annex.get("insurance_companies") or {}).get("name", ""),
                    "has_data": has_data,
                    "annex_id": row.get("annex_id"),
                })
            return result
        except Exception as e:
            print(f"[InsuranceClientDB] get_user_policies: {e}")
            return []

    # ── OTP ───────────────────────────────────────────────────────────────────

    @staticmethod
    def generate_otp() -> str:
        return str(random.randint(100000, 999999))

    # ── WHATSAPP ──────────────────────────────────────────────────────────────

    def _whatsapp(self, phone: str, message: str) -> bool:
        if not self._green_instance or not self._green_token:
            return False
        digits = re.sub(r"\D", "", phone)
        if digits.startswith("0"):
            digits = "972" + digits[1:]
        # Use instance-specific subdomain (e.g. 7107552876 → 7107.api.greenapi.com)
        subdomain = self._green_instance[:4]
        base = _load_secret("GREEN_API_URL") or f"https://{subdomain}.api.greenapi.com"
        url = f"{base}/waInstance{self._green_instance}/sendMessage/{self._green_token}"
        try:
            r = requests.post(
                url,
                json={"chatId": f"{digits}@c.us", "message": message},
                timeout=10,
            )
            return r.status_code == 200
        except Exception:
            return False

    def send_otp(self, phone: str, code: str) -> bool:
        return self._whatsapp(
            phone,
            f"BituachBot 🛡️\n\nקוד האימות שלך: *{code}*\n\nהקוד תקף ל-10 דקות.",
        )

    def send_no_pdf_notice(self, phone: str, name: str) -> bool:
        return self._whatsapp(
            phone,
            (
                f"שלום {name}! 👋\n\n"
                f"קיבלנו את פרטיך ב-BituachBot 🛡️\n\n"
                f"בקרוב אחד מהנציגים שלנו ייצור איתך קשר "
                f"כדי לעזור לך להעלות את קובץ הפוליסה.\n\n"
                f"תודה על הסבלנות! 🙏"
            ),
        )

    def send_ready(self, phone: str, name: str, annex_count: int) -> bool:
        return self._whatsapp(
            phone,
            (
                f"שלום {name}! 🎉\n\n"
                f"הרישום הושלם בהצלחה — מצאנו {annex_count} נספחים בפוליסה שלך.\n\n"
                f"הכל מוכן, מה תרצה לדעת? 😊\n\n"
                f"לדוגמה:\n"
                f'• "יש לי כיסוי לכירופרקטיקה?"\n'
                f'• "כמה ההשתתפות העצמית ב-MRI?"'
            ),
        )
