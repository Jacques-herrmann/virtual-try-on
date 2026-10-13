// Visites guidées : une par écran, jouée à sa première visite (composables/tour.ts).
// Chaque `target` vise un attribut data-tour="…" posé dans le composant de l'écran.

export type TourId = 'articles' | 'articles-list' | 'article-form' | 'review' | 'scenes' | 'settings'

export interface TourStep {
  target: string
  title: string
  text: string
}

const at = (name: string) => `[data-tour="${name}"]`

export const TOURS: Record<TourId, TourStep[]> = {
  articles: [
    {
      target: at('new-article'),
      title: 'Ajoute un vêtement',
      text: 'Tout commence ici : une photo de ton vêtement, et Kaloé crée les photos portées et l’annonce.',
    },
    {
      target: at('nav-scenes'),
      title: 'Tes scènes',
      text: 'Chaque scène active (mannequin, cintre…) produit une photo par article. Tu peux ajouter tes propres décors.',
    },
    {
      target: at('nav-settings'),
      title: 'Ton compte Vinted',
      text: 'Avant le premier envoi, connecte ton compte Vinted dans les réglages.',
    },
    {
      target: at('nav-help'),
      title: 'Besoin d’aide ?',
      text: 'Tout est expliqué ici, et tu peux y revoir la vidéo de présentation.',
    },
  ],
  'articles-list': [
    {
      target: at('search'),
      title: 'Retrouve un article',
      text: 'Tape un mot du titre, la marque, la taille ou la couleur, ou filtre par type et par public.',
    },
    {
      target: at('status-filter'),
      title: 'Où en sont tes articles',
      text: '« À relire » : prêts à vérifier. « Validés » : prêts à partir sur Vinted.',
    },
    {
      target: at('article-card'),
      title: 'Ouvre un article',
      text: 'Clique sur un article pour relire ses photos et son annonce.',
    },
    {
      target: at('check-all'),
      title: 'Envoie sur Vinted',
      text: 'Coche les articles validés, puis clique sur « Envoyer sur Vinted » : Kaloé remplit les annonces à ta place.',
    },
  ],
  'article-form': [
    {
      target: at('photos'),
      title: 'Les photos',
      text: 'Dépose une ou plusieurs photos nettes et bien éclairées. La première sert de référence.',
    },
    {
      target: at('garment-type'),
      title: 'Le type de vêtement',
      text: 'Seuls le type et le public sont obligatoires.',
    },
    {
      target: at('optional-fields'),
      title: 'Le reste est facultatif',
      text: 'Marque, taille, état, prix : laisse vide et l’IA proposera, tu corrigeras à la relecture.',
    },
    {
      target: at('generate'),
      title: 'Génère',
      text: 'Kaloé crée une photo par scène et rédige l’annonce. Tu peux ajouter d’autres articles pendant ce temps.',
    },
  ],
  review: [
    {
      target: at('scene-photos'),
      title: 'Les photos générées',
      text: '« Régénérer » refait une photo, « Écarter » la retire de l’annonce.',
    },
    {
      target: at('gallery'),
      title: 'L’ordre des photos',
      text: 'La première photo est celle que Vinted affiche en couverture.',
    },
    {
      target: at('listing'),
      title: 'L’annonce',
      text: 'Titre, description, catégorie, taille, prix : tout se modifie directement.',
    },
    {
      target: at('validate'),
      title: 'Valide',
      text: 'Rien ne part sur Vinted sans ta validation.',
    },
  ],
  scenes: [
    {
      target: at('scene-toggle'),
      title: 'Active ou désactive',
      text: 'Chaque scène active produit une photo par article. Les flèches changent l’ordre des photos.',
    },
    {
      target: at('scene-prompt'),
      title: 'Les consignes',
      text: 'Ce texte dit à l’IA comment mettre en scène le vêtement. Tu peux l’adapter.',
    },
    {
      target: at('backgrounds'),
      title: 'Tes décors',
      text: 'Ajoute tes propres photos de décor, vides et sans vêtement : Kaloé en tire une au hasard.',
    },
  ],
  settings: [
    {
      target: at('vinted-connect'),
      title: 'Connecte Vinted',
      text: 'Connecte-toi une fois dans la fenêtre qui s’ouvre. Kaloé ne connaît jamais ton mot de passe.',
    },
    {
      target: at('vinted-mode'),
      title: 'Brouillon ou publication',
      text: 'Choisis si Kaloé enregistre l’annonce en brouillon (à publier depuis Vinted) ou la publie directement.',
    },
  ],
}
