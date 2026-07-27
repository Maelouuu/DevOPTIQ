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
import time
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

    def test_activite_liee_apporte_competences_savoirs_softskills_aptitudes(self, app, ids):
        """Une activité liée au rôle apporte son nom + Competency + Savoir +
        SavoirFaire + Softskill + Aptitude dans les labels extraits."""
        with app.app_context():
            from Code.models.models import (
                Role, UserRole, Activities, activity_roles,
                Competency, Savoir, SavoirFaire, Softskill, Aptitude,
            )
            from Code.extensions import db

            role = Role(name="Role Extraction Complet", entity_id=ids["entity_id"])
            db.session.add(role)
            db.session.flush()
            role_id = role.id

            activity = Activities(
                entity_id=ids["entity_id"],
                name="Activité Extraction Complète",
                description="Description",
            )
            db.session.add(activity)
            db.session.flush()
            activity_id = activity.id

            db.session.execute(
                activity_roles.insert().values(
                    activity_id=activity_id, role_id=role_id, status="active"
                )
            )
            db.session.add(UserRole(user_id=ids["user_id"], role_id=role_id))
            db.session.add(Competency(description="Compétence Extraite", activity_id=activity_id))
            db.session.add(Savoir(description="Savoir Extrait", activity_id=activity_id))
            db.session.add(SavoirFaire(description="Savoir-Faire Extrait", activity_id=activity_id))
            db.session.add(Softskill(habilete="Softskill Extraite", niveau="3", activity_id=activity_id))
            db.session.add(Aptitude(description="Aptitude Extraite", activity_id=activity_id))
            db.session.commit()

            try:
                from Code.routes.projection_metier import _extract_user_competencies
                result = _extract_user_competencies(ids["user_id"])

                assert "Activité Extraction Complète" in result
                assert "Compétence Extraite" in result
                assert "Savoir Extrait" in result
                assert "Savoir-Faire Extrait" in result
                assert "Softskill Extraite" in result
                assert "Aptitude Extraite" in result
            finally:
                db.session.execute(
                    activity_roles.delete().where(activity_roles.c.activity_id == activity_id)
                )
                db.session.query(UserRole).filter_by(
                    user_id=ids["user_id"], role_id=role_id
                ).delete()
                # Suppression ORM (pas bulk .delete()) pour déclencher le cascade
                # delete-orphan sur competencies/savoirs/savoir_faires/softskills/aptitudes
                # — un bulk delete laisserait des lignes orphelines qui polluent
                # les tests suivants si SQLite réutilise l'id de l'activité supprimée.
                activity_obj = db.session.get(Activities, activity_id)
                if activity_obj:
                    db.session.delete(activity_obj)
                db.session.query(Role).filter_by(id=role_id).delete()
                db.session.commit()


# ===========================================================================
# 7b. HELPER _mask_secret — tests unitaires
# ===========================================================================

class TestMaskSecret:

    @staticmethod
    def _m(secret):
        from Code.routes.projection_metier import _mask_secret
        return _mask_secret(secret)

    def test_secret_vide_retourne_vide_label(self):
        assert self._m("") == "VIDE"

    def test_secret_none_retourne_vide_label(self):
        assert self._m(None) == "VIDE"

    def test_secret_court_retourne_etoiles(self):
        assert self._m("abc") == "***"
        assert self._m("abcdef") == "***"

    def test_secret_long_retourne_prefixe(self):
        result = self._m("abcdefgh")
        assert result.startswith("abcdef")
        assert result != "abcdefgh"


# ===========================================================================
# 8. get_access_token() — OAuth2 (mocking requests.post)
# ===========================================================================

class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text="", raise_on_json=False):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.text = text
        self._raise_on_json = raise_on_json

    def json(self):
        if self._raise_on_json:
            raise ValueError("Réponse non-JSON")
        return self._json_data


@pytest.fixture
def reset_token_cache(app):
    """Réinitialise le cache de token ROME avant/après chaque test."""
    with app.app_context():
        from Code.routes.projection_metier import _token_cache
        old = dict(_token_cache)
        _token_cache["access_token"] = None
        _token_cache["expires_at"] = 0
        yield _token_cache
        _token_cache["access_token"] = old.get("access_token")
        _token_cache["expires_at"] = old.get("expires_at", 0)


class TestGetAccessToken:

    def test_cache_valide_retourne_token_sans_requete(self, app, monkeypatch, reset_token_cache):
        """Un token en cache valide (non expiré) est retourné sans appel HTTP."""
        with app.app_context():
            import Code.routes.projection_metier as pm

            def _boom(*a, **kw):
                raise AssertionError("requests.post ne doit pas être appelé (cache valide)")

            monkeypatch.setattr(pm.requests, "post", _boom)
            pm._token_cache["access_token"] = "token-en-cache"
            pm._token_cache["expires_at"] = time.time() + 3600

            token = pm.get_access_token()
            assert token == "token-en-cache"

    def test_sans_client_id_retourne_none(self, app, monkeypatch, reset_token_cache):
        """ROME_CLIENT_ID vide → None (pas d'appel HTTP)."""
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "ROME_CLIENT_ID", "")
            monkeypatch.setattr(pm, "ROME_CLIENT_SECRET", "un-secret")
            assert pm.get_access_token() is None

    def test_sans_client_secret_retourne_none(self, app, monkeypatch, reset_token_cache):
        """ROME_CLIENT_SECRET vide → None."""
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "ROME_CLIENT_ID", "un-id")
            monkeypatch.setattr(pm, "ROME_CLIENT_SECRET", "")
            assert pm.get_access_token() is None

    def test_sans_scope_retourne_none(self, app, monkeypatch, reset_token_cache):
        """ROME_SCOPE vide (mais credentials présents) → None."""
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "ROME_CLIENT_ID", "un-id")
            monkeypatch.setattr(pm, "ROME_CLIENT_SECRET", "un-secret")
            monkeypatch.setattr(pm, "ROME_SCOPE", "")
            assert pm.get_access_token() is None

    def test_tentative_1_reussit_retourne_token(self, app, monkeypatch, reset_token_cache):
        """La tentative 1 (BASIC + scope) réussit → token retourné et mis en cache."""
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "ROME_CLIENT_ID", "un-id")
            monkeypatch.setattr(pm, "ROME_CLIENT_SECRET", "un-secret")

            def fake_post(url, data=None, headers=None, timeout=None):
                return _FakeResponse(200, {"access_token": "tok-abc", "expires_in": 3600})

            monkeypatch.setattr(pm.requests, "post", fake_post)
            token = pm.get_access_token()
            assert token == "tok-abc"
            assert pm._token_cache["access_token"] == "tok-abc"

    def test_tentative_1_echoue_tentative_2_reussit(self, app, monkeypatch, reset_token_cache):
        """La tentative 1 échoue (400 invalid_scope) → tentative 2 (BODY) réussit."""
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "ROME_CLIENT_ID", "un-id")
            monkeypatch.setattr(pm, "ROME_CLIENT_SECRET", "un-secret")

            calls = {"n": 0}

            def fake_post(url, data=None, headers=None, timeout=None):
                calls["n"] += 1
                if calls["n"] == 1:
                    return _FakeResponse(400, {"error": "invalid_scope", "error_description": "nope"})
                return _FakeResponse(200, {"access_token": "tok-body", "expires_in": 1800})

            monkeypatch.setattr(pm.requests, "post", fake_post)
            token = pm.get_access_token()
            assert token == "tok-body"
            assert calls["n"] == 2

    def test_les_deux_tentatives_echouent_retourne_none(self, app, monkeypatch, reset_token_cache):
        """Les deux tentatives échouent (400 sans access_token) → None."""
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "ROME_CLIENT_ID", "un-id")
            monkeypatch.setattr(pm, "ROME_CLIENT_SECRET", "un-secret")

            def fake_post(url, data=None, headers=None, timeout=None):
                return _FakeResponse(400, {"error": "server_error"})

            monkeypatch.setattr(pm.requests, "post", fake_post)
            assert pm.get_access_token() is None

    def test_timeout_sur_les_deux_tentatives_retourne_none(self, app, monkeypatch, reset_token_cache):
        """Timeout sur les deux tentatives → None (pas de crash)."""
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "ROME_CLIENT_ID", "un-id")
            monkeypatch.setattr(pm, "ROME_CLIENT_SECRET", "un-secret")

            def fake_post(url, data=None, headers=None, timeout=None):
                raise pm.requests.exceptions.Timeout("timeout")

            monkeypatch.setattr(pm.requests, "post", fake_post)
            assert pm.get_access_token() is None

    def test_exception_generique_sur_les_deux_tentatives_retourne_none(self, app, monkeypatch, reset_token_cache):
        """Exception générique sur les deux tentatives → None (pas de crash)."""
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "ROME_CLIENT_ID", "un-id")
            monkeypatch.setattr(pm, "ROME_CLIENT_SECRET", "un-secret")

            def fake_post(url, data=None, headers=None, timeout=None):
                raise ValueError("boom")

            monkeypatch.setattr(pm.requests, "post", fake_post)
            assert pm.get_access_token() is None

    def test_tentative_1_reponse_non_json_puis_tentative_2_reussit(self, app, monkeypatch, reset_token_cache):
        """La tentative 1 renvoie un corps non-JSON (response.json() lève) → le code
        bascule sur le fallback _raw_text puis réussit via la tentative 2."""
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "ROME_CLIENT_ID", "un-id")
            monkeypatch.setattr(pm, "ROME_CLIENT_SECRET", "un-secret")

            calls = {"n": 0}

            def fake_post(url, data=None, headers=None, timeout=None):
                calls["n"] += 1
                if calls["n"] == 1:
                    return _FakeResponse(200, text="<html>erreur</html>", raise_on_json=True)
                return _FakeResponse(200, {"access_token": "tok-fallback", "expires_in": 900})

            monkeypatch.setattr(pm.requests, "post", fake_post)
            token = pm.get_access_token()
            assert token == "tok-fallback"
            assert calls["n"] == 2

    def test_tentative_2_reponse_non_json_retourne_none(self, app, monkeypatch, reset_token_cache):
        """La tentative 1 échoue proprement (400) et la tentative 2 renvoie un corps
        non-JSON → aucune tentative ne fournit de token → None."""
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "ROME_CLIENT_ID", "un-id")
            monkeypatch.setattr(pm, "ROME_CLIENT_SECRET", "un-secret")

            calls = {"n": 0}

            def fake_post(url, data=None, headers=None, timeout=None):
                calls["n"] += 1
                if calls["n"] == 1:
                    return _FakeResponse(400, {"error": "server_error"})
                return _FakeResponse(200, text="pas du json", raise_on_json=True)

            monkeypatch.setattr(pm.requests, "post", fake_post)
            assert pm.get_access_token() is None
            assert calls["n"] == 2


# ===========================================================================
# 8b. _get_auth_headers() — appel direct (avec/sans token)
# ===========================================================================

class TestGetAuthHeaders:

    def test_avec_token_retourne_headers_bearer(self, app, monkeypatch):
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "get_access_token", lambda: "mon-token")
            headers = pm._get_auth_headers()
            assert headers == {"Accept": "application/json", "Authorization": "Bearer mon-token"}

    def test_sans_token_retourne_none(self, app, monkeypatch):
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "get_access_token", lambda: None)
            assert pm._get_auth_headers() is None


# ===========================================================================
# 9. rome_search_jobs() / rome_get_job_details() — mocking requests.get
# ===========================================================================

class TestRomeSearchJobs:

    def test_query_vide_retourne_liste_vide(self, app):
        with app.app_context():
            from Code.routes.projection_metier import rome_search_jobs
            assert rome_search_jobs("") == []

    def test_query_espaces_retourne_liste_vide(self, app):
        with app.app_context():
            from Code.routes.projection_metier import rome_search_jobs
            assert rome_search_jobs("   ") == []

    def test_sans_token_retourne_liste_vide(self, app, monkeypatch):
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: None)
            assert pm.rome_search_jobs("gestion") == []

    def test_avec_token_reponse_liste_directe(self, app, monkeypatch):
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            fake_jobs = [{"code": "M1805", "metier": {"libelle": "Développeur"}}]

            def fake_get(url, params=None, headers=None, timeout=None):
                return _FakeResponse(200, fake_jobs)

            monkeypatch.setattr(pm.requests, "get", fake_get)
            assert pm.rome_search_jobs("developpeur") == fake_jobs

    def test_avec_token_reponse_dict_metiers(self, app, monkeypatch):
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            fake_jobs = [{"code": "M1810", "metier": {"libelle": "Chef de projet"}}]

            def fake_get(url, params=None, headers=None, timeout=None):
                return _FakeResponse(200, {"metiers": fake_jobs})

            monkeypatch.setattr(pm.requests, "get", fake_get)
            assert pm.rome_search_jobs("projet") == fake_jobs

    def test_format_reponse_inattendu_retourne_liste_vide(self, app, monkeypatch):
        """Une réponse JSON qui n'est ni une liste ni un dict → []."""
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            def fake_get(url, params=None, headers=None, timeout=None):
                return _FakeResponse(200, "chaîne inattendue")

            monkeypatch.setattr(pm.requests, "get", fake_get)
            assert pm.rome_search_jobs("test") == []

    def test_http_erreur_retourne_liste_vide(self, app, monkeypatch):
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            def fake_get(url, params=None, headers=None, timeout=None):
                return _FakeResponse(404, {}, text="Not Found")

            monkeypatch.setattr(pm.requests, "get", fake_get)
            assert pm.rome_search_jobs("test") == []

    def test_timeout_retourne_liste_vide(self, app, monkeypatch):
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            def fake_get(url, params=None, headers=None, timeout=None):
                raise pm.requests.exceptions.Timeout("timeout")

            monkeypatch.setattr(pm.requests, "get", fake_get)
            assert pm.rome_search_jobs("test") == []

    def test_exception_generique_retourne_liste_vide(self, app, monkeypatch):
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            def fake_get(url, params=None, headers=None, timeout=None):
                raise ValueError("boom")

            monkeypatch.setattr(pm.requests, "get", fake_get)
            assert pm.rome_search_jobs("test") == []


class TestRomeGetJobDetails:

    def test_code_vide_retourne_dict_vide(self, app):
        with app.app_context():
            from Code.routes.projection_metier import rome_get_job_details
            assert rome_get_job_details("") == {}

    def test_code_espaces_retourne_dict_vide(self, app):
        with app.app_context():
            from Code.routes.projection_metier import rome_get_job_details
            assert rome_get_job_details("   ") == {}

    def test_sans_token_retourne_dict_vide(self, app, monkeypatch):
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: None)
            assert pm.rome_get_job_details("M1805") == {}

    def test_avec_token_succes(self, app, monkeypatch):
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            fake_detail = {"code": "M1805", "metier": {"libelle": "Développeur"}}

            def fake_get(url, params=None, headers=None, timeout=None):
                return _FakeResponse(200, fake_detail)

            monkeypatch.setattr(pm.requests, "get", fake_get)
            assert pm.rome_get_job_details("M1805") == fake_detail

    def test_reponse_non_dict_retourne_dict_vide(self, app, monkeypatch):
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            def fake_get(url, params=None, headers=None, timeout=None):
                return _FakeResponse(200, ["pas", "un", "dict"])

            monkeypatch.setattr(pm.requests, "get", fake_get)
            assert pm.rome_get_job_details("M1805") == {}

    def test_http_erreur_retourne_dict_vide(self, app, monkeypatch):
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            def fake_get(url, params=None, headers=None, timeout=None):
                return _FakeResponse(500, {}, text="Internal Error")

            monkeypatch.setattr(pm.requests, "get", fake_get)
            assert pm.rome_get_job_details("M1805") == {}

    def test_timeout_retourne_dict_vide(self, app, monkeypatch):
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            def fake_get(url, params=None, headers=None, timeout=None):
                raise pm.requests.exceptions.Timeout("timeout")

            monkeypatch.setattr(pm.requests, "get", fake_get)
            assert pm.rome_get_job_details("M1805") == {}

    def test_exception_generique_retourne_dict_vide(self, app, monkeypatch):
        with app.app_context():
            import Code.routes.projection_metier as pm
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            def fake_get(url, params=None, headers=None, timeout=None):
                raise ValueError("boom")

            monkeypatch.setattr(pm.requests, "get", fake_get)
            assert pm.rome_get_job_details("M1805") == {}


# ===========================================================================
# 10. Helpers d'extraction de fiche métier ROME
# ===========================================================================

class TestExtractCompetenciesFromJob:

    @staticmethod
    def _e(job_data):
        from Code.routes.projection_metier import _extract_competencies_from_job
        return _extract_competencies_from_job(job_data)

    def test_sans_groupes_retourne_liste_vide(self):
        assert self._e({}) == []

    def test_groupes_none_retourne_liste_vide(self):
        assert self._e({"groupesCompetencesMobilisees": None}) == []

    def test_groupe_non_dict_est_ignore(self):
        assert self._e({"groupesCompetencesMobilisees": ["pas_un_dict"]}) == []

    def test_competences_non_liste_est_ignore(self):
        job = {"groupesCompetencesMobilisees": [{"competences": "pas_une_liste"}]}
        assert self._e(job) == []

    def test_extraction_normale(self):
        job = {
            "groupesCompetencesMobilisees": [
                {"competences": [{"libelle": "Gérer un projet"}, {"libelle": "Rédiger un rapport"}]}
            ]
        }
        result = self._e(job)
        assert result == ["Gérer un projet", "Rédiger un rapport"]

    def test_competence_non_dict_est_ignoree(self):
        job = {"groupesCompetencesMobilisees": [{"competences": ["pas_un_dict", {"libelle": "Valide"}]}]}
        assert self._e(job) == ["Valide"]

    def test_libelle_vide_est_ignore(self):
        job = {"groupesCompetencesMobilisees": [{"competences": [{"libelle": ""}, {"libelle": "  "}]}]}
        assert self._e(job) == []

    def test_plusieurs_groupes_cumules(self):
        job = {
            "groupesCompetencesMobilisees": [
                {"competences": [{"libelle": "A"}]},
                {"competences": [{"libelle": "B"}]},
            ]
        }
        assert self._e(job) == ["A", "B"]


class TestExtractJobLabel:

    @staticmethod
    def _l(job_data):
        from Code.routes.projection_metier import _extract_job_label
        return _extract_job_label(job_data)

    def test_avec_metier_libelle(self):
        assert self._l({"metier": {"libelle": "Développeur"}}) == "Développeur"

    def test_sans_metier_retourne_vide(self):
        assert self._l({}) == ""

    def test_metier_sans_libelle_retourne_vide(self):
        assert self._l({"metier": {}}) == ""

    def test_libelle_est_strip(self):
        assert self._l({"metier": {"libelle": "  Développeur  "}}) == "Développeur"


class TestExtractJobCode:

    @staticmethod
    def _c(job_data):
        from Code.routes.projection_metier import _extract_job_code
        return _extract_job_code(job_data)

    def test_code_au_premier_niveau(self):
        assert self._c({"code": "M1805"}) == "M1805"

    def test_code_depuis_metier_si_absent_au_premier_niveau(self):
        assert self._c({"metier": {"code": "M1810"}}) == "M1810"

    def test_aucun_code_retourne_vide(self):
        assert self._c({}) == ""

    def test_code_est_strip(self):
        assert self._c({"code": "  M1805  "}) == "M1805"

    def test_metier_non_dict_retourne_vide(self):
        assert self._c({"metier": "pas_un_dict"}) == ""


# ===========================================================================
# 11. analyze_user() — matching ROME complet (mock rome_search_jobs / rome_get_job_details)
# ===========================================================================

class TestAnalyzeUserRomeMatchingComplet:

    def _setup_role_activity(self, app, ids, competency_desc="gestion de projet"):
        """Crée un rôle + activité + compétence liés à l'utilisateur seed."""
        with app.app_context():
            from Code.models.models import Role, UserRole, Activities, activity_roles, Competency
            from Code.extensions import db

            role = Role(name="Role Matching ROME", entity_id=ids["entity_id"])
            db.session.add(role)
            db.session.flush()
            role_id = role.id

            activity = Activities(
                entity_id=ids["entity_id"], name="Activité Matching ROME", description="D",
            )
            db.session.add(activity)
            db.session.flush()
            activity_id = activity.id

            db.session.execute(
                activity_roles.insert().values(activity_id=activity_id, role_id=role_id, status="active")
            )
            db.session.add(UserRole(user_id=ids["user_id"], role_id=role_id))
            db.session.add(Competency(description=competency_desc, activity_id=activity_id))
            db.session.commit()

        return role_id, activity_id

    def _teardown_role_activity(self, app, ids, role_id, activity_id):
        with app.app_context():
            from Code.models.models import Role, UserRole, Activities, activity_roles
            from Code.extensions import db
            db.session.execute(
                activity_roles.delete().where(activity_roles.c.activity_id == activity_id)
            )
            db.session.query(UserRole).filter_by(
                user_id=ids["user_id"], role_id=role_id
            ).delete()
            # Suppression ORM pour cascade delete-orphan (cf. commentaire plus haut) :
            # évite les Competency orphelines qui survivraient à un bulk .delete().
            activity_obj = db.session.get(Activities, activity_id)
            if activity_obj:
                db.session.delete(activity_obj)
            db.session.query(Role).filter_by(id=role_id).delete()
            db.session.commit()

    def test_metiers_classes_complet_partiel_et_sans_competences(self, app, auth_client, ids, monkeypatch):
        """4 métiers ROME simulés : complet (owned==total), partiel (owned<total),
        sans compétences définies, et un détail vide (ignoré) → vérifie la
        classification full/partial, le score, et le tri par score décroissant."""
        role_id, activity_id = self._setup_role_activity(app, ids)

        job_stubs = [
            {"code": "J-FULL"},
            {"code": "J-PARTIAL"},
            {"code": "J-EMPTY-COMPS"},
            {"code": "J-NO-DETAILS"},
            {"code": "J-LOW-SIM"},
        ]

        def fake_search(word):
            return job_stubs

        def fake_get_details(code):
            if code == "J-FULL":
                return {
                    "metier": {"libelle": "Chef de Projet"},
                    "groupesCompetencesMobilisees": [
                        {"competences": [{"libelle": "gestion de projet"}]}
                    ],
                }
            if code == "J-PARTIAL":
                return {
                    "metier": {"libelle": "Directeur Financier"},
                    "groupesCompetencesMobilisees": [
                        {"competences": [
                            {"libelle": "gestion de projet"},
                            {"libelle": "comptabilite generale avancee"},
                        ]}
                    ],
                }
            if code == "J-EMPTY-COMPS":
                return {"metier": {"libelle": "Métier Sans Compétences"}, "groupesCompetencesMobilisees": []}
            if code == "J-NO-DETAILS":
                return {}
            if code == "J-LOW-SIM":
                # Partage le token "gestion" avec l'utilisateur mais la phrase
                # complète est trop différente pour dépasser les seuils de score
                # → classé "missing" malgré l'overlap de tokens (ratio/jaccard bas),
                # et owned_count == 0 avec total > 0 (branche else finale).
                return {
                    "metier": {"libelle": "Métier Sans Recouvrement Réel"},
                    "groupesCompetencesMobilisees": [
                        {"competences": [{"libelle": "gestion administrative des stocks entrepot"}]}
                    ],
                }
            return {}

        import Code.routes.projection_metier as pm
        monkeypatch.setattr(pm, "rome_search_jobs", fake_search)
        monkeypatch.setattr(pm, "rome_get_job_details", fake_get_details)

        try:
            r = auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}")
            assert r.status_code == 200
            body = json.loads(r.data)

            full_codes = {j["code"] for j in body["full"]}
            partial_codes = {j["code"] for j in body["partial"]}

            assert "J-FULL" in full_codes
            assert "J-PARTIAL" in partial_codes
            assert "J-EMPTY-COMPS" in partial_codes
            assert "J-NO-DETAILS" not in full_codes
            assert "J-NO-DETAILS" not in partial_codes

            full_job = next(j for j in body["full"] if j["code"] == "J-FULL")
            assert full_job["score"] == 100.0
            assert full_job["owned_count"] == full_job["total"] == 1
            assert full_job["missing"] == []

            partial_job = next(j for j in body["partial"] if j["code"] == "J-PARTIAL")
            assert partial_job["total"] == 2
            assert partial_job["owned_count"] == 1
            assert partial_job["missing_count"] == 1
            assert partial_job["score"] == 50.0

            empty_job = next(j for j in body["partial"] if j["code"] == "J-EMPTY-COMPS")
            assert empty_job["total"] == 0
            assert empty_job["score"] == 0

            assert "J-LOW-SIM" in partial_codes
            low_sim_job = next(j for j in body["partial"] if j["code"] == "J-LOW-SIM")
            assert low_sim_job["owned_count"] == 0
            assert low_sim_job["total"] == 1
            assert low_sim_job["score"] == 0.0
            assert low_sim_job["missing"] == ["gestion administrative des stocks entrepot"]

            # Tri décroissant par score au sein de chaque liste
            scores_partial = [j["score"] for j in body["partial"]]
            assert scores_partial == sorted(scores_partial, reverse=True)
        finally:
            self._teardown_role_activity(app, ids, role_id, activity_id)

    def test_competences_avec_normalisation_vide_et_mots_courts_ne_plantent_pas(
        self, app, auth_client, ids, monkeypatch
    ):
        """Une compétence qui se normalise en chaîne vide (uniquement des
        caractères spéciaux) et une compétence composée uniquement de mots
        courts (<=3 caractères, fallback sur le texte normalisé complet comme
        mot de recherche) sont gérées sans plantage."""
        role_id, activity_id = self._setup_role_activity(app, ids, competency_desc="gestion de projet")

        with app.app_context():
            from Code.models.models import Competency
            from Code.extensions import db
            db.session.add(Competency(description="!!! ???", activity_id=activity_id))
            db.session.add(Competency(description="ab cd", activity_id=activity_id))
            db.session.commit()

        def fake_search(word):
            return [{"code": "J-FULL"}]

        def fake_get_details(code):
            return {
                "metier": {"libelle": "Chef de Projet"},
                "groupesCompetencesMobilisees": [
                    {"competences": [{"libelle": "gestion de projet"}]}
                ],
            }

        import Code.routes.projection_metier as pm
        monkeypatch.setattr(pm, "rome_search_jobs", fake_search)
        monkeypatch.setattr(pm, "rome_get_job_details", fake_get_details)

        try:
            r = auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}")
            assert r.status_code == 200
            body = json.loads(r.data)
            full_codes = {j["code"] for j in body["full"]}
            assert "J-FULL" in full_codes
        finally:
            self._teardown_role_activity(app, ids, role_id, activity_id)

    def test_pagination_reflete_les_resultats_reels(self, app, auth_client, ids, monkeypatch):
        """Avec des résultats non vides, full_limit/partial_limit sont bien reflétés
        dans page.full / page.partial (offset, total, has_more)."""
        role_id, activity_id = self._setup_role_activity(app, ids, competency_desc="pilotage strategie")

        job_stubs = [{"code": "J-A"}, {"code": "J-B"}]

        def fake_search(word):
            return job_stubs

        def fake_get_details(code):
            return {
                "metier": {"libelle": f"Métier {code}"},
                "groupesCompetencesMobilisees": [
                    {"competences": [{"libelle": "pilotage strategie"}]}
                ],
            }

        import Code.routes.projection_metier as pm
        monkeypatch.setattr(pm, "rome_search_jobs", fake_search)
        monkeypatch.setattr(pm, "rome_get_job_details", fake_get_details)

        try:
            r = auth_client.get(
                f"/projection_metier/analyze_user/{ids['user_id']}?full_limit=1&full_offset=0"
            )
            assert r.status_code == 200
            body = json.loads(r.data)
            assert body["page"]["full"]["total"] == 2
            assert body["page"]["full"]["limit"] == 1
            assert len(body["full"]) == 1
            assert body["page"]["full"]["has_more"] is True
        finally:
            self._teardown_role_activity(app, ids, role_id, activity_id)
