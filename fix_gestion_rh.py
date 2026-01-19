#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SCRIPT DE DIAGNOSTIC ET CORRECTION - Page Gestion RH
=====================================================
Ce script vérifie et corrige les problèmes potentiels
qui causent l'erreur 500 sur la page /gestion_rh/

UTILISATION:
    python fix_gestion_rh.py
"""

import os
import sqlite3

# Chemin vers la base de données (ajuster si nécessaire)
DB_PATH = os.path.join(os.path.dirname(__file__), "Code", "instance", "optiq.db")

# Alternative si le chemin est différent
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(os.path.dirname(__file__), "instance", "optiq.db")


def main():
    print("=" * 70)
    print("DIAGNOSTIC - Erreur page Gestion RH")
    print("=" * 70)

    if not os.path.exists(DB_PATH):
        print(f"\n❌ Base de données non trouvée!")
        print(f"   Chemins testés:")
        print(f"   - Code/instance/optiq.db")
        print(f"   - instance/optiq.db")
        print(f"\n   Modifiez DB_PATH dans ce script avec le bon chemin.")
        return False

    print(f"\n📁 Base de données: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # ============================================
        # 1. Vérifier si la table entreprise_settings existe
        # ============================================
        print("\n" + "-" * 50)
        print("1. Vérification de la table entreprise_settings")
        print("-" * 50)
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='entreprise_settings'
        """)
        
        if not cursor.fetchone():
            print("   ❌ La table 'entreprise_settings' N'EXISTE PAS!")
            print("   → Création de la table...")
            
            cursor.execute("""
                CREATE TABLE entreprise_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    work_hours_per_day REAL,
                    work_days_per_week REAL,
                    work_weeks_per_year REAL,
                    work_days_per_year REAL,
                    entity_id INTEGER
                )
            """)
            conn.commit()
            print("   ✓ Table créée avec succès!")
        else:
            print("   ✓ La table 'entreprise_settings' existe")

        # ============================================
        # 2. Vérifier la colonne entity_id
        # ============================================
        print("\n" + "-" * 50)
        print("2. Vérification de la colonne entity_id")
        print("-" * 50)
        
        cursor.execute("PRAGMA table_info(entreprise_settings)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"   Colonnes actuelles: {columns}")
        
        if 'entity_id' not in columns:
            print("   ❌ La colonne 'entity_id' N'EXISTE PAS!")
            print("   → Ajout de la colonne...")
            
            cursor.execute("ALTER TABLE entreprise_settings ADD COLUMN entity_id INTEGER")
            conn.commit()
            print("   ✓ Colonne ajoutée avec succès!")
        else:
            print("   ✓ La colonne 'entity_id' existe")

        # ============================================
        # 3. Vérifier la table entities et l'entité active
        # ============================================
        print("\n" + "-" * 50)
        print("3. Vérification des entités")
        print("-" * 50)
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='entities'")
        if not cursor.fetchone():
            print("   ❌ La table 'entities' n'existe pas!")
            print("   → L'application n'est probablement pas initialisée correctement.")
        else:
            cursor.execute("SELECT id, name, is_active FROM entities")
            entities = cursor.fetchall()
            
            if not entities:
                print("   ⚠️  Aucune entité dans la base de données!")
                print("   → Vous devez créer au moins une entité.")
            else:
                print(f"   Entités trouvées: {len(entities)}")
                active_count = 0
                for e in entities:
                    status = "🟢 ACTIVE" if e[2] else "⚪"
                    print(f"      - ID {e[0]}: {e[1]} {status}")
                    if e[2]:
                        active_count += 1
                
                if active_count == 0:
                    print("\n   ⚠️  AUCUNE ENTITÉ ACTIVE!")
                    print("   → Activation de la première entité...")
                    
                    cursor.execute("UPDATE entities SET is_active = 1 WHERE id = ?", (entities[0][0],))
                    conn.commit()
                    print(f"   ✓ Entité '{entities[0][1]}' activée!")
                elif active_count > 1:
                    print(f"\n   ⚠️  {active_count} entités actives (devrait être 1)")

        # ============================================
        # 4. Associer les paramètres existants à l'entité active
        # ============================================
        print("\n" + "-" * 50)
        print("4. Association des paramètres à l'entité active")
        print("-" * 50)
        
        cursor.execute("SELECT id FROM entities WHERE is_active = 1 LIMIT 1")
        row = cursor.fetchone()
        
        if row:
            active_entity_id = row[0]
            cursor.execute(
                "UPDATE entreprise_settings SET entity_id = ? WHERE entity_id IS NULL",
                (active_entity_id,)
            )
            updated = cursor.rowcount
            conn.commit()
            
            if updated > 0:
                print(f"   ✓ {updated} ligne(s) associée(s) à l'entité {active_entity_id}")
            else:
                print("   ✓ Tous les paramètres sont déjà associés")
        else:
            print("   ⚠️  Pas d'entité active - impossible d'associer les paramètres")

        # ============================================
        # Résumé
        # ============================================
        print("\n" + "=" * 70)
        print("✅ DIAGNOSTIC ET CORRECTIONS TERMINÉS")
        print("=" * 70)
        print("\nRedémarrez votre serveur Flask et testez la page /gestion_rh/")
        
        return True

    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    main()