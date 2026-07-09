"""
Client GLPI — API REST v1
Gère l'authentification, la session, et la récupération des actifs personnalisés.
"""

import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class GLPIClient:
    def __init__(self, url: str, app_token: str, user_token: str):
        self.base_url = url.rstrip("/")
        self.api_url = f"{self.base_url}/apirest.php"
        self.app_token = app_token
        self.user_token = user_token
        self.session_token: Optional[str] = None
        self._asset_type_ids: dict = {}

    # ------------------------------------------------------------------ session

    def connect(self):
        """Ouvre une session GLPI et stocke le session_token."""
        resp = requests.get(
            f"{self.api_url}/initSession",
            headers={
                "App-Token": self.app_token,
                "Authorization": f"user_token {self.user_token}",
            },
        )
        resp.raise_for_status()
        self.session_token = resp.json()["session_token"]
        logger.info("Session GLPI ouverte")

    def disconnect(self):
        """Ferme proprement la session GLPI."""
        if not self.session_token:
            return
        requests.get(
            f"{self.api_url}/killSession",
            headers=self._headers(),
        )
        logger.info("Session GLPI fermée")
        self.session_token = None

    def _headers(self) -> dict:
        return {
            "App-Token": self.app_token,
            "Session-Token": self.session_token,
            "Content-Type": "application/json",
        }

    # -------------------------------------------------------- asset type lookup

    def get_asset_type_id(self, asset_name: str) -> int:
        """
        Résout le nom d'un actif personnalisé en son itemtype GLPI.
        GLPI 11 expose les actifs custom sous /CustomAsset/ ou via un type dédié.
        """
        if asset_name in self._asset_type_ids:
            return self._asset_type_ids[asset_name]

        resp = requests.get(
            f"{self.api_url}/listSearchOptions/CustomAsset",
            headers=self._headers(),
        )
        # En pratique, GLPI 11 génère un itemtype slug : CustomAsset_<id>
        # On recherche par le nom déclaré dans l'interface
        resp = requests.get(
            f"{self.api_url}/search/CustomAssetDefinition",
            params={"criteria[0][field]": "name",
                    "criteria[0][searchtype]": "equals",
                    "criteria[0][value]": asset_name},
            headers=self._headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("data"):
            raise ValueError(f"Actif personnalisé introuvable : {asset_name}")
        asset_id = data["data"][0]["id"]
        self._asset_type_ids[asset_name] = asset_id
        logger.debug(f"Actif '{asset_name}' → id={asset_id}")
        return asset_id

    # --------------------------------------------------------- generic fetch

    def get_custom_assets(
        self,
        asset_name: str,
        modified_since: Optional[str] = None,
    ) -> list[dict]:
        """
        Récupère tous les enregistrements d'un actif personnalisé.

        Args:
            asset_name:      Nom de l'actif (ex: "Serveur", "Flux")
            modified_since:  Date ISO 8601 — filtre delta (ex: "2024-01-01 00:00:00")

        Returns:
            Liste de dicts représentant chaque enregistrement
        """
        asset_id = self.get_asset_type_id(asset_name)
        itemtype = f"CustomAsset_{asset_id}"

        params = {
            "range": "0-500",
            "expand_dropdowns": 1,
            "with_infocoms": 0,
        }

        # Filtre delta : ne récupérer que les objets modifiés depuis la dernière synchro
        if modified_since:
            params.update({
                "criteria[0][field]": "date_mod",
                "criteria[0][searchtype]": "morethan",
                "criteria[0][value]": modified_since,
            })

        resp = requests.get(
            f"{self.api_url}/search/{itemtype}",
            headers=self._headers(),
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", [])
        logger.info(f"GLPI → {len(items)} '{asset_name}' récupérés")
        return items

    def get_custom_asset_by_id(self, asset_name: str, item_id: int) -> dict:
        """Récupère un enregistrement unique par son ID GLPI."""
        asset_id = self.get_asset_type_id(asset_name)
        itemtype = f"CustomAsset_{asset_id}"
        resp = requests.get(
            f"{self.api_url}/{itemtype}/{item_id}",
            headers=self._headers(),
            params={"expand_dropdowns": 1},
        )
        resp.raise_for_status()
        return resp.json()

    def update_custom_asset(self, asset_name: str, item_id: int, fields: dict):
        """
        Met à jour des champs d'un actif GLPI.
        Utilisé par le bridge pour écrire mercator_id et derniere_synchro.
        """
        asset_id = self.get_asset_type_id(asset_name)
        itemtype = f"CustomAsset_{asset_id}"
        resp = requests.put(
            f"{self.api_url}/{itemtype}/{item_id}",
            headers=self._headers(),
            json={"input": fields},
        )
        resp.raise_for_status()
        logger.debug(f"GLPI update {itemtype}/{item_id} : {list(fields.keys())}")
