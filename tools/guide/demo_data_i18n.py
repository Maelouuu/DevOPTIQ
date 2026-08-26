# -*- coding: utf-8 -*-
"""Jeu de donnees de demonstration bilingue (guide utilisateur).

Le guide existe en francais ET en anglais : les captures et les videos doivent
montrer des donnees dans la langue de la page, sinon le lecteur anglais lit une
carto francaise (et inversement pour les roles, qui sont anglais dans
example.vsdx). On traduit donc les libelles du diagramme AVANT de l'injecter,
et tout le contenu enrichi (taches, outils, competences...) est decline.

Les valeurs techniques envoyees aux API temps (« heures », « hebdomadaire »...)
restent en francais : ce sont des CLES backend, pas de l'affichage.
"""
import os

LANG = (os.environ.get('GUIDE_LANG') or 'fr').lower()
EN = LANG == 'en'


def T(fr, en):
    return en if EN else fr


# -- Libelles du diagramme : source (example_diagram.json) -> langue cible --
# Bandes : anglaises dans le VSDX d'origine. Formes et fleches : francaises.
# Les fautes de frappe du fichier source sont corrigees au passage.
BANDES = {
    "End user":               ("Utilisateur final",     "End user"),
    "Tutor Coach":            ("Tuteur / Coach",        "Tutor / Coach"),
    "Pruchase Request":       ("Demande d'achat",       "Purchase request"),
    "Department request":     ("Demande de service",    "Department request"),
    "Prescriber":             ("Prescripteur",          "Prescriber"),
    "Customer relation":      ("Relation client",       "Customer relation"),
    "Administration":         ("Administration",        "Administration"),
    "Measurement":            ("Métrologie",       "Measurement"),
    "Project":                ("Projet",                "Project"),
    "Engineering":            ("Bureau d'études",  "Engineering"),
    "Production":             ("Production",            "Production"),
    "Planning":               ("Ordonnancement",        "Planning"),
    "Logistic":               ("Logistique",            "Logistics"),
    "Maintenance":            ("Maintenance",           "Maintenance"),
    "Pilotage":               ("Pilotage",              "Steering"),
    "Internal subcontractor": ("Sous-traitant interne", "Internal subcontractor"),
    "Network":                ("Réseau",           "Network"),
    "Regional pilotage":      ("Pilotage régional", "Regional steering"),
    "Institutional":          ("Institutionnel",        "Institutional"),
    "Supplier":               ("Fournisseur",           "Supplier"),
}

FORMES = {
    "Mise à jour du Web":
        ("Mise à jour du site", "Website update"),
    "Traitement de la demande":
        ("Traitement de la demande", "Request handling"),
    "Analyse de faisabilité":
        ("Analyse de faisabilité", "Feasibility analysis"),
    "Réalisation de l’offre":
        ("Réalisation de l’offre", "Offer preparation"),
    "Préparation projet":
        ("Préparation projet", "Project preparation"),
    "Prise en compte de l’offre":
        ("Prise en compte de l’offre", "Offer acknowledgement"),
    "Cotation":
        ("Cotation", "Pricing"),
    "Négociation de l’ offre":
        ("Négociation de l’offre", "Offer negotiation"),
    "Test laboratoire":
        ("Test laboratoire", "Laboratory test"),
    "Comité de décision":
        ("Comité de décision", "Decision committee"),
    "Contrôle Qualité":
        ("Contrôle qualité", "Quality control"),
    "Contrôle fournisseur":
        ("Contrôle fournisseur", "Supplier control"),
    "Réalisation des facture":
        ("Réalisation des factures", "Invoicing"),
    "Consultation du site":
        ("Consultation du site", "Website browsing"),
    "Relance":
        ("Relance", "Payment reminder"),
    "Encaissement":
        ("Encaissement", "Payment collection"),
}

FLECHES = {
    "Lancement de l’’analyse de faisabilité":
        ("Lancement de l’analyse de faisabilité", "Feasibility analysis kick-off"),
    "Lancement pré-projet":
        ("Lancement pré-projet", "Pre-project kick-off"),
    "Offre à réaliser":
        ("Offre à réaliser", "Offer to prepare"),
    "Liste des composants":
        ("Liste des composants", "Bill of materials"),
    "Planning prévisionnel projet":
        ("Planning prévisionnel projet", "Project schedule"),
    "Offre":
        ("Offre", "Offer"),
    "Demande de cotation":
        ("Demande de cotation", "Quotation request"),
    "cotation":
        ("Cotation", "Pricing"),
    "Produits sélectionnés":
        ("Produits sélectionnés", "Selected products"),
    "Offre à suivre":
        ("Offre à suivre", "Offer to follow up"),
    "Enquête client":
        ("Enquête client", "Customer survey"),
    "Demande de tests qualité":
        ("Demande de tests qualité", "Quality test request"),
    "Feuille de test":
        ("Feuille de test", "Test sheet"),
    "Résultat strétégique":
        ("Résultat stratégique", "Strategic outcome"),
    "Ajustement":
        ("Ajustement", "Adjustment"),
    "Evaluation produit":
        ("Évaluation produit", "Product assessment"),
    "Résultat contrôle produit":
        ("Résultat contrôle produit", "Product control result"),
    "REX":
        ("REX", "Lessons learned"),
    "Feuille de prix":
        ("Feuille de prix", "Price sheet"),
    "AMDEC":
        ("AMDEC", "FMEA"),
    "Bon de commande":
        ("Bon de commande", "Purchase order"),
    "Demande de négociation":
        ("Demande de négociation", "Negotiation request"),
    "Consutation":
        ("Consultation", "Consultation"),
    "Update":
        ("Mise à jour", "Update"),
    "Impayés":
        ("Impayés", "Unpaid invoices"),
    "Résultat labo client":
        ("Résultat labo client", "Customer lab result"),
    "PAiement":
        ("Paiement", "Payment"),
}


def _cle(libelle):
    # Visio coupe les libelles avec des retours ligne et des doubles espaces :
    # la cle de lookup normalise, sinon la moitie des fleches ne matche pas.
    return ' '.join((libelle or '').split())


_INDEX = {nom: {_cle(k): v for k, v in table.items()}
          for nom, table in (('bandes', BANDES), ('formes', FORMES), ('fleches', FLECHES))}


def _tr(nom_table, libelle):
    paire = _INDEX[nom_table].get(_cle(libelle))
    if not paire:
        return libelle
    return paire[1] if EN else paire[0]


def traduire_diagramme(diagram):
    """Reecrit les libelles du diagramme dans la langue courante (sur place)."""
    for b in diagram.get('bands', []) or []:
        b['label'] = _tr('bandes', b.get('label'))
    for s in diagram.get('shapes', []) or []:
        s['label'] = _tr('formes', s.get('label'))
    for c in diagram.get('connections', []) or []:
        if c.get('label'):
            c['label'] = _tr('fleches', c.get('label'))
    return diagram


def libelles_non_traduits(diagram):
    """Libelles du diagramme sans entree dans les tables (controle du seed)."""
    manque = []
    for nom, cle, table in (('bandes', 'bands', BANDES), ('formes', 'shapes', FORMES),
                            ('fleches', 'connections', FLECHES)):
        idx = _INDEX[nom]
        for el in diagram.get(cle, []) or []:
            lab = el.get('label')
            if lab and _cle(lab) not in idx:
                manque.append('%s: %r' % (nom, lab))
    return sorted(set(manque))


# -- Contenu enrichi --
ENTITE_NOM = T("AFDEC Industrie", "AFDEC Industries")
ENTITE_DESC = T("Site de production — démo", "Production site — demo")

OUTILS = [
    (T("ERP OptiFab", "OptiFab ERP"),
     T("ERP de gestion de production", "Production management ERP")),
    (T("CRM VentePlus", "SalesPlus CRM"),
     T("Suivi des demandes et offres clients", "Customer request and offer tracking")),
    (T("Suite bureautique", "Office suite"),
     T("Documents, tableurs et messagerie", "Documents, spreadsheets and email")),
    (T("Banc de test labo", "Lab test bench"),
     T("Essais et mesures en laboratoire", "Laboratory tests and measurements")),
    (T("GED Docurex", "Docurex DMS"),
     T("Gestion électronique des documents", "Electronic document management")),
]

VERBES = T(["Préparer", "Vérifier", "Saisir", "Valider", "Transmettre", "Contrôler"],
           ["Prepare", "Check", "Enter", "Approve", "Forward", "Inspect"])


def description_activite(nom):
    return T("Réaliser « %s » dans le respect des standards qualité." % nom,
             "Carry out “%s” in line with quality standards." % nom)


def competence_activite(nom):
    return T("Produire le résultat attendu de « %s » conforme du premier coup" % nom,
             "Deliver the expected output of “%s” right first time" % nom)


SAVOIR = T("Processus qualité ISO 9001 du site", "Site ISO 9001 quality process")
SAVOIR_FAIRE = T("Utiliser l'ERP OptiFab au quotidien", "Use the OptiFab ERP daily")
APTITUDE = T("Rigueur et sens du détail", "Rigour and attention to detail")
HSC = T("Communiquer efficacement avec les parties prenantes",
        "Communicate effectively with stakeholders")
HSC_JUSTIF = T("Interfaces quotidiennes avec les clients et l'atelier",
               "Daily interfaces with customers and the shop floor")

MISSIONS = T(["Garantir le traitement des demandes clients de bout en bout.",
              "Piloter la réalisation des offres et leur négociation.",
              "Assurer la préparation et le suivi des projets."],
             ["Guarantee end-to-end handling of customer requests.",
              "Steer offer preparation and negotiation.",
              "Ensure project preparation and follow-up."])

PROJET_NOM = T("Lancement gamme 2026", "2026 product line launch")
CHARGE_ROLE = T("Charge type — semaine standard", "Typical workload — standard week")
FAIBLESSE = T("Données client incomplètes à la réception",
              "Incomplete customer data on receipt")
