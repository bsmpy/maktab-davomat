import { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { StepIndicator } from '@/features/registration/StepIndicator'
import { ClassStep } from '@/features/registration/steps/ClassStep'
import { DoneStep } from '@/features/registration/steps/DoneStep'
import { IdentityStep } from '@/features/registration/steps/IdentityStep'
import { OtpStep } from '@/features/registration/steps/OtpStep'
import { PasswordStep } from '@/features/registration/steps/PasswordStep'
import { StudentStep } from '@/features/registration/steps/StudentStep'
import { AuthLayout } from '@/layouts/AuthLayout'
import { useAuthStore } from '@/store/authStore'
import { useChildStore } from '@/store/childStore'
import type {
  ClassGroup,
  LoginResponse,
  Grade,
  RegistrationSession,
  StudentSearchResult,
} from '@/types/api'

// The code is delivered by the bot but typed here, so the wizard is whole.
// Keys rather than words: the indicator resolves them in the language on screen.
const STEP_KEYS = [
  'registration.stepClass',
  'registration.stepStudent',
  'registration.stepIdentity',
  'registration.stepConfirm',
  'registration.stepPassword',
]

type WizardState = {
  grade: Grade | null
  classGroup: ClassGroup | null
  student: StudentSearchResult | null
  session: RegistrationSession | null
  username: string | null
}

const EMPTY: WizardState = {
  grade: null,
  classGroup: null,
  student: null,
  session: null,
  username: null,
}

/**
 * The wizard only tracks *where* the user is; every decision that matters
 * (does this JSHSHIR belong to this pupil, is the phone right, is the OTP
 * valid) is made server-side. Going back never grants access it did not grant
 * going forward.
 */
export function RegisterPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const adoptSession = useAuthStore((store) => store.adoptSession)
  const resetChildren = useChildStore((store) => store.reset)
  const [state, setState] = useState<WizardState>(EMPTY)

  const step = state.username
    ? 5
    : state.session?.phone_verified
      ? 4
      : state.session
        ? 3
        : state.student
          ? 2
          : state.classGroup
            ? 1
            : 0

  const onClassSelected = useCallback((grade: Grade, classGroup: ClassGroup) => {
    setState((current) => ({ ...current, grade, classGroup, student: null }))
  }, [])

  function onCreated(response: LoginResponse) {
    resetChildren()
    adoptSession(response)
    setState((current) => ({
      ...current,
      username: response.username ?? response.user.username,
    }))
  }

  return (
    <AuthLayout
      title={t('auth.register')}
      subtitle={t('auth.registerSubtitle')}
      footer={
        state.username ? null : (
          <>
            Akkauntingiz bormi?{' '}
            <Link to="/kirish" className="font-medium text-brand-600 hover:text-brand-700">
              {t('auth.login')}
            </Link>
          </>
        )
      }
    >
      {state.username ? (
        <DoneStep
          username={state.username}
          onContinue={() => navigate('/', { replace: true })}
        />
      ) : (
        <>
          <StepIndicator steps={STEP_KEYS} current={Math.min(step, STEP_KEYS.length - 1)} />

          {step === 0 ? <ClassStep onSelect={onClassSelected} /> : null}

          {step === 1 && state.classGroup ? (
            <StudentStep
              classGroup={state.classGroup}
              onSelect={(student) => setState((current) => ({ ...current, student }))}
              onBack={() => setState((current) => ({ ...current, classGroup: null }))}
            />
          ) : null}

          {step === 2 && state.student ? (
            <IdentityStep
              student={state.student}
              onVerified={(session) => setState((current) => ({ ...current, session }))}
              onBack={() => setState((current) => ({ ...current, student: null }))}
            />
          ) : null}

          {step === 3 && state.session ? (
            <OtpStep
              session={state.session}
              onVerified={(session) => setState((current) => ({ ...current, session }))}
            />
          ) : null}

          {step === 4 && state.session ? (
            <PasswordStep session={state.session} onCreated={onCreated} />
          ) : null}
        </>
      )}
    </AuthLayout>
  )
}
