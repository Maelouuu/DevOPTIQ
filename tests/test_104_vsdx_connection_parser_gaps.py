"""Compléments de couverture pour Code/routes/vsdx_conection_parser.py."""
import os
import tempfile
import zipfile

NS = "http://schemas.microsoft.com/office/visio/2012/main"


def _page(inner):
    return f'<PageContents xmlns="{NS}">{inner}</PageContents>'


def _vsdx(pages):
    fd, path = tempfile.mkstemp(suffix=".vsdx")
    os.close(fd)
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in pages.items():
            zf.writestr(name, content)
    return path


def _simple_page(src_text, tgt_text, conn_name="N-Flux", conn_text="Donnee"):
    return _page(f"""
        <Shapes>
          <Shape ID="1" Name="A"><Text>{src_text}</Text></Shape>
          <Shape ID="2" Name="B"><Text>{tgt_text}</Text></Shape>
          <Shape ID="3" Name="{conn_name}"><Text>{conn_text}</Text></Shape>
        </Shapes>
        <Connects>
          <Connect FromSheet="3" FromCell="BeginX" ToSheet="1"/>
          <Connect FromSheet="3" FromCell="EndX" ToSheet="2"/>
        </Connects>""")


class TestVsdxConnectionParserGaps:

    def test_source_starting_with_resultat_is_skipped(self):
        from Code.routes.vsdx_conection_parser import VsdxConnectionParser
        path = _vsdx({"visio/pages/page1.xml": _simple_page("Résultat.X", "Cible")})
        try:
            conns, errors = VsdxConnectionParser(path).parse()
            assert errors == []
            assert conns == []
        finally:
            os.unlink(path)

    def test_multiple_pages_are_all_parsed(self):
        from Code.routes.vsdx_conection_parser import VsdxConnectionParser
        path = _vsdx({
            "visio/pages/page1.xml": _simple_page("A1", "B1"),
            "visio/pages/page2.xml": _simple_page("A2", "B2"),
        })
        try:
            conns, _ = VsdxConnectionParser(path).parse()
            assert {c["source_name"] for c in conns} == {"A1", "A2"}
        finally:
            os.unlink(path)

    def test_shape_without_text_falls_back_to_name(self):
        from Code.routes.vsdx_conection_parser import VsdxConnectionParser
        page = _page("""
            <Shapes>
              <Shape ID="1" Name="NomSource"/>
              <Shape ID="2" Name="NomCible"/>
              <Shape ID="3" Name="T-Declencheur"/>
            </Shapes>
            <Connects>
              <Connect FromSheet="3" FromCell="BeginX" ToSheet="1"/>
              <Connect FromSheet="3" FromCell="EndX" ToSheet="2"/>
            </Connects>""")
        path = _vsdx({"visio/pages/page1.xml": page})
        try:
            conns, _ = VsdxConnectionParser(path).parse()
            assert len(conns) == 1
            assert conns[0]["source_name"] == "NomSource"
            assert conns[0]["target_name"] == "NomCible"
            assert conns[0]["data_type"] == "déclenchante"
            assert conns[0]["data_name"] == "Declencheur"
        finally:
            os.unlink(path)

    def test_nested_text_is_flattened_and_whitespace_collapsed(self):
        from Code.routes.vsdx_conection_parser import VsdxConnectionParser
        p = VsdxConnectionParser("unused.vsdx")
        p._parse_page(_page(
            '<Shapes><Shape ID="1" Name="S"><Text>  Foo <cp/>\n  Bar </Text></Shape></Shapes>'
        ).encode(), [])
        assert p.shape_info["1"]["text"] == "Foo Bar"

    def test_flag_shape_listed_in_excluded_shapes(self):
        from Code.routes.vsdx_conection_parser import VsdxConnectionParser
        p = VsdxConnectionParser("unused.vsdx")
        p._parse_page(_page(
            '<Shapes><Shape ID="7" Name="F"><Cell N="LayerMember" V="6"/>'
            '<Text>Drapeau</Text></Shape></Shapes>'
        ).encode(), [])
        assert p.get_excluded_shapes() == [{"shape_id": "7", "text": "Drapeau"}]

    def test_unique_activities_sorted(self):
        from Code.routes.vsdx_conection_parser import VsdxConnectionParser
        p = VsdxConnectionParser("unused.vsdx")
        p.connections = [{"source_name": "Z", "target_name": "A"},
                         {"source_name": "M", "target_name": "A"}]
        assert p.get_unique_activities() == ["A", "M", "Z"]

    def test_non_page_xml_in_zip_gives_no_page_error(self):
        from Code.routes.vsdx_conection_parser import VsdxConnectionParser
        path = _vsdx({"visio/document.xml": "<a/>"})
        try:
            conns, errors = VsdxConnectionParser(path).parse()
            assert conns == []
            assert errors == ["Aucune page trouvée dans le fichier VSDX"]
        finally:
            os.unlink(path)
