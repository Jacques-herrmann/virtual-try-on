import { driver, type Driver } from 'driver.js'
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
  driver: Driver | null
  /** Écran quitté : la visite se ferme sans être marquée vue. */
  interrupted: boolean
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
    const id = pending.shift()
    if (id) void maybeStart(id)
  }

  async function maybeStart(id: TourId): Promise<void> {
    if (tourSeen(id) || videoOpen.value) return
    if (current) {
      if (current.id !== id && !pending.includes(id)) pending.push(id)
      return
    }
    const session: Session = { id, driver: null, interrupted: false }
    current = session
    const steps = await waitForTargets(TOURS[id], session)
    if (session.interrupted || !steps.length || videoOpen.value || tourSeen(id)) {
      if (current === session) current = null
      next()
      return
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
      showButtons: ['next', 'previous', 'close'],
      popoverClass: 'kaloe-tour',
      stagePadding: 6,
      stageRadius: 12,
      onPopoverRender: (popover) => addSkipButton(popover.footer, () => instance.destroy()),
      onDestroyed: () => {
        if (current === session) current = null
        // Terminée, passée ou fermée : vue. Interrompue parce que l'écran a changé : elle reviendra.
        if (!session.interrupted) void markTourSeen(id)
        next()
      },
    })
    session.driver = instance
    instance.drive()
  }

  /** Ferme la visite `id` (en cours ou en attente) sans la marquer vue. */
  function stop(id: TourId) {
    const index = pending.indexOf(id)
    if (index >= 0) pending.splice(index, 1)
    if (current?.id !== id) return
    current.interrupted = true
    current.driver?.destroy()
  }

  async function resetTours() {
    await save({ tours_seen: [] })
  }

  return { maybeStart, stop, resetTours }
}

/**
 * Joue la visite `id` dès que `when` est vrai et que la vidéo est fermée ;
 * la ferme sans la marquer vue quand le composant disparaît.
 */
export function useAutoTour(id: TourId, when: () => boolean = () => true) {
  const { videoOpen } = useTutorial()
  const { maybeStart, stop } = useTour()
  const stopWatch = watch(
    () => when() && !videoOpen.value,
    (ready) => {
      if (ready) void maybeStart(id)
    },
    { immediate: true },
  )
  onBeforeUnmount(() => {
    stopWatch()
    stop(id)
  })
}
