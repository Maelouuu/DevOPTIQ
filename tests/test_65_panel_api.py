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
