import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { adminApi } from '@/api/adminApi'
import { toApiError } from '@/api/errors'
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
} from '@/components/ui'
import { toast } from '@/store/toastStore'
import type { ImportReport } from '@/types/api'
import { cn } from '@/utils/cn'

/**
 * Excel import — the way a real register gets loaded.
 *
 * Two-phase by design, exactly as the service is: the workbook is always
 * validated and previewed first, and only a second, explicit click writes
 * anything. A file with a single bad row writes nothing at all.
 */
export function ImportPanel() {
  const { t } = useTranslation()
  const [file, setFile] = useState<File | null>(null)
  const [report, setReport] = useState<ImportReport | null>(null)
  const [busy, setBusy] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  async function downloadTemplate() {
    try {
      const blob = await adminApi.importTemplate()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'namuna.xlsx'
      link.click()
      URL.revokeObjectURL(url)
    } catch (error) {
      toast.error(t('register.exportFailed'), toApiError(error).message)
    }
  }

  async function send(commit: boolean) {
    if (!file) return
    setBusy(true)
    try {
      const result = await adminApi.importStudents(file, { commit })
      setReport(result)
      if (commit && result.ok) {
        toast.success(
          t('importing.finished'),
          `${result.students_created} o'quvchi, ${result.guardians_created} yaqini qo'shildi.`,
        )
        setFile(null)
        if (input.current) input.current.value = ''
      } else if (!result.ok) {
        toast.error(t('importing.hasErrors'), `${result.errors.length} ta qator rad etildi.`)
      }
    } catch (error) {
      toast.error(t('importing.failed'), toApiError(error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title={t('importing.title')}
          description={t('importing.hint')}
          action={
            <Button variant="secondary" onClick={downloadTemplate}>
              {t('importing.downloadTemplate')}
            </Button>
          }
        />
        <CardBody className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <input
              ref={input}
              type="file"
              accept=".xlsx"
              className="text-sm text-ink-600 file:mr-3 file:rounded-xl file:border-0 file:bg-ink-100 file:px-4 file:py-2 file:text-sm file:font-medium file:text-ink-700 hover:file:bg-ink-200"
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null)
                setReport(null)
              }}
            />
            <Button variant="secondary" disabled={!file || busy} onClick={() => send(false)}>
              {t('importing.check')}
            </Button>
            <Button
              disabled={!file || busy || !report?.ok || !report?.dry_run}
              onClick={() => send(true)}
            >
              {t('importing.write')}
            </Button>
          </div>

          <p className="text-xs text-ink-500">
            {t('importing.onlyLabel')} <code>.xlsx</code>. Bitta qatorda xato bo‘lsa ham hech narsa
            yozilmaydi — avval xatolarni tuzating.
          </p>
        </CardBody>
      </Card>

      {report ? (
        <Card>
          <CardHeader
            title={report.dry_run ? 'Tekshiruv natijasi' : 'Import natijasi'}
            description={`${report.total_rows} ta qator o'qildi`}
            action={
              report.ok ? (
                <Badge className="bg-emerald-500/15 text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
                  {t('importing.clean')}
                </Badge>
              ) : (
                <Badge className="bg-red-500/15 text-red-700 ring-1 ring-inset ring-red-600/20">
                  {report.errors.length} ta xato
                </Badge>
              )
            }
          />
          <CardBody className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label={t('importing.studentsAdded')} value={report.students_created} />
            <Stat label={t('importing.studentsUpdated')} value={report.students_updated} />
            <Stat label={t('importing.guardiansAdded')} value={report.guardians_created} />
            <Stat label={t('importing.linksAdded')} value={report.links_created} />
          </CardBody>

          {report.errors.length > 0 ? (
            <ul className="divide-y divide-ink-100 border-t border-ink-100">
              {report.errors.slice(0, 50).map((error, index) => (
                <li
                  key={`${error.row}-${error.column}-${index}`}
                  className="flex items-start gap-3 px-5 py-3 text-sm"
                >
                  <span className="w-16 shrink-0 font-medium tabular-nums text-red-600">
                    {error.row}-qator
                  </span>
                  <span className="w-48 shrink-0 font-mono text-xs text-ink-500">
                    {error.column}
                  </span>
                  <span className="text-ink-700">{error.message}</span>
                </li>
              ))}
            </ul>
          ) : report.dry_run ? (
            <CardBody className="border-t border-ink-100">
              <p className="text-sm text-emerald-700">
                {t('importing.fileReady')} <b>{t('importing.write')}</b> tugmasini bosing.
              </p>
            </CardBody>
          ) : null}
        </Card>
      ) : (
        <Card>
          <EmptyState
            title={t('importing.noFile')}
            description={t('importing.noFileHint')}
          />
        </Card>
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-ink-100 p-4">
      <p className="text-xs font-medium text-ink-500">{label}</p>
      <p
        className={cn(
          'mt-1 text-xl font-semibold tabular-nums',
          value > 0 ? 'text-ink-900' : 'text-ink-400',
        )}
      >
        {value}
      </p>
    </div>
  )
}
