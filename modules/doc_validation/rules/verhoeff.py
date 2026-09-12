"""
Verhoeff Checksum Algorithm Implementation.

Used by the Unique Identification Authority of India (UIDAI) for 12-digit Aadhaar cards.
Based on the dihedral group D5 (symmetries of a regular pentagon), it catches:
- 100% of all single-digit substitution errors (e.g., typing 4 instead of 7)
- 100% of all adjacent digit transposition errors (e.g., typing 54 instead of 45)
- Over 95% of twin and jump-transposition errors
"""

from typing import Union

# Dihedral group D5 multiplication table
D_TABLE = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0)
)

# Permutation table p
P_TABLE = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8)
)

# Multiplicative inverse table
INV_TABLE = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def validate_verhoeff(num_str: Union[str, int]) -> bool:
    """
    Validates a number string containing a Verhoeff check digit at the end.
    Returns True if valid, False otherwise.
    """
    clean_digits = "".join(c for c in str(num_str) if c.isdigit())
    if not clean_digits:
        return False
    
    c = 0
    for i, item in enumerate(reversed(clean_digits)):
        c = D_TABLE[c][P_TABLE[i % 8][int(item)]]
    return c == 0


def compute_verhoeff(num_str: Union[str, int]) -> int:
    """
    Computes the Verhoeff check digit to append to a number string.
    """
    clean_digits = "".join(c for c in str(num_str) if c.isdigit())
    if not clean_digits:
        raise ValueError("Cannot compute Verhoeff check digit for empty digits.")
    
    c = 0
    for i, item in enumerate(reversed(clean_digits)):
        c = D_TABLE[c][P_TABLE[(i + 1) % 8][int(item)]]
    return INV_TABLE[c]
