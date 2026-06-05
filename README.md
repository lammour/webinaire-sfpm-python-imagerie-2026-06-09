# Mesure NPS en Python — Tutoriel complet

Ce tutoriel accompagne le webinaire **"Python pour les physiciens médicaux"**.
Il explique pas à pas comment installer tous les outils nécessaires et faire tourner
le logiciel de mesure de la **NPS (Noise Power Spectrum / Spectre de Puissance du Bruit)**
sur des images scanner DICOM.

Aucune connaissance préalable en programmation n'est nécessaire.

---

## Table des matières

1. [Ce que fait le logiciel](#1-ce-que-fait-le-logiciel)
2. [Installer Python](#2-installer-python)
3. [Installer VS Code](#3-installer-vs-code)
4. [Installer Git](#4-installer-git)
5. [Télécharger le projet](#5-télécharger-le-projet)
6. [Créer l'environnement virtuel](#6-créer-lenvironnement-virtuel)
7. [Installer les bibliothèques](#7-installer-les-bibliothèques)
8. [Télécharger les images test](#8-télécharger-les-images-test)
9. [Lancer le logiciel](#9-lancer-le-logiciel)
10. [Comprendre le code](#10-comprendre-le-code)
11. [Résultats attendus](#11-résultats-attendus)
12. [Pour aller plus loin](#12-pour-aller-plus-loin)

---

## 1. Ce que fait le logiciel

Le logiciel charge une série d'images DICOM d'un fantôme eau et calcule automatiquement
la NPS selon le protocole de la décision ANSM du 18/12/2025.

**Étapes du calcul :**
1. Détection automatique du centre du fantôme
2. Positionnement de 8 ROIs en motif octogonal
3. Calcul de la NPS 2D par FFT pour chaque ROI
4. Moyenne radiale → courbe NPS 1D
5. Ajustement par polynôme de degré 11
6. Calcul de la fréquence centroïde f̄

**Interface :**
- Vue gauche : image CT avec les ROIs superposées en vert
- Vue droite : courbe NPS (brute + lissée) avec marqueur f̄
- Barre de statut : résultats synthétiques après analyse

---

## 2. Installer Python

Python est le langage de programmation utilisé par ce projet.

### Téléchargement

1. Ouvrir un navigateur et aller sur **https://www.python.org/downloads/**
2. Cliquer sur le bouton jaune **"Download Python 3.12.x"**

### Installation

1. Ouvrir le fichier téléchargé (`python-3.12.x-amd64.exe`)
2. **Étape cruciale** : cocher la case **"Add python.exe to PATH"** en bas de la fenêtre
   avant de cliquer sur *Install Now*

   > Sans cette case cochée, Windows ne saura pas où trouver Python
   > et les commandes du tutoriel ne fonctionneront pas.

3. Cliquer sur **Install Now** et attendre la fin de l'installation
4. Cliquer sur **Close**

### Vérification

1. Appuyer sur `Windows + R`, taper `powershell`, appuyer sur Entrée
2. Dans la fenêtre noire qui s'ouvre, taper :
   ```
   python --version
   ```
3. Le résultat doit afficher quelque chose comme `Python 3.12.x`

   Si vous voyez un message d'erreur, relancer l'installeur en cochant bien la case PATH.

---

## 3. Installer VS Code

VS Code (Visual Studio Code) est l'éditeur de code que nous utilisons pour écrire et lire le code Python.

### Téléchargement et installation

1. Aller sur **https://code.visualstudio.com/**
2. Cliquer sur **"Download for Windows"**
3. Ouvrir le fichier téléchargé et suivre les étapes de l'installeur
   - Cocher **"Ajouter l'action 'Ouvrir avec Code' au menu contextuel"** (pratique mais optionnel)
   - Laisser les autres options par défaut

### Installer l'extension Python

L'extension Python ajoute la coloration syntaxique, l'autocomplétion et l'exécution de code.

1. Ouvrir VS Code
2. Cliquer sur l'icône Extensions dans la barre de gauche (icône avec 4 carrés)
   ou appuyer sur `Ctrl+Shift+X`
3. Dans la barre de recherche, taper **Python**
4. Cliquer sur **Install** sur l'extension **Python** publiée par *Microsoft*

### Réglage de la taille de police (recommandé pour la démo)

Pour que le code soit bien lisible lors d'un partage d'écran :

1. Appuyer sur `Ctrl+,` pour ouvrir les paramètres
2. Rechercher **Font Size**
3. Mettre la valeur à **16**

---

## 4. Installer Git

Git est un outil de gestion de versions qui permet de télécharger le projet en une commande
et de suivre l'évolution du code.

### Téléchargement et installation

1. Aller sur **https://git-scm.com/download/win**
2. Le téléchargement démarre automatiquement (choisir la version 64-bit)
3. Ouvrir le fichier téléchargé et suivre l'installeur
   - Laisser toutes les options par défaut
   - Sur l'écran *"Choosing the default editor"*, choisir **Use Visual Studio Code as Git's default editor**
   - Sur l'écran *"Adjusting the name of the initial branch"*, choisir **Override → main**
   - Laisser le reste par défaut jusqu'à la fin

### Vérification

Dans PowerShell :
```
git --version
```
Résultat attendu : `git version 2.x.x.windows.x`

---

## 5. Télécharger le projet

### Choisir un emplacement

Créer un dossier pour stocker vos projets Python, par exemple `C:\Projets\` ou sur le Bureau.

### Cloner le dépôt

1. Dans PowerShell, se placer dans le dossier de votre choix :
   ```
   cd C:\Projets
   ```
2. Télécharger le projet avec Git :
   ```
   git clone https://github.com/lammour/python-sfpm.git
   ```
3. Se déplacer dans le dossier téléchargé :
   ```
   cd python-sfpm
   ```

### Ouvrir dans VS Code

```
code .
```

Le point `.` signifie "ouvrir le dossier courant". VS Code s'ouvre avec tous les fichiers du projet visibles dans le panneau de gauche.

---

## 6. Créer l'environnement virtuel

Un **environnement virtuel** est un espace isolé qui contient uniquement les bibliothèques
nécessaires à ce projet, sans interférer avec le reste de votre système.
C'est la bonne pratique à adopter pour tout projet Python.

### Création

Dans le terminal intégré de VS Code (`Ctrl+ù` ou menu *Terminal → New Terminal*) :
```
python -m venv .venv
```
Un dossier `.venv` apparaît dans le projet. Il contient une copie de Python et un espace
pour installer les bibliothèques.

### Activation

```
.venv\Scripts\activate
```

Le terminal affiche maintenant `(.venv)` au début de chaque ligne — c'est la confirmation
que l'environnement virtuel est bien actif.

> **Note :** il faut activer l'environnement à chaque nouvelle session de terminal.
> VS Code propose de le faire automatiquement si vous sélectionnez l'interpréteur (étape suivante).

### Sélectionner l'interpréteur dans VS Code

1. Appuyer sur `Ctrl+Shift+P`
2. Taper **Python: Select Interpreter**
3. Choisir l'option qui commence par `.venv` (quelque chose comme `.venv\Scripts\python.exe`)

VS Code utilisera maintenant automatiquement cet environnement.

---

## 7. Installer les bibliothèques

Le fichier `requirements.txt` liste toutes les bibliothèques nécessaires.
Une seule commande suffit pour tout installer :

```
pip install -r requirements.txt
```

L'installation prend environ 1 à 2 minutes. Vous verrez des lignes de téléchargement défiler.

### Bibliothèques installées

| Bibliothèque | Rôle dans le projet |
|---|---|
| `numpy` | Calculs sur les tableaux de pixels, FFT |
| `scipy` | Interpolation bilinéaire pour la moyenne radiale |
| `pydicom` | Lecture des fichiers DICOM |
| `matplotlib` | Affichage des images CT et des courbes NPS |
| `customtkinter` | Interface graphique moderne |

### Vérification

```
pip list
```
Les 5 bibliothèques ci-dessus doivent apparaître dans la liste.

---

## 8. Télécharger les images test

Les images DICOM de fantôme eau ne sont pas incluses dans le dépôt Git (fichiers trop volumineux).

### Téléchargement

Télécharger l'archive d'images de référence et la décompresser.
Le contenu doit être placé dans un dossier `images/` à la racine du projet :

```
python-sfpm/
├── images/
│   ├── Serie_1/
│   │   └── S1/
│   │       ├── CT000000.dcm
│   │       ├── CT000001.dcm
│   │       └── ...
│   ├── Serie_2/S2/
│   ├── Serie_3a/S3a/
│   ├── Serie_3b/S3b/
│   └── Serie_4/S4/
├── app.py
├── main.py
└── ...
```

### Description des séries

| Série | Coupes | kV | mA | Noyau |
|-------|--------|----|----|-------|
| Serie_1 | 233 | 120 | 350 | STANDARD |
| Serie_2 | 151 | 120 | 275 | B |
| Serie_3a | 132 | 120 | 182 | Hr38s |
| Serie_3b | 43 | 100 | 288 | Br38f |
| Serie_4 | 130 | 100 | 250 | BODY_SHARP |

---

## 9. Lancer le logiciel

```
python main.py
```

La fenêtre de l'application s'ouvre.

### Utilisation

**Charger une série :**
1. Cliquer sur **"📂 Charger dossier DICOM"**
2. Naviguer jusqu'au dossier d'une série, par exemple `images/Serie_1/S1`
3. Cliquer sur **Sélectionner ce dossier**

La coupe centrale s'affiche immédiatement. Utiliser le slider en bas pour naviguer entre les coupes.
La barre de statut affiche les informations du scanner (constructeur, kV, mA, noyau).

**Lancer l'analyse NPS :**
1. Vérifier les paramètres : **Coupes = 10**, **Taille ROI = 64** (valeurs recommandées par l'ANSM)
2. Cliquer sur **"▶ Analyser NPS"**

Après quelques secondes :
- Les 8 ROIs apparaissent en vert sur l'image CT
- La courbe NPS s'affiche à droite (courbe bleue claire = NPS brut, bleue foncée = NPS lissé)
- La ligne orange verticale indique la fréquence centroïde f̄
- La barre de statut affiche f̄ et le NPS moyen

---

## 10. Comprendre le code

Le projet est organisé en 4 fichiers, chacun avec un rôle bien défini.

### `dicom_loader.py` — Chargement des images

Ce fichier lit les fichiers DICOM avec la bibliothèque `pydicom` et organise les coupes
en série triée par position Z.

La conversion en unités Hounsfield suit la formule standard :
```
UH = valeur_brute × RescaleSlope + RescaleIntercept
```

### `nps_calculator.py` — Algorithme NPS

C'est le cœur du projet. Les fonctions s'enchaînent dans cet ordre :

```
detecter_centre_fantome()
    → seuillage des pixels eau (-100 à +100 UH)
    → centroïde du masque

calculer_positions_roi()
    → 8 ROIs en motif octogonal
    → 4 cardinales à 42% du rayon, 4 diagonales à 34%

detrender_roi()
    → ajustement polynômial 2D d'ordre 2
    → supprime les tendances basse fréquence avant la FFT

calculer_nps_2d()
    → FFT 2D de la ROI
    → NPS_2D = |FFT|² × taille_pixel² / N_pixels

moyenne_radiale()
    → 37 profils angulaires (0° à 360°, pas 10°)
    → interpolation bilinéaire le long de chaque profil
    → moyenne → NPS 1D

lisser_nps_polynome()
    → ajustement polynôme degré 11 (standard ANSM)
    → valeurs forcées à zéro si négatives

calculer_frequence_moyenne()
    → f̄ = ∫ f·NPS(f) df / ∫ NPS(f) df
```

### `app.py` — Interface graphique

Trois classes CustomTkinter :

- **`VueCT`** : affiche les coupes CT (matplotlib embarqué) avec le slider de navigation
  et les rectangles ROI superposés après analyse
- **`VueNPS`** : affiche la courbe NPS avec les deux courbes et le marqueur f̄
- **`ApplicationNPS`** : fenêtre principale — gère les boutons, les paramètres,
  et lance le calcul dans un thread secondaire pour ne pas figer l'interface

### `main.py` — Point d'entrée

```python
from app import ApplicationNPS

if __name__ == "__main__":
    app = ApplicationNPS()
    app.mainloop()
```

Trois lignes suffisent pour lancer l'application.

---

## 11. Résultats attendus

| Série | f̄ (cy/mm) | NPS moyen (UH²·mm²) | Interprétation |
|-------|-----------|---------------------|----------------|
| Serie_1 | 0.242 | 27.7 | Référence noyau standard |
| Serie_2 | 0.275 | 340.7 | Dose plus faible → bruit plus élevé |
| Serie_3a | 0.259 | 12.2 | Noyau dur → fréquences plus élevées |
| Serie_3b | 0.254 | 27.1 | Noyau dur + 100 kV |
| Serie_4 | 0.324 | 59.1 | Noyau très dur → f̄ maximale |

**Ce qu'on observe :**
- La **fréquence centroïde f̄** augmente avec la dureté du noyau de reconstruction
  (noyau "sharp" → résolution spatiale plus élevée → NPS décalée vers les hautes fréquences)
- L'**amplitude** de la NPS diminue quand la dose augmente
  (plus de photons → moins de bruit quantique)

---

## 12. Pour aller plus loin

Quelques pistes pour adapter le projet à vos besoins :

**Changer le fenêtrage de l'image CT**
Dans `app.py`, ligne `self.ax.imshow(...)`, modifier `vmin=-200, vmax=200`
pour adapter le contraste (ex. `vmin=-500, vmax=500` pour le poumon).

**Exporter les résultats en CSV**
Ajouter dans `app.py` un bouton "Exporter" qui appelle :
```python
import csv
with open("resultats_nps.csv", "w") as f:
    writer = csv.writer(f)
    writer.writerow(["Frequence (cy/mm)", "NPS lisse"])
    writer.writerows(zip(resultat.frequences, resultat.nps_lisse))
```

**Tester d'autres paramètres**
- Changer la taille des ROIs (32, 64, 128 pixels) et observer l'effet sur la courbe
- Augmenter le nombre de coupes analysées (20 au lieu de 10)

**Calculer d'autres métriques**
- Bruit moyen (écart-type dans une ROI centrale)
- Uniformité (écart entre ROIs)
- CTF/MTF (nécessite un fantôme fil ou bord)

---

## Références

- Décision ANSM du 18/12/2025 relative au contrôle qualité des scanographes
- Projet cq-tdm : [github.com/lammour/cq-tdm](https://github.com/lammour/cq-tdm)
- Documentation pydicom : [pydicom.github.io](https://pydicom.github.io)
- Documentation matplotlib : [matplotlib.org](https://matplotlib.org)
