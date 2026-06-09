"""
Étape 2 — Détecter automatiquement le centre du fantôme eau.

Le fantôme eau apparaît en valeurs proches de 0 UH (entre -100 et +100 UH).
On crée un masque binaire sur ces pixels, puis on calcule le centroïde
(la moyenne des positions ligne et colonne) pour trouver le centre.

Usage :
    python etape_2_detecter_centre.py chemin/vers/dossier/dicom
"""

import sys
from pathlib import Path

import numpy as np
import pydicom
import matplotlib.pyplot as plt


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
    """
    Centroïde des pixels eau (entre -100 et +100 UH).
    Retourne (ligne, colonne) du centre en pixels.
    """
    masque = (image >= -100) & (image <= 100)
    lignes, cols = np.where(masque)
    if len(lignes) == 0:
        return image.shape[0] // 2, image.shape[1] // 2
    return int(np.mean(lignes)), int(np.mean(cols))


# ──────────────────────────────────────────────────────────────────────────────

if len(sys.argv) < 2:
    print("Usage : python etape_2_detecter_centre.py chemin/vers/dossier/dicom")
    sys.exit(1)

coupes = charger_serie(sys.argv[1])
coupe  = coupes[len(coupes) // 2]   # coupe centrale
image  = coupe["image"]

masque_eau    = (image >= -100) & (image <= 100)
centre_l, centre_c = trouver_centre(image)

print("── Détection du centre ────────────────────────")
print(f"  Pixels eau détectés : {int(masque_eau.sum())}")
print(f"  Centre détecté      : ligne={centre_l}, colonne={centre_c}")
print("───────────────────────────────────────────────")

# Visualisation : coupe + masque eau + point central
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

axes[0].imshow(image, cmap="gray", vmin=-200, vmax=200)
axes[0].set_title("Coupe centrale (UH)")
axes[0].axis("off")

axes[1].imshow(image, cmap="gray", vmin=-200, vmax=200)
axes[1].imshow(masque_eau, cmap="Blues", alpha=0.4)      # masque eau en bleu
axes[1].plot(centre_c, centre_l, "r+", markersize=20, markeredgewidth=2)
axes[1].set_title(f"Masque eau (bleu) + centre détecté (croix rouge)\n"
                  f"centre : ligne={centre_l}, col={centre_c}")
axes[1].axis("off")

plt.tight_layout()
plt.savefig("etape_2_centre.png", dpi=150)
print("Image sauvegardée : etape_2_centre.png")
