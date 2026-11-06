# services/whatsapp/contacts.py — Local Verified Contact Registry
"""
Local SQLite & JSON backed Contact Registry for WhatsApp Messaging.
Guarantees:
- Deterministic, case-insensitive matching across display names and aliases.
- Ambiguity detection: Refuses to guess when multiple contacts match.
- Strict phone number validation & E.164 normalization via phonenumbers.
- Safe logging: Masks full numbers, only exposing last four digits.
- Never scrapes WhatsApp Web or invents phone numbers.
"""
import json
import logging
import re
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import phonenumbers  # type: ignore[import-not-found]
except ImportError:
    phonenumbers = None  # type: ignore[assignment]
from pydantic import ValidationError

from core.config import Config
from services.whatsapp.models import Contact

logger = Config.get_logger(__name__)


@dataclass
class ContactResolution:
    """Outcome of attempting to resolve a contact name from speech."""
    status: str  # "MATCHED", "AMBIGUOUS", "NOT_FOUND"
    contact: Optional[Contact] = None
    matches: Optional[List[Contact]] = None
    message: str = ""


class ContactRegistry:
    """
    Thread-safe local contact registry backed by SQLite with JSON seed capability.
    """

    def __init__(
        self,
        db_path: Optional[str | Path] = None,
        seed_json_path: Optional[str | Path] = None,
        default_region: str = "IN",
    ):
        if db_path is None:
            memory_dir = Path(Config.MEMORY_DIR)
            memory_dir.mkdir(parents=True, exist_ok=True)
            self._db_path = str(memory_dir / "son_structured.db")
        else:
            self._db_path = str(db_path)

        if seed_json_path is None:
            project_root = Path(__file__).parent.parent.parent
            self._seed_json_path = project_root / "config" / "contacts.json"
        else:
            self._seed_json_path = Path(seed_json_path)

        self._default_region = default_region
        self._lock = threading.RLock()
        self._init_table()
        self._seed_if_empty()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_table(self):
        """Create whatsapp_contacts table if not present."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS whatsapp_contacts (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL COLLATE NOCASE,
                    phone_number TEXT NOT NULL,
                    aliases_json TEXT NOT NULL DEFAULT '[]',
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_whatsapp_contacts_name 
                ON whatsapp_contacts(display_name)
            """)
            conn.commit()

    def _seed_if_empty(self):
        """Seed from local config/contacts.json if database is currently empty."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM whatsapp_contacts")
            count = cursor.fetchone()[0]
            if count > 0 or not self._seed_json_path.exists():
                return

            try:
                raw_data = json.loads(self._seed_json_path.read_text(encoding="utf-8"))
                for item in raw_data:
                    try:
                        self.add_contact(
                            display_name=item["display_name"],
                            phone_number=item["phone_number"],
                            aliases=item.get("aliases", []),
                            notes=item.get("notes", ""),
                            contact_id=item.get("id"),
                        )
                    except Exception as ex:
                        logger.warning(f"Failed to seed contact '{item.get('display_name')}': {ex}")
            except Exception as e:
                logger.error(f"Error reading seed contacts from {self._seed_json_path}: {e}")

    def normalize_phone_number(self, phone_raw: str, default_region: Optional[str] = None) -> str:
        """
        Validate and normalize a raw phone number into pure international digits without leading plus.
        Example: '+91 98765 41234' -> '919876541234'
        """
        region = default_region or self._default_region
        cleaned = phone_raw.strip()

        if phonenumbers is not None:
            try:
                if not cleaned.startswith("+") and region:
                    parsed = phonenumbers.parse(cleaned, region)
                else:
                    parsed = phonenumbers.parse(cleaned)

                if not phonenumbers.is_valid_number(parsed):
                    raise ValueError(f"Phone number '{phone_raw}' is not a valid recognized telephone number.")

                e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                # WhatsApp wa.me URLs require international digits WITHOUT the leading '+'
                return e164.lstrip("+")
            except phonenumbers.NumberParseException as e:
                raise ValueError(f"Could not parse phone number '{phone_raw}': {e}")
        else:
            digits = "".join(c for c in cleaned if c.isdigit())
            if len(digits) < 7 or len(digits) > 15:
                raise ValueError(f"Phone number '{phone_raw}' must contain between 7 and 15 digits.")
            return digits

    def add_contact(
        self,
        display_name: str,
        phone_number: str,
        aliases: Optional[List[str]] = None,
        notes: str = "",
        contact_id: Optional[str] = None,
    ) -> Contact:
        """
        Add a verified contact to the local registry.
        """
        display_name = display_name.strip()
        if not display_name:
            raise ValueError("Contact display name cannot be blank.")

        norm_phone = self.normalize_phone_number(phone_number)
        aliases_list = [a.strip().lower() for a in (aliases or []) if a.strip()]
        # Always ensure display name itself is included in search tokens
        if display_name.lower() not in aliases_list:
            aliases_list.append(display_name.lower())

        contact = Contact(
            id=contact_id or f"cnt_{display_name.lower().replace(' ', '_')[:12]}",
            display_name=display_name,
            phone_number=norm_phone,
            aliases=aliases_list,
            notes=notes,
        )

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO whatsapp_contacts (
                    id, display_name, phone_number, aliases_json, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                contact.id,
                contact.display_name,
                contact.phone_number,
                json.dumps(contact.aliases),
                contact.notes,
                contact.created_at,
                datetime.now(timezone.utc).isoformat(),
            ))
            conn.commit()

        logger.info(f"Registered contact '{contact.display_name}' ({contact.masked_phone})")
        return contact

    def remove_contact(self, contact_id_or_name: str) -> bool:
        """Remove a contact by ID or exact display name."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM whatsapp_contacts
                WHERE id = ? OR display_name = ? COLLATE NOCASE
            """, (contact_id_or_name, contact_id_or_name))
            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted

    def clear_all(self):
        """Remove all contacts from database (useful for isolated testing)."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM whatsapp_contacts")
            conn.commit()

    def get_contact_by_id(self, contact_id: str) -> Optional[Contact]:
        """Fetch contact by unique ID."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM whatsapp_contacts WHERE id = ?", (contact_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return Contact(
                id=row["id"],
                display_name=row["display_name"],
                phone_number=row["phone_number"],
                aliases=json.loads(row["aliases_json"]),
                notes=row["notes"] or "",
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def list_all_contacts(self) -> List[Contact]:
        """Retrieve all registered contacts."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM whatsapp_contacts ORDER BY display_name ASC")
            results = []
            for row in cursor.fetchall():
                results.append(Contact(
                    id=row["id"],
                    display_name=row["display_name"],
                    phone_number=row["phone_number"],
                    aliases=json.loads(row["aliases_json"]),
                    notes=row["notes"] or "",
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                ))
            return results

    def resolve_contact(self, query: str) -> ContactResolution:
        """
        Deterministic, safe contact matching with ambiguity detection.
        Matches exact display name, aliases, or distinct word boundaries.
        Never picks arbitrarily among multiple matching contacts.
        """
        q = query.strip().lower()
        if not q:
            return ContactResolution(status="NOT_FOUND", message="Recipient query was empty.")

        all_contacts = self.list_all_contacts()
        if not all_contacts:
            return ContactResolution(
                status="NOT_FOUND",
                message="No contacts are configured in your local address book. Say 'add contact' or configure contacts.json.",
            )

        # Collect all candidate matches (exact display name, alias, or token word match)
        candidates = []
        for c in all_contacts:
            # Check exact match on display name or alias
            is_exact = (c.display_name.lower() == q) or (q in [a.lower() for a in c.aliases])
            # Check constituent words
            name_words = re.findall(r"\w+", c.display_name.lower())
            alias_words = []
            for a in c.aliases:
                alias_words.extend(re.findall(r"\w+", a.lower()))
            is_token = (q in name_words) or (q in alias_words)

            if is_exact or is_token:
                candidates.append(c)

        # Deduplicate
        unique_matches = list({c.id: c for c in candidates}.values())

        if len(unique_matches) == 1:
            return ContactResolution(
                status="MATCHED",
                contact=unique_matches[0],
                message=f"Resolved to {unique_matches[0].display_name} ({unique_matches[0].masked_phone})",
            )
        elif len(unique_matches) > 1:
            details = ", ".join([f"{c.display_name} ({c.masked_phone})" for c in unique_matches])
            return ContactResolution(
                status="AMBIGUOUS",
                matches=unique_matches,
                message=f"I found multiple contacts matching '{query}': {details}. Which one would you like to message?",
            )

        return ContactResolution(
            status="NOT_FOUND",
            message=f"I couldn't find '{query}' in your local contacts. Please verify the name or add them to your contacts.",
        )
