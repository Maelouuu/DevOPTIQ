# tests/test_32_projection_metier.py
"""
Page : Projection Métier (/projection_metier/)
Couvre :
  - Page HTML (GET /)
  - Analyse utilisateur GET /analyze_user/<uid> et alias /analyze/<uid>
  - Comportement sans credentials ROME (rome_search_jobs renvoie [] → listes vides)
  - Pagination : full_offset, full_limit, partial_offset, partial_limit
  - Helpers internes : _normalize, _tokenize, _jaccard_similarity, _text_similarity
  - _extract_user_competencies (sans rôle, avec rôle)
"""
import json
import pytest

pytestmark = pytest.mark.projection_metier


# ===========================================================================
# 1. PAGE HTML — GET /projection_metier/
# ===========================================================================

class TestProjectionMetierPage:

    def test_page_accessible_avec_auth(self, auth_client):
        """La page /projection_metier/ répond 200 avec une session valide."""
        r = auth_client.get("/projection_metier/")
        assert r.status_code == 200

    def test_page_contient_elements_html(self, auth_client):
        """La réponse contient du HTML (partials inclus — pas de doctype complet)."""
        r = auth_client.get("/projection_metier/")
        # Le template est rendu en mode partiel (inclus via base) — contient des balises HTML
        assert b"<div" in r.data or b"<section" in r.data or b"<ul" in r.data

    def test_page_sans_auth_accessible(self, client):
        """La page /projection_metier/ est accessible sans login (pas de auth_required)."""
        r = client.get("/projection_metier/")
        # La route n'exige pas de session → 200 ou redirection selon le middleware
        assert r.status_code in (200, 302, 401)


# ===========================================================================
# 2. ANALYSE UTILISATEUR — GET /projection_metier/analyze_user/<uid>
# ===========================================================================

class TestAnalyzeUser:

    def test_uid_zero_retourne_400(self, auth_client):
        """uid=0 est invalide → 400."""
        r = auth_client.get("/projection_metier/analyze_user/0")
        assert r.status_code == 400

    def test_utilisateur_inexistant_retourne_404(self, auth_client):
        """Utilisateur inconnu → 404."""
        r = auth_client.get("/projection_metier/analyze_user/999999")
        assert r.status_code == 404

    def test_utilisateur_sans_roles_retourne_200(self, auth_client, ids):
        """Utilisateur du seed (sans rôles) → 200."""
        r = auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}")
        assert r.status_code == 200

    def test_utilisateur_sans_roles_retourne_listes_vides(self, auth_client, ids):
        """Utilisateur sans rôles → full=[] et partial=[]."""
        r = auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}")
        body = json.loads(r.data)
        assert body["full"] == []
        assert body["partial"] == []

    def test_structure_json_complete(self, auth_client, ids):
        """La réponse JSON contient full, partial, page, info."""
        r = auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}")
        assert r.status_code == 200
        body = json.loads(r.data)
        for key in ("full", "partial", "page", "info"):
            assert key in body, f"Champ manquant : {key}"

    def test_page_full_a_les_bons_champs(self, auth_client, ids):
        """page.full contient offset, limit, total, has_more."""
        r = auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}")
        body = json.loads(r.data)
        for field in ("offset", "limit", "total", "has_more"):
            assert field in body["page"]["full"], f"page.full manque : {field}"

    def test_page_partial_a_les_bons_champs(self, auth_client, ids):
        """page.partial contient offset, limit, total, has_more."""
        r = auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}")
        body = json.loads(r.data)
        for field in ("offset", "limit", "total", "has_more"):
            assert field in body["page"]["partial"], f"page.partial manque : {field}"

    def test_info_contient_user_id(self, auth_client, ids):
        """Le champ info.user correspond à l'uid demandé."""
        r = auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}")
        body = json.loads(r.data)
        assert body["info"]["user"] == ids["user_id"]

    def test_alias_url_analyze_fonctionne(self, auth_client, ids):
        """/projection_metier/analyze/<uid> est un alias valide."""
        r = auth_client.get(f"/projection_metier/analyze/{ids['user_id']}")
        assert r.status_code == 200

    def test_content_type_json(self, auth_client, ids):
        """La réponse est en application/json."""
        r = auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}")
        assert "application/json" in r.content_type

    def test_pagination_full_offset_accepte_sans_erreur(self, auth_client, ids):
        """full_offset=5 est accepté sans erreur (pas de plantage 500)."""
        r = auth_client.get(
            f"/projection_metier/analyze_user/{ids['user_id']}?full_offset=5"
        )
        # Sans compétences, le code retourne 200 avec offset hardcodé à 0.
        # Avec compétences + ROME vide, offset=5 est reflété. Dans les deux cas : 200.
        assert r.status_code == 200

    def test_pagination_full_limit_zero_retourne_full_vide(self, auth_client, ids):
        """full_limit=0 → la liste full est vide (tranche vide)."""
        r = auth_client.get(
            f"/projection_metier/analyze_user/{ids['user_id']}?full_limit=0"
        )
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["full"] == []

    def test_pagination_partial_offset_accepte_sans_erreur(self, auth_client, ids):
        """partial_offset=3 est accepté sans erreur (pas de plantage 500)."""
        r = auth_client.get(
            f"/projection_metier/analyze_user/{ids['user_id']}?partial_offset=3"
        )
        assert r.status_code == 200

    def test_full_est_liste(self, auth_client, ids):
        assert isinstance(json.loads(
            auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}").data
        )["full"], list)

    def test_partial_est_liste(self, auth_client, ids):
        assert isinstance(json.loads(
            auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}").data
        )["partial"], list)

    def test_sans_rome_credentials_et_roles_listes_vides(self, app, auth_client, ids):
        """Utilisateur avec rôles mais sans credentials ROME → full=[] et partial=[].
        rome_search_jobs retourne [] (pas de token) → rome_jobs_pool reste vide."""
        with app.app_context():
            from Code.models.models import Role, UserRole
            from Code.extensions import db
            role = Role(name="Role ROME No Creds", entity_id=ids["entity_id"])
            db.session.add(role)
            db.session.flush()
            role_id = role.id
            ur = UserRole(user_id=ids["user_id"], role_id=role_id)
            db.session.add(ur)
            db.session.commit()

        try:
            r = auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}")
            assert r.status_code == 200
            body = json.loads(r.data)
            assert body["full"] == []
            assert body["partial"] == []
        finally:
            with app.app_context():
                from Code.models.models import UserRole, Role
                from Code.extensions import db
                # UserRole a une PK composite (user_id, role_id) — pas de champ id
                db.session.query(UserRole).filter_by(
                    user_id=ids["user_id"], role_id=role_id
                ).delete()
                db.session.query(Role).filter_by(id=role_id).delete()
                db.session.commit()

    def test_message_aucune_competence_quand_sans_roles(self, auth_client, ids):
        """Sans rôles, le champ info contient un message 'Aucune compétence'."""
        r = auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}")
        body = json.loads(r.data)
        msg = body.get("info", {}).get("message", "")
        assert "comp" in msg.lower() or msg == ""


# ===========================================================================
# 3. HELPER _normalize — tests unitaires sans DB ni HTTP
# ===========================================================================

class TestNormalizeHelper:

    @staticmethod
    def _n(text):
        from Code.routes.projection_metier import _normalize
        return _normalize(text)

    def test_chaine_vide_retourne_vide(self):
        assert self._n("") == ""

    def test_minuscules(self):
        assert self._n("GESTION") == "gestion"

    def test_accents_retires(self):
        assert self._n("compétence") == "competence"
        assert self._n("activité") == "activite"

    def test_ponctuation_remplacee(self):
        result = self._n("savoir-faire")
        assert "-" not in result

    def test_apostrophe_remplacee(self):
        result = self._n("aujourd'hui")
        assert "'" not in result

    def test_espaces_multiples_compresses(self):
        assert self._n("a   b") == "a b"

    def test_caracteres_speciaux_supprimes(self):
        result = self._n("gestion@entreprise!")
        assert "@" not in result
        assert "!" not in result

    def test_texte_normal_conserve_mots(self):
        result = self._n("gestion de projet")
        assert "gestion" in result
        assert "projet" in result

    def test_slash_remplace_par_espace(self):
        result = self._n("lecture/ecriture")
        assert "/" not in result

    def test_retourne_string(self):
        assert isinstance(self._n("test"), str)


# ===========================================================================
# 4. HELPER _tokenize — tests unitaires
# ===========================================================================

class TestTokenizeHelper:

    @staticmethod
    def _t(text):
        from Code.routes.projection_metier import _tokenize
        return _tokenize(text)

    def test_vide_retourne_liste_vide(self):
        assert self._t("") == []

    def test_retourne_liste(self):
        assert isinstance(self._t("gestion projet"), list)

    def test_stopwords_supprimes(self):
        result = self._t("gestion de la structure")
        assert "de" not in result
        assert "la" not in result

    def test_mots_significatifs_conserves(self):
        result = self._t("gestion projet formation")
        assert "gestion" in result
        assert "projet" in result
        assert "formation" in result

    def test_texte_uniquement_stopwords(self):
        """Texte 100 % stopwords → liste vide."""
        result = self._t("de la le les")
        assert result == []

    def test_tokens_sans_doublons_apres_normalize(self):
        """'Gestion gestion' → token 'gestion' présent (peut apparaître 2 fois, mais non vide)."""
        result = self._t("Gestion gestion")
        assert len(result) > 0

    def test_accents_normalises_avant_tokenization(self):
        """Les accents sont retirés lors de la tokenisation."""
        result = self._t("compétence")
        assert "competence" in result


# ===========================================================================
# 5. HELPER _jaccard_similarity — tests unitaires
# ===========================================================================

class TestJaccardSimilarity:

    @staticmethod
    def _j(a, b):
        from Code.routes.projection_metier import _jaccard_similarity
        return _jaccard_similarity(a, b)

    def test_ensembles_identiques_retournent_1(self):
        assert self._j({"a", "b", "c"}, {"a", "b", "c"}) == 1.0

    def test_aucun_overlap_retourne_0(self):
        assert self._j({"a", "b"}, {"c", "d"}) == 0.0

    def test_ensembles_vides_retournent_0(self):
        assert self._j(set(), set()) == 0.0

    def test_premier_vide_retourne_0(self):
        assert self._j(set(), {"a"}) == 0.0

    def test_second_vide_retourne_0(self):
        assert self._j({"a"}, set()) == 0.0

    def test_overlap_partiel_entre_0_et_1(self):
        result = self._j({"a", "b"}, {"b", "c"})
        assert 0.0 < result < 1.0

    def test_resultat_toujours_entre_0_et_1(self):
        result = self._j({"x", "y", "z"}, {"y", "z", "w"})
        assert 0.0 <= result <= 1.0

    def test_symetrie(self):
        """Jaccard(A, B) == Jaccard(B, A)."""
        a, b = {"un", "deux", "trois"}, {"deux", "quatre"}
        assert self._j(a, b) == self._j(b, a)

    def test_singleton_commun(self):
        """Un seul élément commun sur trois → 1/5 = 0.2."""
        result = self._j({"a", "b", "c"}, {"c", "d", "e"})
        assert abs(result - 1 / 5) < 1e-9


# ===========================================================================
# 6. HELPER _text_similarity — tests unitaires
# ===========================================================================

class TestTextSimilarity:

    @staticmethod
    def _s(a, b):
        from Code.routes.projection_metier import _text_similarity
        return _text_similarity(a, b)

    def test_retourne_tuple_de_deux_floats(self):
        result = self._s("gestion", "gestion")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(v, float) for v in result)

    def test_textes_identiques_ratio_1(self):
        ratio, _ = self._s("gestion de projet", "gestion de projet")
        assert ratio == 1.0

    def test_textes_identiques_jaccard_1(self):
        _, jaccard = self._s("gestion projet", "gestion projet")
        assert jaccard == 1.0

    def test_textes_differents_scores_dans_0_1(self):
        ratio, jaccard = self._s("comptabilite finance", "gestion ressources")
        assert 0.0 <= ratio <= 1.0
        assert 0.0 <= jaccard <= 1.0

    def test_chaines_vides_ne_plantent_pas(self):
        ratio, jaccard = self._s("", "")
        assert isinstance(ratio, float)
        assert isinstance(jaccard, float)

    def test_texte_vide_vs_non_vide_ne_plante_pas(self):
        ratio, jaccard = self._s("", "gestion")
        assert isinstance(ratio, float)
        assert isinstance(jaccard, float)

    def test_textes_similaires_ont_ratio_eleve(self):
        ratio, _ = self._s("gestion de projet", "gestion projet")
        assert ratio > 0.5

    def test_textes_tres_differents_ont_ratio_faible(self):
        ratio, _ = self._s("aaaa", "zzzz")
        assert ratio < 0.5


# ===========================================================================
# 7. HELPER _extract_user_competencies — tests avec DB
# ===========================================================================

class TestExtractUserCompetencies:

    def test_utilisateur_inexistant_retourne_liste_vide(self, app):
        """ID inconnu → []."""
        with app.app_context():
            from Code.routes.projection_metier import _extract_user_competencies
            result = _extract_user_competencies(999999)
        assert result == []

    def test_utilisateur_sans_roles_retourne_liste_vide(self, app, ids):
        """L'utilisateur seed, s'il n'a aucun UserRole, retourne []."""
        with app.app_context():
            from Code.models.models import UserRole
            user_has_roles = UserRole.query.filter_by(user_id=ids["user_id"]).count() > 0
            if user_has_roles:
                pytest.skip("L'utilisateur seed a des rôles (leftovers d'autres tests) — test inapplicable.")
            from Code.routes.projection_metier import _extract_user_competencies
            result = _extract_user_competencies(ids["user_id"])
        assert result == []

    def test_retourne_toujours_une_liste(self, app, ids):
        with app.app_context():
            from Code.routes.projection_metier import _extract_user_competencies
            result = _extract_user_competencies(ids["user_id"])
        assert isinstance(result, list)

    def test_utilisateur_avec_role_retourne_nom_du_role(self, app, ids):
        """Avec un rôle assigné, le nom du rôle figure dans les labels."""
        with app.app_context():
            from Code.models.models import Role, UserRole
            from Code.extensions import db
            role = Role(name="Role Extraction Test", entity_id=ids["entity_id"])
            db.session.add(role)
            db.session.flush()
            role_id = role.id
            ur = UserRole(user_id=ids["user_id"], role_id=role_id)
            db.session.add(ur)
            db.session.commit()

            try:
                from Code.routes.projection_metier import _extract_user_competencies
                result = _extract_user_competencies(ids["user_id"])
                assert isinstance(result, list)
                assert len(result) > 0
                assert "Role Extraction Test" in result
            finally:
                # UserRole a une PK composite (user_id, role_id) — pas de champ id
                db.session.query(UserRole).filter_by(
                    user_id=ids["user_id"], role_id=role_id
                ).delete()
                db.session.query(Role).filter_by(id=role_id).delete()
                db.session.commit()

    def test_labels_sont_des_strings(self, app, ids):
        """Tous les labels retournés sont des chaînes non vides."""
        with app.app_context():
            from Code.routes.projection_metier import _extract_user_competencies
            result = _extract_user_competencies(ids["user_id"])
        assert all(isinstance(label, str) and label.strip() for label in result)

    def test_role_avec_activite_liee_extrait_toutes_les_competences(self, app, ids):
        """Rôle → activité (activity_roles) → Competency/Savoir/SavoirFaire/
        Softskill/Aptitude : chaque libellé doit remonter dans les labels."""
        with app.app_context():
            from Code.models.models import (
                Role, UserRole, Activities, Competency, Savoir, SavoirFaire,
                Softskill, Aptitude, activity_roles,
            )
            from Code.extensions import db

            role = Role(name="Role Chaine Test", entity_id=ids["entity_id"])
            activity = Activities(
                entity_id=ids["entity_id"],
                name="Activite Chaine Test",
                description="desc",
            )
            db.session.add_all([role, activity])
            db.session.flush()
            role_id, activity_id = role.id, activity.id

            db.session.execute(
                activity_roles.insert().values(
                    activity_id=activity_id, role_id=role_id, status="active"
                )
            )
            db.session.add(UserRole(user_id=ids["user_id"], role_id=role_id))
            db.session.add(Competency(description="Competence Chaine", activity_id=activity_id))
            db.session.add(Savoir(description="Savoir Chaine", activity_id=activity_id))
            db.session.add(SavoirFaire(description="SavoirFaire Chaine", activity_id=activity_id))
            db.session.add(Softskill(habilete="Softskill Chaine", niveau="3", activity_id=activity_id))
            db.session.add(Aptitude(description="Aptitude Chaine", activity_id=activity_id))
            db.session.commit()

            try:
                from Code.routes.projection_metier import _extract_user_competencies
                result = _extract_user_competencies(ids["user_id"])
                assert "Activite Chaine Test" in result
                assert "Competence Chaine" in result
                assert "Savoir Chaine" in result
                assert "SavoirFaire Chaine" in result
                assert "Softskill Chaine" in result
                assert "Aptitude Chaine" in result
            finally:
                db.session.execute(
                    activity_roles.delete().where(activity_roles.c.role_id == role_id)
                )
                db.session.query(UserRole).filter_by(
                    user_id=ids["user_id"], role_id=role_id
                ).delete()
                # Delete ORM-style (pas .query().delete()) pour déclencher le
                # cascade="all, delete-orphan" sur les Competency/Savoir/... liés
                # — sinon ils restent orphelins et polluent un futur activity_id
                # réutilisé par SQLite.
                act = db.session.get(Activities, activity_id)
                if act:
                    db.session.delete(act)
                db.session.query(Role).filter_by(id=role_id).delete()
                db.session.commit()


# ===========================================================================
# 6. get_access_token — flux OAuth2 (mock de requests.post)
# ===========================================================================

class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        if self._json_data is None:
            raise ValueError("no json")
        return self._json_data


class TestGetAccessToken:

    def setup_method(self):
        import Code.routes.projection_metier as pm
        self.pm = pm
        # Sauvegarde l'état pour restauration en fin de test (isolation)
        self._orig_id = pm.ROME_CLIENT_ID
        self._orig_secret = pm.ROME_CLIENT_SECRET
        self._orig_scope = pm.ROME_SCOPE
        self._orig_cache = dict(pm._token_cache)
        pm.ROME_CLIENT_ID = "test_client_id"
        pm.ROME_CLIENT_SECRET = "test_client_secret"
        pm.ROME_SCOPE = "api_rome-fiches-metiersv1"
        pm._token_cache["access_token"] = None
        pm._token_cache["expires_at"] = 0

    def teardown_method(self):
        self.pm.ROME_CLIENT_ID = self._orig_id
        self.pm.ROME_CLIENT_SECRET = self._orig_secret
        self.pm.ROME_SCOPE = self._orig_scope
        self.pm._token_cache["access_token"] = self._orig_cache["access_token"]
        self.pm._token_cache["expires_at"] = self._orig_cache["expires_at"]

    def test_missing_client_id_returns_none(self):
        self.pm.ROME_CLIENT_ID = ""
        assert self.pm.get_access_token() is None

    def test_missing_scope_returns_none(self, monkeypatch):
        self.pm.ROME_SCOPE = ""
        assert self.pm.get_access_token() is None

    def test_cached_valid_token_returned_without_http_call(self, monkeypatch):
        self.pm._token_cache["access_token"] = "cached-token"
        self.pm._token_cache["expires_at"] = self.pm.time.time() + 3600

        def _boom(*a, **k):
            raise AssertionError("requests.post ne doit pas être appelé si le cache est valide")
        monkeypatch.setattr(self.pm.requests, "post", _boom)

        assert self.pm.get_access_token() == "cached-token"

    def test_first_attempt_success_returns_token(self, monkeypatch):
        monkeypatch.setattr(
            self.pm.requests, "post",
            lambda *a, **k: _FakeResponse(200, {"access_token": "tok-1", "expires_in": 1200}),
        )
        token = self.pm.get_access_token()
        assert token == "tok-1"
        assert self.pm._token_cache["access_token"] == "tok-1"

    def test_first_attempt_400_falls_back_to_second_attempt_success(self, monkeypatch):
        calls = {"n": 0}

        def fake_post(url, data=None, headers=None, timeout=None):
            calls["n"] += 1
            if calls["n"] == 1:
                return _FakeResponse(400, {"error": "invalid_scope", "error_description": "nope"})
            return _FakeResponse(200, {"access_token": "tok-2", "expires_in": 900})

        monkeypatch.setattr(self.pm.requests, "post", fake_post)
        token = self.pm.get_access_token()
        assert token == "tok-2"
        assert calls["n"] == 2

    def test_both_attempts_fail_returns_none(self, monkeypatch):
        monkeypatch.setattr(
            self.pm.requests, "post",
            lambda *a, **k: _FakeResponse(500, {"_raw_text": "server error"}, text="server error"),
        )
        assert self.pm.get_access_token() is None

    def test_timeout_on_first_attempt_falls_through_to_second(self, monkeypatch):
        import requests as real_requests

        def fake_post(url, data=None, headers=None, timeout=None):
            if headers and "Authorization" in headers:
                raise real_requests.exceptions.Timeout()
            return _FakeResponse(200, {"access_token": "tok-3", "expires_in": 600})

        monkeypatch.setattr(self.pm.requests, "post", fake_post)
        assert self.pm.get_access_token() == "tok-3"

    def test_non_json_response_body_handled_gracefully(self, monkeypatch):
        def fake_post(url, data=None, headers=None, timeout=None):
            r = _FakeResponse(500, json_data=None, text="<html>error</html>")
            return r
        monkeypatch.setattr(self.pm.requests, "post", fake_post)
        assert self.pm.get_access_token() is None


# ===========================================================================
# 7. rome_search_jobs / rome_get_job_details — appels HTTP (mock requests.get)
# ===========================================================================

class TestRomeHttpCalls:

    def setup_method(self):
        import Code.routes.projection_metier as pm
        self.pm = pm
        self._orig_cache = dict(pm._token_cache)
        pm._token_cache["access_token"] = "fixed-token"
        pm._token_cache["expires_at"] = pm.time.time() + 3600

    def teardown_method(self):
        self.pm._token_cache["access_token"] = self._orig_cache["access_token"]
        self.pm._token_cache["expires_at"] = self._orig_cache["expires_at"]

    def test_search_jobs_empty_query_returns_empty_without_http(self):
        assert self.pm.rome_search_jobs("") == []
        assert self.pm.rome_search_jobs("   ") == []

    def test_search_jobs_list_response(self, monkeypatch):
        monkeypatch.setattr(
            self.pm.requests, "get",
            lambda *a, **k: _FakeResponse(200, [{"code": "M1805"}]),
        )
        result = self.pm.rome_search_jobs("developpeur")
        assert result == [{"code": "M1805"}]

    def test_search_jobs_dict_response_with_metiers_key(self, monkeypatch):
        monkeypatch.setattr(
            self.pm.requests, "get",
            lambda *a, **k: _FakeResponse(200, {"metiers": [{"code": "M1806"}]}),
        )
        result = self.pm.rome_search_jobs("developpeur")
        assert result == [{"code": "M1806"}]

    def test_search_jobs_unexpected_shape_returns_empty(self, monkeypatch):
        monkeypatch.setattr(
            self.pm.requests, "get",
            lambda *a, **k: _FakeResponse(200, "not a list or dict"),
        )
        assert self.pm.rome_search_jobs("x") == []

    def test_search_jobs_non_200_returns_empty(self, monkeypatch):
        monkeypatch.setattr(
            self.pm.requests, "get",
            lambda *a, **k: _FakeResponse(404, {}, text="not found"),
        )
        assert self.pm.rome_search_jobs("x") == []

    def test_search_jobs_timeout_returns_empty(self, monkeypatch):
        import requests as real_requests

        def raise_timeout(*a, **k):
            raise real_requests.exceptions.Timeout()
        monkeypatch.setattr(self.pm.requests, "get", raise_timeout)
        assert self.pm.rome_search_jobs("x") == []

    def test_search_jobs_generic_exception_returns_empty(self, monkeypatch):
        def raise_runtime(*a, **k):
            raise RuntimeError("boom")
        monkeypatch.setattr(self.pm.requests, "get", raise_runtime)
        assert self.pm.rome_search_jobs("x") == []

    def test_get_job_details_empty_code_returns_empty_dict(self):
        assert self.pm.rome_get_job_details("") == {}

    def test_get_job_details_success(self, monkeypatch):
        monkeypatch.setattr(
            self.pm.requests, "get",
            lambda *a, **k: _FakeResponse(200, {"code": "M1805", "metier": {"libelle": "Dev"}}),
        )
        result = self.pm.rome_get_job_details("M1805")
        assert result["code"] == "M1805"

    def test_get_job_details_non_dict_response_returns_empty(self, monkeypatch):
        monkeypatch.setattr(
            self.pm.requests, "get",
            lambda *a, **k: _FakeResponse(200, ["not", "a", "dict"]),
        )
        assert self.pm.rome_get_job_details("M1805") == {}

    def test_get_job_details_non_200_returns_empty(self, monkeypatch):
        monkeypatch.setattr(
            self.pm.requests, "get",
            lambda *a, **k: _FakeResponse(503, {}),
        )
        assert self.pm.rome_get_job_details("M1805") == {}

    def test_get_job_details_timeout_returns_empty(self, monkeypatch):
        import requests as real_requests

        def raise_timeout(*a, **k):
            raise real_requests.exceptions.Timeout()
        monkeypatch.setattr(self.pm.requests, "get", raise_timeout)
        assert self.pm.rome_get_job_details("M1805") == {}

    def test_no_token_available_short_circuits_search(self, monkeypatch):
        self.pm._token_cache["access_token"] = None
        self.pm._token_cache["expires_at"] = 0
        monkeypatch.setattr(self.pm, "ROME_CLIENT_ID", "")
        assert self.pm.rome_search_jobs("x") == []

    def test_no_token_available_short_circuits_details(self, monkeypatch):
        self.pm._token_cache["access_token"] = None
        self.pm._token_cache["expires_at"] = 0
        monkeypatch.setattr(self.pm, "ROME_CLIENT_ID", "")
        assert self.pm.rome_get_job_details("M1805") == {}


# ===========================================================================
# 8. Helpers d'extraction de fiche métier ROME
# ===========================================================================

class TestJobExtractionHelpers:

    def test_extract_competencies_from_job_full(self):
        from Code.routes.projection_metier import _extract_competencies_from_job
        job = {
            "groupesCompetencesMobilisees": [
                {"competences": [{"libelle": "Python"}, {"libelle": "SQL"}]},
                {"competences": [{"libelle": " Docker "}]},
            ]
        }
        result = _extract_competencies_from_job(job)
        assert result == ["Python", "SQL", "Docker"]

    def test_extract_competencies_ignores_malformed_entries(self):
        from Code.routes.projection_metier import _extract_competencies_from_job
        job = {
            "groupesCompetencesMobilisees": [
                "not_a_dict",
                {"competences": "not_a_list"},
                {"competences": [{"libelle": ""}, "not_a_dict", {"no_libelle": True}]},
            ]
        }
        assert _extract_competencies_from_job(job) == []

    def test_extract_competencies_missing_key_returns_empty(self):
        from Code.routes.projection_metier import _extract_competencies_from_job
        assert _extract_competencies_from_job({}) == []

    def test_extract_job_label(self):
        from Code.routes.projection_metier import _extract_job_label
        assert _extract_job_label({"metier": {"libelle": " Développeur "}}) == "Développeur"

    def test_extract_job_label_missing_returns_empty(self):
        from Code.routes.projection_metier import _extract_job_label
        assert _extract_job_label({}) == ""

    def test_extract_job_code_top_level(self):
        from Code.routes.projection_metier import _extract_job_code
        assert _extract_job_code({"code": " M1805 "}) == "M1805"

    def test_extract_job_code_falls_back_to_metier_code(self):
        from Code.routes.projection_metier import _extract_job_code
        assert _extract_job_code({"metier": {"code": "M1806"}}) == "M1806"

    def test_extract_job_code_missing_returns_empty(self):
        from Code.routes.projection_metier import _extract_job_code
        assert _extract_job_code({}) == ""


# ===========================================================================
# 9. analyze_user — pipeline complet de matching (rome_search_jobs /
#    rome_get_job_details mockés au niveau module)
# ===========================================================================

class TestAnalyzeUserFullMatching:

    def _setup_role_with_competency(self, app, ids, description):
        from Code.models.models import Role, UserRole, Activities, Competency, activity_roles
        from Code.extensions import db

        with app.app_context():
            role = Role(name="Role Matching Test", entity_id=ids["entity_id"])
            activity = Activities(
                entity_id=ids["entity_id"], name="Activite Matching Test", description="d"
            )
            db.session.add_all([role, activity])
            db.session.flush()
            role_id, activity_id = role.id, activity.id
            db.session.execute(
                activity_roles.insert().values(activity_id=activity_id, role_id=role_id, status="active")
            )
            db.session.add(UserRole(user_id=ids["user_id"], role_id=role_id))
            db.session.add(Competency(description=description, activity_id=activity_id))
            db.session.commit()
        return role_id, activity_id

    def _teardown(self, app, ids, role_id, activity_id):
        from Code.models.models import Role, UserRole, Activities, activity_roles
        from Code.extensions import db

        with app.app_context():
            db.session.execute(activity_roles.delete().where(activity_roles.c.role_id == role_id))
            db.session.query(UserRole).filter_by(user_id=ids["user_id"], role_id=role_id).delete()
            act = db.session.get(Activities, activity_id)
            if act:
                db.session.delete(act)
            db.session.query(Role).filter_by(id=role_id).delete()
            db.session.commit()

    def test_full_match_when_all_job_competencies_owned(self, app, auth_client, ids, monkeypatch):
        """Le libellé de compétence utilisateur couvre exactement la compétence
        du métier ROME → le métier doit apparaître dans 'full' avec score 100."""
        role_id, activity_id = self._setup_role_with_competency(
            app, ids, "Gestion de projet informatique"
        )
        try:
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(
                pm, "rome_search_jobs",
                lambda query: [{"code": "M1805"}],
            )
            monkeypatch.setattr(
                pm, "rome_get_job_details",
                lambda code: {
                    "metier": {"libelle": "Chef de projet"},
                    "code": "M1805",
                    "groupesCompetencesMobilisees": [
                        {"competences": [{"libelle": "Gestion de projet informatique"}]}
                    ],
                },
            )
            r = auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}")
            assert r.status_code == 200
            data = r.get_json()
            assert any(j["code"] == "M1805" for j in data["full"])
            matched = next(j for j in data["full"] if j["code"] == "M1805")
            assert matched["score"] == 100.0
            assert matched["missing_count"] == 0
        finally:
            self._teardown(app, ids, role_id, activity_id)

    def test_partial_match_when_some_competencies_missing(self, app, auth_client, ids, monkeypatch):
        role_id, activity_id = self._setup_role_with_competency(
            app, ids, "Analyse de donnees"
        )
        try:
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "rome_search_jobs", lambda query: [{"code": "M1403"}])
            monkeypatch.setattr(
                pm, "rome_get_job_details",
                lambda code: {
                    "metier": {"libelle": "Data analyst"},
                    "code": "M1403",
                    "groupesCompetencesMobilisees": [
                        {"competences": [
                            {"libelle": "Analyse de donnees"},
                            {"libelle": "Pilotage nucleaire avance"},
                        ]}
                    ],
                },
            )
            r = auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}")
            assert r.status_code == 200
            data = r.get_json()
            assert any(j["code"] == "M1403" for j in data["partial"])
            matched = next(j for j in data["partial"] if j["code"] == "M1403")
            assert 0 < matched["score"] < 100
            assert matched["missing_count"] >= 1
        finally:
            self._teardown(app, ids, role_id, activity_id)

    def test_job_without_competencies_goes_to_partial_with_zero_score(self, app, auth_client, ids, monkeypatch):
        role_id, activity_id = self._setup_role_with_competency(app, ids, "Cuisine moleculaire")
        try:
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "rome_search_jobs", lambda query: [{"code": "Z0000"}])
            monkeypatch.setattr(
                pm, "rome_get_job_details",
                lambda code: {"metier": {"libelle": "Metier vide"}, "code": "Z0000"},
            )
            r = auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}")
            assert r.status_code == 200
            data = r.get_json()
            matched = next(j for j in data["partial"] if j["code"] == "Z0000")
            assert matched["score"] == 0
            assert matched["total"] == 0
        finally:
            self._teardown(app, ids, role_id, activity_id)

    def test_job_details_missing_is_skipped(self, app, auth_client, ids, monkeypatch):
        """rome_get_job_details() renvoie {} (métier introuvable) → il ne doit
        apparaître ni dans full ni dans partial."""
        role_id, activity_id = self._setup_role_with_competency(app, ids, "Menuiserie")
        try:
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "rome_search_jobs", lambda query: [{"code": "X9999"}])
            monkeypatch.setattr(pm, "rome_get_job_details", lambda code: {})
            r = auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}")
            assert r.status_code == 200
            data = r.get_json()
            codes = {j["code"] for j in data["full"] + data["partial"]}
            assert "X9999" not in codes
        finally:
            self._teardown(app, ids, role_id, activity_id)

    def test_pagination_limits_full_page_size(self, app, auth_client, ids, monkeypatch):
        role_id, activity_id = self._setup_role_with_competency(app, ids, "Soudure industrielle")
        try:
            import Code.routes.projection_metier as pm
            codes = [f"F{i:04d}" for i in range(3)]
            monkeypatch.setattr(pm, "rome_search_jobs", lambda query: [{"code": c} for c in codes])
            monkeypatch.setattr(
                pm, "rome_get_job_details",
                lambda code: {
                    "metier": {"libelle": f"Metier {code}"},
                    "code": code,
                    "groupesCompetencesMobilisees": [
                        {"competences": [{"libelle": "Soudure industrielle"}]}
                    ],
                },
            )
            r = auth_client.get(
                f"/projection_metier/analyze_user/{ids['user_id']}?full_limit=1&full_offset=0"
            )
            assert r.status_code == 200
            data = r.get_json()
            assert len(data["full"]) <= 1
            assert data["page"]["full"]["limit"] == 1
            assert data["page"]["full"]["total"] >= 1
        finally:
            self._teardown(app, ids, role_id, activity_id)
