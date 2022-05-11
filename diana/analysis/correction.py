"""Multiple testing correction procedures."""
from typing import Hashable, Mapping


def benjamini_hochberg(
        p_values: Mapping[Hashable, float]) -> dict[Hashable, float]:
    """
    Benjamini-Hochberg procedure for multiple testing correction.

    Benjamini, Y. et al. (2009) Selective inference in complex research,
        Philos. Trans. R. Soc. A, 367, 4255-4271.

    Args:
        p_values: Keyed p-values.

    Returns:
        Benjamini-Hochberg-adjusted p-values.
    """
    m = len(p_values)
    sorted_p_values = sorted([list(item) for item in p_values.items()],
                             key=lambda item: item[1])

    for i in range(m - 1, 0, -1):
        if sorted_p_values[i - 1][1] / i > sorted_p_values[i][1] / (i + 1):
            sorted_p_values[i - 1][1] = sorted_p_values[i][1] * i / (i + 1)

    return {
        key: min(m * p_value / i, 1.0)
        for i, (key, p_value) in enumerate(sorted_p_values, start=1)
    }


def bonferroni(p_values: Mapping[Hashable, float]) -> dict[Hashable, float]:
    """
    Bonferroni procedure for multiple testing correction.

    Goeman, J. J. and Solari, A (2014)  Multiple hypothesis testing in genomics,
        Stat. in Med., 33, 1946-1978.

    Args:
        p_values: Keyed p-values.

    Returns:
        Bonferroni-adjusted p-values.
    """
    m = len(p_values)

    return {key: min(m * p_value, 1.0) for key, p_value in p_values.items()}
