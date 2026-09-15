import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import { ChildSwitcher } from '@/components/layout/ChildSwitcher'
import { useChildStore } from '@/store/childStore'
import type { Child } from '@/types/api'

function child(id: string, name: string, group: string, rate: number): Child {
  return {
    id,
    first_name: name,
    last_name: 'Valiyev',
    middle_name: '',
    full_name: `Valiyev ${name}`,
    display_name: `${name} Valiyev`,
    initials: `${name[0]}V`,
    class_group: group,
    class_group_id: `cg-${group}`,
    grade_level: Number(group.split('-')[0]),
    school: 'Test maktabi',
    relation: 'FATHER',
    relation_label: 'Otasi',
    current_month: {
      school_days: 20, days_present: 19, days_absent: 1, days_late: 2,
      entries: 21, exits: 21, inside_minutes: 6000, outside_minutes: 45,
      late_minutes: 30, avg_inside_minutes: 315, rate,
    },
  }
}

const CHILDREN = [
  child('c1', 'Azizbek', '7-A', 94),
  child('c2', 'Madina', '3-B', 98),
  child('c3', 'Sardor', '1-A', 88),
]

describe('child switcher', () => {
  beforeEach(() => {
    useChildStore.setState({
      children: CHILDREN,
      activeChildId: 'c1',
      loading: false,
      error: null,
    })
  })

  it('shows the active child and their class', () => {
    render(<ChildSwitcher />)
    expect(screen.getByText('Azizbek Valiyev')).toBeInTheDocument()
    expect(screen.getByText(/7-A sinf/)).toBeInTheDocument()
  })

  it('lists every child and switches the active one', async () => {
    render(<ChildSwitcher />)
    await userEvent.click(screen.getByRole('button'))

    const options = screen.getAllByRole('option')
    expect(options).toHaveLength(3)
    expect(screen.getByText('Madina Valiyev')).toBeInTheDocument()
    expect(screen.getByText('Sardor Valiyev')).toBeInTheDocument()

    await userEvent.click(screen.getByText('Madina Valiyev'))
    expect(useChildStore.getState().activeChildId).toBe('c2')
  })

  it('does not open a menu for an only child', async () => {
    useChildStore.setState({ children: [CHILDREN[0]], activeChildId: 'c1' })
    render(<ChildSwitcher />)
    await userEvent.click(screen.getByRole('button'))
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })
})
