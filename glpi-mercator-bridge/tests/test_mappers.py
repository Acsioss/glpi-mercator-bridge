"""
Tests unitaires — ServerMapper
Vérifie les transformations GLPI → Mercator sans appel réseau.
"""

import unittest
from unittest.mock import MagicMock
from src.mappers.server_mapper import ServerMapper


def make_mapper():
    mercator = MagicMock()
    mercator.resolve_site_id.return_value = 42
    mercator.resolve_bay_id.return_value  = None
    return ServerMapper(mercator)


class TestServerMapper(unittest.TestCase):

    def test_physical_server_basic(self):
        mapper  = make_mapper()
        item    = {
            "id": 1, "name": "srv-prod-01",
            "adresse_ip": "10.0.0.1", "cpu": "8 vCPU",
            "memoire_go": 16, "disque_go": 500,
            "os": "Ubuntu", "version_os": "22.04",
            "site": "DC-Paris", "statut": "production",
        }
        payload = mapper.to_physical_server(item)
        self.assertEqual(payload["name"], "srv-prod-01")
        self.assertEqual(payload["ip_address"], "10.0.0.1")
        self.assertEqual(payload["os"], "Ubuntu 22.04")
        self.assertEqual(payload["site_id"], 42)

    def test_logical_server_active_flag(self):
        mapper = make_mapper()

        item_prod = {"id": 2, "name": "vm-01", "statut": "production",
                     "adresse_ip": "10.0.0.2"}
        payload   = mapper.to_logical_server(item_prod)
        self.assertTrue(payload["active"])

        item_dev = {"id": 3, "name": "vm-dev", "statut": "développement",
                    "adresse_ip": "10.0.0.3"}
        payload  = mapper.to_logical_server(item_dev)
        self.assertFalse(payload["active"])

    def test_physical_link_passed_explicitly(self):
        mapper  = make_mapper()
        item    = {"id": 4, "name": "vm-02", "statut": "production",
                   "adresse_ip": "10.0.0.4"}
        payload = mapper.to_logical_server(item, physical_mercator_id=99)
        self.assertIn(99, payload["physicalServers"])

    def test_none_values_cleaned(self):
        mapper  = make_mapper()
        item    = {"id": 5, "name": "srv", "statut": "production",
                   "adresse_ip": "10.0.0.5", "cpu": None, "memoire_go": None}
        payload = mapper.to_physical_server(item)
        self.assertNotIn("cpu", payload)
        self.assertNotIn("memory", payload)


class TestFluxMapper(unittest.TestCase):

    def test_endpoint_routing(self):
        from src.mappers.flux_mapper import FluxMapper
        mercator = MagicMock()
        mapper   = FluxMapper(mercator)

        self.assertEqual(
            mapper.get_endpoint({"type_flux": "applicatif"}), "fluxes"
        )
        self.assertEqual(
            mapper.get_endpoint({"type_flux": "réseau"}), "logical-flows"
        )

    def test_logical_flow_missing_ip(self):
        from src.mappers.flux_mapper import FluxMapper
        mercator = MagicMock()
        mapper   = FluxMapper(mercator)
        item = {
            "id": 10, "type_flux": "réseau",
            "ip_source": "", "ip_dest": "",
            "serveur_source": None, "serveur_dest": None,
        }
        result = mapper.to_mercator(item)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
