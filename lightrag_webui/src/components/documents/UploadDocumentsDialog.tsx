import { useState, useCallback } from 'react'
import { FileRejection } from 'react-dropzone'
import Button from '@/components/ui/Button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from '@/components/ui/Dialog'
import FileUploader from '@/components/ui/FileUploader'
import Input from '@/components/ui/Input'
import Checkbox from '@/components/ui/Checkbox'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs'
import { toast } from 'sonner'
import { errorMessage } from '@/lib/utils'
import { uploadDocument, crawlWebPage } from '@/api/lightrag'

import { UploadIcon, Globe } from 'lucide-react'
import { useTranslation } from 'react-i18next'

interface UploadDocumentsDialogProps {
  onDocumentsUploaded?: () => Promise<void>
}

export default function UploadDocumentsDialog({ onDocumentsUploaded }: UploadDocumentsDialogProps) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [progresses, setProgresses] = useState<Record<string, number>>({})
  const [fileErrors, setFileErrors] = useState<Record<string, string>>({})
  const [crawlUrl, setCrawlUrl] = useState('')
  const [crawlTitle, setCrawlTitle] = useState('')
  const [isCrawling, setIsCrawling] = useState(false)
  const [crawlLinks, setCrawlLinks] = useState(false)
  const [maxLinks, setMaxLinks] = useState(10)
  const [sameDomainOnly, setSameDomainOnly] = useState(true)
  const [linkPattern, setLinkPattern] = useState('')
  const [mergePages, setMergePages] = useState(false)

  const handleRejectedFiles = useCallback(
    (rejectedFiles: FileRejection[]) => {
      // Process rejected files and add them to fileErrors
      rejectedFiles.forEach(({ file, errors }) => {
        // Get the first error message
        let errorMsg = errors[0]?.message || t('documentPanel.uploadDocuments.fileUploader.fileRejected', { name: file.name })

        // Simplify error message for unsupported file types
        if (errorMsg.includes('file-invalid-type')) {
          errorMsg = t('documentPanel.uploadDocuments.fileUploader.unsupportedType')
        }

        // Set progress to 100% to display error message
        setProgresses((pre) => ({
          ...pre,
          [file.name]: 100
        }))

        // Add error message to fileErrors
        setFileErrors(prev => ({
          ...prev,
          [file.name]: errorMsg
        }))
      })
    },
    [setProgresses, setFileErrors, t]
  )

  const handleDocumentsUpload = useCallback(
    async (filesToUpload: File[]) => {
      setIsUploading(true)
      let hasSuccessfulUpload = false

      // Only clear errors for files that are being uploaded, keep errors for rejected files
      setFileErrors(prev => {
        const newErrors = { ...prev };
        filesToUpload.forEach(file => {
          delete newErrors[file.name];
        });
        return newErrors;
      });

      // Show uploading toast
      const toastId = toast.loading(t('documentPanel.uploadDocuments.batch.uploading'))

      try {
        // Track errors locally to ensure we have the final state
        const uploadErrors: Record<string, string> = {}

        // Create a collator that supports Chinese sorting
        const collator = new Intl.Collator(['zh-CN', 'en'], {
          sensitivity: 'accent',  // consider basic characters, accents, and case
          numeric: true           // enable numeric sorting, e.g., "File 10" will be after "File 2"
        });
        const sortedFiles = [...filesToUpload].sort((a, b) =>
          collator.compare(a.name, b.name)
        );

        // Upload files in sequence, not parallel
        for (const file of sortedFiles) {
          try {
            // Initialize upload progress
            setProgresses((pre) => ({
              ...pre,
              [file.name]: 0
            }))

            const result = await uploadDocument(file, (percentCompleted: number) => {
              console.debug(t('documentPanel.uploadDocuments.single.uploading', { name: file.name, percent: percentCompleted }))
              setProgresses((pre) => ({
                ...pre,
                [file.name]: percentCompleted
              }))
            })

            if (result.status === 'duplicated') {
              uploadErrors[file.name] = t('documentPanel.uploadDocuments.fileUploader.duplicateFile')
              setFileErrors(prev => ({
                ...prev,
                [file.name]: t('documentPanel.uploadDocuments.fileUploader.duplicateFile')
              }))
            } else if (result.status !== 'success') {
              uploadErrors[file.name] = result.message
              setFileErrors(prev => ({
                ...prev,
                [file.name]: result.message
              }))
            } else {
              // Mark that we had at least one successful upload
              hasSuccessfulUpload = true
            }
          } catch (err) {
            console.error(`Upload failed for ${file.name}:`, err)

            // Handle HTTP errors, including 400 errors
            let errorMsg = errorMessage(err)

            // If it's an axios error with response data, try to extract more detailed error info
            if (err && typeof err === 'object' && 'response' in err) {
              const axiosError = err as { response?: { status: number, data?: { detail?: string } } }
              if (axiosError.response?.status === 400) {
                // Extract specific error message from backend response
                errorMsg = axiosError.response.data?.detail || errorMsg
              }

              // Set progress to 100% to display error message
              setProgresses((pre) => ({
                ...pre,
                [file.name]: 100
              }))
            }

            // Record error message in both local tracking and state
            uploadErrors[file.name] = errorMsg
            setFileErrors(prev => ({
              ...prev,
              [file.name]: errorMsg
            }))
          }
        }

        // Check if any files failed to upload using our local tracking
        const hasErrors = Object.keys(uploadErrors).length > 0

        // Update toast status
        if (hasErrors) {
          toast.error(t('documentPanel.uploadDocuments.batch.error'), { id: toastId })
        } else {
          toast.success(t('documentPanel.uploadDocuments.batch.success'), { id: toastId })
        }

        // Only update if at least one file was uploaded successfully
        if (hasSuccessfulUpload) {
          // Refresh document list
          if (onDocumentsUploaded) {
            onDocumentsUploaded().catch(err => {
              console.error('Error refreshing documents:', err)
            })
          }
        }
      } catch (err) {
        console.error('Unexpected error during upload:', err)
        toast.error(t('documentPanel.uploadDocuments.generalError', { error: errorMessage(err) }), { id: toastId })
      } finally {
        setIsUploading(false)
      }
    },
    [setIsUploading, setProgresses, setFileErrors, t, onDocumentsUploaded]
  )

  const handleCrawlWebPage = useCallback(
    async () => {
      if (!crawlUrl.trim()) {
        toast.error('请输入网页URL')
        return
      }

      // 简单的URL验证
      if (!crawlUrl.trim().startsWith('http://') && !crawlUrl.trim().startsWith('https://')) {
        toast.error('URL必须以http://或https://开头')
        return
      }

      setIsCrawling(true)
      const toastId = toast.loading('正在抓取网页...')

      try {
        const result = await crawlWebPage(
          crawlUrl.trim(),
          crawlTitle.trim() || undefined,
          crawlLinks,
          crawlLinks ? maxLinks : undefined,
          crawlLinks ? sameDomainOnly : undefined,
          crawlLinks && linkPattern ? linkPattern : undefined,
          mergePages
        )

        if (result.status === 'duplicated') {
          toast.error(result.message, { id: toastId })
        } else if (result.status === 'success') {
          toast.success(result.message, { id: toastId })
          // 清空输入
          setCrawlUrl('')
          setCrawlTitle('')
          // 刷新文档列表
          if (onDocumentsUploaded) {
            onDocumentsUploaded().catch(err => {
              console.error('Error refreshing documents:', err)
            })
          }
        } else {
          toast.error(result.message, { id: toastId })
        }
      } catch (err) {
        console.error('Crawl failed:', err)
        let errorMsg = errorMessage(err)
        if (err && typeof err === 'object' && 'response' in err) {
          const axiosError = err as { response?: { status: number, data?: { detail?: string } } }
          if (axiosError.response?.status === 400) {
            errorMsg = axiosError.response.data?.detail || errorMsg
          }
        }
        toast.error(`抓取网页失败: ${errorMsg}`, { id: toastId })
      } finally {
        setIsCrawling(false)
      }
    },
    [crawlUrl, crawlTitle, onDocumentsUploaded]
  )

  return (
    <Dialog
      open={open}
      onOpenChange={(open) => {
        if (isUploading) {
          return
        }
        if (!open) {
          setProgresses({})
          setFileErrors({})
          setCrawlUrl('')
          setCrawlTitle('')
          setCrawlLinks(false)
          setMaxLinks(10)
          setSameDomainOnly(true)
          setLinkPattern('')
          setMergePages(false)
        }
        setOpen(open)
      }}
    >
      <DialogTrigger asChild>
        <Button variant="default" side="bottom" tooltip={t('documentPanel.uploadDocuments.tooltip')} size="sm">
          <UploadIcon /> {t('documentPanel.uploadDocuments.button')}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-xl" onCloseAutoFocus={(e) => e.preventDefault()}>
        <DialogHeader>
          <DialogTitle>{t('documentPanel.uploadDocuments.title')}</DialogTitle>
          <DialogDescription>
            {t('documentPanel.uploadDocuments.description')}
          </DialogDescription>
        </DialogHeader>
        <Tabs defaultValue="upload" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="upload">
              <UploadIcon className="mr-2 h-4 w-4" />
              上传文件
            </TabsTrigger>
            <TabsTrigger value="crawl">
              <Globe className="mr-2 h-4 w-4" />
              网页抓取
            </TabsTrigger>
          </TabsList>
          <TabsContent value="upload" className="mt-4">
            <FileUploader
              maxFileCount={Infinity}
              maxSize={200 * 1024 * 1024}
              description={t('documentPanel.uploadDocuments.fileTypes')}
              onUpload={handleDocumentsUpload}
              onReject={handleRejectedFiles}
              progresses={progresses}
              fileErrors={fileErrors}
              disabled={isUploading}
            />
          </TabsContent>
          <TabsContent value="crawl" className="mt-4 space-y-4">
            <div className="space-y-2">
              <label htmlFor="crawl-url" className="text-sm font-medium">
                网页URL <span className="text-red-500">*</span>
              </label>
              <Input
                id="crawl-url"
                type="url"
                placeholder="https://example.com/article"
                value={crawlUrl}
                onChange={(e) => setCrawlUrl(e.target.value)}
                disabled={isCrawling}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !isCrawling) {
                    handleCrawlWebPage()
                  }
                }}
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="crawl-title" className="text-sm font-medium">
                标题（可选）
              </label>
              <Input
                id="crawl-title"
                type="text"
                placeholder="网页标题（留空将自动提取）"
                value={crawlTitle}
                onChange={(e) => setCrawlTitle(e.target.value)}
                disabled={isCrawling}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !isCrawling) {
                    handleCrawlWebPage()
                  }
                }}
              />
            </div>
            <div className="space-y-3 border-t pt-3">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="crawl-links"
                  checked={crawlLinks}
                  onCheckedChange={(checked) => setCrawlLinks(checked === true)}
                  disabled={isCrawling}
                />
                <label htmlFor="crawl-links" className="text-sm font-medium cursor-pointer">
                  自动抓取页面中的相关链接
                </label>
              </div>
              {crawlLinks && (
                <div className="space-y-3 pl-6 border-l-2">
                  <div className="space-y-2">
                    <label htmlFor="max-links" className="text-sm font-medium">
                      最大抓取数量
                    </label>
                    <Input
                      id="max-links"
                      type="number"
                      min="1"
                      max="100"
                      value={maxLinks}
                      onChange={(e) => setMaxLinks(parseInt(e.target.value) || 10)}
                      disabled={isCrawling}
                    />
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="same-domain"
                      checked={sameDomainOnly}
                      onCheckedChange={(checked) => setSameDomainOnly(checked === true)}
                      disabled={isCrawling}
                    />
                    <label htmlFor="same-domain" className="text-sm font-medium cursor-pointer">
                      仅抓取同域名链接
                    </label>
                  </div>
                  <div className="space-y-2">
                    <label htmlFor="link-pattern" className="text-sm font-medium">
                      链接路径过滤（可选，如：.asp）
                    </label>
                    <Input
                      id="link-pattern"
                      type="text"
                      placeholder="例如：.asp 或 /products/"
                      value={linkPattern}
                      onChange={(e) => setLinkPattern(e.target.value)}
                      disabled={isCrawling}
                    />
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="merge-pages"
                      checked={mergePages}
                      onCheckedChange={(checked) => setMergePages(checked === true)}
                      disabled={isCrawling}
                    />
                    <label htmlFor="merge-pages" className="text-sm font-medium cursor-pointer">
                      合并所有页面为一个文档
                    </label>
                  </div>
                </div>
              )}
            </div>
            <Button
              onClick={handleCrawlWebPage}
              disabled={isCrawling || !crawlUrl.trim()}
              className="w-full"
            >
              {isCrawling 
                ? '抓取中...' 
                : crawlLinks 
                  ? (mergePages 
                      ? `开始抓取并合并（最多${maxLinks + 1}个页面）` 
                      : `开始抓取（最多${maxLinks + 1}个页面）`)
                  : '开始抓取'}
            </Button>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}
