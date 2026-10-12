"""Mises à jour de l'app : manifeste distant, vérification, installation."""

from vto.core.errors import VtoError


class UpdateError(VtoError):
    user_message = "La mise à jour a échoué. Réessaie plus tard."
