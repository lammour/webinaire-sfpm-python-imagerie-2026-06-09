"""
Étape 5 — Accumuler les NPS 2D et obtenir la NPS 1D par moyenne radiale.

On répète le calcul de l'étape 4 sur les 10 coupes centrales × 8 ROIs,
on accumule les NPS 2D, puis on les moyenne.

La NPS 2D obtenue doit être isotrope (symétrie radiale) pour un fantôme eau.
On en extrait la NPS 1D par moyenne radiale : on trace 37 profils angulaires
(de 0° à 360°, tous les 10°) et on fait la moyenne.

Usage :
    python etape_5_nps_1d.py chemin/vers/dossier/dicom
"""

import sys
from pathlib import Path

import numpy as np
import pydicom
import matplotlib.pyplot as plt
from scipy import ndimage


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
    masque = (image >= -100) & (image <= 100)
    rayon  = (np.sum(masque[centre_l, :]) + np.sum(masque[:, centre_c])) / 4.0
    d = int(rayon * 0.34)
    r = int(rayon * 0.42)
    positions = [
        (centre_l - d, centre_c - d), (centre_l - d, centre_c + d),
        (centre_l + d, centre_c - d), (centre_l + d, centre_c + d),
        (centre_l - r, centre_c),     (centre_l + r, centre_c),
        (centre_l,     centre_c - r), (centre_l,     centre_c + r),
    ]
    h, w = image.shape
    demi = taille_roi // 2
    return [(l, c) for l, c in positions if demi <= l < h - demi and demi <= c < w - demi]


def detrendre(roi):
    n, m = roi.shape
    X, Y = np.meshgrid(np.arange(m), np.arange(n))
    A = np.column_stack([
        np.ones(n * m), X.ravel(), Y.ravel(),
        X.ravel()**2, Y.ravel()**2, (X * Y).ravel(),
    ])
    coeffs = np.linalg.lstsq(A, roi.ravel(), rcond=None)[0]
    fond = (coeffs[0] + coeffs[1]*X + coeffs[2]*Y
            + coeffs[3]*X**2 + coeffs[4]*Y**2 + coeffs[5]*X*Y)
    return roi - fond


def nps_2d_roi(roi, pixel_mm):
    n, m  = roi.shape
    fft   = np.fft.fftshift(np.fft.fft2(detrendre(roi)))
    return (np.abs(fft)**2) * pixel_mm**2 / (n * m)


def moyenne_radiale(nps_2d, pixel_mm):
    """
    Trace 37 profils radiaux (0° à 360°, pas 10°) sur la NPS 2D
    et retourne leur moyenne → NPS 1D.
    """
    n       = nps_2d.shape[0]
    nyquist = 1.0 / (2.0 * pixel_mm)
    freq_max = nyquist * 1.375
    nb_pts   = int(n // 2 * 1.375) + 1
    freq_r   = np.linspace(0, freq_max, nb_pts)
    centre   = n // 2
    r_max    = int(n // 2 * 1.375)
    r_vals   = np.linspace(0, r_max, nb_pts)

    profils = []
    for angle_deg in range(0, 361, 10):
        theta = np.deg2rad(angle_deg)
        coords = np.array([
            centre + r_vals * np.sin(theta),
            centre + r_vals * np.cos(theta),
        ])
        profil = ndimage.map_coordinates(nps_2d, coords, order=1, mode="constant", cval=0)
        profils.append(profil)

    return np.mean(profils, axis=0), freq_r


# ──────────────────────────────────────────────────────────────────────────────

if len(sys.argv) < 2:
    print("Usage : python etape_5_nps_1d.py chemin/vers/dossier/dicom")
    sys.exit(1)

coupes    = charger_serie(sys.argv[1])
taille_roi = 64
nb_coupes  = min(10, len(coupes))
debut      = (len(coupes) - nb_coupes) // 2
coupes_c   = coupes[debut:debut + nb_coupes]

coupe_ref = coupes_c[len(coupes_c) // 2]
image_ref = coupe_ref["image"]
pixel_mm  = coupe_ref["pixel_mm"]

centre_l, centre_c = trouver_centre(image_ref)
positions = placer_rois(image_ref, centre_l, centre_c, taille_roi)
demi = taille_roi // 2

# Accumulation NPS 2D
print("Calcul de la NPS 2D en cours...")
nps_somme = np.zeros((taille_roi, taille_roi))
nb_rois   = 0
for coupe in coupes_c:
    img = coupe["image"]
    for (l, c) in positions:
        roi = img[l - demi:l + demi, c - demi:c + demi]
        nps_somme += nps_2d_roi(roi, pixel_mm)
        nb_rois += 1

nps_2d_moy = nps_somme / nb_rois
print(f"  {nb_rois} ROIs accumulées ({nb_coupes} coupes × {len(positions)} ROIs)")

# NPS 1D par moyenne radiale
nps_brut, frequences = moyenne_radiale(nps_2d_moy, pixel_mm)

print()
print("── NPS 1D brute ───────────────────────────────")
print(f"  Nombre de points fréquentiels : {len(frequences)}")
print(f"  Fréquence max                 : {frequences[-1]:.3f} cycles/mm")
print(f"  (Nyquist = {1/(2*pixel_mm):.3f} cycles/mm, étendu × 1.375)")
print("───────────────────────────────────────────────")

# Visualisation : NPS 2D + quelques profils radiaux + NPS 1D
freq_2d = np.fft.fftshift(np.fft.fftfreq(taille_roi)) / pixel_mm

fig, axes = plt.subplots(1, 3, figsize=(15, 5))

# NPS 2D
axes[0].imshow(nps_2d_moy, cmap="hot",
               extent=[freq_2d[0], freq_2d[-1], freq_2d[-1], freq_2d[0]])
axes[0].set_title(f"NPS 2D moyennée\n({nb_rois} ROIs)")
axes[0].set_xlabel("fx (cy/mm)")
axes[0].set_ylabel("fy (cy/mm)")

# Quelques profils radiaux sur la NPS 2D
r_vals_pix = np.linspace(0, int(taille_roi // 2 * 1.375), len(frequences))
centre = taille_roi // 2
axes[1].imshow(nps_2d_moy, cmap="hot")
for angle_deg in range(0, 360, 45):   # 8 profils illustratifs
    theta = np.deg2rad(angle_deg)
    l_end = centre + r_vals_pix[-1] * np.sin(theta)
    c_end = centre + r_vals_pix[-1] * np.cos(theta)
    axes[1].plot([centre, c_end], [centre, l_end], "c-", linewidth=0.8, alpha=0.8)
axes[1].set_title("37 profils radiaux\n(8 illustrés en cyan)")
axes[1].axis("off")

# NPS 1D brute
axes[2].plot(frequences, nps_brut, color="steelblue", linewidth=1.5)
axes[2].set_xlabel("Fréquence (cycles/mm)")
axes[2].set_ylabel("NPS (mm²)")
axes[2].set_title("NPS 1D brute\n(moyenne des 37 profils)")
axes[2].grid(True, alpha=0.3)
axes[2].axvline(1 / (2 * pixel_mm), color="orange", linestyle="--",
                linewidth=1, label=f"Nyquist = {1/(2*pixel_mm):.2f} cy/mm")
axes[2].legend(fontsize=9)

plt.tight_layout()
plt.savefig("etape_5_nps_1d.png", dpi=150)
print("Image sauvegardée : etape_5_nps_1d.png")
