"""
Synchroniseur Serveurs
Orchestre la lecture GLPI, la transformation, et l'écriture dans Mercator
pour les actifs de type "Serveur".
"""

import logging
from datetime import datetime
from src.glpi.client import GLPIClient
from src.mercator.client import MercatorClient
from src.mappers.server_mapper import ServerMapper

logger = logging.getLogger(__name__)

EXCLUDED_STATUSES = {"décommissionné"}


class ServerSync:
    def __init__(self, glpi: GLPIClient, mercator: MercatorClient, config: dict):
        self.glpi = glpi
        self.mercator = mercator
        self.mapper = ServerMapper(mercator)
        self.asset_name = config["glpi"]["asset_type_serveur"]
        self.delta_only = config["sync"]["delta_only"]

    def run(self, last_sync: str = None) -> dict:
        """
        Lance la synchronisation des serveurs.

        Args:
            last_sync: Horodatage ISO de la dernière synchro (mode delta)

        Returns:
            Rapport : {"created": n, "updated": n, "skipped": n, "errors": n}
        """
        modified_since = last_sync if self.delta_only else None
        items = self.glpi.get_custom_assets(self.asset_name, modified_since)

        report = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

        for item in items:
            try:
                self._sync_one(item, report)
            except Exception as e:
                logger.error(f"Erreur serveur GLPI id={item.get('id')} : {e}")
                report["errors"] += 1

        logger.info(
            f"Serveurs — créés:{report['created']} "
            f"màj:{report['updated']} "
            f"ignorés:{report['skipped']} "
            f"erreurs:{report['errors']}"
        )
        return report

    # ---------------------------------------------------------- private

    def _sync_one(self, item: dict, report: dict):
        """Traite un seul serveur GLPI."""
        glpi_id   = item["id"]
        type_srv  = item.get("type_serveur", "").lower()
        statut    = item.get("statut", "").lower()

        # Ignorer les décommissionnés
        if statut in EXCLUDED_STATUSES:
            logger.debug(f"Serveur GLPI id={glpi_id} ignoré (statut={statut})")
            report["skipped"] += 1
            return

        fields_to_write_back = {}  # champs à réécrire dans GLPI après synchro

        # --- Serveur physique ---
        if type_srv in ("physique", "les deux"):
            payload     = self.mapper.to_physical_server(item)
            mercator_id = item.get("mercator_id_physique")
            result      = self.mercator.upsert("physical-servers", mercator_id, payload)

            new_id = result.get("id")
            if not mercator_id and new_id:
                fields_to_write_back["mercator_id_physique"] = new_id
                report["created"] += 1
            else:
                report["updated"] += 1

            # Conserver l'id pour le lien logical → physical ci-dessous
            physical_mercator_id = new_id or mercator_id
        else:
            physical_mercator_id = item.get("mercator_id_physique")

        # --- Serveur logique ---
        if type_srv in ("virtuel / logique", "logique", "virtuel", "les deux"):
            payload     = self.mapper.to_logical_server(item, physical_mercator_id)
            mercator_id = item.get("mercator_id_logique")
            result      = self.mercator.upsert("logical-servers", mercator_id, payload)

            new_id = result.get("id")
            if not mercator_id and new_id:
                fields_to_write_back["mercator_id_logique"] = new_id
                report["created"] += 1
            else:
                report["updated"] += 1

        # --- Écriture en retour dans GLPI ---
        if fields_to_write_back:
            fields_to_write_back["derniere_synchro"] = datetime.now().isoformat(
                sep=" ", timespec="seconds"
            )
            self.glpi.update_custom_asset(self.asset_name, glpi_id, fields_to_write_back)
