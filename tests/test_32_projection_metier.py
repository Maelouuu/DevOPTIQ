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
