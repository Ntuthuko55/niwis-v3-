import Highcharts from 'highcharts/highmaps'
import 'highcharts/modules/map'
import proj4 from 'proj4'
import HighchartsReact from 'highcharts-react-official'
import mapData from '@highcharts/map-collection/countries/za/za-all.geo.json'
import { useMemo } from 'react'

const provinceNameMap = {
  'EC': 'Eastern Cape',
  'FS': 'Free State',
  'GP': 'Gauteng',
  'KZN': 'KwaZulu-Natal',
  'LP': 'Limpopo',
  'MP': 'Mpumalanga',
  'NC': 'Northern Cape',
  'NW': 'North West',
  'WC': 'Western Cape',
}

const provinceCodeMap = {
  'Eastern Cape': 'EC',
  'Free State': 'FS',
  'Gauteng': 'GP',
  'KwaZulu-Natal': 'KZN',
  'Limpopo': 'LP',
  'Mpumalanga': 'MP',
  'Northern Cape': 'NC',
  'North West': 'NW',
  'Western Cape': 'WC',
}

const provinceIdFromCode = {
  EC: 'eastern-cape',
  FS: 'free-state',
  GP: 'gauteng',
  KZN: 'kwa-zulu-natal',
  LP: 'limpopo',
  MP: 'mpumalanga',
  NC: 'northern-cape',
  NW: 'north-west',
  WC: 'western-cape',
}

export default function SouthAfricaMap({ selectedProvince, onSelectProvince }) {
  const selectedCode = Object.entries(provinceIdFromCode).find(([, id]) => id === selectedProvince)?.[0] || null

  const options = useMemo(() => {
    const seriesData = mapData.features
      .filter((feature) => {
        const name = feature.properties?.name || feature.properties?.NAME || ''
        return Object.values(provinceNameMap).includes(name)
      })
      .map((feature) => {
        const name = feature.properties?.name || feature.properties?.NAME || ''
        const code = provinceCodeMap[name] || ''
        return {
          'hc-key': code,
          name,
          value: code === selectedCode ? 1 : 0,
          custom: { code },
        }
      })

    return {
      chart: {
        map: 'countries/za/za-all',
        proj4,
        backgroundColor: 'transparent',
        spacing: [0, 0, 0, 0],
        height: 480,
      },
      accessibility: {
        enabled: false,
      },
      title: null,
      credits: { enabled: false },
      legend: { enabled: false },
      mapNavigation: {
        enabled: true,
        enableMouseWheelZoom: true,
        enableDoubleClickZoom: true,
        buttonOptions: {
          verticalAlign: 'bottom',
        },
      },
      tooltip: {
        headerFormat: '',
        pointFormat: '<b>{point.name}</b>',
      },
      colorAxis: {
        min: 0,
        max: 1,
        stops: [
          [0, '#dfeef0'],
          [1, '#e47738'],
        ],
      },
      series: [
        {
          type: 'map',
          data: seriesData,
          mapData,
          joinBy: ['hc-key', 'hc-key'],
          name: 'Province',
          borderColor: '#ffffff',
          borderWidth: 1.2,
          states: {
            hover: {
              color: '#9ad1c2',
              borderColor: '#ffffff',
            },
            select: {
              color: '#e47738',
            },
          },
          point: {
            events: {
              click: function () {
                const code = this.custom?.code || ''
                const provinceId = provinceIdFromCode[code]
                if (provinceId) onSelectProvince(provinceId)
              },
            },
          },
        },
      ],
    }
  }, [onSelectProvince, selectedProvince])

  return (
    <div style={{ width: '100%', height: 480 }}>
      <HighchartsReact highcharts={Highcharts} constructorType="mapChart" options={options} />
    </div>
  )
}
