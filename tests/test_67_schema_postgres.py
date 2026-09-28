# tests/test_67_schema_postgres.py
"""
Le schéma doit être valide sur PostgreSQL, pas seulement sur SQLite.

La suite tourne sur SQLite, qui accepte `BOOLEAN DEFAULT 0`. PostgreSQL le
REFUSE (« column is of type boolean but default expression is of type
integer ») — et comme `_safe_add_column` avale l'erreur pour rester idempotent,
la colonne n'était simplement jamais créée : toute requête sur la table tombait
en 500, en production uniquement. Aucun test SQLite ne pouvait le voir.

On compile donc ici le DDL avec le dialecte PostgreSQL, sans serveur, et on
relit les ALTER écrits à la main dans `create_app`.
"""
import io
import os
import re

import pytest

pytestmark = pytest.mark.schema_postgres

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_APP = os.path.join(RACINE, "Code", "app.py")

# L'image applicative est bytecode-only : les .py y sont compilés puis supprimés
# (tests/ excepté). Les contrôles qui RELISENT la source n'ont donc rien à lire
# là-bas — ils gardent tout leur sens sur un poste de développement et en CI,
# les deux endroits où un ALTER se rédige.
sans_source = pytest.mark.skipif(
    not os.path.exists(SOURCE_APP),
    reason="Code/app.py absent (arbre bytecode) — contrôle de source")


def _ddl_postgres(table):
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))


class TestDefautsBooleens:

    def test_aucun_booleen_ne_prend_un_entier_par_defaut(self, app):
        """`server_default=text('0')` rend « DEFAULT 0 » : invalide en PG."""
        from Code.extensions import db

        fautives = []
        for nom, table in db.metadata.tables.items():
            ddl = _ddl_postgres(table)
            for ligne in ddl.splitlines():
                if re.search(r"\bBOOLEAN\b.*\bDEFAULT\s+(0|1)\b", ligne, re.I):
                    fautives.append(f"{nom}: {ligne.strip()}")
        assert not fautives, (
            "Défaut entier sur une colonne booléenne — PostgreSQL refusera la "
            "création de la table :\n  " + "\n  ".join(fautives))

    def test_entities_is_shared_a_bien_un_defaut_utilisable(self, app):
        from Code.extensions import db
        ddl = _ddl_postgres(db.metadata.tables["entities"])
        ligne = next(l for l in ddl.splitlines() if "is_shared" in l)
        assert re.search(r"DEFAULT\s+false", ligne, re.I), ligne


class TestLargeurDesColonnes:
    """SQLite ignore `VARCHAR(n)` : il accepte n'importe quelle longueur. Une
    colonne trop étroite ne se voit donc QUE sur PostgreSQL, et seulement une
    fois qu'une vraie valeur y passe. On confronte ici la largeur DÉCLARÉE à ce
    que le code écrit réellement."""

    @staticmethod
    def _libelles_hsc():
        """Tout ce que `hsc_level_label` peut produire : « 3 (Maîtrise) »,
        « 3 (Proficient) »… C'est ce qui atterrit dans la colonne."""
        from Code.translations import HSC_LEVELS
        return ["%d (%s)" % (n, libelles[lang])
                for n, libelles in HSC_LEVELS.items()
                for lang in ("fr", "en")]

    def test_le_niveau_hsc_tient_dans_sa_colonne(self, app):
        """172 des 207 lignes de la base du 10/09 dépassaient VARCHAR(10)."""
        from Code.models.models import Softskill

        colonne = Softskill.__table__.c.niveau
        besoin = max(len(v) for v in self._libelles_hsc())
        assert colonne.type.length >= besoin, (
            "softskills.niveau est en VARCHAR(%s) alors que le plus long "
            "libellé HSC en fait %d (« %s ») : sur PostgreSQL, enregistrer "
            "une HSC lèverait « value too long for type character varying »."
            % (colonne.type.length, besoin,
               max(self._libelles_hsc(), key=len)))

    @sans_source
    def test_la_migration_elargit_la_colonne_des_instances_existantes(self):
        """Changer le modèle ne touche PAS une base déjà créée : sans l'ALTER,
        les instances en service gardent leur colonne étroite."""
        source = io.open(SOURCE_APP, encoding="utf-8").read()
        assert "ALTER TABLE softskills ALTER COLUMN niveau TYPE" in source, (
            "L'élargissement de softskills.niveau a disparu de create_app : "
            "les bases déjà déployées resteraient en VARCHAR(10).")


@sans_source
class TestMigrationsAChaud:
    """Les ALTER de `create_app` sont du SQL écrit à la main : personne ne les
    compile, et ils ne s'exécutent qu'au démarrage d'une instance déjà en
    service — c'est-à-dire en production."""

    @staticmethod
    def _alters():
        source = io.open(SOURCE_APP, encoding="utf-8").read()
        return re.findall(r"_safe_add_column\(\s*\"([^\"]+)\"\s*,\s*\"([^\"]+)\"\s*,\s*\"([^\"]+)\"", source)

    def test_les_alter_booleens_n_utilisent_pas_0_ou_1(self):
        fautifs = [f"{t}.{c} {ty}" for t, c, ty in self._alters()
                   if re.match(r"\s*BOOL", ty, re.I) and re.search(r"DEFAULT\s+(0|1)\b", ty, re.I)]
        assert not fautifs, (
            "PostgreSQL refuse un entier comme défaut de booléen ; utiliser "
            "FALSE / TRUE :\n  " + "\n  ".join(fautifs))

    def test_la_colonne_du_partage_est_bien_declaree(self):
        alters = {(t, c): ty for t, c, ty in self._alters()}
        for colonne in ("is_shared", "statuts_regles"):
            assert ("entities", colonne) in alters, (
                f"L'ALTER de entities.{colonne} a disparu : les instances déjà "
                "déployées n'auraient pas la colonne.")
            assert re.search(r"DEFAULT\s+FALSE", alters[("entities", colonne)], re.I)

    def test_aucune_table_n_est_declaree_deux_fois(self):
        """⚠️ Deux modèles pour la même table : `Table 'x' is already defined
        for this MetaData instance` DÈS QU'ON IMPORTE le second — et l'erreur
        frappe l'appelant, pas le fichier fautif.

        `Code/routes/time_extra.py` redéclarait cinq tables de `models.py`.
        Personne ne l'importait : c'est ce qui l'a laissé passer des mois, et la
        première importation (la réunion des rôles) est tombée en production.
        """
        import glob
        import os

        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        motif = re.compile(r"""__tablename__\s*=\s*['"]([^'"]+)['"]""")
        ou = {}
        for chemin in glob.glob(os.path.join(racine, "Code", "**", "*.py"),
                                recursive=True):
            src = io.open(chemin, encoding="utf-8", errors="replace").read()
            for trouve in motif.finditer(src):
                # ⚠️ Le voisinage, pas le fichier : `models.py` déclare
                # `extend_existing` sur ses tables d'ASSOCIATION, et sauter le
                # fichier entier rendait le contrôle aveugle à ses 60 modèles.
                autour = src[max(0, trouve.start() - 400):trouve.end() + 400]
                if "extend_existing" in autour:
                    continue      # redéclaration assumée
                ou.setdefault(trouve.group(1), []).append(
                    os.path.relpath(chemin, racine))
        fautifs = {t: sorted(set(f)) for t, f in ou.items() if len(set(f)) > 1}
        assert not fautifs, (
            "tables déclarées dans plusieurs fichiers :\n  "
            + "\n  ".join("%s → %s" % (t, ", ".join(f)) for t, f in fautifs.items()))

    def test_le_demarrage_verifie_les_colonnes_indispensables(self):
        """_safe_add_column est muet : sans cette vérification, une migration
        ratée ne se voit qu'en 500 sur toutes les pages."""
        source = io.open(SOURCE_APP, encoding="utf-8").read()
        assert "_verifier_colonnes(" in source
        bloc = source.split("_verifier_colonnes(", 1)[1].split("})", 1)[0]
        attendues = re.search(r'"entities":\s*\[([^\]]*)\]', bloc)
        assert attendues, "entities ne figure plus dans les colonnes vérifiées"
        colonnes = {c.strip().strip('"') for c in attendues.group(1).split(",") if c.strip()}
        assert {"is_shared", "statuts_regles"} <= colonnes
