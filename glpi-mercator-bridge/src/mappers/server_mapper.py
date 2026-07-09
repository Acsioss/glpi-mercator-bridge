"""
Mapper Serveur
Transforme un enregistrement GLPI "Serveur" en payload(s) Mercator.

Selon type_serveur :
  - "physique"        → physical_server payload uniquement
  - "virtuel/logique" → logical_server payload uniquement
  - "les deux"        → les deux payloads
"""

import logging
from typing import Optional
from src.mercator.client import MercatorClient

logger = logging.getLogger(__name__)

# Correspondance statut GLPI → booléen active Mercator
STATUT_TO_ACTIVE = {
    "production":     True,
    "recette":        True,
    "développement":  False,
    "test":           False,
    "décommissionné": False,
}


class ServerMapper:
    def __init__(self, mercator: MercatorClient):
        self.mercator = mercator

    # ---------------------------------------------------- payload builders

    def to_physical_server(self, item: dict) -> dict:
        """Construit le payload pour /api/physical-servers."""
        payload = {
            "name":        item.get("name", ""),
            "description": item.get("description", ""),
            "ip_address":  item.get("adresse_ip", ""),
            "cpu":         item.get("cpu", ""),
            "memory":      item.get("memoire_go"),
            "disk":        item.get("disque_go"),
            "os":          self._os_string(item),
            "install_date": item.get("date_installation"),
        }

        # Résolution site → id Mercator
        site_name = item.get("site")
        if site_name:
            site_id = self.mercator.resolve_site_id(site_name)
            if site_id:
                payload["site_id"] = site_id

        # Résolution baie → id Mercator
        bay_name = item.get("baie")
        if bay_name:
            bay_id = self.mercator.resolve_bay_id(bay_name)
            if bay_id:
                payload["bay_id"] = bay_id

        return self._clean(payload)

    def to_logical_server(self, item: dict, physical_mercator_id: Optional[int] = None) -> dict:
        """Construit le payload pour /api/logical-servers."""
        statut = item.get("statut", "").lower()
        payload = {
            "name":             item.get("name", ""),
            "description":      item.get("description", ""),
            "ip_address":       item.get("adresse_ip", ""),
            "cpu":              item.get("cpu", ""),
            "memory":           item.get("memoire_go"),
            "disk":             item.get("disque_go"),
            "os":               self._os_string(item),
            "environment":      item.get("environnement", ""),
            "network_services": item.get("services_reseau", ""),
            "active":           STATUT_TO_ACTIVE.get(statut, True),
            "install_date":     item.get("date_installation"),
        }

        # Lien vers le serveur physique hôte
        # Priorité 1 : champ serveur_physique_hote (lien vers actif GLPI)
        # Priorité 2 : physical_mercator_id passé directement (cas "les deux")
        if physical_mercator_id:
            payload["physicalServers"] = [physical_mercator_id]
        elif item.get("mercator_id_physique"):
            payload["physicalServers"] = [item["mercator_id_physique"]]

        return self._clean(payload)

    # ------------------------------------------------------ helpers

    def _os_string(self, item: dict) -> str:
        """Concatène os et version_os si les deux sont présents."""
        os_name = item.get("os", "")
        os_ver  = item.get("version_os", "")
        if os_name and os_ver and os_ver not in os_name:
            return f"{os_name} {os_ver}"
        return os_name or os_ver

    def _clean(self, payload: dict) -> dict:
        """Supprime les valeurs None pour ne pas écraser des données existantes."""
        return {k: v for k, v in payload.items() if v is not None}
