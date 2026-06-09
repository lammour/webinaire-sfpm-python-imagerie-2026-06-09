"""
Étape 6 — Lissage, métriques et figure finale.

La NPS brute est un peu bruitée. On l'ajuste par un polynôme de degré 11
pour obtenir une courbe lisse, puis on calcule :

  • Fréquence moyenne  f̄ = ∫ f · NPS(f) df / ∫ NPS(f) df
      → indique si le bruit est plutôt basse ou haute fréquence
  • NPS max                         → pic du spectre de bruit
  • Puissance totale du bruit       → ∫ NPS(f) df  (aire sous la courbe)

Usage :
    python etape_6_resultats_finaux.py chemin/vers/dossier/dicom
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
                "kv":       float(getattr(ds, "KVP", 0)),
                "ma":       float(getattr(ds, "XRayTubeCurrent", 0)),
                "noyau":    str(getattr(ds, "ConvolutionKernel", "?")),
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
    n, m = roi.shape
    fft  = np.fft.fftshift(np.fft.fft2(detrendre(roi)))
    return (np.abs(fft)**2) * pixel_mm**2 / (n * m)


def moyenne_radiale(nps_2d, pixel_mm):
    n        = nps_2d.shape[0]
    freq_max = (1.0 / (2.0 * pixel_mm)) * 1.375
    nb_pts   = int(n // 2 * 1.375) + 1
    freq_r   = np.linspace(0, freq_max, nb_pts)
    centre   = n // 2
    r_vals   = np.linspace(0, int(n // 2 * 1.375), nb_pts)
    profils  = []
    for angle_deg in range(0, 361, 10):
        theta  = np.deg2rad(angle_deg)
        coords = np.array([centre + r_vals * np.sin(theta),
                           centre + r_vals * np.cos(theta)])
        profils.append(ndimage.map_coordinates(nps_2d, coords, order=1, mode="constant", cval=0))
    return np.mean(profils, axis=0), freq_r


# ──────────────────────────────────────────────────────────────────────────────

if len(sys.argv) < 2:
    print("Usage : python etape_6_resultats_finaux.py chemin/vers/dossier/dicom")
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

print("Calcul NPS en cours...")
nps_somme = np.zeros((taille_roi, taille_roi))
nb_rois   = 0
for coupe in coupes_c:
    img = coupe["image"]
    for (l, c) in positions:
        nps_somme += nps_2d_roi(img[l - demi:l + demi, c - demi:c + demi], pixel_mm)
        nb_rois += 1

nps_brut, frequences = moyenne_radiale(nps_somme / nb_rois, pixel_mm)

# Lissage par polynôme degré 11
coeffs_poly = np.polyfit(frequences, nps_brut, 11)
nps_lisse   = np.maximum(np.polyval(coeffs_poly, frequences), 0.0)

# Métriques
freq_moy  = (np.trapezoid(frequences * nps_lisse, frequences)
             / np.trapezoid(nps_lisse, frequences))
puissance = float(np.trapezoid(nps_lisse, frequences))
nps_max   = float(np.max(nps_lisse))

print()
print("╔══════════════════════════════════════════════╗")
print("║           RÉSULTATS NPS — ANSM 2025          ║")
print("╠══════════════════════════════════════════════╣")
print(f"║  Scanner    : {coupe_ref['kv']:.0f} kV · {coupe_ref['ma']:.0f} mA · noyau {coupe_ref['noyau']:<9s}║")
print(f"║  Pixel      : {pixel_mm:.4f} mm                          ║")
print(f"║  ROIs       : {nb_rois} ({nb_coupes} coupes × {len(positions)} ROIs)               ║")
print("╠══════════════════════════════════════════════╣")
print(f"║  Fréquence moyenne  f̄ : {freq_moy:8.3f} cycles/mm       ║")
print(f"║  NPS max              : {nps_max:8.4f} mm²              ║")
print(f"║  Puissance du bruit   : {puissance:8.4f} mm²              ║")
print("╚══════════════════════════════════════════════╝")

# Figure finale
fig, axes = plt.subplots(1, 2, figsize=(13, 5))

# Panneau gauche : coupe + ROIs
ax = axes[0]
ax.imshow(image_ref, cmap="gray", vmin=-200, vmax=200)
ax.plot(centre_c, centre_l, "r+", markersize=18, markeredgewidth=2)
for (l, c) in positions:
    rect = plt.Rectangle((c - demi, l - demi), taille_roi, taille_roi,
                          edgecolor="yellow", facecolor="none", linewidth=1.5)
    ax.add_patch(rect)
ax.set_title(f"Coupe centrale + 8 ROIs\n"
             f"{coupe_ref['kv']:.0f} kV · {coupe_ref['ma']:.0f} mA · {coupe_ref['noyau']}")
ax.axis("off")

# Panneau droit : courbe NPS
ax = axes[1]
ax.plot(frequences, nps_brut,  color="steelblue", alpha=0.45, linewidth=1.2, label="NPS brute")
ax.plot(frequences, nps_lisse, color="tomato",    linewidth=2.5,             label="NPS lissée (poly. deg. 11)")
ax.axvline(freq_moy, color="forestgreen", linestyle="--", linewidth=2,
           label=f"f̄ = {freq_moy:.2f} cy/mm")

# Zone sous la courbe lissée
ax.fill_between(frequences, nps_lisse, alpha=0.12, color="tomato")

ax.set_xlabel("Fréquence spatiale (cycles/mm)", fontsize=11)
ax.set_ylabel("NPS (mm²)", fontsize=11)
ax.set_title(f"Noise Power Spectrum\n"
             f"NPS max = {nps_max:.4f} mm²  |  puissance = {puissance:.4f} mm²")
ax.legend(fontsize=10)
ax.grid(True, alpha=0.3)
ax.set_xlim(left=0)
ax.set_ylim(bottom=0)

plt.tight_layout()
plt.savefig("etape_6_resultats_finaux.png", dpi=150)
print("\nFigure sauvegardée : etape_6_resultats_finaux.png")
