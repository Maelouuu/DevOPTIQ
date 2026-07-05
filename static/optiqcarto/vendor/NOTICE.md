# Third-party: libavoid-js

Routage orthogonal des flèches de l'éditeur OptiqCarto.

- **libavoid-js** 0.5.0-beta.5 — https://github.com/Aksem/libavoid-js
- Portage WebAssembly de **libavoid** (projet Adaptagrams, Monash University) —
  http://www.adaptagrams.org/ / https://github.com/mjwybrow/adaptagrams
- Licence : **LGPL-2.1-or-later** (voir `libavoid-LICENSE.txt`).

Fichiers vendorisés non modifiés : `libavoid.mjs` (glue Emscripten, uniquement la
ligne `sourceMappingURL` retirée) et `libavoid.wasm`. Aucune modification du code
de libavoid lui-même. Algorithme : Wybrow, Marriott, Stuckey — « Orthogonal
Connector Routing », Graph Drawing 2009.
