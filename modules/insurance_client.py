"""
InsuranceClientDB — Supabase client for BituachBot landing page.

Tables used:
  profiles         (id, phone_number, full_name, teudat_zehut)
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

    # ── PROFILES ──────────────────────────────────────────────────────────────

    def get_profile_by_phone(self, phone: str) -> dict | None:
        try:
            res = self.client.table("profiles").select("*").eq("phone_number", phone).limit(1).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[InsuranceClientDB] get_profile_by_phone: {e}")
            return None

    def register_user_with_policies(
        self, phone: str, name: str, annex_codes: list[str], tz: str
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

            try:
                res = self.client.table("profiles").insert(profile_data).execute()
            except Exception:
                profile_data.pop("teudat_zehut", None)
                res = self.client.table("profiles").insert(profile_data).execute()

            if not res.data:
                return False, "שגיאה ביצירת הפרופיל"

            user_id: str = res.data[0]["id"]

            # Link annex codes
            for code in annex_codes:
                try:
                    annex = (
                        self.client.table("master_annexes")
                        .select("id")
                        .eq("annex_code", code)
                        .limit(1)
                        .execute()
                    )
                    if annex.data:
                        self.client.table("user_policies").insert(
                            {"user_id": user_id, "annex_id": annex.data[0]["id"]}
                        ).execute()
                except Exception as e:
                    print(f"[InsuranceClientDB] linking annex {code}: {e}")

            return True, user_id

        except Exception as e:
            print(f"[InsuranceClientDB] register_user_with_policies: {e}")
            return False, f"שגיאה: {str(e)}"

    # ── POLICIES ──────────────────────────────────────────────────────────────

    def get_user_policies(self, user_id: str) -> list[dict]:
        """Returns list of annexed policies for a user with annex details."""
        try:
            res = (
                self.client.table("user_policies")
                .select("annex_id, master_annexes(annex_code, annex_name, insurance_companies(name))")
                .eq("user_id", user_id)
                .execute()
            )
            return res.data or []
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
        url = (
            f"https://api.green-api.com/waInstance{self._green_instance}"
            f"/sendMessage/{self._green_token}"
        )
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
