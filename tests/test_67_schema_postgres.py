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
        assert ("entities", "is_shared") in alters, (
            "L'ALTER de entities.is_shared a disparu : les instances déjà "
            "déployées n'auraient pas la colonne.")
        assert re.search(r"DEFAULT\s+FALSE", alters[("entities", "is_shared")], re.I)

    def test_le_demarrage_verifie_les_colonnes_indispensables(self):
        """_safe_add_column est muet : sans cette vérification, une migration
        ratée ne se voit qu'en 500 sur toutes les pages."""
        source = io.open(SOURCE_APP, encoding="utf-8").read()
        assert "_verifier_colonnes(" in source
        assert '"entities": ["is_shared"]' in source
