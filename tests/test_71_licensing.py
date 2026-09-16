# tests/test_71_licensing.py
"""
Licence d'utilisation OptiqFluent signée à expiration (Code/licensing.py).

Aucun test direct n'existait pour ce module, alors qu'il porte l'enforcement
même de l'application chez le client (REQUIRE_LICENSE=1) : lecture du fichier
ou de la variable d'environnement, vérification de signature Ed25519, gestion
de l'expiration, et le before_request qui bloque (ou pas) une requête.

On ne peut pas utiliser la vraie clé privée AFDEC (jamais commitée) : chaque
test qui a besoin d'une licence VALIDE génère sa propre paire Ed25519 et
route `Code.licensing._PUBKEY_PATH` (monkeypatch, restauré automatiquement)
vers sa clé publique de test — exactement le même format que
`tools/licensing/make_license.py` produit avec la vraie clé.
"""
import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from Code import licensing


def _keypair():
    priv = Ed25519PrivateKey.generate()
    pub_pem = priv.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    return priv, pub_pem


def _sign_license(priv, payload):
    sig = priv.sign(licensing.canonical_payload_bytes(payload))
    return json.dumps({
        "payload": payload,
        "signature": base64.b64encode(sig).decode(),
    }).encode("utf-8")


@pytest.fixture
def cle_publique_test(tmp_path, monkeypatch):
    """Une paire Ed25519 de test ; la clé publique remplace celle de l'app."""
    priv, pub_pem = _keypair()
    pubkey_path = tmp_path / "license_pubkey_test.pem"
    pubkey_path.write_bytes(pub_pem)
    monkeypatch.setattr(licensing, "_PUBKEY_PATH", str(pubkey_path))
    return priv


class TestCanonicalPayloadBytes:

    def test_ordre_des_cles_n_influence_pas_le_resultat(self):
        a = licensing.canonical_payload_bytes({"b": 1, "a": 2})
        b = licensing.canonical_payload_bytes({"a": 2, "b": 1})
        assert a == b

    def test_est_compact_sans_espaces_superflus(self):
        raw = licensing.canonical_payload_bytes({"a": 1})
        assert raw == b'{"a":1}'


class TestReadLicenseRaw:

    def test_variable_env_base64_valide(self, monkeypatch):
        monkeypatch.setenv("OPTIQFLUENT_LICENSE", base64.b64encode(b"contenu-lic").decode())
        raw, mtime = licensing._read_license_raw()
        assert raw == b"contenu-lic"
        assert mtime is None

    def test_variable_env_base64_invalide_leve(self, monkeypatch):
        monkeypatch.setenv("OPTIQFLUENT_LICENSE", "!!! pas du base64 valide !!!")
        with pytest.raises(licensing.LicenseError):
            licensing._read_license_raw()

    def test_fichier_license_path(self, monkeypatch, tmp_path):
        monkeypatch.delenv("OPTIQFLUENT_LICENSE", raising=False)
        lic_file = tmp_path / "optiqfluent.lic"
        lic_file.write_bytes(b"contenu-fichier")
        monkeypatch.setenv("LICENSE_PATH", str(lic_file))
        raw, mtime = licensing._read_license_raw()
        assert raw == b"contenu-fichier"
        assert mtime is not None

    def test_aucune_source_leve_une_erreur_explicite(self, monkeypatch, tmp_path):
        monkeypatch.delenv("OPTIQFLUENT_LICENSE", raising=False)
        monkeypatch.setenv("LICENSE_PATH", str(tmp_path / "absent.lic"))
        monkeypatch.setenv("CONFIG_DIR", str(tmp_path / "config_absent"))
        with pytest.raises(licensing.LicenseError, match="Aucune licence trouvée"):
            licensing._read_license_raw()


class TestVerifyLicenseBytes:

    def test_cle_publique_absente_leve(self, monkeypatch, tmp_path):
        monkeypatch.setattr(licensing, "_PUBKEY_PATH", str(tmp_path / "n_existe_pas.pem"))
        with pytest.raises(licensing.LicenseError, match="Clé publique"):
            licensing.verify_license_bytes(b"{}")

    def test_json_malforme_leve(self, cle_publique_test):
        with pytest.raises(licensing.LicenseError, match="malformé"):
            licensing.verify_license_bytes(b"pas du json")

    def test_licence_valide_retourne_les_infos(self, cle_publique_test):
        payload = {"product": "OptiqFluent", "licensee": "ACME Test",
                   "issued_at": "2026-01-01", "expires_at": "2099-12-31",
                   "prompts_key": "cle-fernet-test"}
        raw = _sign_license(cle_publique_test, payload)
        info = licensing.verify_license_bytes(raw, mtime=123.0)
        assert info["licensee"] == "ACME Test"
        assert info["product"] == "OptiqFluent"
        from datetime import date
        assert info["expires_at"] == date(2099, 12, 31)
        assert info["mtime"] == 123.0
        assert info["prompts_key"] == "cle-fernet-test"

    def test_signature_invalide_leve(self, cle_publique_test):
        payload = {"licensee": "ACME", "expires_at": "2099-12-31"}
        raw = _sign_license(cle_publique_test, payload)
        doc = json.loads(raw)
        doc["payload"]["licensee"] = "ACME MODIFIÉ APRÈS SIGNATURE"
        with pytest.raises(licensing.LicenseError, match="Signature de licence invalide"):
            licensing.verify_license_bytes(json.dumps(doc).encode("utf-8"))

    def test_expires_at_absent_leve(self, cle_publique_test):
        payload = {"licensee": "ACME"}
        raw = _sign_license(cle_publique_test, payload)
        with pytest.raises(licensing.LicenseError, match="date d'expiration valide"):
            licensing.verify_license_bytes(raw)

    def test_expires_at_invalide_leve(self, cle_publique_test):
        payload = {"licensee": "ACME", "expires_at": "pas-une-date"}
        raw = _sign_license(cle_publique_test, payload)
        with pytest.raises(licensing.LicenseError, match="date d'expiration valide"):
            licensing.verify_license_bytes(raw)


class TestVerifyLicenseIntegration:

    def test_via_variable_environnement(self, cle_publique_test, monkeypatch):
        payload = {"licensee": "ACME Env", "expires_at": "2099-01-01"}
        raw = _sign_license(cle_publique_test, payload)
        monkeypatch.setenv("OPTIQFLUENT_LICENSE", base64.b64encode(raw).decode())
        info = licensing.verify_license()
        assert info["licensee"] == "ACME Env"


class TestInitLicenseEnforcement:

    def _app_minimal(self):
        from flask import Flask
        from pathlib import Path
        templates = Path(licensing.__file__).parent / "routes" / "templates"
        app = Flask(__name__, template_folder=str(templates))
        app.add_url_rule("/dummy", "dummy", lambda: "ok")
        app.add_url_rule("/healthz", "healthz", lambda: "healthy")
        return app

    def test_require_license_absent_desactive_l_enforcement(self, monkeypatch):
        monkeypatch.delenv("REQUIRE_LICENSE", raising=False)
        app = self._app_minimal()
        licensing.init_license_enforcement(app)
        assert app.config["LICENSE_STATE"] == {"enforced": False}
        assert "license_status" not in app.view_functions  # pas de route /license ajoutée
        with app.test_client() as c:
            assert c.get("/dummy").status_code == 200

    def test_require_license_actif_avec_licence_valide_laisse_passer(
            self, monkeypatch, cle_publique_test):
        payload = {"licensee": "ACME Gate", "expires_at": "2099-01-01"}
        raw = _sign_license(cle_publique_test, payload)
        monkeypatch.setenv("OPTIQFLUENT_LICENSE", base64.b64encode(raw).decode())
        monkeypatch.setenv("REQUIRE_LICENSE", "1")
        app = self._app_minimal()
        licensing.init_license_enforcement(app)
        assert app.config["LICENSE_STATE"]["enforced"] is True
        with app.test_client() as c:
            assert c.get("/dummy").status_code == 200
            r = c.get("/license")
            assert r.status_code == 200
            assert r.get_json()["valid"] is True
            assert r.get_json()["licensee"] == "ACME Gate"

    def test_require_license_actif_sans_licence_bloque(self, monkeypatch, tmp_path):
        monkeypatch.delenv("OPTIQFLUENT_LICENSE", raising=False)
        monkeypatch.setenv("LICENSE_PATH", str(tmp_path / "absent.lic"))
        monkeypatch.setenv("CONFIG_DIR", str(tmp_path / "config_absent"))
        monkeypatch.setenv("REQUIRE_LICENSE", "1")
        app = self._app_minimal()
        licensing.init_license_enforcement(app)
        with app.test_client() as c:
            assert c.get("/dummy").status_code == 403
            assert c.get("/license").status_code == 403

    def test_chemins_exempts_passent_meme_sans_licence(self, monkeypatch, tmp_path):
        monkeypatch.delenv("OPTIQFLUENT_LICENSE", raising=False)
        monkeypatch.setenv("LICENSE_PATH", str(tmp_path / "absent.lic"))
        monkeypatch.setenv("CONFIG_DIR", str(tmp_path / "config_absent"))
        monkeypatch.setenv("REQUIRE_LICENSE", "1")
        app = self._app_minimal()
        licensing.init_license_enforcement(app)
        with app.test_client() as c:
            assert c.get("/healthz").status_code == 200

    def test_licence_expiree_bloque(self, monkeypatch, cle_publique_test):
        payload = {"licensee": "ACME Expirée", "expires_at": "2020-01-01"}
        raw = _sign_license(cle_publique_test, payload)
        monkeypatch.setenv("OPTIQFLUENT_LICENSE", base64.b64encode(raw).decode())
        monkeypatch.setenv("REQUIRE_LICENSE", "1")
        app = self._app_minimal()
        licensing.init_license_enforcement(app)
        with app.test_client() as c:
            r = c.get("/dummy")
            assert r.status_code == 403
            r2 = c.get("/license")
            assert r2.status_code == 403
            assert r2.get_json()["valid"] is False
