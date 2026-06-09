"""
Tests du calculateur NPS.

Chaque test utilise un fantôme eau synthétique (disque ~0 UH dans l'air -1000 UH)
pour vérifier les étapes clés de l'algorithme sans avoir besoin de fichiers DICOM.
"""

import numpy as np
import pytest

from dicom_loader import SliceDicom, SerieDicom
from nps_calculator import (
    analyser_nps,
    calculer_frequence_moyenne,
    calculer_nps_2d,
    calculer_positions_roi,
    detecter_centre_fantome,
)


# ---------------------------------------------------------------------------
# Données synthétiques
# ---------------------------------------------------------------------------

def creer_coupe_fantome(taille=256, rayon=90, pixel_size_mm=0.7, seed=42) -> SliceDicom:
    """Disque d'eau (~0 UH ± bruit) centré dans une image d'air (-1000 UH)."""
    rng = np.random.default_rng(seed)
    image = np.full((taille, taille), -1000.0, dtype=np.float32)
    cy, cx = taille // 2, taille // 2
    y, x = np.ogrid[:taille, :taille]
    masque_eau = (x - cx) ** 2 + (y - cy) ** 2 <= rayon ** 2
    image[masque_eau] = rng.normal(0.0, 20.0, size=int(masque_eau.sum())).astype(np.float32)
    return SliceDicom(
        pixel_array=image, pixel_size_mm=pixel_size_mm,
        slice_location=0.0, instance_number=1, rows=taille, columns=taille,
    )


def creer_serie_fantome(nb_coupes=15) -> SerieDicom:
    """Série de coupes identiques avec positions Z distinctes."""
    coupes = []
    for i in range(nb_coupes):
        coupe = creer_coupe_fantome(seed=i)
        coupe.slice_location = float(i * 3.0)
        coupe.instance_number = i + 1
        coupes.append(coupe)
    return SerieDicom(coupes=coupes)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_detection_centre_fantome():
    """Le centre du fantôme eau doit être détecté au centre géométrique de l'image (±2 pixels)."""
    coupe = creer_coupe_fantome(taille=256)
    ligne, col = detecter_centre_fantome(coupe)
    assert abs(ligne - 128) <= 2
    assert abs(col - 128) <= 2


def test_placement_8_rois_dans_image():
    """L'algorithme doit placer exactement 8 ROIs et toutes doivent rester dans l'image."""
    taille_roi = 64
    coupe = creer_coupe_fantome(taille=256)
    centre = detecter_centre_fantome(coupe)
    positions = calculer_positions_roi(coupe, centre, taille_roi=taille_roi)

    assert len(positions) == 8

    demi = taille_roi // 2
    for pos in positions:
        assert pos.y - demi >= 0 and pos.y + demi <= 256, f"ROI hors image en Y : {pos}"
        assert pos.x - demi >= 0 and pos.x + demi <= 256, f"ROI hors image en X : {pos}"


def test_normalisation_nps_2d():
    """
    La NPS 2D est définie par : NPS = |FFT|² × taille_pixel² / N_pixels.
    Ce test vérifie que la formule est bien implémentée.
    """
    rng = np.random.default_rng(0)
    roi = rng.normal(0, 10, (64, 64))
    pixel_mm = 0.7

    nps_2d, _, _ = calculer_nps_2d(roi, taille_pixel_mm=pixel_mm)

    fft_centre = np.fft.fftshift(np.fft.fft2(roi))
    attendu = np.abs(fft_centre) ** 2 * pixel_mm ** 2 / (64 * 64)
    np.testing.assert_allclose(nps_2d, attendu)


def test_frequence_moyenne():
    """
    La fréquence moyenne f̄ = ∫f·NPS df / ∫NPS df.
    Avec un pic unique à une fréquence connue, f̄ doit retourner cette fréquence exactement.
    """
    freq = np.linspace(0, 1, 200)
    nps = np.zeros(200)
    nps[100] = 1.0  # pic unique à freq[100] ≈ 0.502 cy/mm

    f_moy = calculer_frequence_moyenne(freq, nps)

    assert abs(f_moy - freq[100]) < 1e-6


def test_pipeline_complet_sur_serie_synthetique():
    """
    Test de bout en bout : une série synthétique de fantôme eau doit produire
    une NPS physiquement cohérente (lissée ≥ 0, f̄ entre 0 et Nyquist).
    """
    serie = creer_serie_fantome(nb_coupes=15)
    resultat = analyser_nps(serie, nb_coupes=10, taille_roi=64)

    nyquist = 1.0 / (2.0 * 0.7)  # ~0.714 cy/mm pour pixel_size = 0.7 mm

    assert np.all(resultat.nps_lisse >= 0), "La NPS lissée ne peut pas être négative"
    assert 0 < resultat.frequence_moyenne < nyquist, "f̄ doit être dans la plage fréquentielle physique"
