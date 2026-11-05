"""
Export de prospects depuis l'API publique Recherche d'entreprises (data.gouv.fr).
Pas de clé API. Limite : ~7 requêtes/seconde, 25 résultats par page.

Usage :  pip install requests
         python export_prospects.py
Sortie : prospects_sirene.csv (importable dans Notion)
"""
import csv
import time
import requests

API = "https://recherche-entreprises.api.gouv.fr/search"

DEPARTEMENTS = ["44", "85", "49", "35", "56"]

# Codes NAF à tester (ajoute / retire librement)
NAF = [
    "46.69B",  # gros fournitures et équipements industriels divers
    "46.74A",  # gros quincaillerie
    "46.74B",  # gros plomberie-chauffage
    "46.73A",  # gros bois et matériaux de construction
    "46.61Z",  # gros matériel agricole
    "46.34Z",  # gros boissons
    "46.33Z",  # gros produits laitiers, oeufs, huiles
    "46.38B",  # gros alimentaire spécialisé divers
    "46.39B",  # gros alimentaire non spécialisé
    "46.31Z",  # gros fruits et légumes
    "10.61A",  # meunerie
    "10.72Z",  # biscuiterie
    "16.24Z",  # emballages bois / palettes
    "25.94Z",  # vis et boulons
    "28.12Z",  # équipements hydrauliques et pneumatiques
    "20.41Z",  # savons, détergents
]

# Tranches INSEE : 12 = 20-49, 21 = 50-99, 22 = 100-199
TRANCHES = "12,21,22"


def fetch(dep, naf):
    page = 1
    while True:
        params = {
            "departement": dep,
            "activite_principale": naf,
            "tranche_effectif_salarie": TRANCHES,
            "etat_administratif": "A",
            "per_page": 25,
            "page": page,
        }
        r = requests.get(API, params=params, timeout=30)
        if r.status_code == 429:
            time.sleep(2)
            continue
        r.raise_for_status()
        data = r.json()
        yield from data.get("results", [])
        if page >= data.get("total_pages", 1):
            break
        page += 1
        time.sleep(0.2)


def dirigeants(e):
    personnes, morales = [], []
    for d in e.get("dirigeants", []) or []:
        if d.get("type_dirigeant") == "personne morale" or d.get("denomination"):
            morales.append(f"{d.get('denomination', '')} ({d.get('qualite', '')})")
        else:
            nom = f"{d.get('prenoms', '')} {d.get('nom', '')}".strip()
            personnes.append(f"{nom} ({d.get('qualite', '')})")
    return "; ".join(personnes), "; ".join(morales)


def derniere_finance(e):
    fin = e.get("finances") or {}
    if not fin:
        return "", ""
    annee = max(fin.keys())
    return annee, fin[annee].get("ca", "")


rows, vus = [], set()
for dep in DEPARTEMENTS:
    for naf in NAF:
        for e in fetch(dep, naf):
            siren = e.get("siren")
            siege = e.get("siege") or {}
            # On ne garde que les entreprises dont le SIÈGE est dans la zone
            # (sinon les agences locales de groupes nationaux remontent)
            if siren in vus or siege.get("departement") not in DEPARTEMENTS:
                continue
            vus.add(siren)
            pers, morales = dirigeants(e)
            annee, ca = derniere_finance(e)
            rows.append({
                "Entreprise": e.get("nom_complet"),
                "SIREN": siren,
                "NAF": e.get("activite_principale"),
                "Tranche effectif": e.get("tranche_effectif_salarie"),
                "Catégorie": e.get("categorie_entreprise"),
                "Ville siège": siege.get("libelle_commune"),
                "Dépt": siege.get("departement"),
                "Nb établissements": e.get("nombre_etablissements_ouverts"),
                "CA": ca,
                "Année CA": annee,
                "Dirigeants (personnes)": pers,
                "Dirigeants (sociétés) : signal de groupe ?": morales,
                "Fiche": f"https://annuaire-entreprises.data.gouv.fr/entreprise/{siren}",
                "LinkedIn": "https://www.linkedin.com/search/results/people/?keywords="
                            + requests.utils.quote(e.get("nom_complet") or ""),
            })
        print(f"{dep} {naf} -> {len(rows)} entreprises au total")

with open("prospects_sirene.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print(f"OK : {len(rows)} lignes -> prospects_sirene.csv")