"""
Synchroniseur Flux
Orchestre la lecture GLPI, la transformation, et l'écriture dans Mercator
pour les actifs de type "Flux".

Doit s'exécuter APRÈS ServerSync (les serveurs/applications doivent exister
dans Mercator avant que les flux puissent y être liés).
"""

import logging
from datetime import datetime
from src.glpi.client import GLPIClient
from src.mercator.client import MercatorClient
from src.mappers.flux_mapper import FluxMapper

logger = logging.getLogger(__name__)

EXCLUDED_STATUSES = {"décommissionné"}


class FluxSync:
    def __init__(self, glpi: GLPIClient, mercator: MercatorClient, config: dict):
        self.glpi = glpi
        self.mercator = mercator
        self.mapper = FluxMapper(mercator)
        self.asset_name = config["glpi"]["asset_type_flux"]
        self.delta_only = config["sync"]["delta_only"]

    def run(self, last_sync: str = None) -> dict:
        """
        Lance la synchronisation des flux.

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
                logger.error(f"Erreur flux GLPI id={item.get('id')} : {e}")
                report["errors"] += 1

        logger.info(
            f"Flux — créés:{report['created']} "
            f"màj:{report['updated']} "
            f"ignorés:{report['skipped']} "
            f"erreurs:{report['errors']}"
        )
        return report

    # ---------------------------------------------------------- private

    def _sync_one(self, item: dict, report: dict):
        """Traite un seul flux GLPI."""
        glpi_id = item["id"]
        statut  = item.get("statut", "").lower()

        # Ignorer les flux non actifs
        if statut in EXCLUDED_STATUSES:
            logger.debug(f"Flux GLPI id={glpi_id} ignoré (statut={statut})")
            report["skipped"] += 1
            return

        # Ignorer les flux en attente de validation
        if statut == "à valider":
            logger.debug(f"Flux GLPI id={glpi_id} ignoré (statut=à valider)")
            report["skipped"] += 1
            return

        # Transformation
        endpoint = self.mapper.get_endpoint(item)
        payload  = self.mapper.to_mercator(item)

        if payload is None:
            # Données insuffisantes — mapper a déjà loggué le détail
            report["skipped"] += 1
            return

        # Upsert dans Mercator
        mercator_id = item.get("mercator_id")
        result      = self.mercator.upsert(endpoint, mercator_id, payload)
        new_id      = result.get("id")

        # Écriture en retour dans GLPI
        fields_to_write_back = {"derniere_synchro": datetime.now().isoformat(
            sep=" ", timespec="seconds"
        )}
        if not mercator_id and new_id:
            fields_to_write_back["mercator_id"] = new_id
            report["created"] += 1
        else:
            report["updated"] += 1

        self.glpi.update_custom_asset(self.asset_name, glpi_id, fields_to_write_back)
