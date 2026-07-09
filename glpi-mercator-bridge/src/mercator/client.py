"""
Client Mercator — API REST (Laravel Passport / OAuth2)
Gère l'authentification par token et toutes les opérations CRUD.
"""

import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class MercatorClient:
    def __init__(self, url: str, email: str, password: str):
        self.base_url = url.rstrip("/")
        self.api_url = f"{self.base_url}/api"
        self.email = email
        self.password = password
        self.token: Optional[str] = None
        # Cache local : nom_site → id_mercator  (évite les GET répétés)
        self._sites_cache: dict = {}

    # ------------------------------------------------------------------ auth

    def connect(self):
        """Authentification OAuth2 — récupère le Bearer token."""
        resp = requests.post(
            f"{self.base_url}/api/login",
            json={"email": self.email, "password": self.password},
        )
        resp.raise_for_status()
        self.token = resp.json()["access_token"]
        logger.info("Authentification Mercator réussie")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # --------------------------------------------------------- generic CRUD

    def get_all(self, endpoint: str) -> list[dict]:
        resp = requests.get(
            f"{self.api_url}/{endpoint}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def get_by_id(self, endpoint: str, obj_id: int) -> dict:
        resp = requests.get(
            f"{self.api_url}/{endpoint}/{obj_id}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def create(self, endpoint: str, payload: dict) -> dict:
        """POST — crée un objet et retourne la réponse complète avec l'id."""
        resp = requests.post(
            f"{self.api_url}/{endpoint}",
            headers=self._headers(),
            json=payload,
        )
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"Mercator CREATE /{endpoint} → id={result.get('id')}")
        return result

    def update(self, endpoint: str, obj_id: int, payload: dict) -> dict:
        """PUT — met à jour un objet existant."""
        resp = requests.put(
            f"{self.api_url}/{endpoint}/{obj_id}",
            headers=self._headers(),
            json=payload,
        )
        resp.raise_for_status()
        logger.info(f"Mercator UPDATE /{endpoint}/{obj_id}")
        return resp.json()

    def upsert(self, endpoint: str, mercator_id: Optional[int], payload: dict) -> dict:
        """
        Crée ou met à jour selon la présence d'un mercator_id.
        Retourne toujours l'objet Mercator résultant.
        """
        if mercator_id:
            return self.update(endpoint, mercator_id, payload)
        return self.create(endpoint, payload)

    # ---------------------------------------------------- résolution de sites

    def resolve_site_id(self, site_name: str) -> Optional[int]:
        """
        Résout un nom de site en ID Mercator.
        Met en cache le résultat pour éviter des appels répétés.
        """
        if not self._sites_cache:
            sites = self.get_all("sites")
            self._sites_cache = {s["name"]: s["id"] for s in sites}
            logger.debug(f"Cache sites chargé : {len(self._sites_cache)} entrées")

        site_id = self._sites_cache.get(site_name)
        if not site_id:
            logger.warning(f"Site '{site_name}' introuvable dans Mercator")
        return site_id

    def resolve_bay_id(self, bay_name: str) -> Optional[int]:
        """Résout un nom de baie en ID Mercator (même logique que les sites)."""
        bays = self.get_all("bays")
        for bay in bays:
            if bay["name"] == bay_name:
                return bay["id"]
        logger.warning(f"Baie '{bay_name}' introuvable dans Mercator")
        return None
