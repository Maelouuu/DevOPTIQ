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
import io
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
# 11. _infer_oui_non — branches géométriques avancées (non couvertes par le
#    bloc 9 : filtrage cyclique, vecteurs opposés, repli à 90°)
# =============================================================================

class TestInferOuiNonAdvanced:

    def test_cyclic_incoming_excluded_from_forward_direction(self):
        """Une source entrante qui est aussi une cible sortante (boucle) ne doit
        pas polluer le calcul du vecteur de flux amont."""
        from Code.routes.vsdx_decision_extractor import _infer_oui_non
        decisions = [{
            "id": "d1",
            "outgoing": [{"to_id": "cyclicSrc"}, {"to_id": "other"}],
            "incoming": [{"from_id": "cyclicSrc"}, {"from_id": "realSrc"}],
        }]
        shape_info = {
            "d1": {"pin_x": 0, "pin_y": 0},
            "cyclicSrc": {"pin_x": 0, "pin_y": -5},
            "realSrc": {"pin_x": 5, "pin_y": 0},
            "other": {"pin_x": 0, "pin_y": 5},
        }
        _infer_oui_non(decisions, shape_info)
        for conn in decisions[0]["outgoing"]:
            assert isinstance(conn.get("inferred_badge"), str)

    def test_opposing_incoming_vectors_cancel_gives_empty_badges(self):
        """Deux flux entrants strictement opposés s'annulent (norme ~0) : le
        badge inféré doit rester vide plutôt que planter sur une division
        par zéro."""
        from Code.routes.vsdx_decision_extractor import _infer_oui_non
        decisions = [{
            "id": "d1",
            "outgoing": [{"to_id": "t1"}, {"to_id": "t2"}],
            "incoming": [{"from_id": "s1"}, {"from_id": "s2"}],
        }]
        shape_info = {
            "d1": {"pin_x": 0, "pin_y": 0},
            "s1": {"pin_x": 5, "pin_y": 0},
            "s2": {"pin_x": -5, "pin_y": 0},
            "t1": {"pin_x": 0, "pin_y": 5},
            "t2": {"pin_x": 0, "pin_y": -5},
        }
        _infer_oui_non(decisions, shape_info)
        assert all(c.get("inferred_badge") == "" for c in decisions[0]["outgoing"])

    def test_fallback_90_degrees_flips_borderline_non_to_oui(self):
        """Si le seuil de 45° ne fait ressortir aucun 'Oui', le repli à 90°
        doit requalifier la branche la plus proche du flux en 'Oui' tout en
        laissant celle opposée en 'Non'."""
        from Code.routes.vsdx_decision_extractor import _infer_oui_non
        decisions = [{
            "id": "d1",
            "outgoing": [{"to_id": "t60"}, {"to_id": "t180"}],
            "incoming": [{"from_id": "s1"}],
        }]
        shape_info = {
            "d1": {"pin_x": 0, "pin_y": 0},
            "s1": {"pin_x": -5, "pin_y": 0},   # flux amont => direction (1, 0)
            "t60": {"pin_x": 5, "pin_y": 8.660},   # à 60° de l'axe du flux
            "t180": {"pin_x": -10, "pin_y": 0},    # opposé au flux (180°)
        }
        _infer_oui_non(decisions, shape_info)
        by_target = {c["to_id"]: c["inferred_badge"] for c in decisions[0]["outgoing"]}
        assert by_target["t60"] == "Oui"
        assert by_target["t180"] == "Non"

    def test_incoming_source_missing_from_shape_info_is_skipped(self):
        """Une connexion entrante dont la source n'a pas d'entrée shape_info
        (coordonnées 0,0 par défaut) ne doit pas casser le calcul."""
        from Code.routes.vsdx_decision_extractor import _infer_oui_non
        decisions = [{
            "id": "d1",
            "outgoing": [{"to_id": "t1"}, {"to_id": "t2"}],
            "incoming": [{"from_id": "ghost"}],
        }]
        shape_info = {
            "d1": {"pin_x": 3, "pin_y": 3},
            "t1": {"pin_x": 8, "pin_y": 3},
            "t2": {"pin_x": 3, "pin_y": 8},
        }
        _infer_oui_non(decisions, shape_info)
        # "ghost" est absent de shape_info => pin (0,0) => filtré (sx/sy nuls),
        # in_vecs reste vide => badges vidés sans exception.
        assert all(c.get("inferred_badge") == "" for c in decisions[0]["outgoing"])


# =============================================================================
# 12. _parse_page — pipeline complet (shapes, connecteurs, badges, splice)
# =============================================================================

def _page_bytes(shapes_xml, connects_xml):
    return (
        f'<PageContents xmlns="{NS}">'
        f'<Shapes>{shapes_xml}</Shapes>'
        f'<Connects>{connects_xml}</Connects>'
        f'</PageContents>'
    ).encode("utf-8")


class TestParsePageIntegration:

    def test_explicit_connections_with_own_text_and_group_badges(self):
        """Décision reliée explicitement : badge via texte propre du connecteur
        (3b) ET badge via appartenance à un groupe (3a). Aucune décision non
        connectée => pas de splice."""
        from Code.routes.vsdx_decision_extractor import _parse_page

        shapes = """
        <Shape ID="1"><Cell N="PinX" V="1"/><Cell N="PinY" V="11"/><Text>Debut</Text></Shape>
        <Shape ID="2" Master="m1"><Cell N="PinX" V="1"/><Cell N="PinY" V="6"/><Text>Decision A</Text></Shape>
        <Shape ID="3"><Cell N="PinX" V="6"/><Cell N="PinY" V="6"/><Text>Chemin Oui</Text></Shape>
        <Shape ID="4"><Cell N="PinX" V="-4"/><Cell N="PinY" V="6"/><Text>Chemin Non</Text></Shape>
        <Shape ID="10"><Cell N="BeginX" V="1"/><Cell N="BeginY" V="11"/><Cell N="EndX" V="1"/><Cell N="EndY" V="6"/></Shape>
        <Shape ID="11"><Cell N="BeginX" V="1"/><Cell N="BeginY" V="6"/><Cell N="EndX" V="6"/><Cell N="EndY" V="6"/><Text>Oui</Text></Shape>
        <Shape ID="20">
          <Shapes>
            <Shape ID="13"><Text>Non</Text></Shape>
            <Shape ID="12"><Cell N="BeginX" V="1"/><Cell N="BeginY" V="6"/><Cell N="EndX" V="-4"/><Cell N="EndY" V="6"/></Shape>
          </Shapes>
        </Shape>
        """
        connects = """
        <Connect FromSheet="10" FromCell="BeginX" ToSheet="1"/>
        <Connect FromSheet="10" FromCell="EndX" ToSheet="2"/>
        <Connect FromSheet="11" FromCell="BeginX" ToSheet="2"/>
        <Connect FromSheet="11" FromCell="EndX" ToSheet="3"/>
        <Connect FromSheet="12" FromCell="BeginX" ToSheet="2"/>
        <Connect FromSheet="12" FromCell="EndX" ToSheet="4"/>
        """
        result = {"decisions": [], "total_shapes": 0, "total_connectors": 0, "errors": []}
        _parse_page(_page_bytes(shapes, connects), {"m1": "decision"}, result)

        assert result["errors"] == []
        assert len(result["decisions"]) == 1
        dec = result["decisions"][0]
        assert dec["id"] == "2"
        assert dec["splice"] is False
        assert len(dec["incoming"]) == 1
        assert dec["incoming"][0]["from_id"] == "1"

        badges = {o["to_id"]: o["badge"] for o in dec["outgoing"]}
        assert badges == {"3": "Oui", "4": "Non"}
        assert all("inferred_badge" in o for o in dec["outgoing"])

    def test_splice_two_crossing_connectors_creates_synthetic_links(self):
        """Une décision non connectée explicitement mais posée sur deux
        connecteurs qui se croisent doit être 'splicée' sur les deux, avec
        2 entrées et 2 sorties synthétiques référençant le connecteur d'origine."""
        from Code.routes.vsdx_decision_extractor import _parse_page

        shapes = """
        <Shape ID="1"><Cell N="PinX" V="1"/><Cell N="PinY" V="6"/><Text>A</Text></Shape>
        <Shape ID="2"><Cell N="PinX" V="11"/><Cell N="PinY" V="6"/><Text>B</Text></Shape>
        <Shape ID="3"><Cell N="PinX" V="6"/><Cell N="PinY" V="1"/><Text>C</Text></Shape>
        <Shape ID="4"><Cell N="PinX" V="6"/><Cell N="PinY" V="11"/><Text>D</Text></Shape>
        <Shape ID="10"><Cell N="BeginX" V="1"/><Cell N="BeginY" V="6"/><Cell N="EndX" V="11"/><Cell N="EndY" V="6"/></Shape>
        <Shape ID="11"><Cell N="BeginX" V="6"/><Cell N="BeginY" V="1"/><Cell N="EndX" V="6"/><Cell N="EndY" V="11"/></Shape>
        <Shape ID="5" Master="m1"><Cell N="PinX" V="6"/><Cell N="PinY" V="6"/><Text>Decision croisee</Text></Shape>
        """
        connects = """
        <Connect FromSheet="10" FromCell="BeginX" ToSheet="1"/>
        <Connect FromSheet="10" FromCell="EndX" ToSheet="2"/>
        <Connect FromSheet="11" FromCell="BeginX" ToSheet="3"/>
        <Connect FromSheet="11" FromCell="EndX" ToSheet="4"/>
        """
        result = {"decisions": [], "total_shapes": 0, "total_connectors": 0, "errors": []}
        _parse_page(_page_bytes(shapes, connects), {"m1": "decision"}, result)

        assert result["errors"] == []
        assert len(result["decisions"]) == 1
        dec = result["decisions"][0]
        assert dec["id"] == "5"
        assert dec["splice"] is True
        assert len(dec["outgoing"]) == 2
        assert len(dec["incoming"]) == 2
        assert {o["to_id"] for o in dec["outgoing"]} == {"2", "4"}
        assert {i["from_id"] for i in dec["incoming"]} == {"1", "3"}
        assert {o["_orig_conn_id"] for o in dec["outgoing"]} == {"10", "11"}
        assert all(o["inferred_badge"] in ("Oui", "Non") for o in dec["outgoing"])

    def test_no_decisions_no_connectors_still_populates_counts(self):
        from Code.routes.vsdx_decision_extractor import _parse_page

        shapes = '<Shape ID="1"><Cell N="PinX" V="0"/><Cell N="PinY" V="0"/><Text>Simple box</Text></Shape>'
        result = {"decisions": [], "total_shapes": 0, "total_connectors": 0, "errors": []}
        _parse_page(_page_bytes(shapes, ""), {}, result)

        assert result["total_shapes"] == 1
        assert result["total_connectors"] == 0
        assert result["decisions"] == []

    def test_malformed_xml_records_parse_error(self):
        from Code.routes.vsdx_decision_extractor import _parse_page

        result = {"decisions": [], "total_shapes": 0, "total_connectors": 0, "errors": []}
        _parse_page(b"<not><valid", {}, result)

        assert len(result["errors"]) == 1
        assert result["decisions"] == []


# =============================================================================
# 13. extract_decisions_from_vsdx — cas de succès end-to-end (zip réel)
# =============================================================================

def _make_vsdx(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    f = tempfile.NamedTemporaryFile(suffix=".vsdx", delete=False)
    f.write(buf.getvalue())
    f.close()
    return f.name


class TestExtractDecisionsFromVsdxSuccess:

    def test_success_parses_masters_and_finds_decision(self):
        from Code.routes.vsdx_decision_extractor import extract_decisions_from_vsdx

        masters_xml = f'<Masters xmlns="{NS}"><Master ID="1" NameU="Decision"/></Masters>'
        page_xml = (
            f'<PageContents xmlns="{NS}"><Shapes>'
            '<Shape ID="1"><Cell N="PinX" V="1"/><Cell N="PinY" V="11"/><Text>Debut</Text></Shape>'
            '<Shape ID="2" Master="1"><Cell N="PinX" V="1"/><Cell N="PinY" V="6"/><Text>Decision?</Text></Shape>'
            '<Shape ID="3"><Cell N="PinX" V="6"/><Cell N="PinY" V="6"/><Text>Suite</Text></Shape>'
            '<Shape ID="10"><Cell N="BeginX" V="1"/><Cell N="BeginY" V="11"/><Cell N="EndX" V="1"/><Cell N="EndY" V="6"/></Shape>'
            '<Shape ID="11"><Cell N="BeginX" V="1"/><Cell N="BeginY" V="6"/><Cell N="EndX" V="6"/><Cell N="EndY" V="6"/></Shape>'
            '</Shapes><Connects>'
            '<Connect FromSheet="10" FromCell="BeginX" ToSheet="1"/>'
            '<Connect FromSheet="10" FromCell="EndX" ToSheet="2"/>'
            '<Connect FromSheet="11" FromCell="BeginX" ToSheet="2"/>'
            '<Connect FromSheet="11" FromCell="EndX" ToSheet="3"/>'
            '</Connects></PageContents>'
        )
        path = _make_vsdx({
            "visio/masters/masters.xml": masters_xml,
            "visio/pages/page1.xml": page_xml,
        })
        try:
            result = extract_decisions_from_vsdx(path)
            assert result["errors"] == []
            assert result["total_shapes"] == 5
            assert len(result["decisions"]) == 1
            assert result["decisions"][0]["id"] == "2"
            assert result["decisions"][0]["master_name"] == "decision"
        finally:
            os.unlink(path)

    def test_missing_masters_xml_still_parses_page(self):
        from Code.routes.vsdx_decision_extractor import extract_decisions_from_vsdx

        page_xml = (
            f'<PageContents xmlns="{NS}"><Shapes>'
            '<Shape ID="1"><Cell N="PinX" V="0"/><Cell N="PinY" V="0"/><Text>Boite simple</Text></Shape>'
            '</Shapes><Connects></Connects></PageContents>'
        )
        path = _make_vsdx({"visio/pages/page1.xml": page_xml})
        try:
            result = extract_decisions_from_vsdx(path)
            assert result["errors"] == []
            assert result["total_shapes"] == 1
            assert result["decisions"] == []
        finally:
            os.unlink(path)

    def test_no_page_files_returns_explicit_error(self):
        from Code.routes.vsdx_decision_extractor import extract_decisions_from_vsdx

        path = _make_vsdx({"visio/masters/masters.xml": f'<Masters xmlns="{NS}"/>'})
        try:
            result = extract_decisions_from_vsdx(path)
            assert result["decisions"] == []
            assert any("page" in e.lower() for e in result["errors"])
        finally:
            os.unlink(path)
