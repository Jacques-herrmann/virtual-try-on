"""Licence : clé saisie par le vendeur, jeton signé par le Worker, état de l'abonnement.

Dépend de `vto.core`, jamais l'inverse.
"""

from vto.core.errors import VtoError


class LicenseError(VtoError):
    user_message = "Cette action demande un abonnement actif."
