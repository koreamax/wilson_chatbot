import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "services" / "rag-server" / "src"))

from wilson_rag.chroma_collections import ChromaCollection, REQUIRED_COLLECTIONS
from wilson_rag.repository import ChromaRepository


class FakeChromaClient:
    def __init__(self) -> None:
        self.collections: dict[str, dict] = {}

    def get_or_create_collection(self, name: str, metadata: dict | None = None):
        self.collections.setdefault(name, metadata or {})

    def list_collections(self):
        return list(self.collections)


class StructureTest(unittest.TestCase):
    def test_chroma_collections_are_fixed_to_three(self):
        self.assertEqual(
            {collection.value for collection in REQUIRED_COLLECTIONS},
            {"static_knowledge", "elder", "guardian"},
        )

    def test_fastapi_router_package_removed(self):
        router_dir = ROOT / "app" / "routers"
        self.assertFalse(any(router_dir.glob("*.py")))

    def test_four_service_directories_exist(self):
        self.assertTrue((ROOT / "services" / "orchestrator-server").exists())
        self.assertTrue((ROOT / "services" / "rag-server").exists())
        self.assertTrue((ROOT / "services" / "llm-server").exists())
        self.assertTrue((ROOT / "services" / "chroma-db").exists())

    def test_chroma_nodeport_overlay_exists(self):
        self.assertTrue(
            (
                ROOT
                / "services"
                / "chroma-db"
                / "k8s"
                / "overlays"
                / "nodeport"
                / "service-nodeport.yaml"
            ).exists()
        )

    def test_chroma_docker_compose_exists(self):
        self.assertTrue((ROOT / "services" / "chroma-db" / "docker-compose.yml").exists())

    def test_chroma_docker_compose_has_tunnel_service(self):
        compose = (ROOT / "services" / "chroma-db" / "docker-compose.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("chroma-tunnel:", compose)
        self.assertIn("cloudflare/cloudflared", compose)

    def test_chroma_repository_creates_required_collections(self):
        client = FakeChromaClient()
        repository = ChromaRepository(client)

        repository.ensure_required_collections()

        self.assertTrue(repository.has_required_collections())
        self.assertEqual(
            set(repository.collection_names()),
            {"static_knowledge", "elder", "guardian"},
        )


if __name__ == "__main__":
    unittest.main()
