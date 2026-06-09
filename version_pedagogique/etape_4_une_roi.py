"""
Étape 4 — Zoom sur une ROI : détrending et FFT 2D.

Avant de calculer la NPS, il faut supprimer les variations lentes de l'image
(non uniformité de l'image) qui créeraient un artefact au centre
du spectre de Fourier. On appelle cette étape le "détrending".

Méthode : on ajuste un polynôme 2D du 2ème degré sur la ROI (6 coefficients),
on le soustrait, puis on applique la FFT 2D.

Ce fichier montre les trois étapes sur UNE seule ROI pour bien les visualiser.

Usage :
    python etape_4_une_roi.py chemin/vers/dossier/dicom
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
    masque = (image >= -100) & (image <= 100)
    lignes, cols = np.where(masque)
    if len(lignes) == 0:
        return image.shape[0] // 2, image.shape[1] // 2
    return int(np.mean(lignes)), int(np.mean(cols))


def detrendre(roi):
    """
    Soustrait un polynôme 2D du 2ème degré ajusté sur la ROI.
    Cela élimine les tendances basse fréquence sans toucher au bruit.
    """
    n, m = roi.shape
    X, Y = np.meshgrid(np.arange(m), np.arange(n))
    A = np.column_stack([
        np.ones(n * m),
        X.ravel(), Y.ravel(),
        X.ravel()**2, Y.ravel()**2,
        (X * Y).ravel(),
    ])
    coeffs = np.linalg.lstsq(A, roi.ravel(), rcond=None)[0]
    fond = (coeffs[0]
            + coeffs[1]*X + coeffs[2]*Y
            + coeffs[3]*X**2 + coeffs[4]*Y**2
            + coeffs[5]*X*Y)
    return roi - fond, fond


def calculer_nps_2d(roi_dt, pixel_mm):
    """FFT 2D normalisée → NPS 2D en mm²."""
    n, m = roi_dt.shape
    fft   = np.fft.fftshift(np.fft.fft2(roi_dt))
    nps2d = (np.abs(fft)**2) * pixel_mm**2 / (n * m)
    freq  = np.fft.fftshift(np.fft.fftfreq(n)) / pixel_mm
    return nps2d, freq


# ──────────────────────────────────────────────────────────────────────────────

if len(sys.argv) < 2:
    print("Usage : python etape_4_une_roi.py chemin/vers/dossier/dicom")
    sys.exit(1)

coupes   = charger_serie(sys.argv[1])
coupe    = coupes[len(coupes) // 2]
image    = coupe["image"]
pixel_mm = coupe["pixel_mm"]

# On extrait la ROI "haut" (cardinale nord) — position 34% du rayon
centre_l, centre_c = trouver_centre(image)
masque = (image >= -100) & (image <= 100)
rayon  = (np.sum(masque[centre_l, :]) + np.sum(masque[:, centre_c])) / 4.0
r      = int(rayon * 0.42)
taille = 64
demi   = taille // 2

l_roi, c_roi = centre_l - r, centre_c   # position de la ROI "haut"
roi_brute = image[l_roi - demi:l_roi + demi, c_roi - demi:c_roi + demi].copy()

roi_dt, fond = detrendre(roi_brute)
nps2d, freq  = calculer_nps_2d(roi_dt, pixel_mm)

print("── ROI 'haut' (cardinale nord) ────────────────")
print(f"  Centre ROI         : ligne={l_roi}, col={c_roi}")
print(f"  Moyenne ROI brute  : {roi_brute.mean():.2f} UH")
print(f"  Moyenne ROI détr.  : {roi_dt.mean():.4f} UH  (≈ 0 attendu)")
print(f"  Écart-type (bruit) : {roi_dt.std():.4f} UH")
print("───────────────────────────────────────────────")

# Visualisation en 4 panneaux
fig, axes = plt.subplots(1, 4, figsize=(16, 4))

vmin, vmax = roi_brute.min(), roi_brute.max()

im0 = axes[0].imshow(roi_brute, cmap="gray", vmin=vmin, vmax=vmax)
axes[0].set_title("ROI brute (UH)")
plt.colorbar(im0, ax=axes[0])

im1 = axes[1].imshow(fond, cmap="RdBu_r")
axes[1].set_title("Tendance basse fréquence\n(polynôme 2D ordre 2)")
plt.colorbar(im1, ax=axes[1])

im2 = axes[2].imshow(roi_dt, cmap="gray")
axes[2].set_title("ROI après détrending\n(bruit pur)")
plt.colorbar(im2, ax=axes[2])

# NPS 2D en échelle log pour mieux voir la structure
im3 = axes[3].imshow(np.log10(nps2d + 1e-12), cmap="hot",
                     extent=[freq[0], freq[-1], freq[-1], freq[0]])
axes[3].set_title("NPS 2D (log₁₀)\nfréquences en cycles/mm")
axes[3].set_xlabel("fx (cy/mm)")
axes[3].set_ylabel("fy (cy/mm)")
plt.colorbar(im3, ax=axes[3])

plt.suptitle(f"Décomposition d'une ROI de {taille}×{taille} px ({taille*pixel_mm:.1f}×{taille*pixel_mm:.1f} mm)",
             fontsize=12)
plt.tight_layout()
plt.savefig("etape_4_une_roi.png", dpi=150)
print("Image sauvegardée : etape_4_une_roi.png")
