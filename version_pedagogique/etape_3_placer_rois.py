"""
Étape 3 — Placer les 8 ROIs en motif octogonal autour du centre.

8 ROIs carrées de 64×64 pixels :
- 4 ROIs en position diagonale  (à 34 % du rayon)
- 4 ROIs en position cardinale  (à 42 % du rayon, haut/bas/gauche/droite)

Usage :
    python etape_3_placer_rois.py chemin/vers/dossier/dicom
"""

import sys
from pathlib import Path

import numpy as np
import pydicom
import matplotlib.pyplot as plt
import matplotlib.patches as patches


def charger_serie(dossier):
    coupes = []
    for fichier in sorted(Path(dossier).iterdir()):
        try:
            ds = pydicom.dcmread(str(fichier))
            if not hasattr(ds, "PixelData"):
                continue
            img = ds.pixel_array.astype(np.float32)
            img = img * float(getattr(ds, "RescaleSlope", 1.0)) \
                      + float(getattr(ds, "RescaleIntercept", 0.0))
            coupes.append({
                "image":    img,
                "pixel_mm": float(getattr(ds, "PixelSpacing", [1.0])[0]),
                "position": float(getattr(ds, "SliceLocation", 0.0)),
            })
        except Exception:
            pass
    coupes.sort(key=lambda c: c["position"])
    return coupes


def trouver_centre(image):
    masque = (image >= -100) & (image <= 100)
    lignes, cols = np.where(masque)
    if len(lignes) == 0:
        return image.shape[0] // 2, image.shape[1] // 2
    return int(np.mean(lignes)), int(np.mean(cols))


def placer_rois(image, centre_l, centre_c, taille_roi=64):
    """
    Retourne les 8 positions (ligne, colonne) du centre de chaque ROI.
    On estime le rayon du fantôme par la largeur du masque eau.
    """
    masque = (image >= -100) & (image <= 100)
    rayon  = (np.sum(masque[centre_l, :]) + np.sum(masque[:, centre_c])) / 4.0

    d = int(rayon * 0.34)   # décalage pour les diagonales
    r = int(rayon * 0.42)   # distance pour les cardinales

    positions = [
        ("haut-gauche", centre_l - d, centre_c - d),
        ("haut-droite", centre_l - d, centre_c + d),
        ("bas-gauche",  centre_l + d, centre_c - d),
        ("bas-droite",  centre_l + d, centre_c + d),
        ("haut",        centre_l - r, centre_c),
        ("bas",         centre_l + r, centre_c),
        ("gauche",      centre_l,     centre_c - r),
        ("droite",      centre_l,     centre_c + r),
    ]

    h, w = image.shape
    demi = taille_roi // 2
    valides = [
        (nom, l, c) for nom, l, c in positions
        if demi <= l < h - demi and demi <= c < w - demi
    ]
    return valides


# ──────────────────────────────────────────────────────────────────────────────

if len(sys.argv) < 2:
    print("Usage : python etape_3_placer_rois.py chemin/vers/dossier/dicom")
    sys.exit(1)

coupes    = charger_serie(sys.argv[1])
coupe     = coupes[len(coupes) // 2]
image     = coupe["image"]
pixel_mm  = coupe["pixel_mm"]
taille_roi = 64

centre_l, centre_c = trouver_centre(image)
rois = placer_rois(image, centre_l, centre_c, taille_roi)

print("── Positionnement des ROIs ────────────────────")
print(f"  Rayon estimé : {int((np.sum((image[centre_l,:] >= -100) & (image[centre_l,:] <= 100)) + np.sum((image[:,centre_c] >= -100) & (image[:,centre_c] <= 100))) / 4)} pixels")
print(f"  ROIs valides : {len(rois)} / 8")
for nom, l, c in rois:
    print(f"    {nom:12s}  ligne={l:4d}  col={c:4d}")
print("───────────────────────────────────────────────")

# Visualisation
fig, ax = plt.subplots(figsize=(7, 7))
ax.imshow(image, cmap="gray", vmin=-200, vmax=200)
ax.plot(centre_c, centre_l, "r+", markersize=20, markeredgewidth=2, label="Centre")

demi = taille_roi // 2
couleurs = {"haut-gauche": "yellow", "haut-droite": "yellow",
            "bas-gauche":  "yellow", "bas-droite":  "yellow",
            "haut": "cyan",  "bas":    "cyan",
            "gauche": "cyan", "droite": "cyan"}

for nom, l, c in rois:
    rect = patches.Rectangle(
        (c - demi, l - demi), taille_roi, taille_roi,
        edgecolor=couleurs.get(nom, "white"), facecolor="none", linewidth=2
    )
    ax.add_patch(rect)
    ax.text(c, l - demi - 4, nom, color=couleurs.get(nom, "white"),
            fontsize=7, ha="center", va="bottom")

# Légende manuelle
from matplotlib.patches import Patch
legende = [Patch(edgecolor="yellow", facecolor="none", label="Diagonales (34% rayon)"),
           Patch(edgecolor="cyan",   facecolor="none", label="Cardinales (42% rayon)")]
ax.legend(handles=legende, loc="lower right", fontsize=9)
ax.set_title(f"8 ROIs de {taille_roi}×{taille_roi} px ({taille_roi*pixel_mm:.1f}×{taille_roi*pixel_mm:.1f} mm)")
ax.axis("off")

plt.tight_layout()
plt.savefig("etape_3_rois.png", dpi=150)
print("Image sauvegardée : etape_3_rois.png")
