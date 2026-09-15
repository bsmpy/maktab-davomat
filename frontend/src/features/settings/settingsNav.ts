import type { ComponentType, SVGProps } from 'react'

import {
  GateIcon,
  PaletteIcon,
  ScanFaceIcon,
  SlidersIcon,
  SparklesIcon,
  TelegramIcon,
} from '@/components/ui'
import type { IntegrationKind, Permission } from '@/types/api'

/**
 * The Sozlamalar menu, as data.
 *
 * Adding a section is a line in this array plus a branch in the page's
 * renderer — the sidebar, the header and the routing all read from here.
 */
export interface SettingsItem {
  /** Slug used in `?bolim=`, so a section is linkable and survives a reload. */
  id: string
  /** Translation key, resolved where the item is drawn. */
  labelKey: string
  icon: ComponentType<SVGProps<SVGSVGElement>>
  /** One line under the section title in the working area. */
  /** Translation key for the one line under the title. */
  descriptionKey: string
  /**
   * The integration row this section edits. Sections without one either read
   * no backend at all (Umumiy) or are not built yet.
   */
  kind?: IntegrationKind
  /** False until a backend exists for it — the section says so plainly. */
  ready?: boolean
  /** Extra permissions this one section needs on top of its group's. */
  permissions?: Permission[]
}

export interface SettingsGroup {
  /** Small uppercase heading above the group. */
  /** Translation key for the small heading above the group. */
  titleKey: string
  /**
   * What it costs to see this group at all.
   *
   * An ADMIN opens Sozlamalar for the two appearance switches and never sees
   * the integrations group — the credentials in it are the platform's, not the
   * school's. The server refuses those endpoints to them regardless; this is
   * what keeps the menu honest about it.
   */
  permissions: Permission[]
  items: SettingsItem[]
}

export const SETTINGS_GROUPS: SettingsGroup[] = [
  {
    // The register page that is not on the rail. It moved here rather than
    // disappearing: an administrator still edits positions, just not every day,
    // so it sits one click deeper than the daily sections.
    titleKey: 'settings.groupRegister',
    permissions: ['register.access'],
    items: [
      {
        id: 'lavozimlar',
        labelKey: 'nav.positions',
        icon: SlidersIcon,
        descriptionKey: 'settings.positionsNavHint',
        permissions: ['positions.view'],
      },
    ],
  },
  {
    titleKey: 'settings.groupIntegrations',
    permissions: ['integrations.view'],
    items: [
      {
        id: 'telegram',
        labelKey: 'settings.telegramTitle',
        icon: TelegramIcon,
        descriptionKey: 'settings.telegramNavHint',
        kind: 'TELEGRAM_BOT',
      },
      {
        id: 'face-id',
        labelKey: 'settings.faceIdTitle',
        icon: ScanFaceIcon,
        descriptionKey: 'settings.faceIdNavHint',
        kind: 'FACE_ID',
      },
      {
        id: 'terminallar',
        labelKey: 'settings.terminalsTitle',
        icon: GateIcon,
        descriptionKey: 'settings.terminalsNavHint',
        kind: 'TERMINALS',
      },
    ],
  },
  {
    titleKey: 'settings.groupAppearance',
    permissions: ['settings.appearance'],
    items: [
      {
        // Held on the server, one row for the installation: these two say what
        // the interface *offers*, so turning them off has to reach everybody,
        // not just the browser of whoever flipped the switch. The palette a
        // person then picks out of what is offered is still their own.
        id: 'mavzular',
        labelKey: 'settings.themes',
        icon: PaletteIcon,
        descriptionKey: 'settings.themesNavHint',
      },
      {
        id: 'zarrachalar',
        labelKey: 'settings.particles',
        icon: SparklesIcon,
        descriptionKey: 'settings.particlesNavHint',
      },
    ],
  },
]

export const SETTINGS_ITEMS: SettingsItem[] = SETTINGS_GROUPS.flatMap((group) => group.items)

export const DEFAULT_SETTINGS_ITEM = 'telegram'

/** The groups this session may open, in menu order. */
export function settingsGroupsFor(
  can: (...permissions: Permission[]) => boolean,
): SettingsGroup[] {
  return SETTINGS_GROUPS.filter((group) => can(...group.permissions))
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => !item.permissions || can(...item.permissions)),
    }))
    .filter((group) => group.items.length > 0)
}

/**
 * The section to show for `?bolim=`, limited to what this viewer may open.
 *
 * Falling back to the first section they *can* open matters: an ADMIN whose
 * URL still says `?bolim=telegram` should land on Mavzular, not on a section
 * the server will refuse.
 */
export function findSettingsItem(
  id: string | null,
  groups: SettingsGroup[] = SETTINGS_GROUPS,
): SettingsItem | undefined {
  const items = groups.flatMap((group) => group.items)
  return (
    items.find((item) => item.id === id) ??
    items.find((item) => item.id === DEFAULT_SETTINGS_ITEM) ??
    items[0]
  )
}
