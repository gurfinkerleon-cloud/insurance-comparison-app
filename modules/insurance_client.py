"""
Insurance Client Portal - Supabase Module
Handles operations for: profiles, user_policies, master_annexes, insurance_companies

Required env vars:
  SUPABASE_URL          - e.g. https://xqbkkvqtdezyhthdlhv.supabase.co
  SUPABASE_SERVICE_KEY  - Service Role key (starts with eyJ...)
"""

import os
from typing import Optional, List, Dict, Tuple
from supabase import create_client, Client


class InsuranceClientDB:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        # Accept either env var name
        self.key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

        if not self.url or not self.key:
            raise ValueError(
                "Missing env vars. Set SUPABASE_URL and SUPABASE_SERVICE_KEY."
            )

        self.client: Client = create_client(self.url, self.key)

    # ── PROFILES ──────────────────────────────────────────────────────────────

    def get_profile_by_phone(self, phone: str) -> Optional[Dict]:
        """Return the profiles row for a given phone number, or None."""
        result = (
            self.client.table("profiles")
            .select("id, full_name, phone_number")
            .eq("phone_number", phone)
            .execute()
        )
        return result.data[0] if result.data else None

    # ── REGISTRATION RPC ──────────────────────────────────────────────────────

    def register_user_with_policies(
        self, phone: str, full_name: str, codes: List[str]
    ) -> Tuple[bool, str]:
        """
        Upsert the client profile and link all annex codes via the
        register_user_with_policies Postgres function.

        Returns (success: bool, message: str).
        """
        try:
            self.client.rpc(
                "register_user_with_policies",
                {"p_phone": phone, "p_full_name": full_name, "p_codes": codes},
            ).execute()
            return True, "הרישום הושלם בהצלחה!"
        except Exception as e:
            return False, f"שגיאה ברישום: {str(e)}"

    # ── USER ANNEX DETAILS ────────────────────────────────────────────────────

    def get_user_annexes(self, phone: str) -> List[Dict]:
        """
        Return all master_annexes rows linked to a client (identified by phone).
        Each row is enriched with the company name.

        Tries the SQL view v_detalles_seguro_cliente first; falls back to
        a manual join if the view does not exist yet.
        """
        # --- attempt view ---
        try:
            result = (
                self.client.table("v_detalles_seguro_cliente")
                .select("annex_name, full_text, phone_number, full_name")
                .eq("phone_number", phone)
                .execute()
            )
            if result.data:
                return result.data
        except Exception:
            pass  # view not created yet — fall through to manual join

        # --- manual join fallback ---
        profile = self.get_profile_by_phone(phone)
        if not profile:
            return []

        up_rows = (
            self.client.table("user_policies")
            .select("annex_id")
            .eq("user_id", profile["id"])
            .execute()
        )
        if not up_rows.data:
            return []

        annexes: List[Dict] = []
        companies_cache: Dict[str, str] = {}

        for row in up_rows.data:
            annex_id = row["annex_id"]
            annex_result = (
                self.client.table("master_annexes")
                .select("id, annex_code, annex_name, full_text, company_id")
                .eq("id", annex_id)
                .execute()
            )
            if not annex_result.data:
                continue

            annex = dict(annex_result.data[0])

            # Resolve company name with a tiny cache
            company_id = annex.get("company_id")
            if company_id and company_id not in companies_cache:
                comp = (
                    self.client.table("insurance_companies")
                    .select("name")
                    .eq("id", company_id)
                    .execute()
                )
                companies_cache[company_id] = (
                    comp.data[0]["name"] if comp.data else "לא ידוע"
                )
            annex["company_name"] = companies_cache.get(company_id, "לא ידוע")
            annexes.append(annex)

        return annexes

    # ── MASTER ANNEXES LIBRARY ────────────────────────────────────────────────

    def get_annex_by_code(self, annex_code: str) -> Optional[Dict]:
        """Fetch a single annex from the master library by its code."""
        result = (
            self.client.table("master_annexes")
            .select("id, annex_code, annex_name, full_text, company_id")
            .eq("annex_code", annex_code)
            .execute()
        )
        return result.data[0] if result.data else None

    def get_annexes_for_codes(self, codes: List[str]) -> List[Dict]:
        """Fetch master_annexes rows for a list of annex codes."""
        if not codes:
            return []
        result = (
            self.client.table("master_annexes")
            .select("id, annex_code, annex_name, full_text, company_id")
            .in_("annex_code", codes)
            .execute()
        )
        return result.data or []

    # ── COMPANIES ─────────────────────────────────────────────────────────────

    def get_all_companies(self) -> List[Dict]:
        """Return all rows from insurance_companies."""
        result = self.client.table("insurance_companies").select("id, name").execute()
        return result.data or []
