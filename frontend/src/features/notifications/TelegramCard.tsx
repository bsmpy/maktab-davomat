import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { telegramApi } from '@/api/profileApi'
import { ApiError } from '@/api/errors'
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  CheckIcon,
  CopyIcon,
  Modal,
  Skeleton,
  TelegramIcon,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import { toast } from '@/store/toastStore'
import type { TelegramLinkCode } from '@/types/api'

/** Telegram linking: the site issues a single-use code, the bot redeems it. */
export function TelegramCard() {
  const { t } = useTranslation()
  const status = useAsyncData(() => telegramApi.status(), [])
  const [code, setCode] = useState<TelegramLinkCode | null>(null)
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)

  async function requestCode() {
    setBusy(true)
    try {
      setCode(await telegramApi.requestLinkCode())
    } catch (error) {
      toast.error(t('common.error'), error instanceof ApiError ? error.message : undefined)
    } finally {
      setBusy(false)
    }
  }

  async function unlink() {
    setBusy(true)
    try {
      await telegramApi.unlink()
      toast.success(t('notifications.disconnected'), 'Telegram akkaunt ajratildi.')
      status.reload()
    } catch (error) {
      toast.error(t('common.error'), error instanceof ApiError ? error.message : undefined)
    } finally {
      setBusy(false)
    }
  }

  async function copyCode() {
    if (!code) return
    try {
      await navigator.clipboard.writeText(code.code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      /* clipboard blocked – the code is on screen anyway */
    }
  }

  if (status.initialLoading) {
    return <Skeleton className="h-44 w-full rounded-2xl" />
  }

  const linked = status.data?.linked ?? false

  return (
    <>
      <Card>
        <CardHeader
          title="Telegram"
          description={t('notifications.telegramHint')}
          action={
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-600">
              <TelegramIcon width={20} height={20} />
            </span>
          }
        />
        <CardBody className="space-y-4">
          {linked ? (
            <>
              <div className="flex items-center gap-2 rounded-xl bg-emerald-500/15 px-3.5 py-3 text-sm text-emerald-800">
                <CheckIcon width={18} height={18} />
                <span>
                  Ulangan
                  {status.data?.username ? ` · @${status.data.username}` : ''}
                </span>
              </div>
              <Button variant="secondary" loading={busy} onClick={() => void unlink()}>
                {t('notifications.disconnect')}
              </Button>
            </>
          ) : (
            <>
              <p className="text-sm text-ink-600">
                Bog'lash uchun bir martalik kod oling va uni{' '}
                <span className="font-medium text-ink-800">
                  @{status.data?.bot_username || 'botga'}
                </span>{' '}
                yuboring.
              </p>
              <Button loading={busy} onClick={() => void requestCode()}>
                {t('notifications.linkTelegram')}
              </Button>
            </>
          )}
        </CardBody>
      </Card>

      <Modal
        open={Boolean(code)}
        onClose={() => {
          setCode(null)
          status.reload()
        }}
        title={t('notifications.connect')}
        description={t('notifications.codeHint')}
        footer={
          <Button
            onClick={() => {
              setCode(null)
              status.reload()
            }}
          >
            {t('notifications.connected')}
          </Button>
        }
      >
        {code ? (
          <div className="space-y-5 text-center">
            <div className="rounded-xl border border-dashed border-brand-300 bg-brand-50/60 px-4 py-6">
              <p className="text-xs font-medium uppercase tracking-wide text-brand-600">
                {t('notifications.code')}
              </p>
              <p className="mt-2 select-all text-3xl font-semibold tracking-[0.3em] text-ink-900">
                {code.code}
              </p>
              <Button
                variant="ghost"
                size="sm"
                className="mt-2 text-brand-700"
                leftIcon={
                  copied ? <CheckIcon width={16} height={16} /> : <CopyIcon width={16} height={16} />
                }
                onClick={() => void copyCode()}
              >
                {copied ? 'Nusxalandi' : 'Nusxalash'}
              </Button>
            </div>

            <div className="space-y-2 text-left text-sm text-ink-600">
              <p>1. Telegramda botni oching.</p>
              <p>2. Yuqoridagi kodni botga yuboring.</p>
              <p>3. Bot akkauntingizni tanib, xabarlarni yubora boshlaydi.</p>
            </div>

            {code.deep_link ? (
              <a
                href={code.deep_link}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-brand-600 px-4 font-medium text-onbrand transition hover:bg-brand-700"
              >
                <TelegramIcon width={18} height={18} />
                {t('notifications.openInTelegram')}
              </a>
            ) : null}
          </div>
        ) : null}
      </Modal>
    </>
  )
}
