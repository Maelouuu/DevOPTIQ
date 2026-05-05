# Code/routes/vsdx_conection_parser.py
"""
Parseur de connexions VSDX pour l'import des liens entre activités.

CORRECTIONS:
- v2: Utilisation de itertext() pour récupérer tout le texte
- v3: Exclusion des drapeaux (layer 6) des connexions
- v4: FIX data_name - utiliser le TEXT du connecteur, pas l'attribut Name
"""

import zipfile
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Tuple, Set
import os


class VsdxConnectionParser:
    """Parse les connexions d'un fichier VSDX."""
    
    VISIO_NS = {'v': 'http://schemas.microsoft.com/office/visio/2012/main'}
    
    # Layers à exclure des connexions (drapeaux, légendes, etc.)
    EXCLUDED_LAYERS = {'6'}  # 6 = Result/Drapeau
    
    def __init__(self, vsdx_path: str):
        self.vsdx_path = vsdx_path
        self.shape_info: Dict[str, Dict] = {}
        self.connections: List[Dict] = []
        self.excluded_shape_ids: Set[str] = set()
        
    def parse(self) -> Tuple[List[Dict], List[str]]:
        errors = []
        
        if not os.path.exists(self.vsdx_path):
            return [], [f"Fichier non trouvé: {self.vsdx_path}"]
        
        if not self.vsdx_path.lower().endswith('.vsdx'):
            return [], ["Le fichier doit être au format .vsdx"]
        
        try:
            with zipfile.ZipFile(self.vsdx_path, 'r') as zf:
                page_files = [f for f in zf.namelist() if 'pages/page' in f and f.endswith('.xml')]
                
                if not page_files:
                    return [], ["Aucune page trouvée dans le fichier VSDX"]
                
                for page_file in page_files:
                    page_xml = zf.read(page_file)
                    self._parse_page(page_xml, errors)
                    
        except zipfile.BadZipFile:
            return [], ["Le fichier VSDX est corrompu ou invalide"]
        except Exception as e:
            return [], [f"Erreur lors du parsing: {str(e)}"]
        
        return self.connections, errors
    
    def _parse_page(self, page_xml: bytes, errors: List[str]):
        try:
            root = ET.fromstring(page_xml)
        except ET.ParseError as e:
            errors.append(f"Erreur parsing XML: {str(e)}")
            return
        
        # 1) Récupérer tous les shapes avec leurs infos
        shapes = root.findall('.//v:Shape', self.VISIO_NS)
        
        for shape in shapes:
            shape_id = shape.get('ID')
            if not shape_id:
                continue
                
            shape_name = shape.get('Name', '')
            
            # Récupérer le layer
            layer_cell = shape.find(".//v:Cell[@N='LayerMember']", self.VISIO_NS)
            layer = layer_cell.get('V') if layer_cell is not None else None
            
            # Marquer les shapes à exclure (drapeaux layer 6)
            if layer in self.EXCLUDED_LAYERS:
                self.excluded_shape_ids.add(shape_id)
            
            # Récupérer le texte avec itertext()
            text_elem = shape.find('.//v:Text', self.VISIO_NS)
            text = ''
            if text_elem is not None:
                text = ''.join(text_elem.itertext()).strip()
                text = ' '.join(text.split())
            
            self.shape_info[shape_id] = {
                'name': shape_name,
                'text': text,
                'layer': layer
            }
        
        # 2) Récupérer toutes les connexions
        connects = root.findall('.//v:Connect', self.VISIO_NS)
        connectors: Dict[str, Dict] = {}
        
        for connect in connects:
            from_sheet = connect.get('FromSheet')
            from_cell = connect.get('FromCell', '')
            to_sheet = connect.get('ToSheet')
            
            if not from_sheet or not to_sheet:
                continue
            
            if from_sheet not in connectors:
                connectors[from_sheet] = {'source': None, 'target': None}
            
            if 'BeginX' in from_cell:
                connectors[from_sheet]['source'] = to_sheet
            elif 'EndX' in from_cell:
                connectors[from_sheet]['target'] = to_sheet
        
        # 3) Construire la liste des connexions
        for conn_id, data in connectors.items():
            source_id = data.get('source')
            target_id = data.get('target')
            
            if not source_id or not target_id:
                continue
            
            # Ignorer les connexions impliquant des drapeaux (layer 6)
            if source_id in self.excluded_shape_ids or target_id in self.excluded_shape_ids:
                continue
            
            source_info = self.shape_info.get(source_id, {})
            target_info = self.shape_info.get(target_id, {})
            conn_info = self.shape_info.get(conn_id, {})
            
            source_name = source_info.get('text') or source_info.get('name', '')
            target_name = target_info.get('text') or target_info.get('name', '')
            
            if not source_name or not target_name:
                continue
            
            if source_name.startswith('Résultat.') or target_name.startswith('Résultat.'):
                continue
            
            # *** FIX v4: Extraire correctement le nom et type de la donnée ***
            connector_text = conn_info.get('text') or ''  # Le VRAI nom de la donnée
            connector_name = conn_info.get('name') or ''  # Sert juste pour le type (T/N prefix)
            
            data_type, data_name = self._extract_data_info(connector_name, connector_text)
            
            self.connections.append({
                'source_shape_id': source_id,
                'source_name': source_name.strip(),
                'target_shape_id': target_id,
                'target_name': target_name.strip(),
                'connector_id': conn_id,
                'data_name': data_name,
                'data_type': data_type
            })
    
    def _extract_data_info(self, connector_name: str, connector_text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extrait le type et le nom de la donnée.
        
        IMPORTANT v4:
        - data_name = le TEXTE du connecteur (connector_text), c'est le vrai nom affiché
        - data_type = extrait du préfixe de connector_name (T=déclenchante, N=nourrissante)
        
        L'attribut Name du connecteur (ex: "N- Project Management") indique le TYPE,
        mais le TEXTE (ex: "Planning prévisionnel projet") est le vrai nom de la donnée.
        """
        data_type = None
        
        # Le nom de la donnée est TOUJOURS le texte affiché sur le connecteur
        data_name = connector_text.strip() if connector_text else None
        
        # Le type est extrait du préfixe de l'attribut Name
        name = connector_name.strip()
        
        if name.startswith('T ') or name.startswith('T-') or name.startswith('T '):
            data_type = 'déclenchante'
        elif name.startswith('N ') or name.startswith('N-') or name.startswith('N '):
            data_type = 'nourrissante'
        
        # Si pas de texte mais un name avec préfixe, utiliser la partie après le préfixe
        if not data_name and name:
            if name.startswith(('T ', 'T-', 'N ', 'N-')):
                data_name = name[2:].strip() if len(name) > 2 else None
            else:
                data_name = name
        
        if data_name == '':
            data_name = None
            
        return data_type, data_name
    
    def get_unique_activities(self) -> List[str]:
        activities = set()
        for conn in self.connections:
            activities.add(conn['source_name'])
            activities.add(conn['target_name'])
        return sorted(list(activities))
    
    def get_excluded_shapes(self) -> List[Dict]:
        return [
            {'shape_id': sid, 'text': self.shape_info.get(sid, {}).get('text', '?')}
            for sid in self.excluded_shape_ids
        ]


def parse_vsdx_connections(vsdx_path: str) -> Tuple[List[Dict], List[str]]:
    parser = VsdxConnectionParser(vsdx_path)
    return parser.parse()


def normalize_activity_name(name: str) -> str:
    if not name:
        return ''
    name = name.replace("'", "'").replace("'", "'").replace("`", "'")
    name = ' '.join(name.lower().split())
    return name


def validate_connections_against_activities(
    connections: List[Dict], 
    existing_activities: Dict[str, int]
) -> Tuple[List[Dict], List[Dict], List[str]]:
    valid_connections = []
    invalid_connections = []
    missing_activities = set()
    
    normalized_activities = {}
    for name, act_id in existing_activities.items():
        norm_name = normalize_activity_name(name)
        normalized_activities[norm_name] = (name, act_id)
    
    for conn in connections:
        source_name = conn['source_name']
        target_name = conn['target_name']
        
        source_norm = normalize_activity_name(source_name)
        target_norm = normalize_activity_name(target_name)
        
        source_match = normalized_activities.get(source_norm)
        target_match = normalized_activities.get(target_norm)
        
        if source_match and target_match:
            conn_with_ids = conn.copy()
            conn_with_ids['source_activity_id'] = source_match[1]
            conn_with_ids['target_activity_id'] = target_match[1]
            valid_connections.append(conn_with_ids)
        else:
            invalid_connections.append(conn)
            if not source_match:
                missing_activities.add(source_name)
            if not target_match:
                missing_activities.add(target_name)
    
    return valid_connections, invalid_connections, sorted(list(missing_activities))


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python vsdx_connection_parser.py <fichier.vsdx>")
        sys.exit(1)
    
    vsdx_path = sys.argv[1]
    parser = VsdxConnectionParser(vsdx_path)
    connections, errors = parser.parse()
    
    if errors:
        print("Erreurs:")
        for e in errors:
            print(f"  - {e}")
    
    excluded = parser.get_excluded_shapes()
    if excluded:
        print(f"\nShapes exclus (drapeaux): {len(excluded)}")
        for ex in excluded:
            print(f"  - Shape {ex['shape_id']}: {ex['text']}")
    
    print(f"\nConnexions trouvées: {len(connections)}")
    for conn in connections:
        dtype = f"[{conn['data_type']}]" if conn['data_type'] else ""
        print(f"  {conn['source_name']} -> {conn['target_name']}")
        print(f"    Data: '{conn['data_name']}' {dtype}")