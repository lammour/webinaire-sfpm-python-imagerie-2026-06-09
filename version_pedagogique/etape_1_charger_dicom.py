"""
Étape 1 — Charger une série DICOM et afficher ses métadonnées.

On lit tous les fichiers d'un dossier, on les trie par position Z (axe tête-pied),
et on sauvegarde la coupe du milieu en image PNG.

Usage :
    python etape_1_charger_dicom.py chemin/vers/dossier/dicom
"""

import sys
from pathlib import Path

import numpy as np
import pydicom
import matplotlib.pyplot as plt


def charger_serie(dossier):
    """Lit tous les fichiers DICOM d'un dossier et les trie par position Z."""
    coupes = []
    for fichier in sorted(Path(dossier).iterdir()):
        try:
            ds = pydicom.dcmread(str(fichier))
            if not hasattr(ds, "PixelData"):
                continue
            # Conversion pixels bruts → unités Hounsfield (UH)
            img = ds.pixel_array.astype(np.float32)
            img = img * float(getattr(ds, "RescaleSlope", 1.0)) \
                      + float(getattr(ds, "RescaleIntercept", 0.0))
            coupes.append({
                "image":      img,
                "pixel_mm":   float(getattr(ds, "PixelSpacing", [1.0])[0]),
                "position":   float(getattr(ds, "SliceLocation", 0.0)),
                "fabricant":  str(getattr(ds, "Manufacturer", "?")),
                "modele":     str(getattr(ds, "ManufacturerModelName", "?")),
                "kv":         float(getattr(ds, "KVP", 0)),
                "ma":         float(getattr(ds, "XRayTubeCurrent", 0)),
                "noyau":      str(getattr(ds, "ConvolutionKernel", "?")),
                "date":       str(getattr(ds, "StudyDate", "?")),
            })
        except Exception:
            pass  # fichier non DICOM → ignoré

    if not coupes:
        raise ValueError(f"Aucun fichier DICOM valide dans : {dossier}")

    coupes.sort(key=lambda c: c["position"])
    return coupes


# ──────────────────────────────────────────────────────────────────────────────

if len(sys.argv) < 2:
    print("Usage : python etape_1_charger_dicom.py chemin/vers/dossier/dicom")
    sys.exit(1)

dossier = sys.argv[1]
coupes = charger_serie(dossier)

# Informations générales (tirées de la coupe centrale)
c = coupes[len(coupes) // 2]
print("── Série DICOM chargée ────────────────────────")
print(f"  Nombre de coupes  : {len(coupes)}")
print(f"  Fabricant / modèle: {c['fabricant']} / {c['modele']}")
print(f"  Date d'examen     : {c['date']}")
print(f"  Tension (kV)      : {c['kv']:.0f}")
print(f"  Courant (mA)      : {c['ma']:.0f}")
print(f"  Noyau             : {c['noyau']}")
print(f"  Taille pixel      : {c['pixel_mm']:.4f} mm")
print(f"  Dimensions image  : {c['image'].shape[1]} × {c['image'].shape[0]} pixels")
print(f"  Plage Z           : {coupes[0]['position']:.1f} → {coupes[-1]['position']:.1f} mm")
print("───────────────────────────────────────────────")

# Sauvegarde de la coupe centrale en PNG
fig, ax = plt.subplots(figsize=(6, 6))
im = ax.imshow(c["image"], cmap="gray", vmin=-200, vmax=200)
plt.colorbar(im, ax=ax, label="Unités Hounsfield (UH)")
ax.set_title(f"Coupe centrale — {c['fabricant']} {c['modele']}\n"
             f"{c['kv']:.0f} kV · {c['ma']:.0f} mA · noyau {c['noyau']}")
ax.axis("off")
plt.tight_layout()
plt.savefig("etape_1_coupe.png", dpi=150)
print("Image sauvegardée : etape_1_coupe.png")
