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


def _vsdx_zip(page_xml, masters_xml=None, extra_pages=None):
    """Crée un fichier .vsdx (zip) temporaire avec une page1 et, optionnellement, des masters."""
    fd, path = tempfile.mkstemp(suffix=".vsdx")
    os.close(fd)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("visio/pages/page1.xml", page_xml)
        if masters_xml is not None:
            zf.writestr("visio/masters/masters.xml", masters_xml)
        if extra_pages:
            for name, content in extra_pages.items():
                zf.writestr(name, content)
    return path


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

    def test_whitespace_only_text_and_empty_name_normalized_to_none(self):
        """connector_text composé uniquement d'espaces + connector_name vide → data_name
        finit à '' (pas de préfixe pour le compléter) → normalisé explicitement à None."""
        _, dname = self.p._extract_data_info("", "   ")
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
# 4bis. VsdxConnectionParser._parse_page — construction des connexions
# =============================================================================

def _page_xml(shapes_xml, connects_xml):
    return f"""<PageContents xmlns="{NS}">
  <Shapes>
    {shapes_xml}
  </Shapes>
  <Connects>
    {connects_xml}
  </Connects>
</PageContents>"""


def _shape(shape_id, name="", text="", layer=None):
    layer_cell = f'<Cell N="LayerMember" V="{layer}"/>' if layer is not None else ""
    return f'<Shape ID="{shape_id}" Name="{name}">{layer_cell}<Text>{text}</Text></Shape>'


def _connect(from_sheet, from_cell, to_sheet):
    return f'<Connect FromSheet="{from_sheet}" FromCell="{from_cell}" ToSheet="{to_sheet}"/>'


def _parser():
    from Code.routes.vsdx_conection_parser import VsdxConnectionParser
    return VsdxConnectionParser.__new__(VsdxConnectionParser)


def _fresh_parser():
    p = _parser()
    p.shape_info = {}
    p.connections = []
    p.excluded_shape_ids = set()
    return p


class TestParsePage:

    def test_full_valid_connection_is_parsed(self):
        p = _fresh_parser()
        xml = _page_xml(
            _shape("1", name="ActA", text="Activité A")
            + _shape("2", name="ActB", text="Activité B")
            + _shape("3", name="N- Project Management", text="Planning prévisionnel"),
            _connect("3", "BeginX", "1") + _connect("3", "EndX", "2"),
        )
        p._parse_page(xml.encode("utf-8"), [])
        assert len(p.connections) == 1
        conn = p.connections[0]
        assert conn["source_name"] == "Activité A"
        assert conn["target_name"] == "Activité B"
        assert conn["data_name"] == "Planning prévisionnel"
        assert conn["data_type"] == "nourrissante"

    def test_shape_without_id_is_skipped(self):
        p = _fresh_parser()
        xml = f"""<PageContents xmlns="{NS}">
  <Shapes>
    <Shape Name="NoId"><Text>Sans ID</Text></Shape>
    {_shape("1", name="ActA", text="Activité A")}
  </Shapes>
  <Connects></Connects>
</PageContents>"""
        p._parse_page(xml.encode("utf-8"), [])
        assert "1" in p.shape_info
        assert len(p.shape_info) == 1

    def test_excluded_layer_flags_shape_and_drops_connection(self):
        p = _fresh_parser()
        xml = _page_xml(
            _shape("1", name="ActA", text="Activité A", layer="6")
            + _shape("2", name="ActB", text="Activité B"),
            _connect("3", "BeginX", "1") + _connect("3", "EndX", "2"),
        )
        p._parse_page(xml.encode("utf-8"), [])
        assert "1" in p.excluded_shape_ids
        assert p.connections == []

    def test_connect_missing_fromsheet_is_ignored(self):
        p = _fresh_parser()
        xml = _page_xml(
            _shape("1", text="Activité A") + _shape("2", text="Activité B"),
            '<Connect FromCell="BeginX" ToSheet="1"/>' + _connect("3", "EndX", "2"),
        )
        p._parse_page(xml.encode("utf-8"), [])
        assert p.connections == []

    def test_connector_with_only_source_is_skipped(self):
        """Un connecteur sans EndX (pas de target) ne produit pas de connexion."""
        p = _fresh_parser()
        xml = _page_xml(
            _shape("1", text="Activité A") + _shape("2", text="Activité B"),
            _connect("3", "BeginX", "1"),
        )
        p._parse_page(xml.encode("utf-8"), [])
        assert p.connections == []

    def test_missing_shape_name_and_text_skips_connection(self):
        """Shape source sans Name ni Text résolvable → nom vide → connexion ignorée."""
        p = _fresh_parser()
        xml = _page_xml(
            _shape("1", name="", text="") + _shape("2", text="Activité B"),
            _connect("3", "BeginX", "1") + _connect("3", "EndX", "2"),
        )
        p._parse_page(xml.encode("utf-8"), [])
        assert p.connections == []

    def test_resultat_prefix_source_is_excluded(self):
        p = _fresh_parser()
        xml = _page_xml(
            _shape("1", text="Résultat.Livraison") + _shape("2", text="Activité B"),
            _connect("3", "BeginX", "1") + _connect("3", "EndX", "2"),
        )
        p._parse_page(xml.encode("utf-8"), [])
        assert p.connections == []

    def test_resultat_prefix_target_is_excluded(self):
        p = _fresh_parser()
        xml = _page_xml(
            _shape("1", text="Activité A") + _shape("2", text="Résultat.Livraison"),
            _connect("3", "BeginX", "1") + _connect("3", "EndX", "2"),
        )
        p._parse_page(xml.encode("utf-8"), [])
        assert p.connections == []

    def test_connector_without_shape_info_still_resolves_names(self):
        """Connecteur sans Shape correspondant (conn_info vide) : data_name/data_type = None,
        mais la connexion source→target reste créée."""
        p = _fresh_parser()
        xml = _page_xml(
            _shape("1", text="Activité A") + _shape("2", text="Activité B"),
            _connect("99", "BeginX", "1") + _connect("99", "EndX", "2"),
        )
        p._parse_page(xml.encode("utf-8"), [])
        assert len(p.connections) == 1
        assert p.connections[0]["data_name"] is None
        assert p.connections[0]["data_type"] is None

    def test_malformed_xml_appends_parse_error(self):
        p = _fresh_parser()
        errors = []
        p._parse_page(b"<not><valid</xml", errors)
        assert len(errors) == 1
        assert "parsing" in errors[0].lower() or "xml" in errors[0].lower()
        assert p.connections == []

    def test_shape_falls_back_to_name_when_no_text(self):
        p = _fresh_parser()
        xml = _page_xml(
            _shape("1", name="ActASansTexte") + _shape("2", text="Activité B"),
            _connect("3", "BeginX", "1") + _connect("3", "EndX", "2"),
        )
        p._parse_page(xml.encode("utf-8"), [])
        assert len(p.connections) == 1
        assert p.connections[0]["source_name"] == "ActASansTexte"


class TestParseFullIntegration:

    def test_valid_vsdx_file_returns_connections_no_errors(self):
        from Code.routes.vsdx_conection_parser import VsdxConnectionParser
        page_xml = _page_xml(
            _shape("1", name="ActA", text="Activité A")
            + _shape("2", name="ActB", text="Activité B")
            + _shape("3", name="N- Fournitures", text="Bon de commande"),
            _connect("3", "BeginX", "1") + _connect("3", "EndX", "2"),
        )
        path = _vsdx_zip(page_xml)
        try:
            conns, errors = VsdxConnectionParser(path).parse()
            assert errors == []
            assert len(conns) == 1
            assert conns[0]["source_name"] == "Activité A"
            assert conns[0]["target_name"] == "Activité B"
        finally:
            os.unlink(path)

    def test_vsdx_without_page_files_returns_error(self):
        from Code.routes.vsdx_conection_parser import VsdxConnectionParser
        fd, path = tempfile.mkstemp(suffix=".vsdx")
        os.close(fd)
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("not_a_page.txt", "hello")
        try:
            conns, errors = VsdxConnectionParser(path).parse()
            assert conns == []
            assert any("page" in e.lower() for e in errors)
        finally:
            os.unlink(path)

    def test_get_excluded_shapes_returns_flagged_entries(self):
        from Code.routes.vsdx_conection_parser import VsdxConnectionParser
        page_xml = _page_xml(_shape("1", text="Drapeau A", layer="6"), "")
        path = _vsdx_zip(page_xml)
        try:
            p = VsdxConnectionParser(path)
            p.parse()
            excluded = p.get_excluded_shapes()
            assert len(excluded) == 1
            assert excluded[0]["shape_id"] == "1"
            assert excluded[0]["text"] == "Drapeau A"
        finally:
            os.unlink(path)


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

    def test_zip_without_pages_returns_explicit_error(self):
        from Code.routes.vsdx_decision_extractor import extract_decisions_from_vsdx
        fd, path = tempfile.mkstemp(suffix=".vsdx")
        os.close(fd)
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("readme.txt", "no pages here")
        try:
            result = extract_decisions_from_vsdx(path)
        finally:
            os.unlink(path)
        assert result["decisions"] == []
        assert any("Aucune page" in e for e in result["errors"])


# =============================================================================
# 11. extract_decisions_from_vsdx — flux complet via un .vsdx synthétique
# =============================================================================

MASTERS_XML = f'''<Masters xmlns="{NS}">
  <Master ID="1" NameU="Decision"/>
  <Master ID="2" NameU="Process"/>
</Masters>'''

# Start(10) --Oui(connecteur 100)--> Decision(20) --(101)--> OuiTarget(30)
#                                                --(102)--> NonTarget(40)
PAGE_BASIC_DECISION = f'''<PageContents xmlns="{NS}">
  <Shapes>
    <Shape ID="10" Master="2">
      <Cell N="PinX" V="100"/>
      <Cell N="PinY" V="110"/>
      <Text>Start</Text>
    </Shape>
    <Shape ID="20" Master="1">
      <Cell N="PinX" V="100"/>
      <Cell N="PinY" V="105"/>
      <Text>Decision?</Text>
    </Shape>
    <Shape ID="30" Master="2">
      <Cell N="PinX" V="100"/>
      <Cell N="PinY" V="100"/>
      <Text>OuiTarget</Text>
    </Shape>
    <Shape ID="40" Master="2">
      <Cell N="PinX" V="105"/>
      <Cell N="PinY" V="105"/>
      <Text>NonTarget</Text>
    </Shape>
    <Shape ID="100" Master="2">
      <Text>Oui</Text>
    </Shape>
    <Shape ID="101" Master="2"/>
    <Shape ID="102" Master="2"/>
  </Shapes>
  <Connects>
    <Connect FromSheet="100" FromCell="BeginX" ToSheet="10"/>
    <Connect FromSheet="100" FromCell="EndX" ToSheet="20"/>
    <Connect FromSheet="101" FromCell="BeginX" ToSheet="20"/>
    <Connect FromSheet="101" FromCell="EndX" ToSheet="30"/>
    <Connect FromSheet="102" FromCell="BeginX" ToSheet="20"/>
    <Connect FromSheet="102" FromCell="EndX" ToSheet="40"/>
  </Connects>
</PageContents>'''


class TestExtractDecisionsFullFlow:

    def test_single_decision_two_branches(self):
        from Code.routes.vsdx_decision_extractor import extract_decisions_from_vsdx
        path = _vsdx_zip(PAGE_BASIC_DECISION, MASTERS_XML)
        try:
            result = extract_decisions_from_vsdx(path)
        finally:
            os.unlink(path)
        assert result["errors"] == []
        assert result["total_shapes"] == 7
        assert result["total_connectors"] == 6
        assert len(result["decisions"]) == 1

        dec = result["decisions"][0]
        assert dec["id"] == "20"
        assert dec["label"] == "Decision?"
        assert dec["master_name"] == "decision"
        assert dec["splice"] is False
        assert len(dec["incoming"]) == 1
        assert dec["incoming"][0]["from_id"] == "10"
        assert dec["incoming"][0]["badge"] == "Oui"

        by_target = {o["to_id"]: o for o in dec["outgoing"]}
        assert by_target["30"]["inferred_badge"] == "Oui"
        assert by_target["40"]["inferred_badge"] == "Non"

    def test_malformed_masters_xml_does_not_crash(self):
        from Code.routes.vsdx_decision_extractor import extract_decisions_from_vsdx
        path = _vsdx_zip(PAGE_BASIC_DECISION, masters_xml="<not valid xml")
        try:
            result = extract_decisions_from_vsdx(path)
        finally:
            os.unlink(path)
        assert result["errors"] == []
        assert isinstance(result["decisions"], list)


PAGE_SECOND = f'''<PageContents xmlns="{NS}">
  <Shapes>
    <Shape ID="999" Master="2"><Text>ShouldNotBeCounted</Text></Shape>
    <Shape ID="998" Master="2"/>
    <Shape ID="997" Master="2"/>
  </Shapes>
</PageContents>'''


class TestExtractDecisionsMultiPage:

    def test_only_first_sorted_page_is_parsed(self):
        from Code.routes.vsdx_decision_extractor import extract_decisions_from_vsdx
        path = _vsdx_zip(
            PAGE_BASIC_DECISION, MASTERS_XML,
            extra_pages={"visio/pages/page2.xml": PAGE_SECOND},
        )
        try:
            result = extract_decisions_from_vsdx(path)
        finally:
            os.unlink(path)
        # page1.xml < page2.xml lexicographiquement → seule page1 est lue
        assert result["total_shapes"] == 7


PAGE_ANNOTATION_DIAMOND = f'''<PageContents xmlns="{NS}">
  <Shapes>
    <Shape ID="50" Master="2">
      <Cell N="PinX" V="0"/>
      <Cell N="PinY" V="0"/>
      <Cell N="Width" V="5"/>
      <Cell N="Height" V="1"/>
      <Text>Big diamond legend</Text>
      <Section N="Geometry">
        <Row T="MoveTo"/>
        <Row T="LineTo"/>
        <Row T="LineTo"/>
        <Row T="LineTo"/>
        <Row T="LineTo"/>
      </Section>
    </Shape>
  </Shapes>
</PageContents>'''


class TestExtractDecisionsAnnotationExclusion:

    def test_large_diamond_geometry_excluded_as_annotation(self):
        from Code.routes.vsdx_decision_extractor import extract_decisions_from_vsdx
        path = _vsdx_zip(PAGE_ANNOTATION_DIAMOND)
        try:
            result = extract_decisions_from_vsdx(path)
        finally:
            os.unlink(path)
        assert result["decisions"] == []
        assert result["total_shapes"] == 1


PAGE_GROUP_BADGE = f'''<PageContents xmlns="{NS}">
  <Shapes>
    <Shape ID="20" Master="1">
      <Cell N="PinX" V="0"/>
      <Cell N="PinY" V="5"/>
      <Text>Decision?</Text>
    </Shape>
    <Shape ID="30" Master="2">
      <Cell N="PinX" V="0"/>
      <Cell N="PinY" V="0"/>
      <Text>Target</Text>
    </Shape>
    <Shape ID="999" Master="2">
      <Shapes>
        <Shape ID="100" Master="2"/>
        <Shape ID="100b" Master="2"><Text>Oui</Text></Shape>
      </Shapes>
    </Shape>
  </Shapes>
  <Connects>
    <Connect FromSheet="100" FromCell="BeginX" ToSheet="20"/>
    <Connect FromSheet="100" FromCell="EndX" ToSheet="30"/>
  </Connects>
</PageContents>'''


class TestExtractDecisionsBadgeGroupMembership:

    def test_badge_via_group_membership(self):
        from Code.routes.vsdx_decision_extractor import extract_decisions_from_vsdx
        path = _vsdx_zip(PAGE_GROUP_BADGE, MASTERS_XML)
        try:
            result = extract_decisions_from_vsdx(path)
        finally:
            os.unlink(path)
        dec = result["decisions"][0]
        assert dec["outgoing"][0]["badge"] == "Oui"


PAGE_PROXIMITY_BADGE = f'''<PageContents xmlns="{NS}">
  <Shapes>
    <Shape ID="20" Master="1">
      <Cell N="PinX" V="0"/>
      <Cell N="PinY" V="5"/>
      <Text>Decision?</Text>
    </Shape>
    <Shape ID="30" Master="2">
      <Cell N="PinX" V="0"/>
      <Cell N="PinY" V="0"/>
      <Text>Target</Text>
    </Shape>
    <Shape ID="100" Master="2"/>
    <Shape ID="500" Master="2">
      <Cell N="PinX" V="0"/>
      <Cell N="PinY" V="2.4"/>
      <Text>Non</Text>
    </Shape>
  </Shapes>
  <Connects>
    <Connect FromSheet="100" FromCell="BeginX" ToSheet="20"/>
    <Connect FromSheet="100" FromCell="EndX" ToSheet="30"/>
  </Connects>
</PageContents>'''


class TestExtractDecisionsBadgeProximityFallback:

    def test_badge_assigned_via_proximity(self):
        from Code.routes.vsdx_decision_extractor import extract_decisions_from_vsdx
        path = _vsdx_zip(PAGE_PROXIMITY_BADGE, MASTERS_XML)
        try:
            result = extract_decisions_from_vsdx(path)
        finally:
            os.unlink(path)
        dec = result["decisions"][0]
        assert dec["outgoing"][0]["badge"] == "Non"


PAGE_SPLICE = f'''<PageContents xmlns="{NS}">
  <Shapes>
    <Shape ID="5" Master="2">
      <Cell N="PinX" V="0"/>
      <Cell N="PinY" V="0"/>
      <Text>SrcA</Text>
    </Shape>
    <Shape ID="6" Master="2">
      <Cell N="PinX" V="10"/>
      <Cell N="PinY" V="0"/>
      <Text>TgtB</Text>
    </Shape>
    <Shape ID="7" Master="2">
      <Cell N="BeginX" V="0"/><Cell N="BeginY" V="0"/>
      <Cell N="EndX" V="10"/><Cell N="EndY" V="0"/>
      <Text>Suite</Text>
    </Shape>
    <Shape ID="8" Master="3">
      <Cell N="PinX" V="5"/>
      <Cell N="PinY" V="0"/>
      <Text>Choix?</Text>
      <Section N="Geometry">
        <Row T="MoveTo"/>
        <Row T="LineTo"/>
        <Row T="LineTo"/>
        <Row T="LineTo"/>
        <Row T="LineTo"/>
      </Section>
    </Shape>
  </Shapes>
  <Connects>
    <Connect FromSheet="7" FromCell="BeginX" ToSheet="5"/>
    <Connect FromSheet="7" FromCell="EndX" ToSheet="6"/>
  </Connects>
</PageContents>'''

SPLICE_MASTERS = f'''<Masters xmlns="{NS}">
  <Master ID="2" NameU="Process"/>
  <Master ID="3" NameU="Etape"/>
</Masters>'''


class TestExtractDecisionsSplice:

    def test_unconnected_diamond_is_spliced_onto_passing_connector(self):
        from Code.routes.vsdx_decision_extractor import extract_decisions_from_vsdx
        path = _vsdx_zip(PAGE_SPLICE, SPLICE_MASTERS)
        try:
            result = extract_decisions_from_vsdx(path)
        finally:
            os.unlink(path)
        assert len(result["decisions"]) == 1
        dec = result["decisions"][0]
        assert dec["id"] == "8"
        assert dec["splice"] is True
        assert len(dec["incoming"]) == 1
        assert dec["incoming"][0]["from_id"] == "5"
        assert len(dec["outgoing"]) == 1
        assert dec["outgoing"][0]["to_id"] == "6"
        assert dec["outgoing"][0]["badge"] == "Suite"
        # Le comptage des connecteurs porte sur les <Connect> d'origine,
        # pas sur les connecteurs synthétiques créés par la scission (splice).
        assert result["total_connectors"] == 2


# =============================================================================
# 12. _infer_oui_non — branches géométriques avancées
# =============================================================================

class TestInferOuiNonAdvanced:

    def test_cyclic_incoming_excluded_from_forward_direction(self):
        from Code.routes.vsdx_decision_extractor import _infer_oui_non
        decisions = [{
            "id": "d1",
            "incoming": [{"from_id": "A"}, {"from_id": "B"}],
            "outgoing": [{"to_id": "A"}, {"to_id": "C"}],
        }]
        shape_info = {
            "d1": {"pin_x": 0, "pin_y": 0},
            "A": {"pin_x": 0, "pin_y": -5},
            "B": {"pin_x": 0, "pin_y": 5},
            "C": {"pin_x": 0, "pin_y": -10},
        }
        _infer_oui_non(decisions, shape_info)
        by_target = {o["to_id"]: o for o in decisions[0]["outgoing"]}
        # Si A (cyclique) n'était pas exclu, son vecteur annulerait celui de B
        # et laisserait les badges vides — ce n'est pas le cas ici.
        assert by_target["C"]["inferred_badge"] == "Oui"

    def test_incoming_vectors_cancel_out_leaves_badges_empty(self):
        from Code.routes.vsdx_decision_extractor import _infer_oui_non
        decisions = [{
            "id": "d1",
            "incoming": [{"from_id": "A"}, {"from_id": "B"}],
            "outgoing": [{"to_id": "C"}, {"to_id": "D"}],
        }]
        shape_info = {
            "d1": {"pin_x": 0, "pin_y": 0},
            "A": {"pin_x": 0, "pin_y": 5},
            "B": {"pin_x": 0, "pin_y": -5},
            "C": {"pin_x": 5, "pin_y": 0},
            "D": {"pin_x": -5, "pin_y": 0},
        }
        _infer_oui_non(decisions, shape_info)
        assert decisions[0]["outgoing"][0]["inferred_badge"] == ""
        assert decisions[0]["outgoing"][1]["inferred_badge"] == ""

    def test_no_valid_incoming_vector_leaves_badges_empty(self):
        from Code.routes.vsdx_decision_extractor import _infer_oui_non
        decisions = [{
            "id": "d1",
            "incoming": [{"from_id": "A"}],
            "outgoing": [{"to_id": "C"}, {"to_id": "D"}],
        }]
        shape_info = {
            "d1": {"pin_x": 5, "pin_y": 5},
            "A": {"pin_x": 0, "pin_y": 0},
            "C": {"pin_x": 10, "pin_y": 5},
            "D": {"pin_x": 5, "pin_y": 10},
        }
        _infer_oui_non(decisions, shape_info)
        assert all(o["inferred_badge"] == "" for o in decisions[0]["outgoing"])

    def test_orig_conn_id_direction_preferred_over_target_center(self):
        from Code.routes.vsdx_decision_extractor import _infer_oui_non
        decisions = [{
            "id": "d1",
            "incoming": [{"from_id": "S"}],
            "outgoing": [
                {"to_id": "T1", "_orig_conn_id": "c1"},
                {"to_id": "T2", "_orig_conn_id": "c2"},
            ],
        }]
        shape_info = {
            "d1": {"pin_x": 0, "pin_y": 0},
            "S": {"pin_x": 0, "pin_y": 10},
            # Centres de cibles volontairement trompeurs : s'ils étaient
            # utilisés, le verdict serait inversé.
            "T1": {"pin_x": 0, "pin_y": 10},
            "T2": {"pin_x": 0, "pin_y": 10},
            # Géométrie réelle du connecteur d'origine (BeginXY → EndXY)
            "c1": {"begin_x": 1, "begin_y": 1, "end_x": 1, "end_y": -9},
            "c2": {"begin_x": 1, "begin_y": 1, "end_x": 11, "end_y": 1},
        }
        _infer_oui_non(decisions, shape_info)
        by_target = {o["to_id"]: o for o in decisions[0]["outgoing"]}
        assert by_target["T1"]["inferred_badge"] == "Oui"
        assert by_target["T2"]["inferred_badge"] == "Non"

    def test_falls_back_to_target_center_when_orig_conn_missing(self):
        from Code.routes.vsdx_decision_extractor import _infer_oui_non
        decisions = [{
            "id": "d1",
            "incoming": [{"from_id": "S"}],
            "outgoing": [
                {"to_id": "T1", "_orig_conn_id": ""},
                {"to_id": "T2"},
            ],
        }]
        shape_info = {
            "d1": {"pin_x": 0, "pin_y": 0},
            "S": {"pin_x": 0, "pin_y": 10},
            "T1": {"pin_x": 0, "pin_y": -10},
            "T2": {"pin_x": 10, "pin_y": 0},
        }
        _infer_oui_non(decisions, shape_info)
        by_target = {o["to_id"]: o for o in decisions[0]["outgoing"]}
        assert by_target["T1"]["inferred_badge"] == "Oui"
        assert by_target["T2"]["inferred_badge"] == "Non"

    def test_target_and_orig_missing_leaves_badge_empty(self):
        from Code.routes.vsdx_decision_extractor import _infer_oui_non
        decisions = [{
            "id": "d1",
            "incoming": [{"from_id": "S"}],
            "outgoing": [{"to_id": "Ghost"}, {"to_id": "T2"}],
        }]
        shape_info = {
            "d1": {"pin_x": 0, "pin_y": 0},
            "S": {"pin_x": 0, "pin_y": 10},
            "Ghost": {"pin_x": 0, "pin_y": 0},
            "T2": {"pin_x": 0, "pin_y": -10},
        }
        _infer_oui_non(decisions, shape_info)
        by_target = {o["to_id"]: o for o in decisions[0]["outgoing"]}
        assert by_target["Ghost"]["inferred_badge"] == ""
        assert by_target["T2"]["inferred_badge"] == "Oui"

    def test_ninety_degree_fallback_promotes_one_to_oui(self):
        from Code.routes.vsdx_decision_extractor import _infer_oui_non
        decisions = [{
            "id": "d1",
            "incoming": [{"from_id": "S"}],
            "outgoing": [{"to_id": "TA"}, {"to_id": "TB"}],
        }]
        shape_info = {
            "d1": {"pin_x": 0, "pin_y": 0},
            "S": {"pin_x": 0, "pin_y": 10},
            "TA": {"pin_x": 8.66, "pin_y": -5},
            "TB": {"pin_x": -8.66, "pin_y": 5},
        }
        _infer_oui_non(decisions, shape_info)
        by_target = {o["to_id"]: o for o in decisions[0]["outgoing"]}
        assert by_target["TA"]["inferred_badge"] == "Oui"
        assert by_target["TB"]["inferred_badge"] == "Non"
