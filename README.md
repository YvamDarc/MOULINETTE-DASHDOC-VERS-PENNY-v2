# FEC + pièces jointes pour Pennylane

Le libellé d’écriture (EcritureLib) est le nom du client uniquement, sur toutes les lignes de chaque facture ou avoir : client, produits et TVA. Il est repris depuis « Client à facturer » dans le CSV, ou depuis le libellé auxiliaire client de l’écriture dans le FEC. La référence de facture reste dans PieceRef. Le tableau permet toujours de modifier manuellement le libellé avant export. Si un FEC ne renseigne aucun nom de client dans ses auxiliaires, le libellé d’origine est conservé : vérifier ce cas dans le tableau.

## Lancer sur ordinateur
Python 3.11 ou 3.12 recommandé. Dans ce dossier :

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Streamlit Community Cloud
Mettre app.py, core.py et requirements.txt à la racine d'un dépôt GitHub, puis sélectionner app.py dans Streamlit Cloud. Ne pas mettre les fichiers clients dans le dépôt. Utiliser un accès privé pour les données du cabinet ; cette application n'intègre pas d'authentification propre.

## Utilisation
1. Déposer le ZIP exporté par le logiciel source, contenant le CSV comptable (format du fichier fourni) ou un FEC tabulé avec en-têtes, et les PDF.
2. Choisir UNE source. Le XLSX et l'export Cegid sont ignorés : ce sont des variantes des mêmes écritures.
3. Journal VT proposé pour les ventes ; il s'applique à toutes les lignes. Adapter pour un autre type d'export.
4. Vérifier les auxiliaires. Un même numéro utilisé pour plusieurs noms reçoit des propositions numériques distinctes, appliquées automatiquement et modifiables. Télécharger la correspondance et la recharger chaque mois pour garder les mêmes comptes, même si un seul des clients revient. Utiliser de préférence les comptes existants dans Pennylane.
5. Corriger au besoin les lignes et associations PDF. Le rapprochement initial utilise exactement le nom du PDF sans extension.
6. Télécharger le pack, puis l'extraire. Importer FEC_IMPORT.txt dans Pennylane via Saisie comptable > Imports > FEC. Vérifier le mapping, les tiers et les options de conversion des écritures en factures.
7. Une fois importé, cliquer sur le trombone « Joindre une archive » et charger PIECES_JOINTES.zip. Ne pas déposer le pack global dans ce champ.

Les références sont sécurisées et dédoublonnées, les PDF renommés avec la même référence sans extension dans PieceRef. L'équilibre est contrôlé à chaque écriture en décimales exactes. Les montants, dates et comptes de TVA ne sont pas recalculés. Pas de ligne supprimée ni de compensation au compte 471. Une erreur isole seulement l’écriture complète concernée dans ECRITURES_A_VERIFIER.csv avec son motif. Le reste est exporté. Si aucune écriture ne peut être exportée, le pack de diagnostic et la source restent téléchargeables, sans faux FEC.

La source fournie contient 210 lignes, 69 références et 69 PDF. L'auxiliaire 41119658 porte SODYTRANS et NEGO TRANSPORTS MAYENNE : vérifier le bon compte dans le dossier avant export. La version 3 propose désormais un compte numérique distinct pour chacun de ces deux clients.

Le format cible comporte les 18 colonnes FEC normalisées. Les alias CompteAuxNum/CompteAuxLib de la source sont convertis en CompAuxNum/CompAuxLib. Les dates de validation absentes restent vides : c'est un import comptable partiel, pas un FEC fiscal annuel certifié. L'analytique et les échéances du CSV ne sont pas exportées dans ce format à 18 colonnes. Les futurs exports doivent garder les en-têtes attendus. Aucune garantie sur un format source différent ou sur les comptes déjà présents dans Pennylane ; le contrôle final se fait dans le dossier.

Documentation consultée le 29/10/2026 : https://help.pennylane.com/fr/articles/18792-importer-un-fec

## Tests
```sh
python -m unittest discover -s tests -v
```

## Version 3 — export sans blocage global
Le pack contient également CORRESPONDANCE_CLIENTS.csv, EXPORT_SOURCE_ORIGINAL.zip, ANOMALIES.csv et BILAN_EXPORT.txt. Le ZIP source conserve tous les fichiers originaux et les champs non repris dans le FEC. Les nouveaux comptes proposés ne sont pas comparés au plan comptable Pennylane. Une pièce manquante, un déséquilibre ou une date invalide place l’écriture entière à vérifier. Aucun montant ou justificatif n’est inventé.
