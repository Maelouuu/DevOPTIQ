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

    def test_extrait_savoirs_savoir_faires_softskills_aptitudes(self, app, ids):
        """Les 4 types de compétences liées à l'activité sont bien extraits en labels."""
        from Code.models.models import Role, UserRole, Activities, Savoir, SavoirFaire, Softskill, Aptitude, activity_roles
        from Code.extensions import db
        with app.app_context():
            role = Role(name="Role Savoirs Test", entity_id=ids["entity_id"])
            db.session.add(role)
            db.session.flush()
            activity = Activities(entity_id=ids["entity_id"], name="Activite Savoirs Test", description="d")
            db.session.add(activity)
            db.session.flush()
            savoir = Savoir(activity_id=activity.id, description="Connaissance réglementaire")
            sf = SavoirFaire(activity_id=activity.id, description="Savoir-faire technique")
            ss = Softskill(activity_id=activity.id, habilete="Communication", niveau="3")
            apt = Aptitude(activity_id=activity.id, description="Rigueur")
            db.session.add_all([savoir, sf, ss, apt])
            db.session.execute(activity_roles.insert().values(
                activity_id=activity.id, role_id=role.id, status="actif", required_mastery_level=None,
            ))
            db.session.add(UserRole(user_id=ids["user_id"], role_id=role.id))
            db.session.commit()
            role_id, activity_id = role.id, activity.id

            try:
                from Code.routes.projection_metier import _extract_user_competencies
                result = _extract_user_competencies(ids["user_id"])
                assert "Connaissance réglementaire" in result
                assert "Savoir-faire technique" in result
                assert "Communication" in result
                assert "Rigueur" in result
            finally:
                db.session.query(UserRole).filter_by(user_id=ids["user_id"], role_id=role_id).delete()
                db.session.execute(activity_roles.delete().where(activity_roles.c.role_id == role_id))
                db.session.query(Savoir).filter_by(activity_id=activity_id).delete()
                db.session.query(SavoirFaire).filter_by(activity_id=activity_id).delete()
                db.session.query(Softskill).filter_by(activity_id=activity_id).delete()
                db.session.query(Aptitude).filter_by(activity_id=activity_id).delete()
                db.session.query(Activities).filter_by(id=activity_id).delete()
                db.session.query(Role).filter_by(id=role_id).delete()
                db.session.commit()


# ===========================================================================
# 8. get_access_token — OAuth2 (requests mockés, aucun appel réseau réel)
# ===========================================================================

class TestGetAccessToken:

    @staticmethod
    def _reset_cache():
        import Code.routes.projection_metier as pm
        pm._token_cache["access_token"] = None
        pm._token_cache["expires_at"] = 0

    def test_pas_de_client_id_retourne_none(self, app, monkeypatch):
        import Code.routes.projection_metier as pm
        with app.app_context():
            self._reset_cache()
            monkeypatch.setattr(pm, "ROME_CLIENT_ID", "")
            monkeypatch.setattr(pm, "ROME_CLIENT_SECRET", "secret")
            result = pm.get_access_token()
        assert result is None
        self._reset_cache()

    def test_pas_de_scope_retourne_none(self, app, monkeypatch):
        import Code.routes.projection_metier as pm
        with app.app_context():
            self._reset_cache()
            monkeypatch.setattr(pm, "ROME_CLIENT_ID", "id")
            monkeypatch.setattr(pm, "ROME_CLIENT_SECRET", "secret")
            monkeypatch.setattr(pm, "ROME_SCOPE", "")
            result = pm.get_access_token()
        assert result is None
        self._reset_cache()

    def test_token_en_cache_valide_evite_appel_http(self, app, monkeypatch):
        import time
        import Code.routes.projection_metier as pm
        with app.app_context():
            pm._token_cache["access_token"] = "cached-token"
            pm._token_cache["expires_at"] = time.time() + 3600

            def fail_post(*a, **k):
                raise AssertionError("requests.post ne doit pas être appelé (cache valide)")

            monkeypatch.setattr(pm.requests, "post", fail_post)
            result = pm.get_access_token()
        assert result == "cached-token"
        self._reset_cache()

    def test_tentative1_succes_retourne_et_cache_le_token(self, app, monkeypatch):
        import Code.routes.projection_metier as pm
        with app.app_context():
            self._reset_cache()
            monkeypatch.setattr(pm, "ROME_CLIENT_ID", "id")
            monkeypatch.setattr(pm, "ROME_CLIENT_SECRET", "secret")
            monkeypatch.setattr(pm, "ROME_SCOPE", "scope")

            class FakeResp:
                status_code = 200
                text = ""
                def json(self):
                    return {"access_token": "tok-1", "expires_in": 1000}

            monkeypatch.setattr(pm.requests, "post", lambda *a, **k: FakeResp())
            result = pm.get_access_token()
        assert result == "tok-1"
        assert pm._token_cache["access_token"] == "tok-1"
        self._reset_cache()

    def test_tentative1_erreur_400_bascule_sur_tentative2(self, app, monkeypatch):
        import Code.routes.projection_metier as pm
        with app.app_context():
            self._reset_cache()
            monkeypatch.setattr(pm, "ROME_CLIENT_ID", "id")
            monkeypatch.setattr(pm, "ROME_CLIENT_SECRET", "secret")
            monkeypatch.setattr(pm, "ROME_SCOPE", "scope")

            calls = {"n": 0}

            class FakeResp400:
                status_code = 400
                text = ""
                def json(self):
                    return {"error": "invalid_scope", "error_description": "bad scope"}

            class FakeResp200:
                status_code = 200
                text = ""
                def json(self):
                    return {"access_token": "tok-2", "expires_in": 500}

            def fake_post(*a, **k):
                calls["n"] += 1
                return FakeResp400() if calls["n"] == 1 else FakeResp200()

            monkeypatch.setattr(pm.requests, "post", fake_post)
            result = pm.get_access_token()
        assert result == "tok-2"
        assert calls["n"] == 2
        self._reset_cache()

    def test_timeout_tentative1_bascule_sur_tentative2(self, app, monkeypatch):
        import requests as real_requests
        import Code.routes.projection_metier as pm
        with app.app_context():
            self._reset_cache()
            monkeypatch.setattr(pm, "ROME_CLIENT_ID", "id")
            monkeypatch.setattr(pm, "ROME_CLIENT_SECRET", "secret")
            monkeypatch.setattr(pm, "ROME_SCOPE", "scope")

            calls = {"n": 0}

            class FakeResp200:
                status_code = 200
                text = ""
                def json(self):
                    return {"access_token": "tok-3", "expires_in": 500}

            def fake_post(*a, **k):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise real_requests.exceptions.Timeout()
                return FakeResp200()

            monkeypatch.setattr(pm.requests, "post", fake_post)
            result = pm.get_access_token()
        assert result == "tok-3"
        self._reset_cache()

    def test_toutes_tentatives_echouent_retourne_none(self, app, monkeypatch):
        import Code.routes.projection_metier as pm
        with app.app_context():
            self._reset_cache()
            monkeypatch.setattr(pm, "ROME_CLIENT_ID", "id")
            monkeypatch.setattr(pm, "ROME_CLIENT_SECRET", "secret")
            monkeypatch.setattr(pm, "ROME_SCOPE", "scope")

            class FakeResp500:
                status_code = 500
                text = "server error"
                def json(self):
                    raise ValueError("not json")

            monkeypatch.setattr(pm.requests, "post", lambda *a, **k: FakeResp500())
            result = pm.get_access_token()
        assert result is None
        self._reset_cache()

    def test_les_deux_tentatives_leve_exception_generique_retourne_none(self, app, monkeypatch):
        """Tentative 1 ET tentative 2 lèvent une exception générique → None, sans plantage."""
        import Code.routes.projection_metier as pm
        with app.app_context():
            self._reset_cache()
            monkeypatch.setattr(pm, "ROME_CLIENT_ID", "id")
            monkeypatch.setattr(pm, "ROME_CLIENT_SECRET", "secret")
            monkeypatch.setattr(pm, "ROME_SCOPE", "scope")

            def fake_post(*a, **k):
                raise ValueError("boom")

            monkeypatch.setattr(pm.requests, "post", fake_post)
            result = pm.get_access_token()
        assert result is None
        self._reset_cache()

    def test_exception_generique_tentative1_bascule_sur_tentative2(self, app, monkeypatch):
        import Code.routes.projection_metier as pm
        with app.app_context():
            self._reset_cache()
            monkeypatch.setattr(pm, "ROME_CLIENT_ID", "id")
            monkeypatch.setattr(pm, "ROME_CLIENT_SECRET", "secret")
            monkeypatch.setattr(pm, "ROME_SCOPE", "scope")

            calls = {"n": 0}

            class FakeResp200:
                status_code = 200
                text = ""
                def json(self):
                    return {"access_token": "tok-4", "expires_in": 500}

            def fake_post(*a, **k):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise ValueError("boom")
                return FakeResp200()

            monkeypatch.setattr(pm.requests, "post", fake_post)
            result = pm.get_access_token()
        assert result == "tok-4"
        self._reset_cache()


# ===========================================================================
# 8bis. _mask_secret
# ===========================================================================

class TestMaskSecret:

    @staticmethod
    def _m(secret):
        from Code.routes.projection_metier import _mask_secret
        return _mask_secret(secret)

    def test_secret_vide_retourne_vide_label(self):
        assert self._m("") == "VIDE"

    def test_secret_court_retourne_etoiles(self):
        assert self._m("abcdef") == "***"

    def test_secret_long_retourne_prefixe_masque(self):
        result = self._m("abcdefghijk")
        assert result.startswith("abcdef")
        assert "abcdefghijk" != result


# ===========================================================================
# 9. _get_auth_headers
# ===========================================================================

class TestGetAuthHeaders:

    def test_sans_token_retourne_none(self, app, monkeypatch):
        import Code.routes.projection_metier as pm
        with app.app_context():
            monkeypatch.setattr(pm, "get_access_token", lambda: None)
            result = pm._get_auth_headers()
        assert result is None

    def test_avec_token_retourne_header_bearer(self, app, monkeypatch):
        import Code.routes.projection_metier as pm
        with app.app_context():
            monkeypatch.setattr(pm, "get_access_token", lambda: "abc123")
            result = pm._get_auth_headers()
        assert result == {"Accept": "application/json", "Authorization": "Bearer abc123"}


# ===========================================================================
# 10. rome_search_jobs — appels HTTP mockés
# ===========================================================================

class TestRomeSearchJobs:

    def test_query_vide_retourne_liste_vide(self, app):
        import Code.routes.projection_metier as pm
        with app.app_context():
            assert pm.rome_search_jobs("") == []
            assert pm.rome_search_jobs("   ") == []

    def test_pas_de_headers_retourne_liste_vide(self, app, monkeypatch):
        import Code.routes.projection_metier as pm
        with app.app_context():
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: None)
            assert pm.rome_search_jobs("gestion") == []

    def test_reponse_liste_retournee_telle_quelle(self, app, monkeypatch):
        import Code.routes.projection_metier as pm
        with app.app_context():
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            class FakeResp:
                status_code = 200
                text = ""
                def json(self):
                    return [{"code": "M1805"}]

            monkeypatch.setattr(pm.requests, "get", lambda *a, **k: FakeResp())
            result = pm.rome_search_jobs("informatique")
        assert result == [{"code": "M1805"}]

    def test_reponse_dict_avec_cle_metiers(self, app, monkeypatch):
        import Code.routes.projection_metier as pm
        with app.app_context():
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            class FakeResp:
                status_code = 200
                text = ""
                def json(self):
                    return {"metiers": [{"code": "M1806"}]}

            monkeypatch.setattr(pm.requests, "get", lambda *a, **k: FakeResp())
            result = pm.rome_search_jobs("gestion")
        assert result == [{"code": "M1806"}]

    def test_reponse_json_forme_inattendue_retourne_liste_vide(self, app, monkeypatch):
        import Code.routes.projection_metier as pm
        with app.app_context():
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            class FakeResp:
                status_code = 200
                text = ""
                def json(self):
                    return "inattendu"

            monkeypatch.setattr(pm.requests, "get", lambda *a, **k: FakeResp())
            result = pm.rome_search_jobs("gestion")
        assert result == []

    def test_statut_non_200_retourne_liste_vide(self, app, monkeypatch):
        import Code.routes.projection_metier as pm
        with app.app_context():
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            class FakeResp:
                status_code = 500
                text = "error"

            monkeypatch.setattr(pm.requests, "get", lambda *a, **k: FakeResp())
            result = pm.rome_search_jobs("gestion")
        assert result == []

    def test_timeout_retourne_liste_vide(self, app, monkeypatch):
        import requests as real_requests
        import Code.routes.projection_metier as pm
        with app.app_context():
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            def fake_get(*a, **k):
                raise real_requests.exceptions.Timeout()

            monkeypatch.setattr(pm.requests, "get", fake_get)
            result = pm.rome_search_jobs("gestion")
        assert result == []

    def test_exception_generique_retourne_liste_vide(self, app, monkeypatch):
        import Code.routes.projection_metier as pm
        with app.app_context():
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            def fake_get(*a, **k):
                raise ValueError("boom")

            monkeypatch.setattr(pm.requests, "get", fake_get)
            result = pm.rome_search_jobs("gestion")
        assert result == []


# ===========================================================================
# 11. rome_get_job_details — appels HTTP mockés
# ===========================================================================

class TestRomeGetJobDetails:

    def test_code_vide_retourne_dict_vide(self, app):
        import Code.routes.projection_metier as pm
        with app.app_context():
            assert pm.rome_get_job_details("") == {}
            assert pm.rome_get_job_details("   ") == {}

    def test_pas_de_headers_retourne_dict_vide(self, app, monkeypatch):
        import Code.routes.projection_metier as pm
        with app.app_context():
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: None)
            assert pm.rome_get_job_details("M1805") == {}

    def test_succes_retourne_le_dict(self, app, monkeypatch):
        import Code.routes.projection_metier as pm
        with app.app_context():
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            class FakeResp:
                status_code = 200
                text = ""
                def json(self):
                    return {"code": "M1805", "metier": {"libelle": "Développeur"}}

            monkeypatch.setattr(pm.requests, "get", lambda *a, **k: FakeResp())
            result = pm.rome_get_job_details("M1805")
        assert result["code"] == "M1805"

    def test_statut_non_200_retourne_dict_vide(self, app, monkeypatch):
        import Code.routes.projection_metier as pm
        with app.app_context():
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            class FakeResp:
                status_code = 404
                text = ""

            monkeypatch.setattr(pm.requests, "get", lambda *a, **k: FakeResp())
            result = pm.rome_get_job_details("UNKNOWN")
        assert result == {}

    def test_reponse_non_dict_retourne_dict_vide(self, app, monkeypatch):
        import Code.routes.projection_metier as pm
        with app.app_context():
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            class FakeResp:
                status_code = 200
                text = ""
                def json(self):
                    return [1, 2, 3]

            monkeypatch.setattr(pm.requests, "get", lambda *a, **k: FakeResp())
            result = pm.rome_get_job_details("M1805")
        assert result == {}

    def test_timeout_retourne_dict_vide(self, app, monkeypatch):
        import requests as real_requests
        import Code.routes.projection_metier as pm
        with app.app_context():
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            def fake_get(*a, **k):
                raise real_requests.exceptions.Timeout()

            monkeypatch.setattr(pm.requests, "get", fake_get)
            result = pm.rome_get_job_details("M1805")
        assert result == {}

    def test_exception_generique_retourne_dict_vide(self, app, monkeypatch):
        import Code.routes.projection_metier as pm
        with app.app_context():
            monkeypatch.setattr(pm, "_get_auth_headers", lambda: {"Authorization": "Bearer x"})

            def fake_get(*a, **k):
                raise ValueError("boom")

            monkeypatch.setattr(pm.requests, "get", fake_get)
            result = pm.rome_get_job_details("M1805")
        assert result == {}


# ===========================================================================
# 12. _extract_competencies_from_job / _extract_job_label / _extract_job_code
# ===========================================================================

class TestExtractCompetenciesFromJob:

    @staticmethod
    def _f(data):
        from Code.routes.projection_metier import _extract_competencies_from_job
        return _extract_competencies_from_job(data)

    def test_dict_vide_retourne_liste_vide(self):
        assert self._f({}) == []

    def test_sans_cle_groupes_retourne_liste_vide(self):
        assert self._f({"metier": {}}) == []

    def test_groupes_valides_extrait_les_libelles(self):
        data = {
            "groupesCompetencesMobilisees": [
                {"competences": [{"libelle": "Gérer un projet"}, {"libelle": "Encadrer une équipe"}]}
            ]
        }
        result = self._f(data)
        assert "Gérer un projet" in result
        assert "Encadrer une équipe" in result

    def test_groupe_non_dict_est_ignore(self):
        assert self._f({"groupesCompetencesMobilisees": ["invalide"]}) == []

    def test_competences_non_liste_est_ignore(self):
        assert self._f({"groupesCompetencesMobilisees": [{"competences": "invalide"}]}) == []

    def test_competence_sans_libelle_est_ignoree(self):
        data = {"groupesCompetencesMobilisees": [{"competences": [{"libelle": ""}, {"autre": "x"}]}]}
        assert self._f(data) == []

    def test_competence_non_dict_est_ignoree(self):
        data = {"groupesCompetencesMobilisees": [{"competences": ["not-a-dict"]}]}
        assert self._f(data) == []


class TestExtractJobLabel:

    def test_extrait_le_libelle(self):
        from Code.routes.projection_metier import _extract_job_label
        assert _extract_job_label({"metier": {"libelle": "Développeur"}}) == "Développeur"

    def test_sans_metier_retourne_vide(self):
        from Code.routes.projection_metier import _extract_job_label
        assert _extract_job_label({}) == ""

    def test_metier_sans_libelle_retourne_vide(self):
        from Code.routes.projection_metier import _extract_job_label
        assert _extract_job_label({"metier": {}}) == ""


class TestExtractJobCode:

    def test_code_au_premier_niveau(self):
        from Code.routes.projection_metier import _extract_job_code
        assert _extract_job_code({"code": "M1805"}) == "M1805"

    def test_fallback_sur_metier_code(self):
        from Code.routes.projection_metier import _extract_job_code
        assert _extract_job_code({"metier": {"code": "M1806"}}) == "M1806"

    def test_aucun_code_retourne_vide(self):
        from Code.routes.projection_metier import _extract_job_code
        assert _extract_job_code({}) == ""


# ===========================================================================
# 13. Flux complet analyze_user avec ROME mocké (matching réel)
# ===========================================================================

class TestAnalyzeUserFullFlowWithMockedRome:

    @staticmethod
    def _setup_role_activity_competency(app, ids):
        from Code.models.models import Role, UserRole, Activities, Competency, activity_roles
        from Code.extensions import db
        with app.app_context():
            role = Role(name="Chef de Projet Test", entity_id=ids["entity_id"])
            db.session.add(role)
            db.session.flush()

            activity = Activities(
                entity_id=ids["entity_id"],
                name="Pilotage Projet Test",
                description="desc",
            )
            db.session.add(activity)
            db.session.flush()

            comp = Competency(activity_id=activity.id, description="Gestion de projet informatique")
            db.session.add(comp)
            db.session.flush()

            db.session.execute(activity_roles.insert().values(
                activity_id=activity.id, role_id=role.id, status="actif", required_mastery_level=None,
            ))
            db.session.add(UserRole(user_id=ids["user_id"], role_id=role.id))
            db.session.commit()

            return {"role_id": role.id, "activity_id": activity.id, "competency_id": comp.id}

    @staticmethod
    def _cleanup(app, ids, created):
        from Code.models.models import Role, UserRole, Activities, Competency, activity_roles
        from Code.extensions import db
        with app.app_context():
            db.session.query(UserRole).filter_by(
                user_id=ids["user_id"], role_id=created["role_id"]
            ).delete()
            db.session.execute(
                activity_roles.delete().where(activity_roles.c.role_id == created["role_id"])
            )
            db.session.query(Competency).filter_by(id=created["competency_id"]).delete()
            db.session.query(Activities).filter_by(id=created["activity_id"]).delete()
            db.session.query(Role).filter_by(id=created["role_id"]).delete()
            db.session.commit()

    def test_job_totalement_couvert_classe_dans_full(self, app, auth_client, ids, monkeypatch):
        created = self._setup_role_activity_competency(app, ids)
        try:
            import Code.routes.projection_metier as pm

            monkeypatch.setattr(pm, "rome_search_jobs", lambda query: [{"code": "M1805"}])
            monkeypatch.setattr(pm, "rome_get_job_details", lambda code: {
                "code": "M1805",
                "metier": {"libelle": "Chef de Projet Informatique"},
                "groupesCompetencesMobilisees": [
                    {"competences": [{"libelle": "Gestion de projet informatique"}]}
                ],
            })

            r = auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}")
            assert r.status_code == 200
            body = json.loads(r.data)
            assert len(body["full"]) == 1
            assert body["full"][0]["code"] == "M1805"
            assert body["full"][0]["score"] == 100.0
            assert body["partial"] == []
        finally:
            self._cleanup(app, ids, created)

    def test_job_sans_competences_classe_dans_partial_score_zero(self, app, auth_client, ids, monkeypatch):
        created = self._setup_role_activity_competency(app, ids)
        try:
            import Code.routes.projection_metier as pm

            monkeypatch.setattr(pm, "rome_search_jobs", lambda query: [{"code": "M1806"}])
            monkeypatch.setattr(pm, "rome_get_job_details", lambda code: {
                "code": "M1806",
                "metier": {"libelle": "Métier Sans Compétences"},
            })

            r = auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}")
            body = json.loads(r.data)
            assert len(body["partial"]) == 1
            assert body["partial"][0]["score"] == 0
            assert body["partial"][0]["total"] == 0
            assert body["full"] == []
        finally:
            self._cleanup(app, ids, created)

    def test_job_partiellement_couvert_classe_dans_partial(self, app, auth_client, ids, monkeypatch):
        created = self._setup_role_activity_competency(app, ids)
        try:
            import Code.routes.projection_metier as pm

            monkeypatch.setattr(pm, "rome_search_jobs", lambda query: [{"code": "M1807"}])
            monkeypatch.setattr(pm, "rome_get_job_details", lambda code: {
                "code": "M1807",
                "metier": {"libelle": "Métier Partiel"},
                "groupesCompetencesMobilisees": [
                    {"competences": [
                        {"libelle": "Gestion de projet informatique"},
                        {"libelle": "Pilotage budgétaire international"},
                    ]}
                ],
            })

            r = auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}")
            body = json.loads(r.data)
            assert len(body["partial"]) == 1
            job = body["partial"][0]
            assert 0 < job["score"] < 100
            assert job["owned_count"] >= 1
            assert job["missing_count"] >= 1
            assert body["full"] == []
        finally:
            self._cleanup(app, ids, created)

    def test_job_sans_details_est_ignore(self, app, auth_client, ids, monkeypatch):
        """rome_get_job_details() renvoie {} → le job est écarté (pas d'entrée créée)."""
        created = self._setup_role_activity_competency(app, ids)
        try:
            import Code.routes.projection_metier as pm

            monkeypatch.setattr(pm, "rome_search_jobs", lambda query: [{"code": "M1808"}])
            monkeypatch.setattr(pm, "rome_get_job_details", lambda code: {})

            r = auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}")
            body = json.loads(r.data)
            assert body["full"] == []
            assert body["partial"] == []
        finally:
            self._cleanup(app, ids, created)

    def test_competence_ponctuation_pure_et_mot_court_ne_font_pas_planter(self, app, auth_client, ids, monkeypatch):
        """Une compétence qui normalise en chaîne vide (continue) et une avec seulement
        des mots ≤3 caractères (fallback words=[normalized]) sont gérées sans erreur."""
        import Code.routes.projection_metier as pm

        monkeypatch.setattr(
            pm, "_extract_user_competencies",
            lambda uid: ["!!!", "abc", "Gestion de projet informatique"],
        )
        monkeypatch.setattr(pm, "rome_search_jobs", lambda query: [{"code": "M1811"}])
        monkeypatch.setattr(pm, "rome_get_job_details", lambda code: {
            "code": "M1811",
            "metier": {"libelle": "Métier Test"},
            "groupesCompetencesMobilisees": [
                {"competences": [{"libelle": "Gestion de projet informatique"}]}
            ],
        })

        r = auth_client.get(f"/projection_metier/analyze_user/{ids['user_id']}")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert len(body["full"]) == 1

    def test_pagination_full_limit_tronque_et_reflete_le_total(self, app, auth_client, ids, monkeypatch):
        created = self._setup_role_activity_competency(app, ids)
        try:
            import Code.routes.projection_metier as pm

            monkeypatch.setattr(
                pm, "rome_search_jobs",
                lambda query: [{"code": "M1809"}, {"code": "M1810"}],
            )
            monkeypatch.setattr(pm, "rome_get_job_details", lambda code: {
                "code": code,
                "metier": {"libelle": f"Métier {code}"},
                "groupesCompetencesMobilisees": [
                    {"competences": [{"libelle": "Gestion de projet informatique"}]}
                ],
            })

            r = auth_client.get(
                f"/projection_metier/analyze_user/{ids['user_id']}?full_limit=1"
            )
            body = json.loads(r.data)
            assert len(body["full"]) == 1
            assert body["page"]["full"]["total"] == 2
            assert body["page"]["full"]["has_more"] is True
        finally:
            self._cleanup(app, ids, created)
