import { driver } from 'driver.js'
import 'driver.js/dist/driver.css'
import '@/tour.css'
import { onBeforeUnmount, watch } from 'vue'

import { useTutorial } from '@/stores/tutorial'
import { TOURS, type TourId, type TourStep } from '@/tours'

// Les listes arrivent par l'API : on laisse aux éléments visés un court délai pour apparaître.
const WAIT_MS = 1500
const POLL_MS = 100

interface Session {
  id: TourId
  /** Écran quitté avant le lancement. */
  interrupted: boolean
  finished: boolean
  finish: ((seen: boolean) => void) | null
}

let current: Session | null = null
const pending: TourId[] = []

function present(steps: TourStep[]): TourStep[] {
  return steps.filter((step) => document.querySelector(step.target))
}

async function waitForTargets(steps: TourStep[], session: Session): Promise<TourStep[]> {
  const deadline = Date.now() + WAIT_MS
  while (present(steps).length < steps.length && Date.now() < deadline && !session.interrupted) {
    await new Promise((resolve) => setTimeout(resolve, POLL_MS))
  }
  return present(steps)
}

function addSkipButton(footer: HTMLElement, close: () => void) {
  const skip = document.createElement('button')
  skip.type = 'button'
  skip.className = 'tour-skip'
  skip.textContent = 'Passer la visite'
  skip.addEventListener('click', close)
  footer.prepend(skip)
}

/** Visites guidées (tours.ts) : une à la fois, jouées une seule fois par écran. */
export function useTour() {
  const { videoOpen, tourSeen, markTourSeen, save } = useTutorial()

  function next() {
    // Hors de onDestroyed : driver.js finit d'abord de retirer la visite précédente du DOM.
    setTimeout(() => {
      const id = pending.shift()
      if (id) void maybeStart(id)
    }, 300)
  }

  async function maybeStart(id: TourId): Promise<void> {
    if (tourSeen(id) || videoOpen.value) return
    if (current) {
      if (current.id !== id && !pending.includes(id)) pending.push(id)
      return
    }
    const session: Session = { id, interrupted: false, finished: false, finish: null }
    current = session
    const steps = await waitForTargets(TOURS[id], session)
    if (session.interrupted || !steps.length || videoOpen.value || tourSeen(id)) {
      if (current === session) current = null
      next()
      return
    }
    // Fin de visite, une seule fois : vue si le vendeur l'a terminée ou passée, pas si l'écran
    // a changé. driver.js n'appelle onDestroyed que s'il a un élément actif : on ne s'y fie pas.
    const finish = (seen: boolean) => {
      if (session.finished) return
      session.finished = true
      instance.destroy()
      if (current === session) current = null
      if (seen) void markTourSeen(id)
      next()
    }
    const instance = driver({
      steps: steps.map((step) => ({
        element: step.target,
        popover: { title: step.title, description: step.text },
      })),
      showProgress: steps.length > 1,
      progressText: '{{current}}/{{total}}',
      nextBtnText: 'Suivant',
      prevBtnText: 'Précédent',
      doneBtnText: 'Terminer',
      // « Passer la visite » (et Échap) remplace la croix.
      showButtons: ['next', 'previous'],
      popoverClass: 'kaloe-tour',
      overlayColor: '#2e1f2b',
      overlayOpacity: 0.55,
      stagePadding: 6,
      stageRadius: 12,
      onPopoverRender: (popover) => addSkipButton(popover.footer, () => finish(true)),
      // Terminer, Échap, clic sur le fond : appelé à la place de la fermeture.
      onDestroyStarted: () => finish(true),
    })
    session.finish = finish
    instance.drive()
  }

  /** Ferme la visite `id` (en cours ou en attente) sans la marquer vue. */
  function stop(id: TourId) {
    const index = pending.indexOf(id)
    if (index >= 0) pending.splice(index, 1)
    if (current?.id !== id) return
    current.interrupted = true
    current.finish?.(false)
  }

  async function resetTours() {
    await save({ tours_seen: [] })
  }

  return { maybeStart, stop, resetTours }
}

/**
 * Joue la visite `id` dès que `when` est vrai et que la vidéo est fermée ; la ferme sans la
 * marquer vue quand `when` redevient faux (ex. : fenêtre ouverte) ou que le composant disparaît.
 */
export function useAutoTour(id: TourId, when: () => boolean = () => true) {
  const { videoOpen } = useTutorial()
  const { maybeStart, stop } = useTour()
  const stopWatch = watch(
    () => when() && !videoOpen.value,
    (ready) => (ready ? void maybeStart(id) : stop(id)),
    { immediate: true },
  )
  onBeforeUnmount(() => {
    stopWatch()
    stop(id)
  })
}
