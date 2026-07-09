"""
Mapper Flux
Transforme un enregistrement GLPI "Flux" en payload Mercator.

Selon type_flux :
  - "applicatif" → /api/fluxes        (vue Application)
  - "réseau"     → /api/logical-flows (vue Infrastructure logique)
"""

import logging
from typing import Optional
from src.mercator.client import MercatorClient

logger = logging.getLogger(__name__)

NATURE_MAP = {
    "données":       "data",
    "événement":     "event",
    "fichier":       "file",
    "api rest":      "api",
    "message queue": "queue",
    "autre":         "other",
}

PROTOCOLE_MAP = {
    "TCP":   "TCP",
    "UDP":   "UDP",
    "ICMP":  "ICMP",
    "HTTPS": "HTTPS",
    "autre": "other",
}


class FluxMapper:
    def __init__(self, mercator: MercatorClient):
        self.mercator = mercator
        # Cache applications Mercator : nom → id
        self._apps_cache: dict = {}

    # ---------------------------------------------------- routing

    def get_endpoint(self, item: dict) -> str:
        """Retourne l'endpoint Mercator cible selon type_flux."""
        type_flux = item.get("type_flux", "").lower()
        if type_flux == "réseau":
            return "logical-flows"
        return "fluxes"

    def to_mercator(self, item: dict) -> Optional[dict]:
        """
        Point d'entrée unique : retourne le payload adapté selon type_flux.
        Retourne None si le flux ne peut pas être mappé (données manquantes).
        """
        type_flux = item.get("type_flux", "").lower()
        if type_flux == "réseau":
            return self._to_logical_flow(item)
        return self._to_application_flux(item)

    # ------------------------------------------- flux applicatif

    def _to_application_flux(self, item: dict) -> Optional[dict]:
        """Payload pour /api/fluxes."""
        src_name  = item.get("application_source")
        dest_name = item.get("application_dest")

        if not src_name or not dest_name:
            logger.warning(
                f"Flux applicatif GLPI id={item.get('id')} ignoré : "
                "application_source ou application_dest manquant"
            )
            return None

        src_id  = self._resolve_application_id(src_name)
        dest_id = self._resolve_application_id(dest_name)

        if not src_id or not dest_id:
            logger.warning(
                f"Flux applicatif GLPI id={item.get('id')} ignoré : "
                f"application '{src_name}' ou '{dest_name}' introuvable dans Mercator"
            )
            return None

        nature_raw = item.get("nature", "").lower()
        payload = {
            "name":        item.get("name", f"{src_name} → {dest_name}"),
            "description": item.get("description", ""),
            "source_id":   src_id,
            "dest_id":     dest_id,
            "nature":      NATURE_MAP.get(nature_raw, nature_raw),
            "encrypt":     bool(item.get("chiffrement")),
        }
        return self._clean(payload)

    # ---------------------------------------------- flux réseau

    def _to_logical_flow(self, item: dict) -> Optional[dict]:
        """Payload pour /api/logical-flows."""
        # Résolution IP : champ explicite > IP principale du serveur lié
        ip_src  = item.get("ip_source")  or self._ip_from_server(item.get("serveur_source"))
        ip_dest = item.get("ip_dest")    or self._ip_from_server(item.get("serveur_dest"))

        if not ip_src or not ip_dest:
            logger.warning(
                f"Flux réseau GLPI id={item.get('id')} ignoré : "
                "ip_source ou ip_dest non résolvable"
            )
            return None

        protocole_raw = item.get("protocole", "TCP")
        payload = {
            "name":        item.get("name", f"{ip_src} → {ip_dest}"),
            "description": item.get("description", ""),
            "source":      ip_src,
            "destination": ip_dest,
            "protocol":    PROTOCOLE_MAP.get(protocole_raw, protocole_raw),
            "port":        item.get("port_dest"),
            "direction":   item.get("sens", ""),
        }
        return self._clean(payload)

    # ------------------------------------------------------ helpers

    def _resolve_application_id(self, app_name: str) -> Optional[int]:
        """Résout un nom d'application Mercator en ID, avec cache."""
        if not self._apps_cache:
            apps = self.mercator.get_all("applications")
            self._apps_cache = {a["name"]: a["id"] for a in apps}
            logger.debug(f"Cache applications chargé : {len(self._apps_cache)} entrées")
        app_id = self._apps_cache.get(app_name)
        if not app_id:
            logger.warning(f"Application '{app_name}' introuvable dans Mercator")
        return app_id

    def _ip_from_server(self, server_item) -> Optional[str]:
        """
        Extrait l'adresse IP depuis un item serveur GLPI lié.
        server_item peut être un dict (objet complet) ou une str (nom).
        """
        if isinstance(server_item, dict):
            return server_item.get("adresse_ip")
        # Si c'est juste un nom, on ne peut pas résoudre sans appel GLPI
        logger.debug(f"Impossible de résoudre l'IP depuis '{server_item}' (pas d'objet complet)")
        return None

    def _clean(self, payload: dict) -> dict:
        return {k: v for k, v in payload.items() if v is not None and v != ""}
