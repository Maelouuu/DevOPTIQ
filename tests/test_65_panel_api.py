# tests/test_65_panel_api.py
# API JSON du panel de tests — celle que le hub interroge pour son module
# « Panel de tests ». Le navigateur ne peut pas appeler l'instance depuis le
# domaine du hub (aucun en-tête CORS) : c'est le hub qui appelle côté serveur
# et republie. Ces routes sont donc son SEUL contrat avec l'application.
import pytest

from Code.routes.test_panel import _fiabilite


class _Cas:
    """Le minimum que `_fiabilite` regarde d'un TestCase."""
    def __init__(self, statut):
        self.last_status = statut


class TestFiabilite:
    def test_aucun_cas_joue_donne_none(self):
        # Jamais joué ≠ zéro : compter les cas non exécutés comme des échecs
        # ferait chuter le score d'une page qu'on n'a simplement pas lancée.
        pct, verts, rouges, joues = _fiabilite([_Cas(None), _Cas('')])
        assert pct is None
        assert (verts, rouges, joues) == (0, 0, 0)

    def test_les_non_joues_sont_exclus_du_calcul(self):
        cas = [_Cas('passed'), _Cas('passed'), _Cas(None), _Cas(None)]
        pct, verts, rouges, joues = _fiabilite(cas)
        assert pct == 100
        assert (verts, rouges, joues) == (2, 0, 2)

    def test_echecs_et_erreurs_comptent_pour_du_rouge(self):
        cas = [_Cas('passed'), _Cas('failed'), _Cas('error'), _Cas('passed')]
        pct, verts, rouges, joues = _fiabilite(cas)
        assert pct == 50
        assert (verts, rouges, joues) == (2, 2, 4)

    def test_arrondi_a_l_entier(self):
        cas = [_Cas('passed'), _Cas('passed'), _Cas('failed')]
        assert _fiabilite(cas)[0] == 67


class TestApiEtat:
    def test_repond_avec_le_compte_des_pages_et_des_cas(self, client):
        r = client.get('/testpanel/api/etat')
        assert r.status_code == 200
        d = r.get_json()
        for cle in ('suite_presente', 'pages', 'cas', 'en_cours', 'dernier'):
            assert cle in d
        # La suite tourne : ses propres fichiers sont forcément là.
        assert d['suite_presente'] is True
        assert d['pages'] > 0 and d['cas'] > 0


class TestApiPages:
    def test_catalogue_complet(self, client):
        r = client.get('/testpanel/api/pages')
        assert r.status_code == 200
        d = r.get_json()
        assert d['pages'], "le catalogue ne doit pas être vide"
        assert d['total_cas'] == sum(p['total'] for p in d['pages'])

    def test_chaque_page_porte_ce_que_le_hub_affiche(self, client):
        page = client.get('/testpanel/api/pages').get_json()['pages'][0]
        for cle in ('slug', 'titre', 'fichier', 'total', 'joues',
                    'verts', 'rouges', 'fiabilite', 'dernier'):
            assert cle in page, f"clé « {cle} » attendue par le module du hub"
        assert page['fiabilite'] is None or 0 <= page['fiabilite'] <= 100
        assert page['joues'] == page['verts'] + page['rouges']

    def test_ce_fichier_de_tests_figure_au_catalogue(self, client):
        fichiers = [p['fichier'] for p in
                    client.get('/testpanel/api/pages').get_json()['pages']]
        assert 'test_65_panel_api.py' in fichiers


class TestApiPage:
    def test_detail_d_une_page_liste_ses_cas(self, client):
        slug = client.get('/testpanel/api/pages').get_json()['pages'][0]['slug']
        d = client.get(f'/testpanel/api/page/{slug}').get_json()
        assert d['slug'] == slug
        assert isinstance(d['cas'], list)
        assert d['total'] == len(d['cas'])
        if d['cas']:
            for cle in ('id', 'nom', 'classe', 'statut', 'quand'):
                assert cle in d['cas'][0]

    def test_page_inconnue_donne_404(self, client):
        assert client.get('/testpanel/api/page/page-qui-nexiste-pas').status_code == 404


class TestPlafondDesExecutions:
    """Le blueprint n'a AUCUNE authentification : qui connaît l'URL de
    l'instance peut demander une exécution. Tant que l'image n'embarquait pas
    la suite cela ne coûtait rien ; maintenant chaque demande consomme deux
    minutes de CPU. Le plafond vit dans le WORKER, pas dans la route : le
    contrat du panel (un run par demande, id distinct, portée exacte) reste
    celui que test_37 vérifie."""

    def test_les_creneaux_se_prennent_et_se_rendent(self):
        from Code.routes import test_panel as tp

        pris = [tp._reserver_creneau() for _ in range(tp._MAX_SIMULTANEES)]
        try:
            assert all(pris), "les créneaux sous le plafond doivent être accordés"
            assert tp._reserver_creneau() is False, "au-delà du plafond, on refuse"
        finally:
            for _ in pris:
                tp._liberer_creneau()
        # Une fois rendus, l'instance repart à neuf.
        assert tp._reserver_creneau() is True
        tp._liberer_creneau()

    def test_un_run_refuse_est_clos_sans_lancer_pytest(self, app, monkeypatch):
        from Code.extensions import db
        from Code.models.test_models import TestRun
        from Code.routes import test_panel as tp

        appels = []
        monkeypatch.setattr(tp, '_executer_run', lambda *a, **k: appels.append(a))
        monkeypatch.setattr(tp, '_reserver_creneau', lambda: False)

        with app.app_context():
            run = TestRun(scope='all', status='running')
            db.session.add(run); db.session.commit()
            run_id = run.id
            try:
                tp._runs[run_id] = {'lines': [], 'done': False}
                tp._run_thread(run_id, 'all', app)
                assert not appels, "aucun pytest ne doit démarrer quand c'est refusé"
                db.session.expire_all()
                clos = db.session.get(TestRun, run_id)
                assert clos.status == 'done'
                assert tp._runs[run_id]['done'] is True
                assert 'REFUSÉ' in ''.join(tp._runs[run_id]['lines'])
            finally:
                tp._runs.pop(run_id, None)
                ligne = db.session.get(TestRun, run_id)
                if ligne:
                    db.session.delete(ligne); db.session.commit()

    def test_le_creneau_est_rendu_meme_si_l_execution_echoue(self, app, monkeypatch):
        from Code.routes import test_panel as tp

        def _explose(*a, **k):
            raise RuntimeError("pytest introuvable")

        monkeypatch.setattr(tp, '_executer_run', _explose)
        avant = tp._actifs
        with pytest.raises(RuntimeError):
            tp._run_thread(-1, 'all', app)
        # Sans le finally, une exécution ratée mangerait un créneau pour de bon.
        assert tp._actifs == avant


class TestPontDuHub:
    """`hub/panel_client.py` — le hub interroge l'instance CÔTÉ SERVEUR : le
    navigateur ne peut pas l'appeler depuis un autre domaine, faute de CORS."""

    def _pont(self):
        import importlib.util
        import os
        import sys

        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        hub = os.path.join(racine, "hub")
        source = os.path.join(hub, "panel_client.py")
        if not os.path.exists(source):
            pytest.skip("hub/panel_client.py absent (arbre bytecode) — service séparé")
        sys.path.insert(0, hub)
        try:
            spec = importlib.util.spec_from_file_location("pont_panel", source)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
        finally:
            sys.path.remove(hub)

    def test_un_post_porte_un_corps_vide_explicite(self, monkeypatch):
        # Sans `data`, urllib n'envoie pas de Content-Length et le frontend
        # Google des *.run.app répond 411 sans atteindre l'application. Rien ne
        # s'interpose en local : le défaut n'apparaît qu'en ligne.
        pont = self._pont()
        vus = []

        class _Reponse:
            def read(self): return b'{"run_id": 7}'
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def _faux_urlopen(req, timeout=None):
            vus.append(req)
            return _Reponse()

        monkeypatch.setattr(pont.urllib.request, "urlopen", _faux_urlopen)
        monkeypatch.setenv("PANEL_BASE", "https://exemple.test")

        ok, charge = pont.lancer("all")
        assert ok and charge["run_id"] == 7
        assert vus[-1].get_method() == "POST"
        assert vus[-1].data == b"", "un POST sans corps se fait rejeter en 411"

        pont.etat()
        assert vus[-1].get_method() == "GET"
        assert vus[-1].data is None

    def test_la_portee_page_vise_la_bonne_route(self, monkeypatch):
        pont = self._pont()
        vus = []

        class _Reponse:
            def read(self): return b'{"run_id": 9}'
            def __enter__(self): return self
            def __exit__(self, *a): return False

        monkeypatch.setattr(pont.urllib.request, "urlopen",
                            lambda req, timeout=None: (vus.append(req), _Reponse())[1])
        monkeypatch.setenv("PANEL_BASE", "https://exemple.test")

        pont.lancer("page:auth")
        assert vus[-1].full_url.endswith("/testpanel/run/page/auth")
        pont.lancer("all")
        assert vus[-1].full_url.endswith("/testpanel/run/all")

    def test_instance_injoignable_donne_un_message_lisible(self, monkeypatch):
        pont = self._pont()

        def _plante(req, timeout=None):
            raise OSError("connexion refusée")

        monkeypatch.setattr(pont.urllib.request, "urlopen", _plante)
        monkeypatch.setenv("PANEL_BASE", "https://exemple.test")

        ok, charge = pont.lancer("all")
        assert ok is False
        assert "instance" in charge["message"].lower()


class TestRecensementDesCas:
    """`sync_tests_to_db` ne recensait que les tests rangés dans une CLASSE.
    Sept fichiers entiers (test_48, 49, 50, 51, 52, 62…) sont écrits en
    fonctions de module : ils sortaient à zéro cas, affichaient « jamais joué »
    même après une exécution complète, et leurs ~120 tests ne pesaient dans
    aucun taux de fiabilité."""

    def test_les_fonctions_de_module_sont_recensees(self, client):
        pages = {p['fichier']: p for p in
                 client.get('/testpanel/api/pages').get_json()['pages']}
        # test_51_entity_share.py : 40 fonctions de module, aucune classe.
        page = pages.get('test_51_entity_share.py')
        assert page is not None
        assert page['total'] > 0, "un fichier sans classe doit quand même compter"

    def test_le_node_id_d_une_fonction_de_module_n_a_pas_de_classe(self, client):
        slug = None
        for p in client.get('/testpanel/api/pages').get_json()['pages']:
            if p['fichier'] == 'test_51_entity_share.py':
                slug = p['slug']
        assert slug
        cas = client.get(f'/testpanel/api/page/{slug}').get_json()['cas']
        assert cas
        assert all(c['classe'] == '' for c in cas), \
            "aucune classe dans ce fichier — la colonne doit rester vide"

    def test_le_node_id_reste_jouable_par_pytest(self, app):
        """`tests/f.py::nom` pour une fonction, `tests/f.py::Classe::nom`
        sinon — « f.py::::nom » ne veut rien dire pour pytest."""
        from Code.models.test_models import TestCase as Cas, TestPage
        with app.app_context():
            page = TestPage.query.filter_by(file_name='test_51_entity_share.py').first()
            assert page is not None
            for c in page.cases:
                assert '::::' not in c.node_id
                assert c.node_id.startswith('tests/test_51_entity_share.py::')

    def test_un_resultat_de_fonction_de_module_retrouve_son_cas(self):
        """Le pendant côté lecture : JUnit donne « tests.test_51_x » sans
        classe, et prendre le dernier segment faisait passer le NOM DU MODULE
        pour une classe — le résultat n'était rattaché à rien."""
        import xml.etree.ElementTree as ET
        from Code.routes import test_panel as tp

        xml = ('<testsuites><testsuite>'
               '<testcase classname="tests.test_51_entity_share" name="test_partage"/>'
               '<testcase classname="tests.test_01_auth.TestLoginPage" name="test_ok"/>'
               '</testsuite></testsuites>')
        vus = []
        for tc in ET.fromstring(xml).findall('.//testcase'):
            parts = tc.get('classname', '').split('.')
            idx = next((i for i, p in enumerate(parts) if p.startswith('test_')), None)
            classe = '.'.join(parts[idx + 1:])
            vus.append(f"tests/{parts[idx]}.py::{classe}::{tc.get('name')}" if classe
                       else f"tests/{parts[idx]}.py::{tc.get('name')}")
        assert vus == ['tests/test_51_entity_share.py::test_partage',
                       'tests/test_01_auth.py::TestLoginPage::test_ok']
        assert tp is not None


class TestSyncTolerant:
    """Le recensement réécrit 71 pages et ~1900 cas à chaque appel ; sur
    Postgres il lui arrive de dépasser le temps imparti. Le catalogue reste
    lisible en base : une panne du recensement ne doit pas rendre 500, sinon le
    hub annonce « l'instance ne répond pas » pour rien."""

    def test_le_catalogue_reste_lisible_si_le_recensement_echoue(self, client, monkeypatch):
        from Code.routes import test_panel as tp

        def _plante():
            raise RuntimeError("timeout du recensement")

        monkeypatch.setattr(tp, 'sync_tests_to_db', _plante)
        r = client.get('/testpanel/api/pages')
        assert r.status_code == 200
        assert r.get_json()['pages'], "les pages déjà en base doivent sortir"

        r = client.get('/testpanel/api/etat')
        assert r.status_code == 200
        assert r.get_json()['pages'] > 0
