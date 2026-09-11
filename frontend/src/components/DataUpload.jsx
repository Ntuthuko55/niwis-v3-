import { useState } from 'react'
import DataPreview from './DataPreview'
import { uploadFile } from '../services/api'

function parseCsvPreview(text, maxRows = 10) {
  const lines = text.split(/\r\n|\n/).filter(Boolean)
  if (lines.length === 0) {
    return { headers: [], rows: [] }
  }

  const headers = lines[0].split(',').map((header) => header.trim())
  const rows = lines.slice(1, 1 + maxRows).map((line) => {
    const values = line.split(',')
    const record = {}
    headers.forEach((header, index) => {
      record[header] = values[index] ?? ''
    })
    return record
  })

  return { headers, rows }
}

function DataUpload({ onUpload, onError, onLoading }) {
  const [file, setFile] = useState(null)
  const [sheetNames, setSheetNames] = useState([])
  const [selectedSheet, setSelectedSheet] = useState('')
  const [previewRows, setPreviewRows] = useState([])
  const [previewColumns, setPreviewColumns] = useState([])
  const [uploading, setUploading] = useState(false)
  const [fileInfo, setFileInfo] = useState('')

  const loadPreview = async (selectedFile, sheetName = null) => {
    const lowerName = selectedFile.name.toLowerCase()
    if (lowerName.endsWith('.csv')) {
      const text = await selectedFile.text()
      const { headers, rows } = parseCsvPreview(text, 10)
      setPreviewColumns(headers)
      setPreviewRows(rows)
      setSheetNames([])
      setSelectedSheet('')
    } else if (lowerName.endsWith('.xls') || lowerName.endsWith('.xlsx')) {
      // Reading a complete workbook in the browser can freeze the page on large files.
      // The backend supplies the first-sheet preview and sheet list immediately after upload.
      setPreviewColumns([])
      setPreviewRows([])
    } else {
      throw new Error('Unsupported file type for preview.')
    }
  }

  const handleFileChange = async (event) => {
    const selected = event.target.files?.[0] || null
    setFile(selected)
    setPreviewRows([])
    setPreviewColumns([])
    setSheetNames([])
    setSelectedSheet('')
    setFileInfo('')

    if (!selected) {
      return
    }

    setFileInfo(`${selected.name} (${Math.round(selected.size / 1024)} KB)${selected.name.match(/\.xls(x)?$/i) ? ' — preview available after upload' : ''}`)

    try {
      await loadPreview(selected)
    } catch (err) {
      onError(err.message || 'Unable to preview file.')
    }
  }

  const handleSheetChange = async (event) => {
    const sheet = event.target.value
    setSelectedSheet(sheet)
    if (!file) return
    try {
      await loadPreview(file, sheet)
    } catch (err) {
      onError(err.message || 'Unable to load selected sheet.')
    }
  }

  return (
    <section className="upload-section">
      <div className="section-heading"><div><p className="eyebrow">STEP 1</p><h2>Upload your dataset</h2></div><span className="format-pill">CSV · XLS · XLSX</span></div>
      <p className="section-description">Choose a data file to preview it before sending it for analysis. Pick a file with a date column and values you want to understand.</p>
      <div className="upload-controls">
        <input
          type="file"
          accept=".csv,.xls,.xlsx"
          onChange={handleFileChange}
        />
        <button
          disabled={!file || uploading}
          onClick={async () => {
            if (!file) return
            setUploading(true)
            onLoading?.(true)
            try {
              const response = await uploadFile(file, selectedSheet)
              onUpload(response)
            } catch (err) {
              onError(err.message || 'Upload failed')
            } finally {
              setUploading(false)
              onLoading?.(false)
            }
          }}
        >
          {uploading ? 'Uploading…' : 'Upload'}
        </button>
      </div>

      {fileInfo && <div className="upload-meta">{fileInfo}</div>}
      <div className="upload-hint">Tip: If you are using Excel, upload the file first, then choose the sheet from the preview section.</div>

      {sheetNames.length > 0 && (
        <div className="sheet-selection">
          <label htmlFor="sheet-select">Preview sheet:</label>
          <select id="sheet-select" value={selectedSheet} onChange={handleSheetChange}>
            {sheetNames.map((sheet) => (
              <option key={sheet} value={sheet}>
                {sheet}
              </option>
            ))}
          </select>
        </div>
      )}

      {previewRows.length > 0 && (
        <div className="preview-before-upload">
          <h3>Preview before upload</h3>
          <DataPreview rows={previewRows} />
        </div>
      )}
    </section>
  )
}

export default DataUpload
