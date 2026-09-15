import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { JshshirInput, PassportIdInput, PhoneInput } from '@/components/ui'

/** The masked inputs are controlled; this is the parent they expect. */
function Harness({ kind }: { kind: 'phone' | 'passport' | 'jshshir' }) {
  const [value, setValue] = useState('')
  const props = { label: 'Field', value, onChange: setValue }
  if (kind === 'phone') return <PhoneInput {...props} />
  if (kind === 'passport') return <PassportIdInput {...props} />
  return <JshshirInput {...props} />
}

describe('PhoneInput', () => {
  it('starts on the country code and builds the mask as digits arrive', async () => {
    const user = userEvent.setup()
    render(<Harness kind="phone" />)
    const field = screen.getByLabelText('Field') as HTMLInputElement
    expect(field.value).toBe('+998(')

    await user.click(field)
    await user.keyboard('901234567')
    expect(field.value).toBe('+998(90)123-45-67')
  })

  it('drops the closing bracket when the digits behind it go away', async () => {
    const user = userEvent.setup()
    render(<Harness kind="phone" />)
    const field = screen.getByLabelText('Field') as HTMLInputElement

    await user.click(field)
    await user.keyboard('901')
    expect(field.value).toBe('+998(90)1')

    await user.keyboard('{Backspace}')
    expect(field.value).toBe('+998(90')
  })

  it('never lets the prefix be deleted', async () => {
    const user = userEvent.setup()
    render(<Harness kind="phone" />)
    const field = screen.getByLabelText('Field') as HTMLInputElement

    await user.click(field)
    await user.keyboard('9{Backspace}{Backspace}{Backspace}{Backspace}')
    expect(field.value).toBe('+998(')
  })

  it('ignores letters', async () => {
    const user = userEvent.setup()
    render(<Harness kind="phone" />)
    const field = screen.getByLabelText('Field') as HTMLInputElement

    await user.click(field)
    await user.keyboard('9a0b1')
    expect(field.value).toBe('+998(90)1')
  })
})

describe('PassportIdInput', () => {
  it('upper-cases the two letters and then takes digits only', async () => {
    const user = userEvent.setup()
    render(<Harness kind="passport" />)
    const field = screen.getByLabelText('Field') as HTMLInputElement

    await user.click(field)
    await user.keyboard('aa1234567')
    expect(field.value).toBe('AA1234567')

    // The eighth digit has nowhere to go.
    await user.keyboard('8')
    expect(field.value).toBe('AA1234567')
  })

  it('refuses a digit where a letter belongs', async () => {
    const user = userEvent.setup()
    render(<Harness kind="passport" />)
    const field = screen.getByLabelText('Field') as HTMLInputElement

    await user.click(field)
    await user.keyboard('1')
    expect(field.value).toBe('')
  })
})

describe('JshshirInput', () => {
  it('keeps fourteen digits and nothing else', async () => {
    const user = userEvent.setup()
    render(<Harness kind="jshshir" />)
    const field = screen.getByLabelText('Field') as HTMLInputElement

    await user.click(field)
    await user.keyboard('31234567890123456')
    expect(field.value).toBe('31234567890123')
  })
})
