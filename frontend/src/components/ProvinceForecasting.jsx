import { useEffect, useState } from 'react'
import { loadProvince } from '../services/api'

const provinces = [['western-cape', 'Western Cape'], ['northern-cape', 'Northern Cape'], ['north-west', 'North West'], ['gauteng', 'Gauteng'], ['free-state', 'Free State'], ['eastern-cape', 'Eastern Cape'], ['limpopo', 'Limpopo'], ['mpumalanga', 'Mpumalanga'], ['kwa-zulu-natal', 'KwaZulu-Natal']]
const regions = [['northern-cape', '70,70 255,40 300,190 210,260 55,215'], ['western-cape', '55,215 210,260 190,340 65,335 25,285'], ['north-west', '255,40 385,60 400,155 300,190'], ['gauteng', '400,105 455,110 455,158 400,155'], ['limpopo', '385,60 520,70 545,145 455,158 455,110 400,105'], ['mpumalanga', '455,158 545,145 575,225 465,235 400,155'], ['free-state', '300,190 400,155 465,235 390,300 270,285 210,260'], ['eastern-cape', '190,340 270,285 390,300 455,355 360,395 215,390'], ['kwa-zulu-natal', '465,235 575,225 590,340 455,355 390,300']]
const name = (id) => provinces.find(([key]) => key === id)?.[1]

export default function ProvinceForecasting({ onLoaded }) {
  const [selected, setSelected] = useState('kwa-zulu-natal')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const chooseProvince = async (id) => { setSelected(id); setLoading(true); setMessage(''); try { const data = await loadProvince(id); onLoaded?.(data); setMessage(`${name(id)} loaded. Choose a model and forecast range in Model Studio below.`) } catch (error) { setMessage(error.response?.data?.detail || 'Unable to load this provincial CSV.') } finally { setLoading(false) } }
  useEffect(() => { chooseProvince('kwa-zulu-natal') }, [])
  return <section className="province-dashboard"><div className="section-heading"><div><p className="eyebrow">SOUTH AFRICA CLIMATE EXPLORER</p><h2>Select a province</h2><p className="section-description">This only loads the selected provincial CSV into the main forecasting application. Training and future forecasts are produced in Model Studio below.</p></div></div><div className="province-layout"><div className="sa-map-wrap"><svg className="sa-map" viewBox="0 0 620 430" role="img" aria-label="Select a South African province">{regions.map(([id, points]) => <polygon key={id} points={points} className={selected === id ? 'selected' : ''} onClick={() => chooseProvince(id)}><title>{name(id)}</title></polygon>)}</svg><div className="province-buttons">{provinces.map(([id, label]) => <button key={id} className={selected === id ? 'active' : ''} onClick={() => chooseProvince(id)}>{label}</button>)}</div></div><div className="province-controls"><p className="selection-label">Selected dataset</p><h3>{name(selected)}</h3><p>{loading ? 'Loading provincial CSV…' : message || 'Choose a province to load its data.'}</p><p>Then select your target variable, model and 2026+ forecast range in Model Studio.</p></div></div></section>
}
