# Bridge GLPI → Mercator

Synchronise les actifs personnalisés GLPI 11 (Serveur, Flux)
vers les objets correspondants de Mercator.

## Structure

```
glpi-mercator-bridge/
├── config/
│   └── config.yml          ← Configuration (URLs, tokens, options)
├── src/
│   ├── glpi/
│   │   └── client.py       ← Client API REST GLPI v1
│   ├── mercator/
│   │   └── client.py       ← Client API REST Mercator (OAuth2)
│   ├── mappers/
│   │   ├── server_mapper.py ← GLPI Serveur → physical/logical server
│   │   └── flux_mapper.py   ← GLPI Flux → fluxes / logical-flows
│   └── sync/
│       ├── server_sync.py   ← Orchestration synchro serveurs
│       └── flux_sync.py     ← Orchestration synchro flux
├── tests/
│   └── test_mappers.py     ← Tests unitaires (sans appel réseau)
├── logs/                   ← Journaux rotatifs (créé automatiquement)
├── main.py                 ← Point d'entrée
├── requirements.txt
└── .last_sync              ← Horodatage dernière synchro (créé automatiquement)
```

## Installation

```bash
python -m venv venv
source venv/bin/activate      # Windows : venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

Éditer `config/config.yml` :

```yaml
glpi:
  url: "https://glpi.mondomaine.fr"
  app_token: "..."
  user_token: "..."

mercator:
  url: "https://mercator.mondomaine.fr"
  email: "bridge@mondomaine.fr"
  password: "..."
```

## Utilisation

```bash
# Synchro complète une fois
python main.py

# Synchro delta (objets modifiés depuis la dernière exécution)
python main.py --delta

# Boucle continue (intervalle défini dans config.yml)
python main.py --watch --delta

# Serveurs uniquement
python main.py --servers-only

# Flux uniquement (serveurs déjà synchronisés)
python main.py --fluxes-only
```

## Cron (exemple — toutes les heures)

```cron
0 * * * * cd /opt/bridge && venv/bin/python main.py --delta >> logs/cron.log 2>&1
```

## Ordre de synchronisation

Les serveurs **doivent** être synchronisés avant les flux.
Les flux applicatifs référencent des applications Mercator (qui doivent exister).
Les flux réseau référencent des IPs (lues depuis les actifs serveur GLPI).

## Champs écrits en retour dans GLPI

| Actif   | Champ GLPI              | Valeur écrite                  |
|---------|-------------------------|--------------------------------|
| Serveur | mercator_id_physique    | ID Mercator physical server    |
| Serveur | mercator_id_logique     | ID Mercator logical server     |
| Flux    | mercator_id             | ID Mercator flux ou flow       |
| Les deux| derniere_synchro        | Horodatage ISO de la synchro   |

## Tests

```bash
python -m pytest tests/ -v
```
