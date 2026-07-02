# tests/test_43_vsdx_parsers.py
"""
Tests unitaires pour les deux parseurs VSDX (pas de Flask, pas de DB) :
  - Code/routes/vsdx_conection_parser.py
      VsdxConnectionParser, normalize_activity_name,
      validate_connections_against_activities, parse_vsdx_connections
  - Code/routes/vsdx_decision_extractor.py
      helpers XML, _is_pure_diamond_geometry, _is_likely_annotation,
      _infer_oui_non, extract_decisions_from_vsdx
"""
import os
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Namespace Visio partagé par les deux modules
NS = "http://schemas.microsoft.com/office/visio/2012/main"


def _xml(inner=""):
    """Crée un élément Shape dans le namespace Visio avec le contenu fourni."""
    return ET.fromstring(f'<Shape xmlns="{NS}">{inner}</Shape>')


def _conn(src, tgt, dtype="nourrissante", dname="Données"):
    return {"source_name": src, "target_name": tgt, "data_type": dtype, "data_name": dname}


# =============================================================================
# 1. normalize_activity_name
# =============================================================================

class TestNormalizeActivityName:

    def setup_method(self):
        from Code.routes.vsdx_conection_parser import normalize_activity_name
        self.fn = normalize_activity_name

    def test_empty_string_returns_empty(self):
        assert self.fn("") == ""

    def test_lowercases_input(self):
        assert self.fn("Gestion DES Commandes") == "gestion des commandes"

    def test_multiple_spaces_collapsed_to_one(self):
        assert self.fn("hello   world") == "hello world"

    def test_leading_trailing_spaces_stripped(self):
        assert self.fn("  activité  ") == "activité"

    def test_plain_apostrophe_preserved(self):
        # apostrophe traverse la normalisation intact (juste lowercasée)
        result = self.fn("l’activit\xe9")
        assert "’" in result  # apostrophe conservée

    def test_backtick_replaced(self):
        result = self.fn("l`activit\xe9")
        assert "`" not in result

    def test_already_normalized_unchanged(self):
        s = "gestion des commandes"
        assert self.fn(s) == s


# =============================================================================
# 2. validate_connections_against_activities
# =============================================================================

class TestValidateConnections:

    def setup_method(self):
        from Code.routes.vsdx_conection_parser import validate_connections_against_activities
        self.fn = validate_connections_against_activities

    def test_empty_connections_all_empty(self):
        valid, invalid, missing = self.fn([], {"A": 1, "B": 2})
        assert valid == invalid == missing == []

    def test_valid_connection_adds_ids(self):
        conns = [_conn("Activité A", "Activité B")]
        valid, invalid, missing = self.fn(conns, {"Activité A": 1, "Activité B": 2})
        assert len(valid) == 1
        assert valid[0]["source_activity_id"] == 1
        assert valid[0]["target_activity_id"] == 2

    def test_unknown_activities_go_to_invalid(self):
        conns = [_conn("Activité X", "Activité Y")]
        valid, invalid, missing = self.fn(conns, {})
        assert len(valid) == 0
        assert len(invalid) == 1
        assert "Activité X" in missing and "Activité Y" in missing

    def test_partial_match_goes_to_invalid(self):
        conns = [_conn("Activité A", "Activité Z")]
        valid, invalid, missing = self.fn(conns, {"Activité A": 1})
        assert len(valid) == 0
        assert "Activité Z" in missing
        assert "Activité A" not in missing

    def test_normalization_case_insensitive(self):
        conns = [_conn("ACTIVITÉ A", "activité b")]
        valid, invalid, _ = self.fn(conns, {"Activité A": 1, "Activité B": 2})
        assert len(valid) == 1

    def test_missing_list_is_sorted(self):
        conns = [_conn("Z Act", "A Act"), _conn("M Act", "B Act")]
        _, _, missing = self.fn(conns, {})
        assert missing == sorted(missing)

    def test_valid_connection_preserves_original_fields(self):
        conns = [_conn("Activité A", "Activité B", dtype="déclenchante", dname="Flux")]
        valid, _, _ = self.fn(conns, {"Activité A": 1, "Activité B": 2})
        assert valid[0]["data_type"] == "déclenchante"
        assert valid[0]["data_name"] == "Flux"


# =============================================================================
# 3. VsdxConnectionParser._extract_data_info
# =============================================================================

class TestExtractDataInfo:

    def setup_method(self):
        from Code.routes.vsdx_conection_parser import VsdxConnectionParser
        self.p = VsdxConnectionParser.__new__(VsdxConnectionParser)

    def test_n_space_prefix_is_nourrissante(self):
        dtype, _ = self.p._extract_data_info("N Données client", "")
        assert dtype == "nourrissante"

    def test_n_dash_prefix_is_nourrissante(self):
        dtype, _ = self.p._extract_data_info("N-Données", "")
        assert dtype == "nourrissante"

    def test_t_space_prefix_is_declenchante(self):
        dtype, _ = self.p._extract_data_info("T Commande", "")
        assert dtype == "déclenchante"

    def test_t_dash_prefix_is_declenchante(self):
        dtype, _ = self.p._extract_data_info("T-Commande", "")
        assert dtype == "déclenchante"

    def test_no_prefix_type_is_none(self):
        dtype, _ = self.p._extract_data_info("Regular Name", "")
        assert dtype is None

    def test_connector_text_takes_priority_as_data_name(self):
        _, dname = self.p._extract_data_info("N Anything", "Planning prévisionnel")
        assert dname == "Planning prévisionnel"

    def test_empty_text_uses_name_without_prefix(self):
        _, dname = self.p._extract_data_info("N-Planning projet", "")
        assert dname is not None
        assert len(dname) > 0

    def test_both_empty_data_name_is_none(self):
        _, dname = self.p._extract_data_info("", "")
        assert dname is None

    def test_empty_string_text_normalized_to_none(self):
        # connector_text = "  " → empty after strip → None
        _, dname = self.p._extract_data_info("", "")
        assert dname is None


# =============================================================================
# 4. VsdxConnectionParser.parse (erreurs de fichier)
# =============================================================================

class TestVsdxConnectionParserParse:

    def test_file_not_found_returns_error(self):
        from Code.routes.vsdx_conection_parser import VsdxConnectionParser
        p = VsdxConnectionParser("/nonexistent/path/file.vsdx")
        conns, errors = p.parse()
        assert conns == []
        assert len(errors) > 0

    def test_wrong_extension_returns_error(self):
        from Code.routes.vsdx_conection_parser import VsdxConnectionParser
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(b"not vsdx")
            path = f.name
        try:
            conns, errors = VsdxConnectionParser(path).parse()
            assert conns == []
            assert any("vsdx" in e.lower() or "format" in e.lower() for e in errors)
        finally:
            os.unlink(path)

    def test_bad_zip_returns_error(self):
        from Code.routes.vsdx_conection_parser import VsdxConnectionParser
        with tempfile.NamedTemporaryFile(suffix=".vsdx", delete=False) as f:
            f.write(b"not a valid zip file")
            path = f.name
        try:
            conns, errors = VsdxConnectionParser(path).parse()
            assert conns == []
            assert len(errors) > 0
        finally:
            os.unlink(path)

    def test_get_unique_activities_empty_connections(self):
        from Code.routes.vsdx_conection_parser import VsdxConnectionParser
        p = VsdxConnectionParser.__new__(VsdxConnectionParser)
        p.connections = []
        assert p.get_unique_activities() == []

    def test_get_unique_activities_deduplicates(self):
        from Code.routes.vsdx_conection_parser import VsdxConnectionParser
        p = VsdxConnectionParser.__new__(VsdxConnectionParser)
        p.connections = [
            {"source_name": "A", "target_name": "B"},
            {"source_name": "B", "target_name": "C"},
        ]
        result = p.get_unique_activities()
        assert sorted(result) == ["A", "B", "C"]

    def test_get_excluded_shapes_empty(self):
        from Code.routes.vsdx_conection_parser import VsdxConnectionParser
        p = VsdxConnectionParser.__new__(VsdxConnectionParser)
        p.excluded_shape_ids = set()
        p.shape_info = {}
        assert p.get_excluded_shapes() == []

    def test_parse_vsdx_connections_wrapper_missing_file(self):
        from Code.routes.vsdx_conection_parser import parse_vsdx_connections
        conns, errors = parse_vsdx_connections("/nonexistent.vsdx")
        assert conns == []
        assert len(errors) > 0


# =============================================================================
# 4bis. VsdxConnectionParser.parse — pipeline complet sur un VSDX synthétique
#
# 4 activités reliées par 2 connecteurs valides + 2 connecteurs à exclure :
#   - 1 -> 2 (connecteur "N- Type", texte "Donnee nourrissante")
#   - 2 -> 4 (connecteur "T- Type2", texte "Signal demarrage")
#   - 2 -> 6 : "6" est un drapeau (LayerMember=6) → connexion exclue
#   - 1 -> 8 : "8" est "Résultat.Something" → connexion exclue (préfixe Résultat.)
# =============================================================================

_CONN_PAGE_XML = """<?xml version="1.0"?>
<PageContents xmlns="http://schemas.microsoft.com/office/visio/2012/main">
  <Shapes>
    <Shape ID="1"><Text>Activite A</Text></Shape>
    <Shape ID="2"><Text>Activite B</Text></Shape>
    <Shape ID="3" Name="N- Type"><Text>Donnee nourrissante</Text></Shape>

    <Shape ID="4"><Text>Activite C</Text></Shape>
    <Shape ID="5" Name="T- Type2"><Text>Signal demarrage</Text></Shape>

    <Shape ID="6"><Cell N="LayerMember" V="6"/><Text>Drapeau</Text></Shape>
    <Shape ID="7" Name="N- Flag"><Text>Donnee vers drapeau</Text></Shape>

    <Shape ID="8"><Text>Résultat.Something</Text></Shape>
    <Shape ID="9" Name="N- Res"><Text>Donnee vers resultat</Text></Shape>
  </Shapes>
  <Connects>
    <Connect FromSheet="3" FromCell="BeginX" ToSheet="1"/>
    <Connect FromSheet="3" FromCell="EndX" ToSheet="2"/>

    <Connect FromSheet="5" FromCell="BeginX" ToSheet="2"/>
    <Connect FromSheet="5" FromCell="EndX" ToSheet="4"/>

    <Connect FromSheet="7" FromCell="BeginX" ToSheet="2"/>
    <Connect FromSheet="7" FromCell="EndX" ToSheet="6"/>

    <Connect FromSheet="9" FromCell="BeginX" ToSheet="1"/>
    <Connect FromSheet="9" FromCell="EndX" ToSheet="8"/>
  </Connects>
</PageContents>""".encode("utf-8")


def _build_conn_vsdx(path):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("visio/pages/page1.xml", _CONN_PAGE_XML)
    return str(path)


class TestVsdxConnectionParserFullPipeline:

    def _parse(self, tmp_path):
        from Code.routes.vsdx_conection_parser import VsdxConnectionParser
        path = _build_conn_vsdx(tmp_path / "conn_sample.vsdx")
        p = VsdxConnectionParser(path)
        conns, errors = p.parse()
        assert errors == []
        return p, conns

    def test_only_valid_connections_are_kept(self, tmp_path):
        """Drapeau (layer 6) et cible 'Résultat.*' sont exclus → seules 2 connexions valides."""
        _, conns = self._parse(tmp_path)
        pairs = {(c["source_name"], c["target_name"]) for c in conns}
        assert pairs == {("Activite A", "Activite B"), ("Activite B", "Activite C")}

    def test_data_type_and_name_extracted_from_connector(self, tmp_path):
        _, conns = self._parse(tmp_path)
        by_target = {c["target_name"]: c for c in conns}
        assert by_target["Activite B"]["data_type"] == "nourrissante"
        assert by_target["Activite B"]["data_name"] == "Donnee nourrissante"
        assert by_target["Activite C"]["data_type"] == "déclenchante"
        assert by_target["Activite C"]["data_name"] == "Signal demarrage"

    def test_flagged_shape_is_excluded_from_shapes(self, tmp_path):
        p, _ = self._parse(tmp_path)
        excluded = p.get_excluded_shapes()
        assert len(excluded) == 1
        assert excluded[0]["shape_id"] == "6"
        assert excluded[0]["text"] == "Drapeau"

    def test_get_unique_activities_matches_valid_connections(self, tmp_path):
        p, _ = self._parse(tmp_path)
        assert p.get_unique_activities() == ["Activite A", "Activite B", "Activite C"]

    def test_parse_vsdx_connections_wrapper_returns_same_result(self, tmp_path):
        from Code.routes.vsdx_conection_parser import parse_vsdx_connections
        path = _build_conn_vsdx(tmp_path / "conn_sample2.vsdx")
        conns, errors = parse_vsdx_connections(path)
        assert errors == []
        assert len(conns) == 2

    def test_validate_connections_against_activities_full_flow(self, tmp_path):
        from Code.routes.vsdx_conection_parser import validate_connections_against_activities
        _, conns = self._parse(tmp_path)
        existing = {"Activite A": 101, "Activite B": 102}
        valid, invalid, missing = validate_connections_against_activities(conns, existing)
        assert len(valid) == 1
        assert valid[0]["source_activity_id"] == 101
        assert valid[0]["target_activity_id"] == 102
        assert len(invalid) == 1
        assert missing == ["Activite C"]


# =============================================================================
# 5. vsdx_decision_extractor — helpers XML
# =============================================================================

class TestDecisionExtractorHelpers:

    def test_text_of_no_text_element_returns_empty(self):
        from Code.routes.vsdx_decision_extractor import _text_of
        assert _text_of(_xml()) == ""

    def test_text_of_simple_content(self):
        from Code.routes.vsdx_decision_extractor import _text_of
        el = _xml("<Text>Hello World</Text>")
        assert _text_of(el) == "Hello World"

    def test_text_of_collapses_whitespace(self):
        from Code.routes.vsdx_decision_extractor import _text_of
        el = _xml("<Text>  multi   spaces  </Text>")
        assert _text_of(el) == "multi spaces"

    def test_cell_val_found(self):
        from Code.routes.vsdx_decision_extractor import _cell_val
        el = _xml('<Cell N="Width" V="2.5"/>')
        assert _cell_val(el, "Width") == "2.5"

    def test_cell_val_missing_returns_empty(self):
        from Code.routes.vsdx_decision_extractor import _cell_val
        assert _cell_val(_xml(), "Width") == ""

    def test_cell_float_valid(self):
        from Code.routes.vsdx_decision_extractor import _cell_float
        el = _xml('<Cell N="PinX" V="3.14"/>')
        result = _cell_float(el, "PinX")
        assert abs(result - 3.14) < 0.001

    def test_cell_float_invalid_value_returns_zero(self):
        from Code.routes.vsdx_decision_extractor import _cell_float
        el = _xml('<Cell N="Width" V="abc"/>')
        assert _cell_float(el, "Width") == 0.0

    def test_cell_float_missing_cell_returns_zero(self):
        from Code.routes.vsdx_decision_extractor import _cell_float
        assert _cell_float(_xml(), "MissingCell") == 0.0


# =============================================================================
# 6. _is_pure_diamond_geometry
# =============================================================================

class TestIsPureDiamondGeometry:

    def _shape(self, rows_xml):
        return ET.fromstring(
            f'<Shape xmlns="{NS}"><Section N="Geometry">{rows_xml}</Section></Shape>'
        )

    def test_one_moveto_four_lineto_is_diamond(self):
        from Code.routes.vsdx_decision_extractor import _is_pure_diamond_geometry
        el = self._shape(
            '<Row T="MoveTo"/><Row T="LineTo"/><Row T="LineTo"/>'
            '<Row T="LineTo"/><Row T="LineTo"/>'
        )
        assert _is_pure_diamond_geometry(el) is True

    def test_with_arc_is_not_diamond(self):
        from Code.routes.vsdx_decision_extractor import _is_pure_diamond_geometry
        el = self._shape(
            '<Row T="MoveTo"/><Row T="LineTo"/><Row T="LineTo"/>'
            '<Row T="ArcTo"/><Row T="LineTo"/>'
        )
        assert _is_pure_diamond_geometry(el) is False

    def test_three_lineto_is_not_diamond(self):
        from Code.routes.vsdx_decision_extractor import _is_pure_diamond_geometry
        el = self._shape(
            '<Row T="MoveTo"/><Row T="LineTo"/><Row T="LineTo"/><Row T="LineTo"/>'
        )
        assert _is_pure_diamond_geometry(el) is False

    def test_no_geometry_section_is_not_diamond(self):
        from Code.routes.vsdx_decision_extractor import _is_pure_diamond_geometry
        el = _xml()
        assert _is_pure_diamond_geometry(el) is False

    def test_two_moveto_four_lineto_is_not_diamond(self):
        from Code.routes.vsdx_decision_extractor import _is_pure_diamond_geometry
        el = self._shape(
            '<Row T="MoveTo"/><Row T="MoveTo"/><Row T="LineTo"/>'
            '<Row T="LineTo"/><Row T="LineTo"/><Row T="LineTo"/>'
        )
        assert _is_pure_diamond_geometry(el) is False


# =============================================================================
# 7. _is_likely_annotation
# =============================================================================

class TestIsLikelyAnnotation:

    def test_long_text_is_annotation(self):
        from Code.routes.vsdx_decision_extractor import _is_likely_annotation
        assert _is_likely_annotation(_xml(), "diamond", "A" * 61) is True

    def test_exactly_60_chars_is_not_annotation(self):
        from Code.routes.vsdx_decision_extractor import _is_likely_annotation
        assert _is_likely_annotation(_xml(), "diamond", "A" * 60) is False

    def test_excluded_master_name_is_annotation(self):
        from Code.routes.vsdx_decision_extractor import _is_likely_annotation
        # "annotation" matches \bannotation\b
        assert _is_likely_annotation(_xml(), "annotation", "short") is True

    def test_excluded_master_note_is_annotation(self):
        from Code.routes.vsdx_decision_extractor import _is_likely_annotation
        assert _is_likely_annotation(_xml(), "note", "x") is True

    def test_large_width_is_annotation(self):
        from Code.routes.vsdx_decision_extractor import _is_likely_annotation
        el = ET.fromstring(
            f'<Shape xmlns="{NS}"><Cell N="Width" V="4.0"/><Cell N="Height" V="0.5"/></Shape>'
        )
        assert _is_likely_annotation(el, "diamond", "Decision") is True

    def test_large_height_is_annotation(self):
        from Code.routes.vsdx_decision_extractor import _is_likely_annotation
        el = ET.fromstring(
            f'<Shape xmlns="{NS}"><Cell N="Width" V="1.0"/><Cell N="Height" V="3.5"/></Shape>'
        )
        assert _is_likely_annotation(el, "diamond", "D") is True

    def test_normal_shape_is_not_annotation(self):
        from Code.routes.vsdx_decision_extractor import _is_likely_annotation
        el = ET.fromstring(
            f'<Shape xmlns="{NS}"><Cell N="Width" V="1.0"/><Cell N="Height" V="0.5"/></Shape>'
        )
        assert _is_likely_annotation(el, "decision", "Decision?") is False

    def test_layer2_with_text_is_annotation(self):
        from Code.routes.vsdx_decision_extractor import _is_likely_annotation
        el = ET.fromstring(
            f'<Shape xmlns="{NS}">'
            f'<Cell N="Width" V="1.0"/><Cell N="Height" V="0.5"/>'
            f'<Cell N="LayerMember" V="2"/>'
            f'</Shape>'
        )
        assert _is_likely_annotation(el, "diamond", "Legend text") is True


# =============================================================================
# 8. OUI_NON_RE
# =============================================================================

class TestOuiNonRegex:

    def setup_method(self):
        from Code.routes.vsdx_decision_extractor import OUI_NON_RE
        self.re = OUI_NON_RE

    def test_matches_oui_lowercase(self):
        assert self.re.match("oui")

    def test_matches_oui_uppercase(self):
        assert self.re.match("OUI")

    def test_matches_non_lowercase(self):
        assert self.re.match("non")

    def test_matches_yes(self):
        assert self.re.match("yes")

    def test_matches_no(self):
        assert self.re.match("no")

    def test_no_match_for_partial_word(self):
        assert not self.re.match("oui oui")

    def test_no_match_for_maybe(self):
        assert not self.re.match("maybe")

    def test_no_match_for_empty(self):
        assert not self.re.match("")


# =============================================================================
# 9. _infer_oui_non
# =============================================================================

class TestInferOuiNon:

    def test_single_outgoing_always_oui(self):
        from Code.routes.vsdx_decision_extractor import _infer_oui_non
        decisions = [{"id": "d1", "outgoing": [{"to_id": "t1"}], "incoming": []}]
        _infer_oui_non(decisions, {})
        assert decisions[0]["outgoing"][0]["inferred_badge"] == "Oui"

    def test_no_outgoing_no_crash(self):
        from Code.routes.vsdx_decision_extractor import _infer_oui_non
        decisions = [{"id": "d1", "outgoing": [], "incoming": []}]
        _infer_oui_non(decisions, {})  # doit s'exécuter sans lever d'exception

    def test_multiple_outgoing_no_incoming_all_empty_badge(self):
        from Code.routes.vsdx_decision_extractor import _infer_oui_non
        decisions = [{
            "id": "d1",
            "outgoing": [{"to_id": "t1"}, {"to_id": "t2"}],
            "incoming": [],
        }]
        _infer_oui_non(decisions, {})
        assert all(c.get("inferred_badge") == "" for c in decisions[0]["outgoing"])

    def test_empty_decisions_list_no_crash(self):
        from Code.routes.vsdx_decision_extractor import _infer_oui_non
        _infer_oui_non([], {})  # liste vide — ne doit pas lever d'exception


# =============================================================================
# 10. extract_decisions_from_vsdx (erreurs de fichier)
# =============================================================================

class TestExtractDecisionsFromVsdx:

    def test_result_has_required_keys(self):
        from Code.routes.vsdx_decision_extractor import extract_decisions_from_vsdx
        result = extract_decisions_from_vsdx("/nonexistent/file.vsdx")
        assert "decisions" in result
        assert "total_shapes" in result
        assert "total_connectors" in result
        assert "errors" in result

    def test_missing_file_returns_error(self):
        from Code.routes.vsdx_decision_extractor import extract_decisions_from_vsdx
        result = extract_decisions_from_vsdx("/nonexistent/file.vsdx")
        assert len(result["errors"]) > 0

    def test_missing_file_decisions_empty(self):
        from Code.routes.vsdx_decision_extractor import extract_decisions_from_vsdx
        result = extract_decisions_from_vsdx("/nonexistent/file.vsdx")
        assert result["decisions"] == []

    def test_bad_zip_returns_error(self):
        from Code.routes.vsdx_decision_extractor import extract_decisions_from_vsdx
        with tempfile.NamedTemporaryFile(suffix=".vsdx", delete=False) as f:
            f.write(b"not a valid zip content")
            path = f.name
        try:
            result = extract_decisions_from_vsdx(path)
            assert len(result["errors"]) > 0
        finally:
            os.unlink(path)

    def test_bad_zip_decisions_empty(self):
        from Code.routes.vsdx_decision_extractor import extract_decisions_from_vsdx
        with tempfile.NamedTemporaryFile(suffix=".vsdx", delete=False) as f:
            f.write(b"garbage")
            path = f.name
        try:
            result = extract_decisions_from_vsdx(path)
            assert result["decisions"] == []
        finally:
            os.unlink(path)


# =============================================================================
# 11. extract_decisions_from_vsdx — pipeline complet sur un VSDX synthétique
#
# Construit un vrai fichier .vsdx (zip contenant masters.xml + une page XML
# Visio) avec 3 scénarios de décision sur la même page :
#   - id "1"  : décision connectée explicitement (2 branches Oui/Non via texte
#               du connecteur) → exerce la classification géométrique multi-
#               branches de _infer_oui_non.
#   - id "52" : décision "posée sur une ligne" (pas de <Connect> la référençant)
#               → exerce la logique de splice (§4) et le raccourci "branche
#               unique = Oui" de _infer_oui_non.
#   - id "61" : décision connectée dont l'une des branches porte son badge
#               Oui/Non via un groupement Visio (connecteur + badge shape sous
#               un même parent) → exerce la détection de badge "par groupe" (§3a).
# =============================================================================

_MASTERS_XML = b"""<?xml version="1.0"?>
<Masters xmlns="http://schemas.microsoft.com/office/visio/2012/main">
  <Master ID="M1" NameU="Decision"/>
</Masters>"""

_PAGE_XML = b"""<?xml version="1.0"?>
<PageContents xmlns="http://schemas.microsoft.com/office/visio/2012/main">
  <Shapes>
    <Shape ID="0"><Cell N="PinX" V="5"/><Cell N="PinY" V="2"/><Text>Reception commande</Text></Shape>
    <Shape ID="1" Master="M1"><Cell N="PinX" V="5"/><Cell N="PinY" V="5"/><Text>Valide ?</Text></Shape>
    <Shape ID="2"><Cell N="PinX" V="5"/><Cell N="PinY" V="8"/><Text>Traiter commande</Text></Shape>
    <Shape ID="3"><Cell N="PinX" V="8"/><Cell N="PinY" V="5"/><Text>Rejeter commande</Text></Shape>
    <Shape ID="10"><Cell N="BeginX" V="5"/><Cell N="BeginY" V="2"/><Cell N="EndX" V="5"/><Cell N="EndY" V="5"/></Shape>
    <Shape ID="11"><Cell N="BeginX" V="5"/><Cell N="BeginY" V="5"/><Cell N="EndX" V="5"/><Cell N="EndY" V="8"/><Text>Oui</Text></Shape>
    <Shape ID="12"><Cell N="BeginX" V="5"/><Cell N="BeginY" V="5"/><Cell N="EndX" V="8"/><Cell N="EndY" V="5"/><Text>Non</Text></Shape>

    <Shape ID="50"><Cell N="PinX" V="0"/><Cell N="PinY" V="0"/><Text>A</Text></Shape>
    <Shape ID="51"><Cell N="PinX" V="10"/><Cell N="PinY" V="0"/><Text>B</Text></Shape>
    <Shape ID="52" Master="M1"><Cell N="PinX" V="5"/><Cell N="PinY" V="0.1"/><Text>Decision spliced</Text></Shape>
    <Shape ID="53"><Cell N="BeginX" V="0"/><Cell N="BeginY" V="0"/><Cell N="EndX" V="10"/><Cell N="EndY" V="0"/><Text>Oui</Text></Shape>

    <Shape ID="60"><Cell N="PinX" V="0"/><Cell N="PinY" V="-100"/><Text>F</Text></Shape>
    <Shape ID="61" Master="M1"><Cell N="PinX" V="0"/><Cell N="PinY" V="-103"/><Text>Second choix ?</Text></Shape>
    <Shape ID="62"><Cell N="PinX" V="0"/><Cell N="PinY" V="-106"/><Text>G</Text></Shape>
    <Shape ID="63"><Cell N="PinX" V="3"/><Cell N="PinY" V="-103"/><Text>H</Text></Shape>
    <Shape ID="70"><Cell N="BeginX" V="0"/><Cell N="BeginY" V="-100"/><Cell N="EndX" V="0"/><Cell N="EndY" V="-103"/></Shape>
    <Shape ID="72">
      <Shapes>
        <Shape ID="71"><Cell N="BeginX" V="0"/><Cell N="BeginY" V="-103"/><Cell N="EndX" V="0"/><Cell N="EndY" V="-106"/></Shape>
        <Shape ID="73"><Cell N="PinX" V="0"/><Cell N="PinY" V="-104.5"/><Text>Oui</Text></Shape>
      </Shapes>
    </Shape>
    <Shape ID="74"><Cell N="BeginX" V="0"/><Cell N="BeginY" V="-103"/><Cell N="EndX" V="3"/><Cell N="EndY" V="-103"/></Shape>
  </Shapes>
  <Connects>
    <Connect FromSheet="10" FromCell="BeginX" ToSheet="0"/>
    <Connect FromSheet="10" FromCell="EndX" ToSheet="1"/>
    <Connect FromSheet="11" FromCell="BeginX" ToSheet="1"/>
    <Connect FromSheet="11" FromCell="EndX" ToSheet="2"/>
    <Connect FromSheet="12" FromCell="BeginX" ToSheet="1"/>
    <Connect FromSheet="12" FromCell="EndX" ToSheet="3"/>

    <Connect FromSheet="53" FromCell="BeginX" ToSheet="50"/>
    <Connect FromSheet="53" FromCell="EndX" ToSheet="51"/>

    <Connect FromSheet="70" FromCell="BeginX" ToSheet="60"/>
    <Connect FromSheet="70" FromCell="EndX" ToSheet="61"/>
    <Connect FromSheet="71" FromCell="BeginX" ToSheet="61"/>
    <Connect FromSheet="71" FromCell="EndX" ToSheet="62"/>
    <Connect FromSheet="74" FromCell="BeginX" ToSheet="61"/>
    <Connect FromSheet="74" FromCell="EndX" ToSheet="63"/>
  </Connects>
</PageContents>"""


def _build_full_vsdx(path):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("visio/masters/masters.xml", _MASTERS_XML)
        zf.writestr("visio/pages/page1.xml", _PAGE_XML)
    return str(path)


class TestExtractDecisionsFromVsdxFullPipeline:

    def _decisions_by_id(self, tmp_path):
        from Code.routes.vsdx_decision_extractor import extract_decisions_from_vsdx
        path = _build_full_vsdx(tmp_path / "sample.vsdx")
        result = extract_decisions_from_vsdx(path)
        assert result["errors"] == []
        return {d["id"]: d for d in result["decisions"]}, result

    def test_finds_all_three_decisions(self, tmp_path):
        decisions, result = self._decisions_by_id(tmp_path)
        assert set(decisions.keys()) == {"1", "52", "61"}
        assert result["total_shapes"] == 20
        assert result["total_connectors"] == 14

    def test_explicit_decision_label_and_incoming(self, tmp_path):
        decisions, _ = self._decisions_by_id(tmp_path)
        d1 = decisions["1"]
        assert d1["label"] == "Valide ?"
        assert d1["splice"] is False
        assert len(d1["incoming"]) == 1
        assert d1["incoming"][0]["from_label"] == "Reception commande"

    def test_explicit_decision_geometry_classifies_oui_non_branches(self, tmp_path):
        """Le connecteur 'dans l'axe' de la décision est classé Oui, celui qui bifurque Non."""
        decisions, _ = self._decisions_by_id(tmp_path)
        outgoing_by_target = {o["to_id"]: o for o in decisions["1"]["outgoing"]}
        assert outgoing_by_target["2"]["badge"] == "Oui"
        assert outgoing_by_target["2"]["inferred_badge"] == "Oui"
        assert outgoing_by_target["3"]["badge"] == "Non"
        assert outgoing_by_target["3"]["inferred_badge"] == "Non"

    def test_spliced_decision_is_flagged_and_keeps_orig_connector(self, tmp_path):
        """Décision posée sur une ligne (aucun <Connect> direct) → splice=True."""
        decisions, _ = self._decisions_by_id(tmp_path)
        d52 = decisions["52"]
        assert d52["splice"] is True
        assert len(d52["outgoing"]) == 1
        assert d52["outgoing"][0]["to_id"] == "51"
        assert d52["outgoing"][0]["_orig_conn_id"] == "53"
        assert d52["outgoing"][0]["badge"] == "Oui"

    def test_spliced_decision_single_branch_always_oui(self, tmp_path):
        """Une décision spliced avec une seule sortie est toujours inférée 'Oui'."""
        decisions, _ = self._decisions_by_id(tmp_path)
        assert decisions["52"]["outgoing"][0]["inferred_badge"] == "Oui"

    def test_group_membership_propagates_badge_to_connector(self, tmp_path):
        """Un badge Oui/Non groupé (Visio) avec un connecteur lui attribue son badge."""
        decisions, _ = self._decisions_by_id(tmp_path)
        outgoing_by_target = {o["to_id"]: o for o in decisions["61"]["outgoing"]}
        assert outgoing_by_target["62"]["badge"] == "Oui"
        assert outgoing_by_target["63"]["badge"] == ""
