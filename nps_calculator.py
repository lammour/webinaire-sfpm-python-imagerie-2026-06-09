"""
Calcul de la NPS (Noise Power Spectrum / Spectre de Puissance du Bruit)
pour le contrôle qualité scanner.

Méthode conforme à la décision ANSM du 18/12/2025.
Algorithme basé sur le projet cq-tdm (https://github.com/lammour/cq-tdm).
"""

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from dicom_loader import SerieDicom, SliceDicom

# Extension au-delà de la fréquence de Nyquist pour capturer les coins diagonaux de la NPS 2D
EXTENSION_NYQUIST = 1.375


# ---------------------------------------------------------------------------
# Structures de données
# ---------------------------------------------------------------------------

@dataclass
class PositionROI:
    """Position d'une ROI (Region Of Interest) carrée."""
    x: int       # Colonne du centre (en pixels)
    y: int       # Ligne du centre (en pixels)
    taille: int  # Côté du carré (en pixels)


@dataclass
class ResultatNPS:
    """Résultats complets d'une analyse NPS."""
    # Courbe NPS 1D
    frequences: np.ndarray     # Axe fréquentiel (cycles/mm)
    nps_brut: np.ndarray       # NPS radial brut
    nps_lisse: np.ndarray      # NPS ajusté par polynôme de degré 11

    # Métriques synthétiques
    frequence_moyenne: float   # Fréquence centroïde (cycles/mm)
    nps_moyen: float           # Valeur moyenne de la NPS
    puissance_bruit: float     # Intégrale de la NPS (puissance totale)

    # NPS 2D (pour visualisation avancée)
    nps_2d: np.ndarray
    freq_x: np.ndarray
    freq_y: np.ndarray

    # Paramètres d'analyse
    nb_coupes: int
    taille_roi: int
    taille_pixel_mm: float
    positions_roi: list[PositionROI]


# ---------------------------------------------------------------------------
# Détection du fantôme
# ---------------------------------------------------------------------------

def detecter_centre_fantome(coupe: SliceDicom) -> tuple[int, int]:
    """
    Détecte automatiquement le centre du fantôme eau dans une coupe CT.

    Méthode : seuillage des valeurs eau (-100 à +100 UH) puis centroïde.

    Returns:
        (ligne, colonne) du centre détecté en pixels
    """
    image = coupe.pixel_array
    masque_eau = (image >= -100) & (image <= 100)

    lignes, cols = np.where(masque_eau)
    if len(lignes) == 0:
        # Aucun pixel eau détecté : on retourne le centre géométrique
        return coupe.rows // 2, coupe.columns // 2

    centre_ligne = int(np.mean(lignes))
    centre_col = int(np.mean(cols))
    return centre_ligne, centre_col


def estimer_diametre_fantome(coupe: SliceDicom, centre: tuple[int, int]) -> float:
    """
    Estime le diamètre du fantôme en pixels.

    Returns:
        Diamètre moyen (horizontal + vertical) en pixels
    """
    image = coupe.pixel_array
    masque = (image >= -100) & (image <= 100)
    centre_ligne, centre_col = centre

    # Largeur et hauteur du fantôme par projection du masque
    largeur = int(np.sum(masque[centre_ligne, :]))
    hauteur = int(np.sum(masque[:, centre_col]))
    return (largeur + hauteur) / 2.0


# ---------------------------------------------------------------------------
# Positionnement des ROIs
# ---------------------------------------------------------------------------

def calculer_positions_roi(
    coupe: SliceDicom,
    centre: tuple[int, int],
    taille_roi: int = 64,
) -> list[PositionROI]:
    """
    Calcule les 8 positions ROI selon le motif octogonal ANSM.

    Disposition :
    - 4 ROIs diagonales à ~34% du rayon dans chaque axe
    - 4 ROIs cardinales (haut, bas, gauche, droite) à ~42% du rayon

    Returns:
        Liste de 8 PositionROI
    """
    centre_ligne, centre_col = centre
    rayon = estimer_diametre_fantome(coupe, centre) / 2.0

    dist_cardinale = int(rayon * 0.42)
    decalage_diag = int(rayon * 0.34)

    return [
        # Diagonales
        PositionROI(x=centre_col - decalage_diag, y=centre_ligne - decalage_diag, taille=taille_roi),  # Haut-gauche
        PositionROI(x=centre_col + decalage_diag, y=centre_ligne + decalage_diag, taille=taille_roi),  # Bas-droite
        PositionROI(x=centre_col - decalage_diag, y=centre_ligne + decalage_diag, taille=taille_roi),  # Bas-gauche
        PositionROI(x=centre_col + decalage_diag, y=centre_ligne - decalage_diag, taille=taille_roi),  # Haut-droite
        # Cardinales
        PositionROI(x=centre_col,                  y=centre_ligne - dist_cardinale, taille=taille_roi),  # Haut
        PositionROI(x=centre_col,                  y=centre_ligne + dist_cardinale, taille=taille_roi),  # Bas
        PositionROI(x=centre_col - dist_cardinale, y=centre_ligne,                  taille=taille_roi),  # Gauche
        PositionROI(x=centre_col + dist_cardinale, y=centre_ligne,                  taille=taille_roi),  # Droite
    ]


# ---------------------------------------------------------------------------
# Calcul NPS
# ---------------------------------------------------------------------------

def extraire_roi(coupe: SliceDicom, position: PositionROI) -> np.ndarray | None:
    """Extrait une ROI carrée centrée sur (position.x, position.y). Retourne None si hors image."""
    demi = position.taille // 2
    r1, r2 = position.y - demi, position.y + demi
    c1, c2 = position.x - demi, position.x + demi

    if r1 < 0 or r2 > coupe.rows or c1 < 0 or c2 > coupe.columns:
        return None

    return coupe.pixel_array[r1:r2, c1:c2]


def detrender_roi(roi: np.ndarray) -> np.ndarray:
    """
    Supprime les tendances basse fréquence par ajustement polynômial 2D du 2ème degré.

    Étape indispensable avant la FFT pour éviter les artefacts au centre du spectre.
    """
    lignes, cols = roi.shape
    x = np.arange(cols)
    y = np.arange(lignes)
    X, Y = np.meshgrid(x, y)

    x_flat = X.flatten()
    y_flat = Y.flatten()
    z_flat = roi.flatten()

    # Design matrix : 6 termes du polynôme 2D d'ordre 2
    # (1, x, y, x², y², xy)
    matrice_design = np.column_stack([
        np.ones_like(x_flat),
        x_flat, y_flat,
        x_flat**2, y_flat**2,
        x_flat * y_flat,
    ])

    # lstsq retourne 4 valeurs ; on ne garde que la première (les coefficients)
    coeffs = np.linalg.lstsq(matrice_design, z_flat, rcond=None)[0]

    fond = (
        coeffs[0]
        + coeffs[1] * X + coeffs[2] * Y
        + coeffs[3] * X**2 + coeffs[4] * Y**2
        + coeffs[5] * X * Y
    )
    return roi - fond


def calculer_nps_2d(roi: np.ndarray, taille_pixel_mm: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calcule la NPS 2D par FFT 2D.

    Returns:
        (nps_2d, freq_x, freq_y) avec fréquences en cycles/mm
    """
    lignes, cols = roi.shape
    aire_pixel = taille_pixel_mm**2

    fft_2d = np.fft.fft2(roi)
    fft_centre = np.fft.fftshift(fft_2d)

    nps_2d = (np.abs(fft_centre)**2) * aire_pixel / (lignes * cols)

    freq_x = np.fft.fftshift(np.fft.fftfreq(cols)) / taille_pixel_mm
    freq_y = np.fft.fftshift(np.fft.fftfreq(lignes)) / taille_pixel_mm

    return nps_2d, freq_x, freq_y


def moyenne_radiale(
    nps_2d: np.ndarray,
    taille_pixel_mm: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Calcule la NPS 1D par moyenne radiale angulaire.

    - 36 profils angulaires de 0° à 350° (pas 10°)
    - Interpolation bilinéaire le long de chaque profil
    - Moyenne des 36 profils → courbe NPS 1D

    Returns:
        (nps_radial, frequences_radial) avec fréquences en cycles/mm
    """
    n = nps_2d.shape[0]
    nyquist = 1.0 / (2.0 * taille_pixel_mm)
    freq_max = nyquist * EXTENSION_NYQUIST
    nb_points = int(n // 2 * EXTENSION_NYQUIST) + 1

    freq_r = np.linspace(0, freq_max, nb_points)
    centre = n // 2
    r_pixels = int(n // 2 * EXTENSION_NYQUIST)

    angles_rad = np.deg2rad(np.arange(0, 360, 10))  # 36 angles de 0° à 350°

    # r_vals est identique pour tous les angles — calculé une seule fois
    r_vals = np.linspace(0, r_pixels, nb_points)

    profils = []
    for theta in angles_rad:
        # map_coordinates attend (ligne, colonne) : sin → axe ligne, cos → axe colonne
        lignes_coords = centre + r_vals * np.sin(theta)
        cols_coords = centre + r_vals * np.cos(theta)
        coords = np.array([lignes_coords, cols_coords])
        profil = ndimage.map_coordinates(nps_2d, coords, order=1, mode="constant", cval=0)
        profils.append(profil)

    nps_r = np.mean(np.array(profils), axis=0)
    return nps_r, freq_r


def lisser_nps_polynome(frequences: np.ndarray, nps: np.ndarray, degre: int = 11) -> np.ndarray:
    """
    Ajuste un polynôme de degré 11 sur la courbe NPS brute.

    Returns:
        Valeurs NPS ajustées, forcées à zéro si négatives (la puissance est toujours positive)
    """
    coeffs = np.polyfit(frequences, nps, degre)
    nps_fit = np.polyval(coeffs, frequences)
    return np.maximum(nps_fit, 0.0)


def calculer_frequence_moyenne(frequences: np.ndarray, nps: np.ndarray) -> float:
    """
    Calcule la fréquence centroïde de la NPS (fréquence moyenne).

    f_moy = ∫ f·NPS(f) df / ∫ NPS(f) df
    """
    integrale_totale = np.trapezoid(nps, frequences)
    if integrale_totale <= 0:
        return 0.0
    integrale_ponderee = np.trapezoid(frequences * nps, frequences)
    return float(integrale_ponderee / integrale_totale)


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def analyser_nps(
    serie: SerieDicom,
    nb_coupes: int = 10,
    taille_roi: int = 64,
) -> ResultatNPS:
    """
    Analyse NPS complète sur une série de coupes scanner.

    Protocole ANSM :
    - 10 coupes centrales
    - 8 ROIs en motif octogonal de 64×64 pixels
    - FFT 2D + moyenne radiale + ajustement polynômial

    Args:
        serie: Série DICOM chargée
        nb_coupes: Nombre de coupes à analyser (défaut 10)
        taille_roi: Côté des ROIs carrées en pixels (défaut 64)

    Returns:
        ResultatNPS avec courbe NPS et métriques

    Raises:
        ValueError: Si la série n'a pas assez de coupes
    """
    if serie.nb_coupes < nb_coupes:
        raise ValueError(
            f"L'analyse NPS nécessite au moins {nb_coupes} coupes, "
            f"mais la série n'en contient que {serie.nb_coupes}."
        )

    # Sélection des coupes centrales
    debut = (serie.nb_coupes - nb_coupes) // 2
    coupes = serie.coupes[debut:debut + nb_coupes]

    # Détection du centre et des ROIs sur la coupe médiane
    coupe_mediane = coupes[len(coupes) // 2]
    centre = detecter_centre_fantome(coupe_mediane)
    taille_pixel_mm = coupe_mediane.pixel_size_mm
    positions = calculer_positions_roi(coupe_mediane, centre, taille_roi)

    # Axes fréquentiels identiques pour toutes les ROIs (même taille, même pixel)
    freq_x = np.fft.fftshift(np.fft.fftfreq(taille_roi)) / taille_pixel_mm
    freq_y = freq_x.copy()

    # Accumulation de la NPS 2D sur toutes les coupes et toutes les ROIs
    nps_somme = np.zeros((taille_roi, taille_roi))
    nb_roi_valides = 0

    for coupe in coupes:
        for pos in positions:
            roi = extraire_roi(coupe, pos)
            if roi is None:
                continue
            roi_dt = detrender_roi(roi)
            nps_2d, _, _ = calculer_nps_2d(roi_dt, taille_pixel_mm)
            nps_somme += nps_2d
            nb_roi_valides += 1

    if nb_roi_valides == 0:
        raise ValueError("Aucune ROI valide extraite. Vérifier la position du fantôme.")

    nps_2d_moyen = nps_somme / nb_roi_valides

    # Moyenne radiale → NPS 1D
    nps_brut, frequences = moyenne_radiale(nps_2d_moyen, taille_pixel_mm)

    # Lissage polynômial et métriques
    nps_lisse = lisser_nps_polynome(frequences, nps_brut)
    freq_moyenne = calculer_frequence_moyenne(frequences, nps_lisse)

    return ResultatNPS(
        frequences=frequences,
        nps_brut=nps_brut,
        nps_lisse=nps_lisse,
        frequence_moyenne=freq_moyenne,
        nps_moyen=float(np.mean(nps_lisse)),
        puissance_bruit=float(np.trapezoid(nps_lisse, frequences)),
        nps_2d=nps_2d_moyen,
        freq_x=freq_x,
        freq_y=freq_y,
        nb_coupes=len(coupes),
        taille_roi=taille_roi,
        taille_pixel_mm=taille_pixel_mm,
        positions_roi=positions,
    )
