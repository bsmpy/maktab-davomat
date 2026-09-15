import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { adminApi } from '@/api/adminApi'
import { toApiError } from '@/api/errors'
import { Button, Card, CardBody, CardHeader, FileTextIcon } from '@/components/ui'
import { toast } from '@/store/toastStore'

import { ImportPanel } from './ImportPanel'

/**
 * Taking the register out, and putting one in.
 *
 * The export is the mirror of the import: the same three sheets — pupils,
 * staff and guardians — so a workbook that leaves here can come back.
 */
export function ExportPanel() {
  const { t } = useTranslation()
  const [busy, setBusy] = useState(false)

  async function download() {
    setBusy(true)
    try {
      const blob = await adminApi.exportRegister()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `reyestr-${new Date().toISOString().slice(0, 10)}.xlsx`
      link.click()
      URL.revokeObjectURL(url)
      toast.success(t('register.exported'))
    } catch (error) {
      toast.error(t('register.exportFailed'), toApiError(error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title={t('register.downloadRegister')}
          description={t('register.exportSubtitle')}
        />
        <CardBody className="flex flex-wrap items-center gap-3">
          <Button
            loading={busy}
            leftIcon={<FileTextIcon width={18} height={18} />}
            onClick={download}
          >
            {t('register.downloadExcel')}
          </Button>
          <p className="text-sm text-ink-500">
            {t('register.exportHintSheets')}
          </p>
        </CardBody>
      </Card>

      <ImportPanel />
    </div>
  )
}
