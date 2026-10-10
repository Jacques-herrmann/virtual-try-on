"""Exceptions du cœur. `user_message` est destiné au client final, en français."""


class VtoError(Exception):
    user_message = "Une erreur inattendue est survenue."

    def __init__(self, user_message: str | None = None):
        if user_message is not None:
            self.user_message = user_message
        super().__init__(self.user_message)


class MissingApiKey(VtoError):
    user_message = "Aucune clé Gemini configurée. Ajoute-la dans les réglages."


class InvalidApiKey(VtoError):
    user_message = "Ta clé Gemini est invalide. Vérifie-la dans les réglages."


class ProjectBlocked(InvalidApiKey):
    user_message = (
        "Google a bloqué l'accès du projet lié à ta clé Gemini (souvent après une fuite de "
        "la clé). Crée une nouvelle clé dans un nouveau projet sur Google AI Studio."
    )


class QuotaExceeded(VtoError):
    user_message = "Quota Gemini atteint. Réessaie plus tard ou vérifie ton forfait Google AI."


class ModelUnavailable(VtoError):
    user_message = "Le modèle Gemini configuré n'est pas disponible. Vérifie les réglages."


class TransientError(VtoError):
    user_message = "Gemini ne répond pas pour le moment. Réessaie dans quelques instants."


class NoImageReturned(VtoError):
    user_message = "Gemini n'a renvoyé aucune image."


class InvalidModelOutput(VtoError):
    user_message = "La réponse de Gemini est inutilisable."


class NoBackground(VtoError):
    def __init__(self, scene_name: str, garment_type: str):
        self.scene_name = scene_name
        self.garment_type = garment_type
        super().__init__(
            f"La scène « {scene_name} » n'a aucun décor pour le type « {garment_type} »."
        )


class InvalidTransition(VtoError):
    def __init__(self, from_: str, to: str):
        self.from_ = from_
        self.to = to
        super().__init__(f"Impossible de passer l'article de « {from_} » à « {to} ».")


class ArticleNotFound(VtoError):
    def __init__(self, article_id: str):
        self.article_id = article_id
        super().__init__(f"Article introuvable : {article_id}.")
