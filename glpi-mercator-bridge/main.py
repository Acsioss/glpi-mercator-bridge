"""
Bridge GLPI → Mercator
Point d'entrée principal.

Usage :
  python main.py               # synchro complète unique
  python main.py --delta       # synchro delta depuis dernière exécution
  python main.py --watch       # boucle continue (intervalle défini dans config.yml)
  python main.py --servers     # serveurs uniquement
  python main.py --fluxes      # flux uniquement
"""

import argparse
import logging
import logging.handlers
import time
import yaml
from datetime import datetime
from pathlib import Path

from src.glpi.client import GLPIClient
from src.mercator.client import MercatorClient
from src.sync.server_sync import ServerSync
from src.sync.flux_sync import FluxSync


# ------------------------------------------------------------------ config

def load_config(path: str = "config/config.yml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def setup_logging(cfg: dict):
    log_cfg = cfg.get("logging", {})
    level   = getattr(logging, log_cfg.get("level", "INFO"))
    logfile = log_cfg.get("file", "logs/bridge.log")

    Path(logfile).parent.mkdir(exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(
        logfile,
        maxBytes=log_cfg.get("max_bytes", 5_242_880),
        backupCount=log_cfg.get("backup_count", 3),
        encoding="utf-8",
    )
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=[handler, logging.StreamHandler()],
    )


# ----------------------------------------------------------------- sync run

LAST_SYNC_FILE = ".last_sync"


def read_last_sync() -> str | None:
    try:
        return Path(LAST_SYNC_FILE).read_text().strip() or None
    except FileNotFoundError:
        return None


def write_last_sync():
    Path(LAST_SYNC_FILE).write_text(
        datetime.now().isoformat(sep=" ", timespec="seconds")
    )


def run_sync(cfg: dict, args):
    logger = logging.getLogger("bridge")
    last_sync = read_last_sync() if args.delta else None

    if last_sync:
        logger.info(f"Mode delta — depuis : {last_sync}")
    else:
        logger.info("Synchro complète")

    glpi     = GLPIClient(cfg["glpi"]["url"], cfg["glpi"]["app_token"], cfg["glpi"]["user_token"])
    mercator = MercatorClient(cfg["mercator"]["url"], cfg["mercator"]["email"], cfg["mercator"]["password"])

    try:
        glpi.connect()
        mercator.connect()

        reports = {}

        # Ordre : serveurs en premier (les flux en dépendent)
        if not args.fluxes_only:
            sync = ServerSync(glpi, mercator, cfg)
            reports["servers"] = sync.run(last_sync)

        if not args.servers_only:
            sync = FluxSync(glpi, mercator, cfg)
            reports["fluxes"] = sync.run(last_sync)

        write_last_sync()

        # Résumé final
        logger.info("=" * 50)
        for name, r in reports.items():
            logger.info(
                f"{name:10} | créés:{r['created']:4}  "
                f"màj:{r['updated']:4}  "
                f"ignorés:{r['skipped']:4}  "
                f"erreurs:{r['errors']:4}"
            )
        logger.info("=" * 50)

    finally:
        glpi.disconnect()


# -------------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description="Bridge GLPI → Mercator")
    parser.add_argument("--delta",        action="store_true", help="Mode delta (objets modifiés uniquement)")
    parser.add_argument("--watch",        action="store_true", help="Boucle continue")
    parser.add_argument("--servers-only", action="store_true", dest="servers_only")
    parser.add_argument("--fluxes-only",  action="store_true", dest="fluxes_only")
    parser.add_argument("--config",       default="config/config.yml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    setup_logging(cfg)
    logger = logging.getLogger("bridge")

    if args.watch:
        interval = cfg["sync"]["interval_minutes"] * 60
        logger.info(f"Mode watch — intervalle : {cfg['sync']['interval_minutes']} min")
        while True:
            try:
                run_sync(cfg, args)
            except Exception as e:
                logger.error(f"Erreur lors de la synchro : {e}", exc_info=True)
            logger.info(f"Prochain passage dans {cfg['sync']['interval_minutes']} min")
            time.sleep(interval)
    else:
        run_sync(cfg, args)


if __name__ == "__main__":
    main()
