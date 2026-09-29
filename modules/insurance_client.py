"""
InsuranceClientDB — Supabase client for BituachBot landing page.

Tables used:
  agents           (id, agent_code, full_name, admin_password [pbkdf2 hash], email)
  profiles         (id, phone_number, full_name, teudat_zehut, agent_id)
  master_annexes   (id, annex_code, annex_name, company_id, full_text)
  user_policies    (id, user_id, annex_id)
  insurance_companies (id, name)
"""

import base64
import hashlib
import hmac
import os
import random
import re
import secrets
from datetime import datetime, timedelta

import requests
from supabase import create_client, Client

from modules.hebrew_text import fix_visual_hebrew


# ── PASSWORD HASHING ─────────────────────────────────────────────────────────
_PBKDF2_ITER = 200_000


def hash_password(password: str) -> str:
    """Return 'pbkdf2$<iterations>$<salt_hex>$<hash_hex>'."""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITER)
    return f"pbkdf2${_PBKDF2_ITER}${salt.hex()}${dk.hex()}"


def is_hashed(stored: str | None) -> bool:
    return bool(stored) and stored.startswith("pbkdf2$")


def verify_password(password: str, stored: str | None) -> bool:
    """Check a password against a stored value (hashed, or legacy plain text)."""
    if not stored or not password:
        return False
    if not is_hashed(stored):
        return hmac.compare_digest(password, stored)
    try:
        _, iters, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


def _load_secret(key: str) -> str | None:
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val:
            return str(val).strip().strip('"').strip("'").strip()  # tolerate stray spaces/quotes from copy-paste
    except Exception:
        pass
    val = os.getenv(key)
    return val.strip() if val else val


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
                .select("id, agent_code, full_name, admin_password, email, phone_number")
                .eq("agent_code", code.upper())
                .limit(1)
                .execute()
            )
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[InsuranceClientDB] get_agent_by_code: {e}")
            return None

    def get_agent_by_id(self, agent_id: str) -> dict | None:
        if not agent_id:
            return None
        try:
            res = (
                self.client.table("agents")
                .select("id, agent_code, full_name, email, phone_number")
                .eq("id", agent_id)
                .limit(1)
                .execute()
            )
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[InsuranceClientDB] get_agent_by_id: {e}")
            return None

    def get_agent_by_email_and_password(self, email: str, password: str) -> dict | None:
        try:
            clean_email = email.strip().lower()
            # Fetch candidates case-insensitively using filter
            res = (
                self.client.table("agents")
                .select("id, agent_code, full_name, admin_password, email, phone_number")
                .filter("email", "ilike", clean_email)
                .limit(1)
                .execute()
            )
            if not res.data:
                return None
            agent = res.data[0]
            stored = agent.get("admin_password")
            if not verify_password(password, stored):
                return None
            if not is_hashed(stored):
                # Legacy plain-text password: upgrade it to a hash on successful login
                self.update_agent_password(agent["id"], password)
            return agent
        except Exception as e:
            print(f"[InsuranceClientDB] get_agent_by_email_and_password: {e}")
            return None

    def get_agent_by_phone(self, phone: str) -> dict | None:
        try:
            res = (
                self.client.table("agents")
                .select("id, agent_code, full_name, admin_password, email, phone_number")
                .eq("phone_number", phone)
                .limit(1)
                .execute()
            )
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[InsuranceClientDB] get_agent_by_phone: {e}")
            return None

    def update_agent_phone(self, agent_id: str, phone: str) -> bool:
        try:
            self.client.table("agents").update({"phone_number": phone}).eq("id", agent_id).execute()
            return True
        except Exception as e:
            print(f"[InsuranceClientDB] update_agent_phone: {e}")
            return False

    def update_agent_password(self, agent_id: str, new_password: str) -> bool:
        try:
            self.client.table("agents").update({"admin_password": hash_password(new_password)}).eq("id", agent_id).execute()
            return True
        except Exception as e:
            print(f"[InsuranceClientDB] update_agent_password: {e}")
            return False

    def update_agent_email(self, agent_id: str, email: str) -> bool:
        try:
            self.client.table("agents").update({"email": email.strip().lower()}).eq("id", agent_id).execute()
            return True
        except Exception as e:
            print(f"[InsuranceClientDB] update_agent_email: {e}")
            return False

    def update_profile(self, user_id: str, full_name: str, teudat_zehut: str) -> bool:
        try:
            data: dict = {}
            if full_name.strip():
                data["full_name"] = full_name.strip()
            if teudat_zehut.strip():
                data["teudat_zehut"] = teudat_zehut.strip()
            if not data:
                return True
            self.client.table("profiles").update(data).eq("id", user_id).execute()
            return True
        except Exception as e:
            print(f"[InsuranceClientDB] update_profile: {e}")
            return False

    def delete_profile(self, user_id: str) -> bool:
        """Delete a user's policies and profile (right to erasure)."""
        try:
            self.delete_client_documents(user_id)
            self.client.table("user_policies").delete().eq("user_id", user_id).execute()
            self.client.table("profiles").delete().eq("id", user_id).execute()
            return True
        except Exception as e:
            print(f"[InsuranceClientDB] delete_profile: {e}")
            return False

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
                {"admin_password": hash_password(new_password)}
            ).eq("id", agent["id"]).execute()
            return True
        except Exception as e:
            print(f"[InsuranceClientDB] reset_agent_password: {e}")
            return False

    def create_agent(self, agent_code: str, full_name: str, admin_password: str, email: str = "", phone: str = "") -> tuple[bool, str]:
        try:
            existing = self.get_agent_by_code(agent_code)
            if existing:
                return False, "agent_exists"
            res = self.client.table("agents").insert({
                "agent_code": agent_code.upper(),
                "full_name": full_name,
                "admin_password": hash_password(admin_password),
                "email": email,
                **({"phone_number": phone} if phone else {}),
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

    def get_profile_by_id(self, user_id: str) -> dict | None:
        if not user_id:
            return None
        try:
            res = self.client.table("profiles").select("*").eq("id", user_id).limit(1).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[InsuranceClientDB] get_profile_by_id: {e}")
            return None

    def assign_agent(self, user_id: str, agent_id: str) -> bool:
        """Link a client to an agent (used for 'claim client' and for clients choosing their agent)."""
        try:
            self.client.table("profiles").update({"agent_id": agent_id}).eq("id", user_id).execute()
            return True
        except Exception as e:
            print(f"[InsuranceClientDB] assign_agent: {e}")
            return False

    def update_profile_phone(self, user_id: str, phone: str) -> tuple[bool, str]:
        """Change a client's phone. Returns (False, 'phone_taken') if another profile uses it."""
        try:
            other = self.get_profile_by_phone(phone)
            if other and other.get("id") != user_id:
                return False, "phone_taken"
            self.client.table("profiles").update({"phone_number": phone}).eq("id", user_id).execute()
            return True, ""
        except Exception as e:
            print(f"[InsuranceClientDB] update_profile_phone: {e}")
            return False, str(e)

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

    def upsert_master_annex(self, annex_code: str, annex_name: str, full_text: str, company_id: str = None, alias_codes: list = None, version_year: int = None) -> tuple[bool, str]:
        """Add or update a nispaj in master_annexes by (annex_code, version_year). Returns (ok, annex_id)."""
        if version_year is None:
            version_year = datetime.now().year
        try:
            saved_id = self._upsert_single_annex(annex_code, annex_name, full_text, company_id, version_year)
            if not saved_id:
                return False, "שגיאה בהוספת הנספח"
            self.resolve_pending_codes(annex_code, saved_id)

            for alias in (alias_codes or []):
                alias = str(alias).strip()
                if not alias or alias == annex_code:
                    continue
                try:
                    alias_id = self._upsert_single_annex(alias, annex_name, full_text, company_id, version_year)
                    if alias_id:
                        self.resolve_pending_codes(alias, alias_id)
                except Exception as e:
                    print(f"[InsuranceClientDB] upsert alias {alias}: {e}")

            return True, saved_id
        except Exception as e:
            print(f"[InsuranceClientDB] upsert_master_annex {annex_code}: {e}")
            return False, str(e)

    def _upsert_single_annex(self, annex_code: str, annex_name: str, full_text: str, company_id: str | None, version_year: int) -> str | None:
        """Insert or update a single master_annexes row keyed by (annex_code, version_year)."""
        data = {"annex_code": annex_code, "annex_name": annex_name, "full_text": full_text, "version_year": version_year}
        if company_id:
            data["company_id"] = company_id
        existing = (
            self.client.table("master_annexes")
            .select("id")
            .eq("annex_code", annex_code)
            .eq("version_year", version_year)
            .limit(1)
            .execute()
        )
        if existing.data:
            annex_id = existing.data[0]["id"]
            self.client.table("master_annexes").update(data).eq("id", annex_id).execute()
            return annex_id
        else:
            res = self.client.table("master_annexes").insert(data).execute()
            return res.data[0]["id"] if res.data else None

    def repair_reversed_annexes(self) -> list[str]:
        """One-off repair: annex texts saved before the Hebrew-order fix were stored reversed
        ("חפסנ" instead of "נספח"), so the bot couldn't find words in them. Fixes them in place.
        Only rows detected as visual-order are touched. Returns the fixed annex codes."""
        fixed = []
        try:
            rows = self.client.table("master_annexes").select("id, annex_code, annex_name, full_text").execute().data or []
        except Exception as e:
            print(f"[InsuranceClientDB] repair_reversed_annexes: {e}")
            return fixed
        for r in rows:
            text = r.get("full_text") or ""
            new_text = fix_visual_hebrew(text)
            name = r.get("annex_name") or ""
            new_name = fix_visual_hebrew(name, min_words=1)
            if new_text == text and new_name == name:
                continue
            try:
                self.client.table("master_annexes").update(
                    {"full_text": new_text, "annex_name": new_name}
                ).eq("id", r["id"]).execute()
                fixed.append(r.get("annex_code", ""))
            except Exception as e:
                print(f"[InsuranceClientDB] repair annex {r.get('annex_code')}: {e}")
        return fixed

    def has_annex(self, annex_code: str) -> bool:
        try:
            res = self.client.table("master_annexes").select("id").eq("annex_code", annex_code).limit(1).execute()
            return bool(res.data)
        except Exception:
            return False

    def find_company_id(self, name: str) -> str | None:
        """Match an insurer name from a document to insurance_companies (never creates rows)."""
        key = re.sub(r'["״\'׳]', "", (name or "")).strip()
        if not key:
            return None
        try:
            rows = self.client.table("insurance_companies").select("id, name").execute().data or []
        except Exception:
            return None
        for r in rows:
            n = re.sub(r'["״\'׳]', "", (r.get("name") or "")).strip()
            if n and (n in key or key in n):
                return r["id"]
        return None

    def add_annex_document(self, codes: list, annex_name: str, full_text: str, version_year: int = None,
                           company: str = "", overwrite: bool = True) -> tuple[list[str], list[str]]:
        """Put one נספח document in the library under every code it covers (e.g. plan 5986 + chapter 6650).
        overwrite=False (client uploads) only fills codes the library doesn't have yet.
        Returns (saved_codes, skipped_codes)."""
        codes = [c for c in dict.fromkeys(str(c).strip() for c in (codes or [])) if re.fullmatch(r"\d{4,6}", c)]
        if not codes or not (full_text or "").strip():
            return [], codes
        skipped = [] if overwrite else [c for c in codes if self.has_annex(c)]
        todo = [c for c in codes if c not in skipped]
        if not todo:
            return [], skipped
        company_id = self.find_company_id(company) if company else None
        annex_name = fix_visual_hebrew((annex_name or "").strip(), min_words=1)
        full_text = fix_visual_hebrew(full_text)
        ok, _ = self.upsert_master_annex(
            todo[0], annex_name or f"נספח {todo[0]}", full_text,
            company_id=company_id, alias_codes=todo[1:], version_year=version_year,
        )
        return (todo, skipped) if ok else ([], skipped + todo)

    def get_annex_versions(self, annex_code: str) -> list[int]:
        """Return all saved years for a given annex_code, newest first."""
        try:
            res = (
                self.client.table("master_annexes")
                .select("version_year")
                .eq("annex_code", annex_code)
                .order("version_year", desc=True)
                .execute()
            )
            return [r["version_year"] for r in res.data if r.get("version_year")]
        except Exception:
            return []

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
                # Fallback: if annex_id is null, look up most recent version by annex_code
                if not annex and row.get("annex_code"):
                    try:
                        master = (
                            self.client.table("master_annexes")
                            .select("id, annex_code, annex_name, full_text, version_year, insurance_companies(name)")
                            .eq("annex_code", row["annex_code"])
                            .order("version_year", desc=True)
                            .limit(1)
                            .execute()
                        )
                        if master.data:
                            annex = master.data[0]
                            self.client.table("user_policies").update(
                                {"annex_id": annex["id"]}
                            ).eq("id", row["id"]).execute()
                    except Exception:
                        pass
                code = annex.get("annex_code") or row.get("annex_code", "")
                has_data = bool(annex.get("full_text"))
                result.append({
                    "annex_code": code,
                    "annex_name": annex.get("annex_name", f"נספח {code}"),
                    "company": (annex.get("insurance_companies") or {}).get("name", ""),
                    "has_data": has_data,
                    "annex_id": row.get("annex_id") or annex.get("id"),
                    "full_text": annex.get("full_text", ""),
                })
            return result
        except Exception as e:
            print(f"[InsuranceClientDB] get_user_policies: {e}")
            return []

    # ── AGENT DASHBOARD DATA ─────────────────────────────────────────────────

    def get_agent_clients(self, agent_id: str = "") -> list[dict]:
        """
        All clients of an agent (all clients when agent_id is empty), each with
        a status summary: ready / pending annex codes and uploaded documents.
        """
        try:
            q = self.client.table("profiles").select("id, full_name, phone_number, teudat_zehut, created_at, agent_id")
            if agent_id:
                q = q.eq("agent_id", agent_id)
            profiles = q.order("created_at", desc=True).execute().data or []
            if not profiles:
                return []
            ids = [p["id"] for p in profiles]
            rows = (
                self.client.table("user_policies")
                .select("user_id, annex_code, annex_id")
                .in_("user_id", ids)
                .execute()
                .data
                or []
            )
            self._link_known_codes(rows)
            by_user: dict[str, dict] = {pid: {"ready": [], "pending": []} for pid in ids}
            for r in rows:
                bucket = "ready" if r.get("annex_id") else "pending"
                by_user.setdefault(r["user_id"], {"ready": [], "pending": []})[bucket].append(r.get("annex_code", ""))
            result = []
            for p in profiles:
                st_ = by_user.get(p["id"], {"ready": [], "pending": []})
                docs = self.list_client_documents(p["id"])
                p = dict(p)
                p["ready_codes"] = sorted(set(st_["ready"]))
                p["pending_codes"] = sorted(set(st_["pending"]))
                p["doc_count"] = len(docs)
                p["status"] = self.client_status(p["ready_codes"], p["pending_codes"], len(docs))
                result.append(p)
            return result
        except Exception as e:
            print(f"[InsuranceClientDB] get_agent_clients: {e}")
            return []

    @staticmethod
    def client_status(ready: list, pending: list, doc_count: int) -> str:
        """One of: 'ready', 'partial', 'waiting_annex', 'empty'."""
        if not ready and not pending:
            return "empty"
        if ready and not pending:
            return "ready"
        if ready and pending:
            return "partial"
        return "waiting_annex"

    def _link_known_codes(self, rows: list[dict]) -> None:
        """For rows with annex_id NULL whose code now exists in master_annexes, link them (in place)."""
        missing = sorted({r["annex_code"] for r in rows if not r.get("annex_id") and r.get("annex_code")})
        if not missing:
            return
        try:
            masters = (
                self.client.table("master_annexes")
                .select("id, annex_code, version_year")
                .in_("annex_code", missing)
                .order("version_year", desc=True)
                .execute()
                .data
                or []
            )
            newest: dict[str, str] = {}
            for m in masters:
                newest.setdefault(m["annex_code"], m["id"])
            for code, annex_id in newest.items():
                self.resolve_pending_codes(code, annex_id)
            for r in rows:
                if not r.get("annex_id") and r.get("annex_code") in newest:
                    r["annex_id"] = newest[r["annex_code"]]
        except Exception as e:
            print(f"[InsuranceClientDB] _link_known_codes: {e}")

    def get_pending_annex_codes(self, agent_id: str = "") -> list[dict]:
        """Annex codes that clients have but that are missing from master_annexes.
        Returns [{annex_code, clients: [full_name, ...]}] sorted by number of clients."""
        try:
            q = self.client.table("profiles").select("id, full_name")
            if agent_id:
                q = q.eq("agent_id", agent_id)
            profiles = q.execute().data or []
            if not profiles:
                return []
            names = {p["id"]: p.get("full_name", "") for p in profiles}
            rows = (
                self.client.table("user_policies")
                .select("user_id, annex_code, annex_id")
                .in_("user_id", list(names))
                .is_("annex_id", "null")
                .execute()
                .data
                or []
            )
            self._link_known_codes(rows)
            pending: dict[str, set] = {}
            for r in rows:
                if not r.get("annex_id") and r.get("annex_code"):
                    pending.setdefault(r["annex_code"], set()).add(names.get(r["user_id"], ""))
            return sorted(
                ({"annex_code": c, "clients": sorted(n)} for c, n in pending.items()),
                key=lambda x: (-len(x["clients"]), x["annex_code"]),
            )
        except Exception as e:
            print(f"[InsuranceClientDB] get_pending_annex_codes: {e}")
            return []

    # ── CLIENT DOCUMENTS (Supabase Storage) ─────────────────────────────────

    DOCS_BUCKET = "client-documents"
    _bucket_checked = False

    def _ensure_docs_bucket(self) -> None:
        if InsuranceClientDB._bucket_checked:
            return
        try:
            self.client.storage.get_bucket(self.DOCS_BUCKET)
        except Exception:
            try:
                self.client.storage.create_bucket(self.DOCS_BUCKET, options={"public": False})
            except Exception as e:
                print(f"[InsuranceClientDB] create bucket {self.DOCS_BUCKET}: {e}")
        InsuranceClientDB._bucket_checked = True

    @staticmethod
    def _encode_filename(name: str) -> str:
        """Storage keys must be ASCII — keep the original (e.g. Hebrew) name as base64url."""
        name = (name or "document.pdf")[-120:]
        return base64.urlsafe_b64encode(name.encode()).decode().rstrip("=")

    @staticmethod
    def _decode_filename(enc: str) -> str:
        try:
            return base64.urlsafe_b64decode(enc + "=" * (-len(enc) % 4)).decode()
        except Exception:
            return enc

    def upload_client_document(self, user_id: str, filename: str, data: bytes, uploaded_by: str = "client") -> bool:
        """Store the original file under client-documents/<user_id>/. uploaded_by: 'client' | 'agent' | 'bot'."""
        if not user_id or not data:
            return False
        self._ensure_docs_bucket()
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = f"{user_id}/{ts}__{uploaded_by}__{self._encode_filename(filename)}"
        try:
            self.client.storage.from_(self.DOCS_BUCKET).upload(
                path, data, {"content-type": "application/pdf", "upsert": "true"}
            )
            return True
        except Exception as e:
            print(f"[InsuranceClientDB] upload_client_document: {e}")
            return False

    def list_client_documents(self, user_id: str) -> list[dict]:
        """[{path, name, uploaded_by, uploaded_at}] newest first."""
        if not user_id:
            return []
        try:
            items = self.client.storage.from_(self.DOCS_BUCKET).list(
                user_id, {"limit": 100, "sortBy": {"column": "name", "order": "desc"}}
            ) or []
        except Exception:
            return []
        docs = []
        for it in items:
            name = it.get("name", "")
            if not name or name.startswith("."):
                continue
            parts = name.split("__", 2)
            ts, who, fname = (parts + ["", "", ""])[:3] if len(parts) == 3 else ("", "", name)
            try:
                when = datetime.strptime(ts, "%Y%m%d-%H%M%S").strftime("%d/%m/%Y %H:%M")
            except ValueError:
                when = ""
            docs.append({"path": f"{user_id}/{name}", "name": self._decode_filename(fname) if fname else name, "uploaded_by": who, "uploaded_at": when})
        return docs

    def download_client_document(self, path: str) -> bytes | None:
        try:
            return self.client.storage.from_(self.DOCS_BUCKET).download(path)
        except Exception as e:
            print(f"[InsuranceClientDB] download_client_document: {e}")
            return None

    def delete_client_documents(self, user_id: str) -> None:
        paths = [d["path"] for d in self.list_client_documents(user_id)]
        if not paths:
            return
        try:
            self.client.storage.from_(self.DOCS_BUCKET).remove(paths)
        except Exception as e:
            print(f"[InsuranceClientDB] delete_client_documents: {e}")

    def document_url(self, path: str, expires_in: int = 3600) -> str | None:
        try:
            res = self.client.storage.from_(self.DOCS_BUCKET).create_signed_url(path, expires_in)
            return res.get("signedURL") or res.get("signedUrl")
        except Exception as e:
            print(f"[InsuranceClientDB] document_url: {e}")
            return None

    # ── OTP ───────────────────────────────────────────────────────────────────

    @staticmethod
    def generate_otp() -> str:
        return str(random.randint(100000, 999999))

    # ── WHATSAPP ──────────────────────────────────────────────────────────────

    last_whatsapp_error = ""

    @staticmethod
    def _green_error_he(status: int, body: str) -> str:
        body = (body or "").strip()[:160]
        if status in (401, 403):
            return f"Green API דחה את הבקשה ({status}) — הטוקן או מספר ה-instance ב-Secrets שגויים."
        if status == 404:
            return "Green API: הכתובת לא נמצאה (404) — בדוק את GREEN_API_URL / GREEN_API_INSTANCE ב-Secrets."
        if status == 466:
            return ("Green API: נגמרה המכסה של החבילה (466). בחבילה החינמית (Developer) אפשר לשלוח רק למספר "
                    "מצומצם של מספרים בחודש — צריך לשדרג את ה-instance.")
        if status == 429:
            return "Green API: יותר מדי בקשות (429) — נסה שוב בעוד דקה."
        return f"Green API החזיר שגיאה {status}: {body}"

    def _whatsapp(self, phone: str, message: str) -> bool:
        """Send a WhatsApp message via Green API. On failure, the reason is in self.last_whatsapp_error."""
        if not self._green_instance or not self._green_token:
            self.last_whatsapp_error = "GREEN_API_INSTANCE / GREEN_API_TOKEN לא מוגדרים ב-Secrets."
            return False
        digits = re.sub(r"\D", "", phone)
        if digits.startswith("0"):
            digits = "972" + digits[1:]
        # Use instance-specific subdomain (e.g. 7107552876 → 7107.api.greenapi.com)
        subdomain = self._green_instance[:4]
        base = (_load_secret("GREEN_API_URL") or f"https://{subdomain}.api.greenapi.com").rstrip("/")
        url = f"{base}/waInstance{self._green_instance}/sendMessage/{self._green_token}"
        try:
            r = requests.post(
                url,
                json={"chatId": f"{digits}@c.us", "message": message},
                timeout=10,
            )
        except Exception as e:
            self.last_whatsapp_error = f"אין חיבור ל-Green API ({type(e).__name__}) — בדוק את GREEN_API_URL."
            print(f"[InsuranceClientDB] _whatsapp: {e}")
            return False
        if r.status_code == 200:
            self.last_whatsapp_error = ""
            return True
        self.last_whatsapp_error = self._green_error_he(r.status_code, r.text)
        print(f"[InsuranceClientDB] _whatsapp {r.status_code}: {r.text[:300]}")
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


    # ── AGENT NOTIFICATIONS ─────────────────────────────────────────────────

    def _client_summary_lines(self, ready: list, pending: list, doc_count: int) -> list[str]:
        lines = []
        if ready:
            lines.append(f"✅ נספחים מוכנים ({len(ready)}): {', '.join(ready)}")
        if pending:
            lines.append(f"⏳ נספחים שחסרים במאגר ({len(pending)}): {', '.join(pending)} — יש להעלות אותם בפאנל")
        lines.append(f"📄 מסמכים שהועלו: {doc_count}")
        if not ready and not pending:
            lines.append("\n⚠️ הלקוח לא העלה פוליסה — צור איתו קשר כדי לקבל את קובץ הפוליסה.")
        elif pending and not ready:
            lines.append("\n⚠️ הבוט עדיין לא יכול לענות ללקוח — חסרים הנספחים במאגר.")
        elif pending:
            lines.append("\nℹ️ הבוט עונה על חלק מהנספחים. השלם את הנספחים החסרים.")
        else:
            lines.append("\n👍 הכל מוכן — הבוט יכול לענות ללקוח.")
        return lines

    def notify_agent_new_client(self, agent_id: str, user_id: str) -> bool:
        """WhatsApp the agent: a new client registered through their link + what is missing."""
        agent = self.get_agent_by_id(agent_id)
        if not agent or not agent.get("phone_number"):
            return False
        status = self._client_snapshot(user_id)
        if not status:
            return False
        msg = [
            "BituachBot 🛡️ — לקוח חדש נרשם!",
            "",
            f"👤 {status['full_name']}",
            f"📱 {status['phone_number']}",
            "",
            *self._client_summary_lines(status["ready"], status["pending"], status["doc_count"]),
        ]
        return self._whatsapp(agent["phone_number"], "\n".join(msg))

    def notify_agent_client_upload(self, agent_id: str, user_id: str, new_codes: list[str],
                                   library_codes: list[str] = None) -> bool:
        """WhatsApp the agent when a client uploads a new document themselves."""
        agent = self.get_agent_by_id(agent_id)
        if not agent or not agent.get("phone_number"):
            return False
        status = self._client_snapshot(user_id)
        if not status:
            return False
        msg = [
            "BituachBot 🛡️ — הלקוח העלה מסמך חדש",
            "",
            f"👤 {status['full_name']} ({status['phone_number']})",
            f"🆕 קודים שזוהו: {', '.join(new_codes) if new_codes else 'לא זוהו קודי נספחים'}",
        ]
        if library_codes:
            msg.append(f"📚 המסמך הוא נספח ונוסף למאגר: {', '.join(library_codes)} — כדאי לוודא שזה הנוסח הנכון")
        msg += [
            "",
            *self._client_summary_lines(status["ready"], status["pending"], status["doc_count"]),
        ]
        return self._whatsapp(agent["phone_number"], "\n".join(msg))

    def _client_snapshot(self, user_id: str) -> dict | None:
        try:
            prof = self.client.table("profiles").select("id, full_name, phone_number").eq("id", user_id).limit(1).execute()
            if not prof.data:
                return None
            rows = self.client.table("user_policies").select("user_id, annex_code, annex_id").eq("user_id", user_id).execute().data or []
            self._link_known_codes(rows)
            ready = sorted({r["annex_code"] for r in rows if r.get("annex_id")})
            pending = sorted({r["annex_code"] for r in rows if not r.get("annex_id")})
            return {
                "full_name": prof.data[0].get("full_name", ""),
                "phone_number": prof.data[0].get("phone_number", ""),
                "ready": ready,
                "pending": pending,
                "doc_count": len(self.list_client_documents(user_id)),
            }
        except Exception as e:
            print(f"[InsuranceClientDB] _client_snapshot: {e}")
            return None

    def send_welcome_from_agent(self, phone: str, name: str, agent_name: str, login_url: str = "") -> bool:
        """Sent from the bot number when an agent creates a client — the client saves this number."""
        lines = [
            f"שלום {name}! 👋",
            "",
            f"הסוכן שלך, {agent_name}, רשם אותך ל-BituachBot 🛡️ — עוזר הביטוח החכם שלך בוואטסאפ.",
            "",
            "שמור את המספר הזה ושלח כאן כל שאלה על הביטוח שלך, למשל:",
            '• "יש לי כיסוי לפיזיותרפיה?"',
            '• "כמה ההשתתפות העצמית ב-MRI?"',
        ]
        if login_url:
            lines += ["", f"לאזור האישי שלך (פוליסות, נספחים ומסמכים): {login_url}"]
        return self._whatsapp(phone, "\n".join(lines))
