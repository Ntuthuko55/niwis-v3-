import { useEffect, useMemo, useState } from 'react'
import Highcharts from 'highcharts/highmaps'
import 'highcharts/modules/map'
import HighchartsReact from 'highcharts-react-official'
import mapData from '@highcharts/map-collection/countries/za/za-all.geo.json'

const DROUGHT_CATEGORIES = [
  { key: 'no_drought', label: 'No Drought', range: 'SPI > -0.5', color: '#dcfce7', min: -0.5, max: Infinity },
  { key: 'd0', label: 'D0', range: '-0.5 to -0.99', color: '#fef3c7', min: -0.99, max: -0.5 },
  { key: 'd1', label: 'D1', range: '-1.0 to -1.49', color: '#fdba74', min: -1.49, max: -1.0 },
  { key: 'd2', label: 'D2', range: '-1.5 to -1.99', color: '#fb923c', min: -1.99, max: -1.5 },
  { key: 'd3', label: 'D3', range: '-2.0 to -2.49', color: '#f97316', min: -2.49, max: -2.0 },
  { key: 'd4', label: 'D4', range: '≤ -2.5', color: '#7f1d1d', min: -Infinity, max: -2.5 },
]

const normalizeProvinceName = (value = '') => String(value).trim().replace(/\s+/g, ' ')

const getDroughtCategory = (value) => {
  if (value == null || Number.isNaN(Number(value))) {
    return {
      key: 'no_data',
      label: 'No data',
      range: '—',
      color: '#e2e8f0',
    }
  }

  const numericValue = Number(value)
  if (numericValue > -0.5) return DROUGHT_CATEGORIES[0]
  if (numericValue <= -2.5) return DROUGHT_CATEGORIES[5]
  if (numericValue <= -2.0) return DROUGHT_CATEGORIES[4]
  if (numericValue <= -1.5) return DROUGHT_CATEGORIES[3]
  if (numericValue <= -1.0) return DROUGHT_CATEGORIES[2]
  if (numericValue <= -0.5) return DROUGHT_CATEGORIES[1]

  return DROUGHT_CATEGORIES[0]
}

const provinceCodeMap = {
  'Eastern Cape': 'za-ec',
  'Free State': 'za-fs',
  'Gauteng': 'za-gp',
  'KwaZulu-Natal': 'za-kw',
  'Limpopo': 'za-lp',
  'Mpumalanga': 'za-mp',
  'Northern Cape': 'za-nc',
  'North West': 'za-nw',
  'Western Cape': 'za-wc',
}

export default function SouthAfricaProvinceMap({
  provinceData = [],
  selectedProvince: controlledSelectedProvince = null,
  onProvinceClick = () => {},
  height = 520,
  title = null,
}) {
  const [selectedProvince, setSelectedProvince] = useState(controlledSelectedProvince || null)

  useEffect(() => {
    if (controlledSelectedProvince !== null && controlledSelectedProvince !== undefined) {
      setSelectedProvince(controlledSelectedProvince)
    }
  }, [controlledSelectedProvince])

  const provinceMap = useMemo(() => {
    const nextMap = new Map()
    provinceData.forEach((item) => {
      const provinceName = normalizeProvinceName(item?.province)
      if (!provinceName) return
      nextMap.set(provinceName.toLowerCase(), item)
    })
    return nextMap
  }, [provinceData])

  const seriesData = useMemo(() => {
    return mapData.features
      .filter((feature) => {
        const provinceName = normalizeProvinceName(feature?.properties?.name || feature?.properties?.NAME || '')
        return !!provinceName && provinceCodeMap[provinceName]
      })
      .map((feature) => {
        const provinceName = normalizeProvinceName(feature?.properties?.name || feature?.properties?.NAME || '')
        const mappedValue = provinceMap.get(provinceName.toLowerCase())?.value
        const category = getDroughtCategory(mappedValue)
        const code = feature?.properties?.['hc-key'] || provinceCodeMap[provinceName] || ''

        return {
          'hc-key': code,
          name: provinceName,
          province: provinceName,
          value: Number(mappedValue ?? 0),
          spi: mappedValue != null ? Number(mappedValue) : null,
          status: category.label,
          range: category.range,
          color: category.color,
          custom: {
            province: provinceName,
            spi: mappedValue != null ? Number(mappedValue) : null,
            status: category.label,
            range: category.range,
          },
        }
      })
  }, [provinceMap])

  const options = useMemo(() => {
    return {
      chart: {
        type: 'map',
        height,
        backgroundColor: '#f8fafc',
        spacing: [10, 10, 10, 10],
      },
      title: null,
      credits: { enabled: false },
      legend: {
        enabled: false,
      },
      mapNavigation: {
        enabled: true,
        enableMouseWheelZoom: true,
        enableDoubleClickZoom: true,
        enableTouchZoom: true,
        buttonOptions: {
          verticalAlign: 'bottom',
          symbolStroke: '#1f2937',
          symbolFill: '#ffffff',
          backgroundColor: '#ffffff',
          borderColor: '#dbe7ea',
          borderRadius: 8,
        },
      },
      tooltip: {
        shared: false,
        useHTML: true,
        borderRadius: 10,
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderWidth: 0,
        shadow: true,
        style: {
          color: '#f8fafc',
          padding: '8px 10px',
          fontSize: '12px',
        },
        formatter: function () {
          const province = this.point?.province || this.point?.name || 'Province'
          const value = this.point?.spi != null ? Number(this.point.spi).toFixed(2) : 'n/a'
          const status = this.point?.status || 'No data'
          return `
            <div style="min-width: 140px;">
              <div style="font-weight:700; margin-bottom:4px;">${province}</div>
              <div>SPI₃: ${value}</div>
              <div>Status: ${status}</div>
            </div>
          `
        },
      },
      colorAxis: {
        dataClasses: [
          { from: -Infinity, to: -2.5, color: '#7f1d1d' },
          { from: -2.5, to: -2.0, color: '#f97316' },
          { from: -2.0, to: -1.5, color: '#fb923c' },
          { from: -1.5, to: -1.0, color: '#fdba74' },
          { from: -1.0, to: -0.5, color: '#fef3c7' },
          { from: -0.5, to: Infinity, color: '#dcfce7' },
        ],
      },
      plotOptions: {
        map: {
          allAreas: true,
          states: {
            hover: {
              color: '#d1fae5',
              borderColor: '#0f172a',
              borderWidth: 1.4,
            },
            select: {
              color: '#22c55e',
              borderColor: '#14532d',
            },
          },
        },
      },
      series: [
        {
          type: 'map',
          name: 'Province',
          mapData,
          data: seriesData,
          joinBy: ['hc-key', 'hc-key'],
          borderColor: '#ffffff',
          borderWidth: 1.1,
          nullColor: '#e2e8f0',
          states: {
            hover: {
              color: '#d1fae5',
              borderColor: '#0f172a',
              borderWidth: 1.4,
            },
          },
          dataLabels: {
            enabled: false,
          },
          point: {
            events: {
              click: function () {
                const provinceName = this.province || this.name || null
                if (!provinceName) return
                setSelectedProvince(provinceName)
                onProvinceClick(provinceName)
              },
            },
          },
        },
      ],
    }
  }, [height, onProvinceClick, seriesData])

  const selectedKey = selectedProvince ? normalizeProvinceName(selectedProvince) : null

  return (
    <div
      style={{
        width: '100%',
        background: '#f8fafc',
        border: '1px solid #dfeaf2',
        borderRadius: 14,
        overflow: 'hidden',
        boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.4)',
      }}
    >
      {title && (
        <div
          style={{
            padding: '12px 16px 0',
            fontWeight: 700,
            fontSize: '0.8rem',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: '#0f766e',
          }}
        >
          {title}
        </div>
      )}

      <div style={{ height: `${height}px`, width: '100%' }}>
        <HighchartsReact highcharts={Highcharts} constructorType="mapChart" options={options} />
      </div>

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '8px 12px',
          padding: '12px 16px 16px',
          background: '#ffffff',
          borderTop: '1px solid #edf2f7',
        }}
      >
        {DROUGHT_CATEGORIES.map((category) => (
          <div
            key={category.key}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: '11px',
              color: '#334155',
              lineHeight: 1.2,
            }}
          >
            <span
              style={{
                width: 14,
                height: 14,
                borderRadius: 4,
                background: category.color,
                border: '1px solid rgba(15, 23, 42, 0.12)',
                display: 'inline-block',
              }}
            />
            <span>
              <strong>{category.label}</strong> {category.range}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
