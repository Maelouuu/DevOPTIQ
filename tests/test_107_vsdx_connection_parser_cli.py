"""Couverture : exception générique du parseur et point d'entrée CLI de
Code/routes/vsdx_conection_parser.py."""
import os
import runpy
import sys
import tempfile
import zipfile

import pytest

NS = "http://schemas.microsoft.com/office/visio/2012/main"
MODULE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "Code", "routes", "vsdx_conection_parser.py",
)

PAGE_OK = f"""<PageContents xmlns="{NS}">
  <Shapes>
    <Shape ID="1" Name="A"><Text>Source</Text></Shape>
    <Shape ID="2" Name="B"><Text>Cible</Text></Shape>
    <Shape ID="3" Name="N-Flux"><Text>Donnee</Text></Shape>
  </Shapes>
  <Connects>
    <Connect FromSheet="3" FromCell="BeginX" ToSheet="1"/>
    <Connect FromSheet="3" FromCell="EndX" ToSheet="2"/>
  </Connects>
</PageContents>"""


# ⚠️ Le CLI s'exécute depuis la SOURCE (`runpy.run_path`), et l'arbre d'image
# est compilé en bytecode : les `.py` y sont supprimés. Sans cette garde les
# trois cas rougissaient à chaque exécution sur l'instance.
pytestmark = pytest.mark.skipif(
    not os.path.exists(MODULE_PATH),
    reason="source Python absente (arbre bytecode-only) : le CLI n'y est pas lançable")


def _vsdx(pages):
    fd, path = tempfile.mkstemp(suffix=".vsdx")
    os.close(fd)
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in pages.items():
            zf.writestr(name, content)
    return path


def _run_cli(argv):
    old = sys.argv
    sys.argv = argv
    try:
        runpy.run_path(MODULE_PATH, run_name="__main__")
    finally:
        sys.argv = old


class TestVsdxConnectionParserCli:

    def test_unexpected_exception_is_reported_as_parsing_error(self, monkeypatch):
        from Code.routes.vsdx_conection_parser import VsdxConnectionParser
        path = _vsdx({"visio/pages/page1.xml": PAGE_OK})

        def boom(self, page_xml, errors):
            raise RuntimeError("kaboom")

        monkeypatch.setattr(VsdxConnectionParser, "_parse_page", boom)
        try:
            conns, errors = VsdxConnectionParser(path).parse()
        finally:
            os.unlink(path)
        assert conns == []
        assert errors == ["Erreur lors du parsing: kaboom"]

    def test_cli_without_argument_prints_usage_and_exits_1(self, capsys):
        try:
            _run_cli(["vsdx_conection_parser.py"])
            raised = None
        except SystemExit as e:
            raised = e.code
        assert raised == 1
        assert "Usage: python vsdx_connection_parser.py" in capsys.readouterr().out

    def test_cli_prints_connections_found(self, capsys):
        path = _vsdx({"visio/pages/page1.xml": PAGE_OK})
        try:
            _run_cli(["vsdx_conection_parser.py", path])
        finally:
            os.unlink(path)
        out = capsys.readouterr().out
        assert "Connexions trouvées: 1" in out
        assert "Source -> Cible" in out
        assert "Data: 'Donnee'" in out

    def test_cli_prints_errors_for_corrupt_file(self, capsys):
        fd, path = tempfile.mkstemp(suffix=".vsdx")
        os.write(fd, b"pas un zip")
        os.close(fd)
        try:
            _run_cli(["vsdx_conection_parser.py", path])
        finally:
            os.unlink(path)
        out = capsys.readouterr().out
        assert "Erreurs:" in out
        assert "corrompu ou invalide" in out
        assert "Connexions trouvées: 0" in out
